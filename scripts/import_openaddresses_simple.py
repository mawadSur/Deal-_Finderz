#!/usr/bin/env python3
"""
Simplified OpenAddresses import for local development.
Downloads Georgia address data and stores in a simple format.
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

import requests
from tqdm import tqdm

# Simple local storage (JSON file)
DATA_FILE = Path(__file__).parent.parent / "data" / "addresses.json"

def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

def fetch_oa_index() -> Dict:
    """Fetch OpenAddresses index."""
    url = "https://results.openaddresses.io/latest/run/index.json"
    print(f"Downloading OA index: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()

def filter_ga_entries(index_json: Dict) -> List[Dict]:
    """Return entries for Georgia."""
    out = []
    runs = index_json.get("runs", [])
    for item in runs:
        url = item.get("url") or ""
        if "/us/ga/" in url.lower():
            out.append(item)
    print(f"Found {len(out)} Georgia OA entries")
    return out

def download_oa_files(entries: List[Dict], out_dir: Path):
    """Download OA files for Georgia."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry in tqdm(entries, desc="Downloading GA OA CSV ZIPs"):
        url = entry.get("url")
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://results.openaddresses.io{url}"

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
            print(f"Warning: Failed download: {url} ({e})")

def oa_csv_rows_from_zip(zip_path: Path) -> Iterable[Dict]:
    """Extract rows from OA CSV ZIP file."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with zf.open(name) as fh:
                    text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
                    reader = csv.DictReader(text)
                    for row in reader:
                        norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
                        yield norm
    except Exception as e:
        print(f"Warning: Failed reading {zip_path}: {e}")

def process_addresses(rows: Iterable[Dict], limit: int = 10000) -> List[Dict]:
    """Process and normalize address rows."""
    addresses = []
    count = 0

    for norm in rows:
        if count >= limit:
            break

        def pick(*keys):
            for k in keys:
                if k in norm and norm[k]:
                    return norm[k]
            return ""

        try:
            lon = pick("lon", "longitude", "x")
            lat = pick("lat", "latitude", "y")

            if not lon or not lat:
                continue

            float(lon)
            float(lat)

            address = {
                "number": pick("number", "housenumber", "house"),
                "street": pick("street", "streetname"),
                "unit": pick("unit"),
                "city": pick("city", "place", "locality", "town"),
                "district": pick("district", "county"),
                "region": pick("region", "state"),
                "postcode": pick("postcode", "zip"),
                "lon": float(lon),
                "lat": float(lat),
                "hash": pick("hash"),
                "source": "openaddresses"
            }

            addresses.append(address)
            count += 1

        except (ValueError, TypeError):
            continue

    return addresses

def save_addresses(addresses: List[Dict]):
    """Save addresses to JSON file."""
    ensure_data_dir()
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(addresses, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(addresses)} addresses to {DATA_FILE}")

def load_addresses() -> List[Dict]:
    """Load addresses from JSON file."""
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Import OpenAddresses Georgia data")
    parser.add_argument("--download", action="store_true", help="Download Georgia OA data")
    parser.add_argument("--limit", type=int, default=10000, help="Max addresses to import")
    parser.add_argument("--out", type=str, default="data/openaddresses/ga", help="Download folder")
    args = parser.parse_args()

    ensure_data_dir()

    if args.download:
        print("🚀 Starting OpenAddresses Georgia import...")

        # Download index and filter for Georgia
        index_json = fetch_oa_index()
        entries = filter_ga_entries(index_json)

        if not entries:
            print("❌ No Georgia entries found in OA index")
            return

        # Download files
        target_dir = Path(args.out)
        download_oa_files(entries, target_dir)

        # Process downloaded files
        addresses = []
        zip_files = list(target_dir.glob("**/*.zip"))

        print(f"Processing {len(zip_files)} ZIP files...")

        for zip_path in tqdm(zip_files, desc="Processing ZIPs"):
            rows = oa_csv_rows_from_zip(zip_path)
            batch_addresses = process_addresses(rows, args.limit - len(addresses))
            addresses.extend(batch_addresses)

            if len(addresses) >= args.limit:
                break

        # Save to JSON
        save_addresses(addresses[:args.limit])
        print(f"Import complete! {len(addresses)} Georgia addresses ready")

    else:
        # Just show current data
        addresses = load_addresses()
        print(f"Current data: {len(addresses)} addresses in {DATA_FILE}")

if __name__ == "__main__":
    main()