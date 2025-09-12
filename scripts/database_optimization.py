#!/usr/bin/env python3
"""
Database Optimization Script
Runs ANALYZE and REFRESH MATERIALIZED VIEW after data loading jobs
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'deal_finder'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_optimization.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection."""
    if not HAS_PSYCOPG2:
        logger.error("psycopg2 not available - cannot connect to database")
        return None

    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def analyze_tables(conn):
    """Run ANALYZE on key tables to update statistics."""
    logger.info("Running ANALYZE on database tables...")

    tables_to_analyze = [
        'app.parcels',
        'app.addresses',
        'app.deals',
        'app.deal_locations',
        'app.deal_attributes',
        'app.deal_zillow_matches',
        'app.zillow_contacts'
    ]

    try:
        with conn.cursor() as cur:
            for table in tables_to_analyze:
                logger.info(f"Analyzing table: {table}")
                cur.execute(f"ANALYZE {table}")

            conn.commit()
            logger.info("ANALYZE completed successfully")
            return True

    except Exception as e:
        logger.error(f"ANALYZE failed: {e}")
        conn.rollback()
        return False

def refresh_materialized_views(conn):
    """Refresh materialized views concurrently."""
    logger.info("Refreshing materialized views...")

    views_to_refresh = [
        'app.deals_enriched',
        'app.deals_from_addresses',
        'app.parcel_summary',
        'app.market_stats'
    ]

    try:
        with conn.cursor() as cur:
            for view in views_to_refresh:
                logger.info(f"Refreshing materialized view: {view}")
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")

            conn.commit()
            logger.info("Materialized view refresh completed successfully")
            return True

    except Exception as e:
        logger.error(f"Materialized view refresh failed: {e}")
        conn.rollback()
        return False

def vacuum_tables(conn):
    """Run VACUUM on tables to reclaim space and update visibility map."""
    logger.info("Running VACUUM on database tables...")

    try:
        with conn.cursor() as cur:
            # VACUUM key tables
            cur.execute("VACUUM ANALYZE app.parcels")
            cur.execute("VACUUM ANALYZE app.addresses")
            cur.execute("VACUUM ANALYZE app.deals")

            conn.commit()
            logger.info("VACUUM completed successfully")
            return True

    except Exception as e:
        logger.error(f"VACUUM failed: {e}")
        conn.rollback()
        return False

def reindex_tables(conn):
    """Reindex tables if needed (run less frequently)."""
    logger.info("Checking for reindexing needs...")

    try:
        with conn.cursor() as cur:
            # Check index bloat and reindex if necessary
            cur.execute("""
                SELECT schemaname, tablename, indexname
                FROM pg_stat_user_indexes
                WHERE schemaname = 'app'
                AND idx_scan = 0
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 5
            """)

            unused_indexes = cur.fetchall()
            if unused_indexes:
                logger.info(f"Found {len(unused_indexes)} potentially unused indexes")
                for schema, table, index in unused_indexes:
                    logger.info(f"  {schema}.{table}.{index}")

            # Reindex key tables (run this less frequently in production)
            # cur.execute("REINDEX TABLE app.parcels")
            # cur.execute("REINDEX TABLE app.addresses")

            logger.info("Reindexing check completed")
            return True

    except Exception as e:
        logger.error(f"Reindexing check failed: {e}")
        return False

def generate_optimization_report(conn):
    """Generate a report on database optimization status."""
    logger.info("Generating optimization report...")

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get table sizes
            cur.execute("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'app'
                ORDER BY size_bytes DESC
            """)

            table_sizes = cur.fetchall()

            # Get index information
            cur.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as size
                FROM pg_stat_user_indexes
                WHERE schemaname = 'app'
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 10
            """)

            index_info = cur.fetchall()

            # Get materialized view info
            cur.execute("""
                SELECT
                    schemaname,
                    matviewname,
                    ispopulated,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size
                FROM pg_matviews
                WHERE schemaname = 'app'
            """)

            matview_info = cur.fetchall()

            report = {
                'timestamp': '2025-01-12T17:36:26',
                'table_sizes': [dict(row) for row in table_sizes],
                'top_indexes': [dict(row) for row in index_info],
                'materialized_views': [dict(row) for row in matview_info],
                'optimization_status': 'completed'
            }

            # Save report
            report_file = Path(__file__).parent.parent / "data" / "optimization_report.json"
            report_file.parent.mkdir(parents=True, exist_ok=True)

            with open(report_file, 'w') as f:
                import json
                json.dump(report, f, indent=2)

            logger.info(f"Optimization report saved to {report_file}")
            return report

    except Exception as e:
        logger.error(f"Failed to generate optimization report: {e}")
        return None

def main():
    """Main optimization routine."""
    logger.info("Starting database optimization...")

    conn = get_db_connection()
    if not conn:
        logger.error("Cannot proceed without database connection")
        return False

    try:
        # Run optimization steps
        success = True

        # 1. Analyze tables
        if not analyze_tables(conn):
            success = False

        # 2. Refresh materialized views
        if not refresh_materialized_views(conn):
            success = False

        # 3. Vacuum tables (run less frequently in production)
        # if not vacuum_tables(conn):
        #     success = False

        # 4. Check reindexing (run less frequently in production)
        # if not reindex_tables(conn):
        #     success = False

        # 5. Generate report
        report = generate_optimization_report(conn)

        if success:
            logger.info("Database optimization completed successfully")
            print("✅ Database optimization completed")
            if report:
                print(f"📊 Report generated with {len(report.get('table_sizes', []))} tables analyzed")
        else:
            logger.error("Database optimization completed with errors")
            print("⚠️ Database optimization completed with some errors")

        return success

    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)