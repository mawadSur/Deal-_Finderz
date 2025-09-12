#!/usr/bin/env python3
"""
Load GA GIO Statewide Parcels Dataset
Downloads and processes Georgia's statewide parcel data from GA GIO
"""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests
from tqdm import tqdm

# GA GIO Statewide Parcels URLs
GA_GIO_BASE_URL = "https://data.georgiaspatial.org"
PARCELS_DATASET_URL = "https://data.georgiaspatial.org/index.php/view/geonetwork/srv/eng/catalog.search#/metadata/ga-statewide-parcels"

# Direct download URLs (these may need to be updated periodically)
PARCELS_DOWNLOAD_URLS = [
    "https://data.georgiaspatial.org/datasets/Georgia::statewide-parcels/about",
    "https://services1.arcgis.com/2TtQfP3M4KJYqsE8/arcgis/rest/services/Statewide_Parcels/FeatureServer/0/query"
]

DATA_DIR = Path(__file__).parent.parent / "data" / "ga_parcels"

def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_parcels_data():
    """Download GA GIO statewide parcels data."""
    ensure_data_dir()

    print("Downloading GA GIO Statewide Parcels data...")

    # Try different download approaches
    for i, url in enumerate(PARCELS_DOWNLOAD_URLS):
        try:
            print(f"Trying download method {i+1}: {url}")

            # For ArcGIS REST API, we need to construct a query
            if "arcgis" in url:
                # Get total count first
                count_url = f"{url}?where=1=1&returnCountOnly=true&f=json"
                count_response = requests.get(count_url, timeout=30)
                count_data = count_response.json()
                total_count = count_data.get('count', 0)

                if total_count == 0:
                    print("No features found via ArcGIS API")
                    continue

                print(f"Found {total_count:,} parcels via ArcGIS API")

                # Download in batches to avoid timeout
                batch_size = 1000
                all_features = []

                for offset in range(0, min(total_count, 50000), batch_size):  # Limit to 50k for demo
                    batch_url = f"{url}?where=1=1&outFields=*&resultOffset={offset}&resultRecordCount={batch_size}&f=json"
                    response = requests.get(batch_url, timeout=60)

                    if response.status_code == 200:
                        batch_data = response.json()
                        features = batch_data.get('features', [])
                        all_features.extend(features)
                        print(f"Downloaded {len(features)} features (offset: {offset})")

                        if len(all_features) >= 50000:  # Demo limit
                            break
                    else:
                        print(f"Failed to download batch at offset {offset}")
                        break

                if all_features:
                    # Save as GeoJSON
                    geojson_data = {
                        "type": "FeatureCollection",
                        "features": all_features
                    }

                    output_file = DATA_DIR / "ga_statewide_parcels.geojson"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(geojson_data, f, indent=2)

                    print(f"Saved {len(all_features)} parcels to {output_file}")
                    return output_file

            else:
                # Try direct download
                response = requests.get(url, stream=True, timeout=60)
                if response.status_code == 200:
                    # Try to determine filename
                    content_disposition = response.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"')
                    else:
                        filename = "ga_parcels.zip"

                    output_file = DATA_DIR / filename

                    with open(output_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)

                    print(f"Downloaded file: {output_file}")
                    return output_file

        except Exception as e:
            print(f"Download method {i+1} failed: {e}")
            continue

    print("All download methods failed")
    return None

def process_parcels_data(input_file: Path) -> List[Dict]:
    """Process downloaded parcels data into standardized format."""
    print(f"Processing parcels data from {input_file}")

    parcels = []

    try:
        if input_file.suffix.lower() == '.geojson':
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            features = data.get('features', [])
            print(f"Processing {len(features)} GeoJSON features")

            for feature in tqdm(features, desc="Processing parcels"):
                parcel = process_geojson_feature(feature)
                if parcel:
                    parcels.append(parcel)

        elif input_file.suffix.lower() == '.zip':
            # Handle shapefile zip
            print("Processing shapefile ZIP (not implemented in demo)")
            # In production, would use geopandas or similar

        else:
            print(f"Unsupported file format: {input_file.suffix}")

    except Exception as e:
        print(f"Error processing {input_file}: {e}")

    return parcels

def process_geojson_feature(feature: Dict) -> Optional[Dict]:
    """Process a single GeoJSON feature into standardized parcel format."""
    try:
        properties = feature.get('properties', {})
        geometry = feature.get('geometry', {})

        # Extract key fields (these may vary based on actual GA GIO schema)
        parcel = {
            'parcel_id': properties.get('PARCEL_ID') or properties.get('parcel_id') or properties.get('OBJECTID'),
            'county_fips': properties.get('COUNTY_FIPS') or properties.get('county_fips'),
            'county_name': properties.get('COUNTY_NAME') or properties.get('county_name'),
            'owner_name': properties.get('OWNER_NAME') or properties.get('owner_name'),
            'owner_address': properties.get('OWNER_ADDR') or properties.get('owner_address'),
            'situs_address': properties.get('SITUS_ADDR') or properties.get('situs_address'),
            'situs_city': properties.get('SITUS_CITY') or properties.get('situs_city'),
            'situs_state': properties.get('SITUS_STATE') or properties.get('situs_state'),
            'situs_zip': properties.get('SITUS_ZIP') or properties.get('situs_zip'),
            'land_use': properties.get('LAND_USE') or properties.get('land_use'),
            'land_use_desc': properties.get('LAND_USE_DESC') or properties.get('land_use_desc'),
            'zoning': properties.get('ZONING') or properties.get('zoning'),
            'acreage': properties.get('ACREAGE') or properties.get('acreage'),
            'sqft': properties.get('SQFT') or properties.get('sqft'),
            'assessed_value': properties.get('ASSESSED_VAL') or properties.get('assessed_value'),
            'taxable_value': properties.get('TAXABLE_VAL') or properties.get('taxable_value'),
            'year_built': properties.get('YEAR_BUILT') or properties.get('year_built'),
            'geometry': geometry,
            'source': 'ga_gio_parcels',
            'last_updated': '2025-01-12'
        }

        # Clean up empty values
        parcel = {k: v for k, v in parcel.items() if v is not None and v != ''}

        return parcel

    except Exception as e:
        print(f"Error processing feature: {e}")
        return None

def save_processed_data(parcels: List[Dict]):
    """Save processed parcels data."""
    ensure_data_dir()

    output_file = DATA_DIR / "processed_parcels.json"

    # Save in chunks to handle large datasets
    chunk_size = 10000
    for i in range(0, len(parcels), chunk_size):
        chunk = parcels[i:i + chunk_size]
        chunk_file = DATA_DIR / f"processed_parcels_chunk_{i//chunk_size}.json"

        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2)

        print(f"Saved chunk {i//chunk_size} with {len(chunk)} parcels")

    # Save metadata
    metadata = {
        'total_parcels': len(parcels),
        'chunks': (len(parcels) + chunk_size - 1) // chunk_size,
        'source': 'GA GIO Statewide Parcels',
        'processed_date': '2025-01-12',
        'fields': list(parcels[0].keys()) if parcels else []
    }

    with open(DATA_DIR / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"Processed {len(parcels)} parcels total")
    print(f"Metadata saved to {DATA_DIR / 'metadata.json'}")

def main():
    """Main execution function."""
    print("GA GIO Statewide Parcels Loader")
    print("=" * 40)

    # Download data
    downloaded_file = download_parcels_data()

    if not downloaded_file:
        print("Failed to download parcels data")
        print("Note: GA GIO data may require manual download from:")
        print(PARCELS_DATASET_URL)
        return

    # Process data
    parcels = process_parcels_data(downloaded_file)

    if not parcels:
        print("No parcels were processed")
        return

    # Save processed data
    save_processed_data(parcels)

    print("\nGA GIO parcels loading complete!")
    print(f"Successfully processed {len(parcels)} parcels")

if __name__ == "__main__":
    main()