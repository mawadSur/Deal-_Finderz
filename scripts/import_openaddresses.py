#!/usr/bin/env python3
"""
Import OpenAddresses (US) into Postgres/PostGIS.

Features:
- Optionally download latest US run index and all .csv.zip for selected states
- Stream-parse ZIP CSVs, normalize fields, and COPY into app.addresses
- Deduplicate via unique(hash) partial index (if available)
- Build geometry from lon/lat
- Refresh materialized views (addresses + unified deals)

Usage examples:
  # 1) Setup DB schema/migrations (run once)
  python scripts/setup_database.py setup

  # 2a) Download all US OA files (large!) and import
  python scripts/import_openaddresses.py --download --states GA,FL,AL,NC,SC

  # 2b) Import from an existing folder of OA .csv.zip
  python scripts/import_openaddresses.py --path "C:/data/oa/us" --states GA

  # 3) Refresh unified view only
  python scripts/import_openaddresses.py --refresh-only
"""

import argparse
import csv
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Iterable

import psycopg2
import psycopg2.extras
import requests
from tqdm import tqdm

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "deal_finder"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

OA_INDEX_URL = "https://results.openaddresses.io/latest/run/index.json"
OA_RESULTS_BASE = "https://results.openaddresses.io"

REQUIRED_TABLE_SQL_HINT = "Please run: python scripts/setup_database.py setup (to apply cdk/lambda/postgis/sql/* including 039_addresses_schema.sql)"


def connect():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(2)


def ensure_schema(conn):
    """Quick sanity check app.addresses exists."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='app' AND table_name='addresses'
        """)
        if not cur.fetchone():
            print(f"❌ app.addresses not found. {REQUIRED_TABLE_SQL_HINT}")
            sys.exit(3)


def fetch_oa_index() -> Dict:
    print(f"📥 Downloading OA index: {OA_INDEX_URL}")
    r = requests.get(OA_INDEX_URL, timeout=60)
    r.raise_for_status()
    return r.json()


def filter_us_entries(index_json: Dict, state_codes: Optional[List[str]] = None) -> List[Dict]:
    """Return entries for US; optionally filter by REGION (state code) or by URL path pattern."""
    out = []
    runs = index_json.get("runs", [])
    for item in runs:
        url = item.get("url") or ""
        # Keep only US items
        if "/us/" not in url:
            continue

        # Extract region (state code) from URL if it exists like .../us/ga/...
        region_code = None
        try:
            parts = url.split("/us/")[1].split("/")
            if parts:
                region_code = parts[0].upper()
        except Exception:
            region_code = None

        if state_codes:
            if region_code and region_code in state_codes:
                out.append(item)
        else:
            out.append(item)
    print(f"ℹ️ OA US entries filtered count: {len(out)}")
    return out


def download_oa_files(entries: List[Dict], out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry in tqdm(entries, desc="Downloading OA CSV ZIPs"):
        url = entry.get("url")
        if not url:
            continue
        # Full URL (OA index uses relative links)
        if url.startswith("/"):
            url = f"{OA_RESULTS_BASE}{url}"

        fname = url.split("/")[-1]
        dest = out_dir / fname
        if dest.exists() and dest.stat().st_size > 0:
            continue

        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            print(f"⚠️ Failed download: {url} ({e})")


def oa_csv_rows_from_zip(zip_path: Path) -> Iterable[Dict]:
    """
    Yield rows from an OA CSV ZIP file as dicts with normalized keys (lower-case).
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Expect one CSV entry per zip; iterate all CSVs inside
            for name in zf.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with zf.open(name) as fh:
                    # read as text
                    text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
                    reader = csv.DictReader(text)
                    for row in reader:
                        # Normalize keys
                        norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
                        yield norm
    except zipfile.BadZipFile:
        print(f"⚠️ Bad ZIP: {zip_path}")
    except Exception as e:
        print(f"⚠️ Failed reading {zip_path}: {e}")


def to_addresses_row(norm: Dict) -> Optional[List[str]]:
    """
    Map OA row dict to our app.addresses columns (order!):
      number, street, unit, city, district, region, postcode, lon, lat, hash, source
    Returns list of stringified values or None if unusable.
    """
    # Common OA headers: number, street, unit, city, district, region, postcode, lon, lat, hash
    # Some datasets use 'house', 'housenumber', etc. We'll handle a few aliases.
    def pick(*keys):
        for k in keys:
            if k in norm and norm[k]:
                return norm[k]
        return ""

    number = pick("number", "housenumber", "house")
    street = pick("street", "streetname")
    unit = pick("unit")
    city = pick("city", "place", "locality", "town")
    district = pick("district", "county")
    region = pick("region", "state")
    postcode = pick("postcode", "zip")

    lon = pick("lon", "longitude", "x")
    lat = pick("lat", "latitude", "y")
    hsh = pick("hash")

    # lon/lat required to build geometry. Skip rows without valid numeric lon/lat.
    try:
        if lon == "" or lat == "":
            return None
        float(lon)
        float(lat)
    except Exception:
        return None

    return [
        number or None,
        street or None,
        unit or None,
        city or None,
        district or None,
        (region or "").upper() or None,
        postcode or None,
        lon,
        lat,
        hsh or None,
        "openaddresses",
    ]


def copy_addresses(conn, rows: Iterable[List[str]], batch_size: int = 100000) -> int:
    """
    COPY rows into app.addresses using a temp CSV buffer in batches.
    """
    total = 0
    batch: List[List[str]] = []
    cols = "number,street,unit,city,district,region,postcode,lon,lat,hash,source"
    for row in rows:
        if row is None:
            continue
        batch.append(row)
        if len(batch) >= batch_size:
            total += _copy_batch(conn, batch, cols)
            batch = []
    if batch:
        total += _copy_batch(conn, batch, cols)
    return total


def _copy_batch(conn, batch: List[List[str]], cols: str) -> int:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(batch)
    buf.seek(0)
    try:
        with conn.cursor() as cur:
            cur.copy_expert(
                sql=f"COPY app.addresses({cols}) FROM STDIN WITH (FORMAT CSV)",
                file=buf,
            )
        conn.commit()
        return len(batch)
    except Exception as e:
        conn.rollback()
        print(f"⚠️ COPY batch failed ({len(batch)} rows): {e}")
        # fallback to row-by-row insert? too slow; instead, drop batch
        return 0


def post_ingest_fixups(conn):
    """Populate geom where missing and analyze."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE app.addresses
            SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            WHERE geom IS NULL AND lon IS NOT NULL AND lat IS NOT NULL;
        """)
        cur.execute("ANALYZE app.addresses;")
    conn.commit()


def refresh_views(conn):
    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY app.deals_from_addresses;")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY app.deals_enriched;")
    conn.commit()


def import_from_folder(conn, folder: Path, state_codes: Optional[List[str]]) -> int:
    zips = list(folder.glob("**/*.zip"))
    if state_codes:
        # filter with /us/STATE/ in filename or parent path if possible
        filt = []
        for z in zips:
            s = str(z).lower()
            if any((f"/us/{st.lower()}/" in s or f"\\us\\{st.lower()}\\" in s or f"_{st.lower()}_" in s or f"-{st.lower()}-" in s) for st in state_codes):
                filt.append(z)
        zips = filt

    print(f"📦 Found {len(zips)} OA zip files to import")

    total_rows = 0
    for zp in tqdm(zips, desc="Importing OA zips"):
        rows = (to_addresses_row(norm) for norm in oa_csv_rows_from_zip(zp))
        inserted = copy_addresses(conn, rows)
        total_rows += inserted
    return total_rows


def main():
    parser = argparse.ArgumentParser(description="Import OpenAddresses US data into PostGIS")
    parser.add_argument("--download", action="store_true", help="Download US OA index and CSV zips")
    parser.add_argument("--path", type=str, default=None, help="Local folder of OA .csv.zip files")
    parser.add_argument("--states", type=str, default=None, help="Comma-separated US state codes to limit (e.g., GA,FL,AL)")
    parser.add_argument("--refresh-only", action="store_true", help="Refresh materialized views only")
    parser.add_argument("--out", type=str, default="data/openaddresses/us", help="Download folder for OA files")
    args = parser.parse_args()

    state_codes = None
    if args.states:
        state_codes = [s.strip().upper() for s in args.states.split(",") if s.strip()]

    conn = connect()
    ensure_schema(conn)

    if args.refresh-only:
        refresh_views(conn)
        print("✅ Refreshed materialized views")
        return

    # Optional download
    target_dir = Path(args.out)
    if args.download:
        index_json = fetch_oa_index()
        entries = filter_us_entries(index_json, state_codes)
        download_oa_files(entries, target_dir)

    # Import from folder (downloaded or user-provided)
    folder = Path(args.path) if args.path else target_dir
    if not folder.exists():
        print(f"❌ OA folder not found: {folder}")
        sys.exit(4)

    total_inserted = import_from_folder(conn, folder, state_codes)
    print(f"✅ Inserted {total_inserted:,} address rows")

    # Fix geometry and refresh views
    post_ingest_fixups(conn)
    refresh_views(conn)
    print("🎉 Import + refresh complete")

if __name__ == "__main__":
    main()