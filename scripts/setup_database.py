#!/usr/bin/env python3
"""
Database setup and property insertion script for Deal Finder
"""

import psycopg2
import psycopg2.extras
import os
from pathlib import Path

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

def setup_database():
    """Set up the database schema."""
    print("Setting up database schema...")

    # Get SQL files in order
    sql_dir = Path(__file__).parent.parent / 'cdk' / 'lambda' / 'postgis' / 'sql'
    sql_files = sorted(sql_dir.glob('*.sql'))

    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False

    try:
        with conn.cursor() as cur:
            # Create schema_migrations table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    executed_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # Execute SQL files in order
            for sql_file in sql_files:
                filename = sql_file.name

                # Check if already executed
                cur.execute("SELECT id FROM schema_migrations WHERE filename = %s", (filename,))
                if cur.fetchone():
                    print(f"Skipping {filename} (already executed)")
                    continue

                print(f"Executing {filename}...")
                with open(sql_file, 'r') as f:
                    sql_content = f.read()

                # Split on semicolons and execute each statement
                statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                for statement in statements:
                    if statement:
                        cur.execute(statement)

                # Record migration
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (filename,))

            conn.commit()
            print("Database setup completed successfully!")
            return True

    except Exception as e:
        print(f"Database setup failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def add_sample_properties():
    """Add sample properties to the database."""
    print("Adding sample properties...")

    sample_properties = [
        {
            'title': 'Beautiful 4BR House in Atlanta',
            'price': 450000,
            'url': 'https://example.com/property1',
            'source': 'mls',
            'lat': 33.7490,
            'lng': -84.3880,
            'city': 'Atlanta',
            'state': 'GA',
            'county': 'Fulton',
            'property_category': 'residential',
            'property_type': 'house',
            'bedrooms': 4,
            'bathrooms': 3,
            'square_feet': 2500,
            'lot_size': 0.5,
            'has_pool': False,
            'has_gym': False,
            'pet_friendly': True,
            'crime_rate': 'low',
            'flood_zone': 'X',
            'school_rating': 8.5,
            'sewage_system': 'municipal',
            'on_market': True
        },
        {
            'title': 'Commercial Office Space',
            'price': 1200000,
            'url': 'https://example.com/property2',
            'source': 'commercial',
            'lat': 33.7600,
            'lng': -84.3900,
            'city': 'Atlanta',
            'state': 'GA',
            'county': 'Fulton',
            'property_category': 'commercial',
            'property_type': 'office_building',
            'bedrooms': None,
            'bathrooms': None,
            'square_feet': 8000,
            'lot_size': 1.2,
            'has_pool': False,
            'has_gym': False,
            'pet_friendly': False,
            'crime_rate': 'low',
            'flood_zone': 'X',
            'school_rating': None,
            'sewage_system': 'municipal',
            'on_market': True
        },
        {
            'title': '20 Acre Farm Land',
            'price': 150000,
            'url': 'https://example.com/property3',
            'source': 'land',
            'lat': 33.8500,
            'lng': -84.2000,
            'city': 'Loganville',
            'state': 'GA',
            'county': 'Walton',
            'property_category': 'land',
            'property_type': 'farm',
            'bedrooms': None,
            'bathrooms': None,
            'square_feet': None,
            'lot_size': 20.0,
            'has_pool': False,
            'has_gym': False,
            'pet_friendly': True,
            'crime_rate': 'low',
            'flood_zone': 'X',
            'school_rating': 7.2,
            'sewage_system': 'septic',
            'on_market': True
        }
    ]

    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False

    try:
        with conn.cursor() as cur:
            for prop in sample_properties:
                # Insert into deals table
                cur.execute("""
                    INSERT INTO app.deals (title, price, url, source)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (prop['title'], prop['price'], prop['url'], prop['source']))

                deal_id = cur.fetchone()[0]

                # Insert location
                cur.execute("""
                    INSERT INTO app.deal_locations (deal_id, geom)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                """, (deal_id, prop['lng'], prop['lat']))

                print(f"Added property: {prop['title']} (ID: {deal_id})")

            conn.commit()
            print("Sample properties added successfully!")
            return True

    except Exception as e:
        print(f"Failed to add properties: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def refresh_materialized_view():
    """Refresh the materialized view."""
    print("Refreshing materialized view...")

    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW app.deals_enriched")
            conn.commit()
            print("Materialized view refreshed successfully!")
            return True
    except Exception as e:
        print(f"Failed to refresh view: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python setup_database.py [setup|add_properties|refresh]")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'setup':
        setup_database()
    elif command == 'add_properties':
        add_sample_properties()
    elif command == 'refresh':
        refresh_materialized_view()
    elif command == 'all':
        if setup_database():
            if add_sample_properties():
                refresh_materialized_view()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: setup, add_properties, refresh, all")