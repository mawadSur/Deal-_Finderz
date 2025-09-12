#!/usr/bin/env python3
"""
Flask web application for Deal Finder UI
"""

from flask import Flask, render_template, request, jsonify
import os
import logging
from datetime import datetime, timedelta
from mock_data import get_mock_deals, get_mock_stats
import json
from pathlib import Path

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
    # Pass Google Maps API key (optional) to template so we can load maps only when available
    google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    maps_enabled = bool(google_maps_key)
    return render_template('index.html', google_maps_key=google_maps_key, maps_enabled=maps_enabled)

@app.route('/api/deals')
def get_deals():
    """API endpoint to get filtered deals."""
    try:
        # Get filter parameters
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', type=float)  # km (optional; only filters when provided)
        source = request.args.get('source')
        min_score = request.args.get('min_score', 0.0, type=float)
        limit = request.args.get('limit', 100, type=int)
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 100, type=int)

        # Validate parameters
        if min_price is not None and min_price < 0:
            return jsonify({'error': 'Invalid parameter', 'message': 'min_price must be non-negative'}), 400
        if max_price is not None and max_price < 0:
            return jsonify({'error': 'Invalid parameter', 'message': 'max_price must be non-negative'}), 400
        if min_price is not None and max_price is not None and min_price > max_price:
            return jsonify({'error': 'Invalid parameter', 'message': 'min_price cannot be greater than max_price'}), 400
        if radius is not None and (radius < 0 or radius > 100):
            return jsonify({'error': 'Invalid parameter', 'message': 'radius must be between 0 and 100 km'}), 400
        if min_score is not None and (min_score < 0 or min_score > 1):
            return jsonify({'error': 'Invalid parameter', 'message': 'min_score must be between 0 and 1'}), 400
        if limit is not None and (limit < 1 or limit > 1000):
            return jsonify({'error': 'Invalid parameter', 'message': 'limit must be between 1 and 1000'}), 400
        if page_size is not None and (page_size < 1 or page_size > 1000):
            return jsonify({'error': 'Invalid parameter', 'message': 'page_size must be between 1 and 1000'}), 400

        if not page or page < 1:
            page = 1
        if not page_size or page_size < 1:
            page_size = 100
    except ValueError as e:
        return jsonify({'error': 'Invalid parameter type', 'message': f'Parameter parsing failed: {str(e)}'}), 400

    # Location filters
    city = request.args.get('city')
    state = request.args.get('state')
    county = request.args.get('county')

    # Property filters
    property_category = request.args.get('property_category')
    property_type = request.args.get('property_type')
    min_bedrooms = request.args.get('min_bedrooms', type=int)
    max_bedrooms = request.args.get('max_bedrooms', type=int)
    min_bathrooms = request.args.get('min_bathrooms', type=float)
    max_bathrooms = request.args.get('max_bathrooms', type=float)
    min_sqft = request.args.get('min_sqft', type=int)
    max_sqft = request.args.get('max_sqft', type=int)
    min_lot_size = request.args.get('min_lot_size', type=float)
    max_lot_size = request.args.get('max_lot_size', type=float)

    # Validate property filters
    if property_category and property_category not in ['residential', 'commercial', 'land']:
        return jsonify({'error': 'Invalid parameter', 'message': 'property_category must be one of: residential, commercial, land'}), 400
    if min_bedrooms is not None and min_bedrooms < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_bedrooms must be non-negative'}), 400
    if max_bedrooms is not None and max_bedrooms < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'max_bedrooms must be non-negative'}), 400
    if min_bedrooms is not None and max_bedrooms is not None and min_bedrooms > max_bedrooms:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_bedrooms cannot be greater than max_bedrooms'}), 400
    if min_bathrooms is not None and min_bathrooms < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_bathrooms must be non-negative'}), 400
    if max_bathrooms is not None and max_bathrooms < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'max_bathrooms must be non-negative'}), 400
    if min_bathrooms is not None and max_bathrooms is not None and min_bathrooms > max_bathrooms:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_bathrooms cannot be greater than max_bathrooms'}), 400
    if min_sqft is not None and min_sqft < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_sqft must be non-negative'}), 400
    if max_sqft is not None and max_sqft < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'max_sqft must be non-negative'}), 400
    if min_sqft is not None and max_sqft is not None and min_sqft > max_sqft:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_sqft cannot be greater than max_sqft'}), 400
    if min_lot_size is not None and min_lot_size < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_lot_size must be non-negative'}), 400
    if max_lot_size is not None and max_lot_size < 0:
        return jsonify({'error': 'Invalid parameter', 'message': 'max_lot_size must be non-negative'}), 400
    if min_lot_size is not None and max_lot_size is not None and min_lot_size > max_lot_size:
        return jsonify({'error': 'Invalid parameter', 'message': 'min_lot_size cannot be greater than max_lot_size'}), 400

    # Amenities
    has_pool = request.args.get('has_pool') == 'true'
    has_gym = request.args.get('has_gym') == 'true'
    pet_friendly = request.args.get('pet_friendly') == 'true'

    # Risk filters
    crime_rate = request.args.get('crime_rate')
    flood_zone = request.args.get('flood_zone')
    min_school_rating = request.args.get('min_school_rating', type=float)
    sewage_system = request.args.get('sewage_system')

    # Market status
    market_status = request.args.get('market_status')

    # Validate market status
    if market_status and market_status not in ['on_market', 'off_market']:
        return jsonify({'error': 'Invalid parameter', 'message': 'market_status must be one of: on_market, off_market'}), 400

    conn = get_db_connection()
    if conn:
        try:
            # Step 1: Get ALL properties in the desired area (location filtering only)
            location_query = """
            SELECT id, title, price, url, source, created_at, lat, lng,
                    zillow_id, match_score, distance_meters, price_diff_percent,
                    agent_name, agent_phone, agent_email, brokerage,
                    city, state, county, property_category, property_type,
                    bedrooms, bathrooms, square_feet, lot_size,
                    has_pool, has_gym, pet_friendly, crime_rate, flood_zone,
                    school_rating, sewage_system, on_market
            FROM app.deals_enriched
            WHERE 1=1
            """
            location_params = []

            # Apply ONLY location filters first
            if radius is not None and lat is not None and lng is not None:
                location_query += " AND ST_DWithin(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geom, %s)"
                location_params.extend([lng, lat, radius * 1000])  # Convert km to meters

            if city:
                location_query += " AND city ILIKE %s"
                location_params.append(f'%{city}%')

            if state:
                location_query += " AND state = %s"
                location_params.append(state)

            if county:
                location_query += " AND county ILIKE %s"
                location_params.append(f'%{county}%')

            location_query += " ORDER BY created_at DESC"

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(location_query, location_params)
                all_deals_in_area = [dict(row) for row in cur.fetchall()]

            # Step 2: Apply all other filters to the location-filtered results
            filtered_deals = []
            for deal in all_deals_in_area:
                # Price filters
                if min_price is not None and deal['price'] < min_price:
                    continue
                if max_price is not None and deal['price'] > max_price:
                    continue

                # Source and score filters
                if source and deal['source'] != source:
                    continue
                ms = deal.get('match_score') or 0.0
                if min_score is not None and min_score > 0 and ms < min_score:
                    continue

                # Property filters
                if property_category and deal.get('property_category') != property_category:
                    continue
                if property_type and deal.get('property_type') != property_type:
                    continue
                if min_bedrooms is not None and deal.get('bedrooms') and deal['bedrooms'] < min_bedrooms:
                    continue
                if max_bedrooms is not None and deal.get('bedrooms') and deal['bedrooms'] > max_bedrooms:
                    continue
                if min_bathrooms is not None and deal.get('bathrooms') and deal['bathrooms'] < min_bathrooms:
                    continue
                if max_bathrooms is not None and deal.get('bathrooms') and deal['bathrooms'] > max_bathrooms:
                    continue

                # Sqft filter only applies to built properties (those with square_feet values)
                if min_sqft is not None and deal.get('square_feet') is not None and deal['square_feet'] < min_sqft:
                    continue
                if max_sqft is not None and deal.get('square_feet') is not None and deal['square_feet'] > max_sqft:
                    continue

                if min_lot_size is not None and deal.get('lot_size') and deal['lot_size'] < min_lot_size:
                    continue
                if max_lot_size is not None and deal.get('lot_size') and deal['lot_size'] > max_lot_size:
                    continue

                # Amenities
                if has_pool and not deal.get('has_pool', False):
                    continue
                if has_gym and not deal.get('has_gym', False):
                    continue
                if pet_friendly and not deal.get('pet_friendly', False):
                    continue

                # Risk filters
                if crime_rate and deal.get('crime_rate') != crime_rate:
                    continue
                if flood_zone and deal.get('flood_zone') != flood_zone:
                    continue
                if min_school_rating is not None and deal.get('school_rating') and deal['school_rating'] < min_school_rating:
                    continue
                if sewage_system and deal.get('sewage_system') != sewage_system:
                    continue

                # Market status filter
                if market_status:
                    if market_status == 'on_market' and not deal.get('on_market', False):
                        continue
                    elif market_status == 'off_market' and deal.get('on_market', True):
                        continue

                filtered_deals.append(deal)

            # Pagination over filtered results (server-side slicing)
            total = len(filtered_deals)
            start = max(0, (page - 1) * page_size)
            end = start + page_size
            page_deals = filtered_deals[start:end]

            return jsonify({
                'deals': page_deals,
                'count': len(page_deals),
                'total': total,
                'page': page,
                'page_size': page_size,
                'has_more': end < total
            })
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return jsonify({
                'error': 'Database query failed',
                'message': 'Unable to retrieve deals from database',
                'details': str(e) if app.debug else 'Internal server error'
            }), 500
    else:
        logger.info("Using mock data (no database connection)")

    # Use mock data - apply same two-step filtering
    mock_deals = get_mock_deals()

    # Step 1: First filter by location only
    deals_in_area = []
    for deal in mock_deals:
        # Location filters only
        if city and city.lower() not in deal.get('city', '').lower():
            continue
        if state and deal.get('state') != state:
            continue
        if county and county.lower() not in deal.get('county', '').lower():
            continue
        # For mock data, we'll assume all deals are within radius since we don't have actual lat/lng filtering
        deals_in_area.append(deal)

    # Step 2: Apply all other filters to the location-filtered results
    filtered_deals = []
    for deal in deals_in_area:
        # Price filters
        if min_price is not None and deal['price'] < min_price:
            continue
        if max_price is not None and deal['price'] > max_price:
            continue

        # Source and score filters
        if source and deal['source'] != source:
            continue
        ms = deal.get('match_score') or 0.0
        if min_score is not None and min_score > 0 and ms < min_score:
            continue

        # Property filters
        if property_category and deal.get('property_category') != property_category:
            continue
        if property_type and deal.get('property_type') != property_type:
            continue
        if min_bedrooms is not None and deal.get('bedrooms') and deal['bedrooms'] < min_bedrooms:
            continue
        if max_bedrooms is not None and deal.get('bedrooms') and deal['bedrooms'] > max_bedrooms:
            continue
        if min_bathrooms is not None and deal.get('bathrooms') and deal['bathrooms'] < min_bathrooms:
            continue
        if max_bathrooms is not None and deal.get('bathrooms') and deal['bathrooms'] > max_bathrooms:
            continue

        # Sqft filter only applies to built properties (those with square_feet values)
        if min_sqft is not None and deal.get('square_feet') is not None and deal['square_feet'] < min_sqft:
            continue
        if max_sqft is not None and deal.get('square_feet') is not None and deal['square_feet'] > max_sqft:
            continue

        if min_lot_size is not None and deal.get('lot_size') and deal['lot_size'] < min_lot_size:
            continue
        if max_lot_size is not None and deal.get('lot_size') and deal['lot_size'] > max_lot_size:
            continue

        # Amenities
        if has_pool and not deal.get('has_pool', False):
            continue
        if has_gym and not deal.get('has_gym', False):
            continue
        if pet_friendly and not deal.get('pet_friendly', False):
            continue

        # Risk filters
        if crime_rate and deal.get('crime_rate') != crime_rate:
            continue
        if flood_zone and deal.get('flood_zone') != flood_zone:
            continue
        if min_school_rating is not None and deal.get('school_rating') and deal['school_rating'] < min_school_rating:
            continue
        if sewage_system and deal.get('sewage_system') != sewage_system:
            continue

        # Market status filter
        if market_status:
            if market_status == 'on_market' and not deal.get('on_market', False):
                continue
            elif market_status == 'off_market' and deal.get('on_market', True):
                continue

        filtered_deals.append(deal)

    # Pagination on filtered result set (mock path)
    total = len(filtered_deals)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    page_deals = filtered_deals[start:end]
    return jsonify({
        'deals': page_deals,
        'count': len(page_deals),
        'total': total,
        'page': page,
        'page_size': page_size,
        'has_more': end < total
    })

@app.route('/api/stats')
def load_georgia_stats():
    """Load realistic Georgia property statistics."""
    stats_file = Path(__file__).parent.parent / "data" / "stats" / "display_stats.json"
    if stats_file.exists():
        try:
            with open(stats_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load Georgia stats: {e}")

    # Fallback to mock stats if Georgia stats not available
    return get_mock_stats()

@app.route('/api/stats')
def get_stats():
    """Get statistics for the dashboard."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Total deals (use unified view with OA + native)
                cur.execute("SELECT COUNT(*) as total_deals FROM app.deals_enriched")
                total_deals = cur.fetchone()['total_deals'] or 0

                # Recent deals (last 7 days) from unified view
                cur.execute("""
                    SELECT COUNT(*) as recent_deals
                    FROM app.deals_enriched
                    WHERE created_at > now() - interval '7 days'
                """)
                recent_deals = cur.fetchone()['recent_deals'] or 0

                # Matched deals (rows that have a zillow_id in unified view)
                cur.execute("""
                    SELECT COUNT(*) as matched_deals
                    FROM app.deals_enriched
                    WHERE zillow_id IS NOT NULL
                """)
                matched_deals = cur.fetchone()['matched_deals'] or 0

                # Average match score (from unified view)
                cur.execute("""
                    SELECT AVG(match_score) as avg_score
                    FROM app.deals_enriched
                    WHERE match_score IS NOT NULL
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
            return jsonify({
                'error': 'Database stats query failed',
                'message': 'Unable to retrieve statistics from database',
                'details': str(e) if app.debug else 'Internal server error'
            }), 500
    else:
        logger.info("Using Georgia stats (no database connection)")

    # Use Georgia stats if available, otherwise mock stats
    return jsonify(load_georgia_stats())

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

# Avoid 404 noise in logs for favicon
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method Not Allowed', 'message': 'The requested method is not allowed for this resource'}), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))