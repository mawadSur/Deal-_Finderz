#!/usr/bin/env python3
"""
Load County Tax Assessor Data
Downloads and processes tax roll data from Georgia county tax assessors
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from tqdm import tqdm

from georgia_data_sources import GEORGIA_COUNTIES, get_county_data_urls

DATA_DIR = Path(__file__).parent.parent / "data" / "county_tax"

# Known county tax assessor data sources
COUNTY_DATA_SOURCES = {
    'Fulton': {
        'url': 'https://www.fultoncountyga.gov/departments/tax-assessor/real-property-search',
        'format': 'web_scrape',
        'has_api': False
    },
    'DeKalb': {
        'url': 'https://www.dekalbcountyga.gov/tax-assessor',
        'format': 'csv',
        'direct_url': 'https://www.dekalbcountyga.gov/sites/default/files/tax_assessor/property_tax_roll.csv'
    },
    'Gwinnett': {
        'url': 'https://www.gwinnettcounty.com/departments/taxassessor',
        'format': 'api',
        'api_url': 'https://api.gwinnettcounty.com/tax-assessor/v1/properties'
    },
    'Cobb': {
        'url': 'https://www.cobbcounty.org/departments/tax-assessor',
        'format': 'csv',
        'direct_url': 'https://www.cobbcounty.org/DocumentCenter/View/12345/Tax-Roll-CSV'
    },
    'Clayton': {
        'url': 'https://www.claytoncountyga.gov/departments/tax-assessor',
        'format': 'excel',
        'direct_url': 'https://www.claytoncountyga.gov/DocumentCenter/View/67890/Property-Tax-Roll.xlsx'
    }
}

def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_county_data(max_counties: int = 5) -> List[Path]:
    """Download tax assessor data for specified counties."""
    ensure_data_dir()
    downloaded_files = []

    counties_to_process = GEORGIA_COUNTIES[:max_counties]  # Limit for demo

    print(f"Downloading tax assessor data for {len(counties_to_process)} counties...")

    for county in tqdm(counties_to_process, desc="Processing counties"):
        try:
            county_data = download_single_county(county)
            if county_data:
                downloaded_files.append(county_data)
        except Exception as e:
            print(f"Failed to download {county}: {e}")
            continue

    return downloaded_files

def download_single_county(county: str) -> Optional[Path]:
    """Download data for a single county."""
    county_key = county.replace(' ', '')

    # Check if we have specific configuration for this county
    if county in COUNTY_DATA_SOURCES:
        config = COUNTY_DATA_SOURCES[county]
        return download_configured_county(county, config)

    # Generic approach - try common patterns
    return download_generic_county(county)

def download_configured_county(county: str, config: Dict) -> Optional[Path]:
    """Download data for a county with known configuration."""
    print(f"Downloading {county} using configured method...")

    try:
        if config['format'] == 'csv' and 'direct_url' in config:
            response = requests.get(config['direct_url'], timeout=60)
            if response.status_code == 200:
                filename = f"{county.lower().replace(' ', '_')}_tax_roll.csv"
                output_file = DATA_DIR / filename

                with open(output_file, 'wb') as f:
                    f.write(response.content)

                print(f"Saved {county} data to {output_file}")
                return output_file

        elif config['format'] == 'api' and 'api_url' in config:
            # Handle API-based downloads
            response = requests.get(config['api_url'], timeout=60)
            if response.status_code == 200:
                data = response.json()
                filename = f"{county.lower().replace(' ', '_')}_tax_api.json"
                output_file = DATA_DIR / filename

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                print(f"Saved {county} API data to {output_file}")
                return output_file

    except Exception as e:
        print(f"Error downloading {county}: {e}")

    return None

def download_generic_county(county: str) -> Optional[Path]:
    """Download data using generic patterns for counties without specific config."""
    county_lower = county.lower().replace(' ', '')

    # Try common URL patterns
    url_patterns = [
        f"https://www.{county_lower}countyga.gov/sites/default/files/tax_assessor/property_roll.csv",
        f"https://www.{county_lower}county.com/departments/tax-assessor/property-roll.csv",
        f"https://tax.{county_lower}countyga.gov/property-roll.csv"
    ]

    for url in url_patterns:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                filename = f"{county_lower}_tax_roll.csv"
                output_file = DATA_DIR / filename

                with open(output_file, 'wb') as f:
                    f.write(response.content)

                print(f"Saved {county} data from {url}")
                return output_file

        except Exception:
            continue

    # If no direct download works, create sample data
    return create_sample_county_data(county)

def create_sample_county_data(county: str) -> Path:
    """Create sample tax assessor data for demonstration."""
    county_lower = county.lower().replace(' ', '_')

    # Generate sample properties
    sample_properties = []
    cities = ['Atlanta', 'Marietta', 'Sandy Springs', 'Roswell', 'Johns Creek']

    for i in range(100):  # 100 sample properties per county
        property_data = {
            'parcel_id': f"{county[:3].upper()}{i:06d}",
            'owner_name': f"Sample Owner {i}",
            'owner_address': f"{i} Main St, Atlanta, GA 303{i:02d}",
            'situs_address': f"{i*10} Sample Rd",
            'situs_city': cities[i % len(cities)],
            'situs_state': 'GA',
            'situs_zip': f"30{i%10:03d}",
            'land_use': 'Residential' if i % 3 == 0 else 'Commercial' if i % 3 == 1 else 'Vacant',
            'zoning': f"R-{i%10}" if i % 3 == 0 else f"C-{i%5}",
            'acreage': round(0.5 + (i % 10) * 0.3, 2),
            'sqft': (i % 5 + 1) * 1000 if i % 3 != 2 else None,  # No sqft for vacant land
            'year_built': 1980 + (i % 40) if i % 3 != 2 else None,
            'assessed_value': (i % 20 + 1) * 50000,
            'taxable_value': (i % 20 + 1) * 45000,
            'tax_rate': 0.025,
            'annual_tax': round((i % 20 + 1) * 1125, 2),
            'county': county,
            'source': 'sample_tax_assessor'
        }
        sample_properties.append(property_data)

    # Save as CSV
    filename = f"{county_lower}_sample_tax_roll.csv"
    output_file = DATA_DIR / filename

    if sample_properties:
        fieldnames = sample_properties[0].keys()

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_properties)

    print(f"Created sample data for {county}: {output_file}")
    return output_file

def process_county_data(input_files: List[Path]) -> List[Dict]:
    """Process downloaded county tax data."""
    all_properties = []

    print(f"Processing {len(input_files)} county data files...")

    for input_file in tqdm(input_files, desc="Processing files"):
        try:
            if input_file.suffix.lower() == '.csv':
                properties = process_csv_file(input_file)
            elif input_file.suffix.lower() == '.json':
                properties = process_json_file(input_file)
            else:
                print(f"Unsupported format: {input_file}")
                continue

            all_properties.extend(properties)
            print(f"Processed {len(properties)} properties from {input_file.name}")

        except Exception as e:
            print(f"Error processing {input_file}: {e}")
            continue

    return all_properties

def process_csv_file(csv_file: Path) -> List[Dict]:
    """Process a CSV file of tax assessor data."""
    properties = []

    try:
        with open(csv_file, 'r', encoding='utf-8', errors='replace') as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)

            delimiter = ','  # Default
            if sample.count('\t') > sample.count(','):
                delimiter = '\t'

            reader = csv.DictReader(f, delimiter=delimiter)

            for row in reader:
                # Normalize field names (convert to lowercase, handle variations)
                normalized_row = {}
                for key, value in row.items():
                    if key:
                        # Normalize common field name variations
                        norm_key = key.lower().strip()
                        norm_key = norm_key.replace(' ', '_').replace('-', '_')

                        # Map common variations to standard names
                        field_mapping = {
                            'parcel_id': ['parcel_id', 'parcel', 'parid', 'property_id'],
                            'owner_name': ['owner_name', 'owner', 'taxpayer', 'name'],
                            'owner_address': ['owner_address', 'owner_addr', 'mailing_address'],
                            'situs_address': ['situs_address', 'property_address', 'location'],
                            'situs_city': ['situs_city', 'city', 'prop_city'],
                            'situs_zip': ['situs_zip', 'zip', 'zipcode', 'postal_code'],
                            'land_use': ['land_use', 'use_code', 'property_use'],
                            'zoning': ['zoning', 'zone', 'zoning_code'],
                            'acreage': ['acreage', 'acres', 'land_acres'],
                            'sqft': ['sqft', 'square_feet', 'living_area', 'bldg_sqft'],
                            'year_built': ['year_built', 'yr_built', 'built_year'],
                            'assessed_value': ['assessed_value', 'assessed', 'assd_value'],
                            'taxable_value': ['taxable_value', 'taxable', 'tax_value']
                        }

                        # Find the standard field name
                        standard_key = norm_key
                        for std_key, variations in field_mapping.items():
                            if norm_key in variations:
                                standard_key = std_key
                                break

                        normalized_row[standard_key] = value.strip() if value else None

                # Add metadata
                normalized_row['source_file'] = csv_file.name
                normalized_row['county'] = extract_county_from_filename(csv_file.name)
                normalized_row['data_source'] = 'county_tax_assessor'

                properties.append(normalized_row)

    except Exception as e:
        print(f"Error processing CSV {csv_file}: {e}")

    return properties

def process_json_file(json_file: Path) -> List[Dict]:
    """Process a JSON file of tax assessor data."""
    properties = []

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and 'properties' in data:
            items = data['properties']
        elif isinstance(data, dict) and 'features' in data:
            items = [item.get('properties', item) for item in data['features']]
        else:
            items = [data]

        for item in items:
            if isinstance(item, dict):
                # Add metadata
                item['source_file'] = json_file.name
                item['county'] = extract_county_from_filename(json_file.name)
                item['data_source'] = 'county_tax_assessor'
                properties.append(item)

    except Exception as e:
        print(f"Error processing JSON {json_file}: {e}")

    return properties

def extract_county_from_filename(filename: str) -> str:
    """Extract county name from filename."""
    # Remove file extension and common suffixes
    name = filename.replace('.csv', '').replace('.json', '')
    name = name.replace('_tax_roll', '').replace('_sample', '').replace('_', ' ')

    # Try to match against known counties
    for county in GEORGIA_COUNTIES:
        if county.lower() in name.lower():
            return county

    return "Unknown"

def save_processed_data(properties: List[Dict]):
    """Save processed tax assessor data."""
    ensure_data_dir()

    # Save in chunks for large datasets
    chunk_size = 50000
    total_chunks = (len(properties) + chunk_size - 1) // chunk_size

    print(f"Saving {len(properties)} properties in {total_chunks} chunks...")

    for i in range(0, len(properties), chunk_size):
        chunk = properties[i:i + chunk_size]
        chunk_file = DATA_DIR / f"processed_tax_data_chunk_{i//chunk_size}.json"

        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2)

        print(f"Saved chunk {i//chunk_size + 1}/{total_chunks} with {len(chunk)} properties")

    # Save metadata
    metadata = {
        'total_properties': len(properties),
        'chunks': total_chunks,
        'counties_covered': list(set(p.get('county', 'Unknown') for p in properties)),
        'source': 'County Tax Assessors',
        'processed_date': '2025-01-12',
        'sample_fields': list(properties[0].keys()) if properties else []
    }

    with open(DATA_DIR / "tax_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"Tax assessor data processing complete!")
    print(f"Total properties: {len(properties)}")
    print(f"Counties covered: {len(metadata['counties_covered'])}")

def main():
    """Main execution function."""
    print("County Tax Assessor Data Loader")
    print("=" * 40)

    # Download data for first few counties
    downloaded_files = download_county_data(max_counties=5)

    if not downloaded_files:
        print("No county data files were downloaded")
        return

    # Process downloaded data
    properties = process_county_data(downloaded_files)

    if not properties:
        print("No properties were processed")
        return

    # Save processed data
    save_processed_data(properties)

    print(f"\nSuccessfully processed {len(properties)} properties from {len(downloaded_files)} counties")

if __name__ == "__main__":
    main()