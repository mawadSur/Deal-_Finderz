#!/usr/bin/env python3
"""
Cross-reference deals with Zillow data and enrich with contact information.
"""

import os
import logging
import psycopg2
import psycopg2.extras
import requests
from typing import List, Dict, Optional
from math import radians, sin, cos, sqrt, atan2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'deal_finder'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
}

# Zillow API configuration (placeholder - replace with actual API)
ZILLOW_API_KEY = os.environ.get('ZILLOW_API_KEY', 'your_api_key')
ZILLOW_BASE_URL = 'https://api.zillow.com/webservice'

def get_db_connection():
    """Establish database connection."""
    return psycopg2.connect(**DB_CONFIG)

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def calculate_match_score(deal: Dict, zillow_prop: Dict) -> float:
    """Calculate match score between deal and Zillow property."""
    # Distance score (0-1, higher for closer)
    distance = calculate_distance(deal['lat'], deal['lng'], zillow_prop['lat'], zillow_prop['lng'])
    distance_score = max(0, 1 - (distance / 1000))  # 1km max for full score

    # Price score (0-1, higher for closer prices)
    price_diff = abs(deal['price'] - zillow_prop.get('price', 0))
    price_score = max(0, 1 - (price_diff / deal['price'])) if deal['price'] > 0 else 0

    # Weighted average
    return 0.6 * distance_score + 0.4 * price_score

def search_zillow_properties(lat: float, lng: float, price: float, radius: int = 1) -> List[Dict]:
    """Search Zillow for properties near location (mock implementation)."""
    # This is a placeholder - replace with actual Zillow API call
    # For now, return mock data
    logger.info(f"Searching Zillow for lat={lat}, lng={lng}, price={price}")
    
    # Mock response
    return [
        {
            'zillow_id': '12345',
            'lat': lat + 0.01,
            'lng': lng + 0.01,
            'price': price * 0.95,
            'address': '123 Mock St',
            'agent_name': 'John Doe',
            'agent_phone': '555-1234',
            'agent_email': 'john@broker.com',
            'brokerage': 'Mock Realty'
        }
    ]

def fetch_zillow_contacts(zillow_id: str) -> Optional[Dict]:
    """Fetch detailed contact info for Zillow property (mock)."""
    # Placeholder for API call to get property details
    logger.info(f"Fetching contacts for Zillow ID: {zillow_id}")
    return {
        'agent_name': 'John Doe',
        'agent_phone': '555-1234',
        'agent_email': 'john@broker.com',
        'brokerage': 'Mock Realty'
    }

def fetch_deals_with_locations(limit: int = 100) -> List[Dict]:
    """Fetch recent deals with location data."""
    query = """
    SELECT d.id, d.title, d.price, d.url, d.source, d.created_at,
           ST_X(dl.geom) as lng, ST_Y(dl.geom) as lat
    FROM app.deals d
    JOIN app.deal_locations dl ON d.id = dl.deal_id
    WHERE d.created_at > now() - interval '30 days'
    ORDER BY d.created_at DESC
    LIMIT %s
    """
    
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]

def save_matches(matches: List[Dict]):
    """Save match results to database."""
    query = """
    INSERT INTO app.deal_zillow_matches 
    (deal_id, zillow_id, match_score, distance_meters, price_diff_percent)
    VALUES (%s, %s, %s, %s, %s)
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for match in matches:
                distance = calculate_distance(
                    match['deal_lat'], match['deal_lng'], 
                    match['zillow_lat'], match['zillow_lng']
                )
                price_diff = ((match['zillow_price'] - match['deal_price']) / match['deal_price'] * 100) if match['deal_price'] > 0 else 0
                
                cur.execute(query, (
                    match['deal_id'], match['zillow_id'], match['score'],
                    distance, price_diff
                ))
        conn.commit()

def save_contacts(contacts: List[Dict]):
    """Save contact information to database."""
    query = """
    INSERT INTO app.zillow_contacts 
    (deal_id, zillow_id, agent_name, agent_phone, agent_email, brokerage)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for contact in contacts:
                cur.execute(query, (
                    contact['deal_id'], contact['zillow_id'],
                    contact.get('agent_name'), contact.get('agent_phone'),
                    contact.get('agent_email'), contact.get('brokerage')
                ))
        conn.commit()

def refresh_enriched_view():
    """Refresh the materialized view."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW app.deals_enriched")
        conn.commit()
    logger.info("Refreshed deals_enriched view")

def main():
    """Main cross-referencing workflow."""
    logger.info("Starting Zillow cross-referencing")
    
    deals = fetch_deals_with_locations()
    logger.info(f"Fetched {len(deals)} deals")
    
    all_matches = []
    all_contacts = []
    
    for deal in deals:
        logger.info(f"Processing deal {deal['id']}: {deal['title']}")
        
        zillow_props = search_zillow_properties(deal['lat'], deal['lng'], deal['price'])
        
        for prop in zillow_props:
            score = calculate_match_score(deal, prop)
            if score >= 0.5:  # Threshold
                match = {
                    'deal_id': deal['id'],
                    'zillow_id': prop['zillow_id'],
                    'score': score,
                    'deal_lat': deal['lat'],
                    'deal_lng': deal['lng'],
                    'zillow_lat': prop['lat'],
                    'zillow_lng': prop['lng'],
                    'deal_price': deal['price'],
                    'zillow_price': prop['price']
                }
                all_matches.append(match)
                
                # Fetch contacts for top matches
                contacts = fetch_zillow_contacts(prop['zillow_id'])
                if contacts:
                    contacts.update({
                        'deal_id': deal['id'],
                        'zillow_id': prop['zillow_id']
                    })
                    all_contacts.append(contacts)
    
    if all_matches:
        save_matches(all_matches)
        logger.info(f"Saved {len(all_matches)} matches")
    
    if all_contacts:
        save_contacts(all_contacts)
        logger.info(f"Saved {len(all_contacts)} contacts")
    
    refresh_enriched_view()
    logger.info("Cross-referencing completed")

if __name__ == '__main__':
    main()