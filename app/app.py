#!/usr/bin/env python3
"""
Flask web application for Deal Finder UI
"""

from flask import Flask, render_template, request, jsonify
import os
import logging
from datetime import datetime, timedelta
from mock_data import get_mock_deals, get_mock_stats

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("Warning: psycopg2 not available, running in mock mode only")

app = Flask(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Parse DATABASE_URL for CDK environment
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DATABASE_URL)
    if match:
        DB_CONFIG = {
            'host': match.group(3),
            'port': int(match.group(4)),
            'database': match.group(5),
            'user': match.group(1),
            'password': match.group(2),
        }
    else:
        DB_CONFIG = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'deal_finder'),
            'user': os.environ.get('DB_USER', 'postgres'),
            'password': os.environ.get('DB_PASSWORD', ''),
        }
else:
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', 5432)),
        'database': os.environ.get('DB_NAME', 'deal_finder'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', ''),
    }

def get_db_connection():
    """Get database connection."""
    if not HAS_PSYCOPG2:
        return None

    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')

@app.route('/api/deals')
def get_deals():
    """API endpoint to get filtered deals."""
    # Get filter parameters
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', 5, type=float)  # km
    source = request.args.get('source')
    min_score = request.args.get('min_score', 0.5, type=float)
    limit = request.args.get('limit', 50, type=int)

    conn = get_db_connection()
    if conn:
        try:
            # Build query
            query = """
            SELECT id, title, price, url, source, created_at, lat, lng,
                   zillow_id, match_score, distance_meters, price_diff_percent,
                   agent_name, agent_phone, agent_email, brokerage
            FROM app.deals_enriched
            WHERE 1=1
            """
            params = []

            if min_price is not None:
                query += " AND price >= %s"
                params.append(min_price)

            if max_price is not None:
                query += " AND price <= %s"
                params.append(max_price)

            if lat is not None and lng is not None:
                query += " AND ST_DWithin(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geom, %s)"
                params.extend([lng, lat, radius * 1000])  # Convert km to meters

            if source:
                query += " AND source = %s"
                params.append(source)

            if min_score > 0:
                query += " AND match_score >= %s"
                params.append(min_score)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                deals = [dict(row) for row in cur.fetchall()]

            return jsonify({'deals': deals, 'count': len(deals)})
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            # Fall back to mock data
    else:
        logger.info("Using mock data (no database connection)")

    # Use mock data
    mock_deals = get_mock_deals()

    # Apply filters to mock data
    filtered_deals = []
    for deal in mock_deals:
        if min_price and deal['price'] < min_price:
            continue
        if max_price and deal['price'] > max_price:
            continue
        if source and deal['source'] != source:
            continue
        if min_score > 0 and deal.get('match_score', 0) < min_score:
            continue
        filtered_deals.append(deal)

    return jsonify({'deals': filtered_deals[:limit], 'count': len(filtered_deals)})

@app.route('/api/stats')
def get_stats():
    """Get statistics for the dashboard."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Total deals
                cur.execute("SELECT COUNT(*) as total_deals FROM app.deals")
                total_deals = cur.fetchone()['total_deals']

                # Recent deals (last 7 days)
                cur.execute("""
                    SELECT COUNT(*) as recent_deals
                    FROM app.deals
                    WHERE created_at > now() - interval '7 days'
                """)
                recent_deals = cur.fetchone()['recent_deals']

                # Matched deals
                cur.execute("""
                    SELECT COUNT(DISTINCT deal_id) as matched_deals
                    FROM app.deal_zillow_matches
                """)
                matched_deals = cur.fetchone()['matched_deals']

                # Average match score
                cur.execute("""
                    SELECT AVG(match_score) as avg_score
                    FROM app.deal_zillow_matches
                """)
                avg_score = cur.fetchone()['avg_score'] or 0

            return jsonify({
                'total_deals': total_deals,
                'recent_deals': recent_deals,
                'matched_deals': matched_deals,
                'avg_match_score': round(avg_score, 2)
            })
        except Exception as e:
            logger.error(f"Database stats query failed: {e}")
            # Fall back to mock data
    else:
        logger.info("Using mock stats (no database connection)")

    # Use mock stats
    return jsonify(get_mock_stats())

@app.route('/health')
def health():
    """Health check endpoint for ALB."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return jsonify({'status': 'healthy'}), 200
        except Exception as e:
            logger.warning(f"Health check database error: {e}")
            return jsonify({'status': 'degraded', 'error': str(e)}), 200
    else:
        # No database, but app is running
        return jsonify({'status': 'healthy (mock mode)'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))