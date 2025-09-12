# Database Setup and Property Management

This guide explains how to set up the database and add properties to your Deal Finder application.

## 🗄️ Database Structure

The application uses PostgreSQL with PostGIS and consists of these tables:

### Core Tables
- **`app.deals`** - Main property listings
- **`app.deal_locations`** - Geographic coordinates (PostGIS geometry)
- **`app.deal_zillow_matches`** - Zillow API matching data
- **`app.zillow_contacts`** - Agent contact information
- **`app.deals_enriched`** - Materialized view combining all data

### Key Fields
- **Location**: `lat`, `lng`, `city`, `state`, `county`
- **Property Details**: `property_category`, `property_type`, `bedrooms`, `bathrooms`, `square_feet`, `lot_size`
- **Features**: `has_pool`, `has_gym`, `pet_friendly`
- **Risk Assessment**: `crime_rate`, `flood_zone`, `school_rating`, `sewage_system`
- **Market Status**: `on_market` (boolean)

## 🚀 Quick Start

### 1. Set up PostgreSQL with PostGIS

**Using Docker (Recommended):**
```bash
# Run PostgreSQL with PostGIS
docker run --name deal-finder-db \
  -e POSTGRES_DB=deal_finder \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -d postgis/postgis:15-3.3

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=deal_finder
export DB_USER=postgres
export DB_PASSWORD=your_password
```

**Using Local PostgreSQL:**
```bash
# Install PostGIS extension
psql -d deal_finder -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 2. Set up Database Schema

```bash
cd scripts
python setup_database.py setup
```

This will:
- Create the `app` schema
- Set up all tables with proper indexes
- Create the materialized view
- Track migrations to avoid duplicates

### 3. Add Sample Properties

```bash
# Add sample properties
python setup_database.py add_properties

# Or add all at once (setup + properties + refresh view)
python setup_database.py all
```

### 4. Refresh Materialized View

After adding properties, refresh the view:

```bash
python setup_database.py refresh
```

## 📝 Adding Your Own Properties

### Method 1: JSON File (Recommended)

Create a JSON file with your properties:

```json
{
  "title": "Beautiful Family Home",
  "price": 450000,
  "url": "https://example.com/property",
  "source": "zillow",
  "lat": 33.7490,
  "lng": -84.3880,
  "city": "Atlanta",
  "state": "GA",
  "county": "Fulton",
  "property_category": "residential",
  "property_type": "house",
  "bedrooms": 4,
  "bathrooms": 3,
  "square_feet": 2500,
  "lot_size": 0.5,
  "has_pool": false,
  "has_gym": false,
  "pet_friendly": true,
  "crime_rate": "low",
  "flood_zone": "X",
  "school_rating": 8.5,
  "sewage_system": "municipal",
  "on_market": true
}
```

Then add it:

```bash
python add_property.py your_properties.json
```

### Method 2: Bulk JSON Array

For multiple properties, use an array:

```json
[
  { "title": "Property 1", ... },
  { "title": "Property 2", ... }
]
```

### Method 3: Direct SQL

Connect to your database and insert directly:

```sql
-- Insert property
INSERT INTO app.deals (title, price, url, source)
VALUES ('My Property', 350000, 'https://example.com', 'manual')
RETURNING id;

-- Insert location (replace DEAL_ID with the returned ID)
INSERT INTO app.deal_locations (deal_id, geom)
VALUES (DEAL_ID, ST_SetSRID(ST_MakePoint(-84.3880, 33.7490), 4326));

-- Refresh the view
REFRESH MATERIALIZED VIEW app.deals_enriched;
```

## 🔧 Configuration

Set these environment variables for database connection:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=deal_finder
export DB_USER=postgres
export DB_PASSWORD=your_password
```

## 📊 Property Categories & Types

### Residential
- **house** - Single family home
- **condo** - Condominium
- **apartment** - Apartment unit
- **townhouse** - Townhouse

### Commercial
- **office_building** - Office space
- **retail_space** - Retail store
- **nnn_lease** - Triple net lease
- **industrial** - Industrial property

### Land
- **farm** - Agricultural land
- **ranch** - Ranch land
- **empty_land** - Vacant land
- **timberland** - Forested land

## 🎯 Important Notes

### SqFt vs Land Size
- **SqFt**: Only applies to built properties (houses, condos, commercial)
- **Land Size**: Applies to all properties in acres
- Land properties should have `square_feet: null`

### Required Fields
- `title`, `price`, `lat`, `lng`, `city`, `state`

### Optional Fields
- All other fields have sensible defaults
- Set to `null` for land properties where not applicable

### Materialized View
- Always refresh after adding properties: `python setup_database.py refresh`
- The view combines data from all tables for efficient queries

## 🐛 Troubleshooting

### Connection Issues
```bash
# Test database connection
psql -h localhost -p 5432 -U postgres -d deal_finder
```

### PostGIS Issues
```sql
-- Check PostGIS installation
SELECT PostGIS_Version();
```

### View Refresh Issues
```sql
-- Manual refresh
REFRESH MATERIALIZED VIEW app.deals_enriched;
```

## 📁 File Structure

```
scripts/
├── setup_database.py      # Database setup and sample data
├── add_property.py        # Add properties from JSON
├── sample_properties.json # Example property data
└── README_DATABASE.md     # This file

cdk/lambda/postgis/sql/
├── 001_init_schema.sql
├── 010_add_indexes.sql
├── 020_deal_locations.sql
├── 035_deal_zillow_matches.sql
├── 036_zillow_contacts.sql
└── 037_deals_enriched_view.sql
```

## 🚀 Next Steps

1. Set up your database
2. Run the setup script
3. Add your properties using JSON files
4. Refresh the materialized view
5. Test the application at `http://localhost:3000`

Your Deal Finder application will now use real data instead of mock data!