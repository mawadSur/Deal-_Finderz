#!/usr/bin/env python3
"""
Georgia Public Records Data Sources Configuration and Loader
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class DataSource:
    """Configuration for a Georgia data source."""
    name: str
    description: str
    url: str
    format: str  # 'shapefile', 'csv', 'json', 'api', 'geojson'
    update_frequency: str  # 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
    license_type: str  # 'public_domain', 'open_data', 'subscription', 'restricted'
    requires_auth: bool
    contact_info: str
    data_types: List[str]  # ['parcels', 'owners', 'sales', 'permits', 'flood', 'schools']

# Georgia data sources configuration
GEORGIA_DATA_SOURCES = {
    'ga_gio_parcels': DataSource(
        name='GA GIO Statewide Parcels',
        description='Statewide parcel dataset with polygons and assessor attributes',
        url='https://data.georgiaspatial.org/index.php/view/geonetwork/srv/eng/catalog.search#/metadata/ga-statewide-parcels',
        format='shapefile',
        update_frequency='quarterly',
        license_type='open_data',
        requires_auth=False,
        contact_info='Georgia GIS Clearinghouse',
        data_types=['parcels', 'owners', 'assessments']
    ),

    'county_tax_assessors': DataSource(
        name='County Tax Assessor Exports',
        description='Individual county tax rolls with owner names, situs addresses, land use, assessed values',
        url='https://www.georgiatax.org/county-tax-assessors',
        format='csv',
        update_frequency='annual',
        license_type='public_domain',
        requires_auth=False,
        contact_info='Individual county tax assessors',
        data_types=['owners', 'assessments', 'addresses']
    ),

    'gsccca_deeds': DataSource(
        name='GSCCCA Deed/Sale Indices',
        description='Statewide deed and sales index with actual sale dates, prices, and chain of title',
        url='https://www.gsccca.org/',
        format='api',
        update_frequency='daily',
        license_type='subscription',
        requires_auth=True,
        contact_info='Georgia Superior Court Clerks Cooperative Authority',
        data_types=['sales', 'owners', 'transfers']
    ),

    'county_permits': DataSource(
        name='County/City Permits (Accela/OpenGov)',
        description='Building permits and development records from county/city systems',
        url='https://www.accela.com/products/citizen-services/',
        format='json',
        update_frequency='daily',
        license_type='open_data',
        requires_auth=False,
        contact_info='Individual counties/cities',
        data_types=['permits', 'improvements']
    ),

    'fema_flood': DataSource(
        name='FEMA National Flood Hazard Layer',
        description='Flood zone boundaries and risk assessment data',
        url='https://www.fema.gov/flood-maps/products-tools/national-flood-hazard-layer',
        format='shapefile',
        update_frequency='annual',
        license_type='public_domain',
        requires_auth=False,
        contact_info='Federal Emergency Management Agency',
        data_types=['flood_zones']
    ),

    'ga_doe_schools': DataSource(
        name='GA DOE School Boundaries',
        description='School district boundaries and attendance zones',
        url='https://www.gadoe.org/Curriculum-Instruction-and-Assessment/Curriculum-and-Instruction/Pages/School-Boundaries.aspx',
        format='shapefile',
        update_frequency='annual',
        license_type='open_data',
        requires_auth=False,
        contact_info='Georgia Department of Education',
        data_types=['schools', 'boundaries']
    )
}

# County-specific configurations
GEORGIA_COUNTIES = [
    'Appling', 'Atkinson', 'Bacon', 'Baker', 'Baldwin', 'Banks', 'Barrow', 'Bartow',
    'Ben Hill', 'Berrien', 'Bibb', 'Bleckley', 'Brantley', 'Brooks', 'Bryan', 'Bulloch',
    'Burke', 'Butts', 'Calhoun', 'Camden', 'Candler', 'Carroll', 'Catoosa', 'Charlton',
    'Chatham', 'Chattahoochee', 'Chattooga', 'Cherokee', 'Clarke', 'Clay', 'Clayton',
    'Clinch', 'Cobb', 'Coffee', 'Colquitt', 'Columbia', 'Cook', 'Coweta', 'Crawford',
    'Crisp', 'Dade', 'Dawson', 'Decatur', 'DeKalb', 'Dodge', 'Dooly', 'Dougherty',
    'Douglas', 'Early', 'Echols', 'Effingham', 'Elbert', 'Emanuel', 'Evans', 'Fannin',
    'Fayette', 'Floyd', 'Forsyth', 'Franklin', 'Fulton', 'Gilmer', 'Glascock', 'Glynn',
    'Gordon', 'Grady', 'Greene', 'Gwinnett', 'Habersham', 'Hall', 'Hancock', 'Haralson',
    'Harris', 'Hart', 'Heard', 'Henry', 'Houston', 'Irwin', 'Jackson', 'Jasper',
    'Jeff Davis', 'Jefferson', 'Jenkins', 'Johnson', 'Jones', 'Lamar', 'Lanier',
    'Laurens', 'Lee', 'Liberty', 'Lincoln', 'Long', 'Lowndes', 'Lumpkin', 'Macon',
    'Madison', 'Marion', 'McDuffie', 'McIntosh', 'Meriwether', 'Miller', 'Mitchell',
    'Monroe', 'Montgomery', 'Morgan', 'Murray', 'Muscogee', 'Newton', 'Oconee',
    'Oglethorpe', 'Paulding', 'Peach', 'Pickens', 'Pierce', 'Pike', 'Polk', 'Pulaski',
    'Putnam', 'Quitman', 'Rabun', 'Randolph', 'Richmond', 'Rockdale', 'Schley',
    'Screven', 'Seminole', 'Spalding', 'Stephens', 'Stewart', 'Sumter', 'Talbot',
    'Taliaferro', 'Tattnall', 'Taylor', 'Telfair', 'Terrell', 'Thomas', 'Tift',
    'Toombs', 'Towns', 'Treutlen', 'Troup', 'Turner', 'Twiggs', 'Union', 'Upson',
    'Walker', 'Walton', 'Ware', 'Warren', 'Washington', 'Wayne', 'Webster', 'Wheeler',
    'White', 'Whitfield', 'Wilcox', 'Wilkes', 'Wilkinson', 'Worth'
]

def get_county_data_urls(county: str) -> Dict[str, str]:
    """Get data URLs for a specific county."""
    county_lower = county.lower().replace(' ', '')

    return {
        'tax_assessor': f'https://www.{county_lower}countyga.gov/departments/tax_assessor',
        'gis_portal': f'https://gis.{county_lower}countyga.gov',
        'property_search': f'https://www.{county_lower}countyga.gov/property-search'
    }

def save_config():
    """Save the data sources configuration to JSON."""
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(exist_ok=True)

    config = {
        'data_sources': {k: v.__dict__ for k, v in GEORGIA_DATA_SOURCES.items()},
        'counties': GEORGIA_COUNTIES,
        'last_updated': '2025-01-12'
    }

    with open(config_dir / 'georgia_data_sources.json', 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Configuration saved to {config_dir / 'georgia_data_sources.json'}")

def load_config() -> Dict:
    """Load the data sources configuration."""
    config_file = Path(__file__).parent.parent / "config" / "georgia_data_sources.json"
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    return {}

if __name__ == "__main__":
    save_config()
    print("Georgia data sources configuration created!")
    print(f"Configured {len(GEORGIA_DATA_SOURCES)} data sources")
    print(f"Covers {len(GEORGIA_COUNTIES)} counties")