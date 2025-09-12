# Georgia Property Data Automation System

This document describes the automated data refresh system for Georgia real estate data, implementing the requirements for keeping property data fresh with scheduled pulls and optimization.

## 🏗️ System Architecture

### Core Components

1. **Data Refresh Scheduler** (`data_refresh_scheduler.py`)
   - Orchestrates all data loading jobs
   - Manages scheduling and execution
   - Handles error recovery and logging

2. **GitHub Actions Workflow** (`.github/workflows/data-refresh.yml`)
   - Automated execution on schedule
   - Docker-based database environment
   - Comprehensive CI/CD pipeline

3. **Database Optimization** (`database_optimization.py`)
   - Post-load ANALYZE and VACUUM operations
   - Materialized view refresh
   - Performance monitoring

4. **Data Quality Monitoring** (`data_quality_report.py`)
   - Comprehensive quality metrics
   - Automated reporting
   - Issue detection and alerting

## ⏰ Scheduled Refresh Frequencies

| Data Source | Frequency | Schedule | Script |
|-------------|-----------|----------|--------|
| GA GIO Parcels | Weekly | Sunday 3 AM EST | `load_ga_gio_parcels.py` |
| County Tax Assessors | Daily | 2 AM EST | `load_county_tax_assessors.py` |
| GSCCCA Deeds/Sales | Daily | 2 AM EST | `load_gsccca_deeds.py` |
| County Permits | Daily | 2 AM EST | `load_county_permits.py` |
| FEMA Flood Zones | Monthly | 1st 4 AM EST | `load_fema_flood.py` |
| GA DOE Schools | Quarterly | 1st 5 AM EST | `load_ga_doe_schools.py` |

## 🚀 Quick Start

### Manual Execution

```bash
# Initialize the scheduler
python scripts/data_refresh_scheduler.py init

# Check current status
python scripts/data_refresh_scheduler.py status

# Run all due jobs
python scripts/data_refresh_scheduler.py run

# Run specific job manually
python scripts/data_refresh_scheduler.py run_ga_gio_parcels
```

### Automated Execution

The system runs automatically via GitHub Actions with these triggers:

- **Scheduled**: Daily/Weekly/Monthly at specified times
- **Manual**: Via GitHub UI with job type selection
- **Push to main**: Deploys updated data to production

## 📊 Data Loading Pipeline

### 1. Pre-Load Validation
```bash
# Check data source availability
python scripts/data_refresh_scheduler.py status
```

### 2. Data Loading
```bash
# Load GA GIO statewide parcels (4.8M records)
python scripts/load_ga_gio_parcels.py

# Load county tax data (200+ records per county)
python scripts/load_county_tax_assessors.py
```

### 3. Post-Load Optimization
```bash
# Run ANALYZE and REFRESH MATERIALIZED VIEW
python scripts/database_optimization.py
```

### 4. Quality Validation
```bash
# Generate comprehensive quality report
python scripts/data_quality_report.py
```

## 🔧 Configuration

### Environment Variables

```bash
# Database connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=deal_finder
DB_USER=postgres
DB_PASSWORD=your_password

# Data source credentials (for subscription services)
GSCCCA_API_KEY=your_key
GA_GIO_API_KEY=your_key
```

### Schedule Configuration

The refresh schedule is stored in `config/refresh_schedule.json`:

```json
{
  "ga_gio_parcels": {
    "frequency": "weekly",
    "next_run": "2025-09-14T03:00:00",
    "status": "pending"
  }
}
```

## 📈 Monitoring & Logging

### Log Files
- `data_refresh.log` - Main scheduler logs
- `database_optimization.log` - Optimization logs
- `data/quality_reports/` - Quality monitoring reports

### Key Metrics Tracked
- **Data Freshness**: Age of last update
- **Load Success Rate**: Percentage of successful loads
- **Data Completeness**: Field population rates
- **Geographic Coverage**: Coordinate accuracy
- **Performance**: Load times and query performance

## 🐳 Docker Integration

The GitHub Actions workflow includes:

```yaml
services:
  postgres:
    image: postgis/postgis:15-3.3
    env:
      POSTGRES_DB: deal_finder
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
```

## 🔄 Data Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │ -> │  Load Scripts    │ -> │   PostgreSQL    │
│                 │    │                  │    │   Database      │
│ • GA GIO       │    │ • ga_gio_loader  │    │                 │
│ • County Tax   │    │ • tax_loader     │    │ • app.parcels   │
│ • GSCCCA       │    │ • deeds_loader   │    │ • app.addresses │
│ • Permits      │    │ • permits_loader │    │ • app.deals     │
│ • FEMA Flood   │    │ • flood_loader   │    │                 │
│ • Schools      │    │ • schools_loader │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Scheduler     │ -> │   Optimization   │ -> │   Quality       │
│                 │    │                  │    │   Reports       │
│ • Cron jobs     │    │ • ANALYZE        │    │                 │
│ • Error handling│    │ • VACUUM         │    │ • Completeness  │
│ • Logging       │    │ • REFRESH MV     │    │ • Accuracy      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚨 Error Handling & Recovery

### Automatic Retry Logic
- Failed jobs are retried up to 3 times
- Exponential backoff between retries
- Email/Slack notifications on persistent failures

### Manual Recovery
```bash
# Force re-run a failed job
python scripts/data_refresh_scheduler.py run_failed_jobs

# Reset schedule for a specific job
python scripts/data_refresh_scheduler.py reset_ga_gio_parcels
```

## 📋 Maintenance Tasks

### Weekly Tasks
- Review data quality reports
- Monitor disk space usage
- Check for new data source formats

### Monthly Tasks
- Archive old log files
- Review performance metrics
- Update data source credentials

### Quarterly Tasks
- Full data reload validation
- Schema optimization review
- Dependency updates

## 🔐 Security Considerations

- **API Keys**: Stored as GitHub secrets
- **Database Credentials**: Environment variables
- **PII Handling**: Compliant with data privacy regulations
- **Access Control**: Role-based permissions for data operations

## 📞 Support & Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check database status
docker-compose ps
# Restart database
docker-compose restart postgres
```

**Data Loading Timeout**
```bash
# Increase timeout in script
TIMEOUT=7200 python scripts/load_ga_gio_parcels.py
```

**Quality Report Errors**
```bash
# Check data file integrity
python -c "import json; json.load(open('data/addresses.json'))"
```

### Getting Help

1. Check the logs in `data_refresh.log`
2. Review GitHub Actions workflow runs
3. Examine data quality reports
4. Contact data source providers for API issues

## 🎯 Success Metrics

- **Data Freshness**: < 7 days for daily sources, < 30 days for monthly
- **Load Success Rate**: > 95% for all automated jobs
- **Query Performance**: < 500ms for common property searches
- **Data Completeness**: > 95% field population rates
- **Geographic Accuracy**: > 98% coordinates within Georgia bounds

This automation system ensures your Georgia property data stays fresh, accurate, and performant while minimizing manual intervention and maximizing reliability.