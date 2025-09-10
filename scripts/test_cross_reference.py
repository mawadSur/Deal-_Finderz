#!/usr/bin/env python3
"""
Unit tests for cross_reference_zillow.py
"""

import unittest
from cross_reference_zillow import calculate_distance, calculate_match_score

class TestCrossReference(unittest.TestCase):
    
    def test_calculate_distance(self):
        # Test distance calculation (New York to Los Angeles approx 3940 km)
        dist = calculate_distance(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(dist / 1000, 3940, delta=50)  # Within 50km
    
    def test_calculate_match_score(self):
        deal = {'lat': 40.0, 'lng': -74.0, 'price': 100000}
        zillow_prop = {'lat': 40.01, 'lng': -74.01, 'price': 95000}
        
        score = calculate_match_score(deal, zillow_prop)
        self.assertGreater(score, 0.5)  # Should be a good match
    
    def test_perfect_match_score(self):
        deal = {'lat': 40.0, 'lng': -74.0, 'price': 100000}
        zillow_prop = {'lat': 40.0, 'lng': -74.0, 'price': 100000}
        
        score = calculate_match_score(deal, zillow_prop)
        self.assertAlmostEqual(score, 1.0, places=1)

if __name__ == '__main__':
    unittest.main()