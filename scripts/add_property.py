#!/usr/bin/env python3
"""
Script to add individual properties to the database
"""

import psycopg2
import psycopg2.extras
import os
import json

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'deal_finder'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

def get_db_connection():
    """Get database connection."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def add_property(property_data):
    """Add a single property to the database."""
    required_fields = ['title', 'price', 'lat', 'lng', 'city', 'state']

    for field in required_fields:
        if field not in property_data:
            print(f"Error: Missing required field '{field}'")
            return False

    # Set defaults for optional fields
    defaults = {
        'url': None,
        'source': 'manual',
        'county': None,
        'property_category': 'residential',
        'property_type': 'house',
        'bedrooms': None,
        'bathrooms': None,
        'square_feet': None,
        'lot_size': None,
        'has_pool': False,
        'has_gym': False,
        'pet_friendly': False,
        'crime_rate': 'medium',
        'flood_zone': 'X',
        'school_rating': None,
        'sewage_system': 'municipal',
        'on_market': True
    }

    for key, default_value in defaults.items():
        if key not in property_data:
            property_data[key] = default_value

    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            # Insert into deals table
            cur.execute("""
                INSERT INTO app.deals (title, price, url, source)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                property_data['title'],
                property_data['price'],
                property_data['url'],
                property_data['source']
            ))

            deal_id = cur.fetchone()[0]

            # Insert location
            cur.execute("""
                INSERT INTO app.deal_locations (deal_id, geom)
                VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            """, (deal_id, property_data['lng'], property_data['lat']))

            # Insert additional property data if it exists in the deals table
            # Note: The current schema is minimal, you may need to extend it

            conn.commit()
            print(f"✅ Property added successfully! ID: {deal_id}")
            print(f"   Title: {property_data['title']}")
            print(f"   Price: ${property_data['price']:,}")
            print(f"   Location: {property_data['city']}, {property_data['state']}")
            return True

    except Exception as e:
        print(f"❌ Failed to add property: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def add_property_from_json(json_file):
    """Add properties from a JSON file."""
    try:
        with open(json_file, 'r') as f:
            properties = json.load(f)

        if isinstance(properties, dict):
            properties = [properties]  # Single property
        elif not isinstance(properties, list):
            print("❌ JSON file must contain an object or array of objects")
            return False

        success_count = 0
        for i, prop in enumerate(properties):
            print(f"\n📝 Adding property {i+1}/{len(properties)}...")
            if add_property(prop):
                success_count += 1

        print(f"\n✅ Successfully added {success_count}/{len(properties)} properties")
        return success_count > 0

    except FileNotFoundError:
        print(f"❌ File not found: {json_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False

# Example usage
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python add_property.py <json_file>")
        print("  python add_property.py example.json")
        print("\nJSON format:")
        print("""
{
  "title": "Beautiful House",
  "price": 350000,
  "lat": 33.7490,
  "lng": -84.3880,
  "city": "Atlanta",
  "state": "GA",
  "url": "https://example.com",
  "property_category": "residential",
  "property_type": "house",
  "bedrooms": 3,
  "bathrooms": 2,
  "square_feet": 2000,
  "lot_size": 0.5
}
        """)
        sys.exit(1)

    json_file = sys.argv[1]
    add_property_from_json(json_file)