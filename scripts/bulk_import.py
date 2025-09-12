#!/usr/bin/env python3
"""
Bulk property data import system for real estate data
Supports CSV, JSON, and API data sources
"""

import psycopg2
import psycopg2.extras
import pandas as pd
import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'deal_finder'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

class PropertyImporter:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("✅ Database connected successfully")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Database connection closed")

    def validate_property(self, prop: Dict[str, Any]) -> bool:
        """Validate required fields for a property."""
        required_fields = ['title', 'price', 'lat', 'lng', 'city', 'state']

        for field in required_fields:
            if field not in prop or prop[field] is None:
                logger.warning(f"Missing required field: {field}")
                return False

        # Validate data types
        try:
            float(prop['price'])
            float(prop['lat'])
            float(prop['lng'])
        except (ValueError, TypeError):
            logger.warning("Invalid numeric values for price/lat/lng")
            return False

        return True

    def normalize_property(self, prop: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize property data with defaults."""
        defaults = {
            'url': None,
            'source': 'bulk_import',
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

        # Apply defaults for missing fields
        for key, default_value in defaults.items():
            if key not in prop or prop[key] is None:
                prop[key] = default_value

        # Convert string numbers to proper types
        numeric_fields = ['price', 'bedrooms', 'bathrooms', 'square_feet', 'lot_size', 'school_rating']
        for field in numeric_fields:
            if isinstance(prop[field], str):
                try:
                    prop[field] = float(prop[field]) if '.' in str(prop[field]) else int(prop[field])
                except (ValueError, TypeError):
                    if field in ['bedrooms', 'bathrooms', 'square_feet', 'lot_size', 'school_rating']:
                        prop[field] = None

        return prop

    def insert_property(self, prop: Dict[str, Any]) -> int:
        """Insert a single property into the database."""
        try:
            with self.conn.cursor() as cur:
                # Insert into deals table
                cur.execute("""
                    INSERT INTO app.deals (title, price, url, source)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (
                    prop['title'],
                    prop['price'],
                    prop['url'],
                    prop['source']
                ))

                deal_id = cur.fetchone()[0]

                # Insert location
                cur.execute("""
                    INSERT INTO app.deal_locations (deal_id, geom)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                """, (deal_id, prop['lng'], prop['lat']))

                return deal_id

        except Exception as e:
            logger.error(f"Failed to insert property {prop.get('title', 'Unknown')}: {e}")
            raise

    def bulk_insert_properties(self, properties: List[Dict[str, Any]], batch_size: int = 1000) -> int:
        """Bulk insert properties with batching for performance."""
        total_inserted = 0
        total_processed = len(properties)

        logger.info(f"Starting bulk import of {total_processed} properties...")

        for i in range(0, total_processed, batch_size):
            batch = properties[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_processed + batch_size - 1) // batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} properties)")

            try:
                # Validate and normalize batch
                valid_properties = []
                for prop in batch:
                    if self.validate_property(prop):
                        valid_properties.append(self.normalize_property(prop))

                if not valid_properties:
                    logger.warning(f"No valid properties in batch {batch_num}")
                    continue

                # Insert batch
                inserted_in_batch = 0
                for prop in valid_properties:
                    self.insert_property(prop)
                    inserted_in_batch += 1

                self.conn.commit()
                total_inserted += inserted_in_batch

                logger.info(f"✅ Batch {batch_num} completed: {inserted_in_batch}/{len(batch)} inserted")

            except Exception as e:
                logger.error(f"❌ Batch {batch_num} failed: {e}")
                self.conn.rollback()
                continue

        logger.info(f"🎉 Bulk import completed: {total_inserted}/{total_processed} properties inserted")
        return total_inserted

    def import_from_csv(self, csv_file: str, batch_size: int = 1000) -> int:
        """Import properties from CSV file."""
        logger.info(f"Importing from CSV: {csv_file}")

        try:
            df = pd.read_csv(csv_file)

            # Convert DataFrame to list of dictionaries
            properties = df.to_dict('records')

            return self.bulk_insert_properties(properties, batch_size)

        except Exception as e:
            logger.error(f"Failed to import CSV: {e}")
            raise

    def import_from_json(self, json_file: str, batch_size: int = 1000) -> int:
        """Import properties from JSON file."""
        logger.info(f"Importing from JSON: {json_file}")

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            if isinstance(data, dict):
                properties = [data]
            elif isinstance(data, list):
                properties = data
            else:
                raise ValueError("JSON must contain an object or array")

            return self.bulk_insert_properties(properties, batch_size)

        except Exception as e:
            logger.error(f"Failed to import JSON: {e}")
            raise

    def refresh_materialized_view(self):
        """Refresh the materialized view after bulk import."""
        logger.info("Refreshing materialized view...")

        try:
            with self.conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW app.deals_enriched")
                self.conn.commit()
                logger.info("✅ Materialized view refreshed")
        except Exception as e:
            logger.error(f"❌ Failed to refresh view: {e}")
            raise

    def get_import_stats(self) -> Dict[str, int]:
        """Get statistics about imported data."""
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Total deals
                cur.execute("SELECT COUNT(*) as total FROM app.deals")
                total = cur.fetchone()['total']

                # By state
                cur.execute("""
                    SELECT state, COUNT(*) as count
                    FROM app.deals_enriched
                    GROUP BY state
                    ORDER BY count DESC
                """)
                by_state = cur.fetchall()

                # By property category
                cur.execute("""
                    SELECT property_category, COUNT(*) as count
                    FROM app.deals_enriched
                    GROUP BY property_category
                    ORDER BY count DESC
                """)
                by_category = cur.fetchall()

                return {
                    'total_properties': total,
                    'by_state': dict(by_state) if by_state else {},
                    'by_category': dict(by_category) if by_category else {}
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

def main():
    """Main function for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='Bulk import properties into Deal Finder database')
    parser.add_argument('file', help='File to import (CSV or JSON)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for bulk insert')
    parser.add_argument('--no-refresh', action='store_true', help='Skip materialized view refresh')

    args = parser.parse_args()

    importer = PropertyImporter()

    try:
        file_path = Path(args.file)

        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            return

        if file_path.suffix.lower() == '.csv':
            inserted = importer.import_from_csv(args.file, args.batch_size)
        elif file_path.suffix.lower() == '.json':
            inserted = importer.import_from_json(args.file, args.batch_size)
        else:
            logger.error("Unsupported file format. Use .csv or .json")
            return

        if not args.no_refresh:
            importer.refresh_materialized_view()

        # Show stats
        stats = importer.get_import_stats()
        logger.info("📊 Import Statistics:")
        logger.info(f"   Total Properties: {stats.get('total_properties', 0)}")
        logger.info(f"   By State: {stats.get('by_state', {})}")
        logger.info(f"   By Category: {stats.get('by_category', {})}")

    except Exception as e:
        logger.error(f"Import failed: {e}")
    finally:
        importer.disconnect()

if __name__ == '__main__':
    main()