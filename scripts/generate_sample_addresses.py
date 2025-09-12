#!/usr/bin/env python3
"""
Generate sample Georgia address data for testing.
"""

import json
import random
from pathlib import Path

# Sample Georgia cities and streets
GEORGIA_CITIES = [
    "Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens", "Sandy Springs",
    "Roswell", "Johns Creek", "Warner Robins", "Alpharetta", "Marietta", "Valdosta",
    "Smyrna", "Peachtree Corners", "Evans", "Newnan", "Rome", "Cartersville", "Kennesaw"
]

STREET_NAMES = [
    "Peachtree", "Piedmont", "North Avenue", "Martin Luther King Jr", "Fulton",
    "Decatur", "Monroe", "Edgewood", "Moreland", "Memorial", "Boulevard", "Highway",
    "Oak", "Pine", "Maple", "Elm", "Cedar", "Spruce", "Birch", "Willow"
]

STREET_TYPES = ["Street", "Avenue", "Road", "Drive", "Lane", "Way", "Place", "Court"]

def generate_addresses(count=5000):
    """Generate sample addresses."""
    addresses = []

    for i in range(count):
        city = random.choice(GEORGIA_CITIES)

        # Generate coordinates roughly within Georgia bounds
        # Georgia lat/lng bounds: ~30.4-35.0 N, ~80.8-85.6 W
        lat = random.uniform(30.4, 35.0)
        lng = random.uniform(-85.6, -80.8)

        # Generate address
        number = random.randint(100, 9999)
        street_name = random.choice(STREET_NAMES)
        street_type = random.choice(STREET_TYPES)
        street = f"{street_name} {street_type}"

        # Sometimes add unit
        unit = ""
        if random.random() < 0.1:  # 10% chance
            unit = f"#{random.randint(1, 50)}"

        address = {
            "number": str(number),
            "street": street,
            "unit": unit,
            "city": city,
            "district": "",  # County would go here
            "region": "GA",
            "postcode": f"30{random.randint(100, 999)}",
            "lon": lng,
            "lat": lat,
            "hash": f"sample_{i}",
            "source": "sample_data"
        }

        addresses.append(address)

    return addresses

def main():
    print("Generating sample Georgia addresses...")

    # Create data directory
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Generate addresses
    addresses = generate_addresses(5000)

    # Save to JSON
    output_file = data_dir / "addresses.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(addresses, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(addresses)} sample addresses")
    print(f"Saved to: {output_file}")

    # Show sample
    print("\nSample addresses:")
    for addr in addresses[:3]:
        full_addr = f"{addr['number']} {addr['street']}"
        if addr['unit']:
            full_addr += f" {addr['unit']}"
        full_addr += f", {addr['city']}, GA {addr['postcode']}"
        print(f"  {full_addr}")

if __name__ == "__main__":
    main()