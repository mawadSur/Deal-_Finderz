#!/usr/bin/env python3
"""
Data Quality Monitoring and Reporting
Generates comprehensive reports on data loading quality and completeness
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Data quality thresholds
QUALITY_THRESHOLDS = {
    'completeness': {
        'min_required': 0.95,  # 95% of fields should be populated
        'warning': 0.90,
        'critical': 0.85
    },
    'accuracy': {
        'coordinate_precision': 0.001,  # Max coordinate deviation in degrees
        'address_match_rate': 0.85,     # Min address matching rate
    },
    'timeliness': {
        'max_age_days': 30,  # Data should be no older than 30 days
        'freshness_warning': 7
    },
    'consistency': {
        'duplicate_rate_max': 0.05,  # Max 5% duplicates
        'format_consistency': 0.98    # 98% should follow expected formats
    }
}

class DataQualityMonitor:
    """Monitors and reports on data quality metrics."""

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"
        self.reports_dir = self.data_dir / "quality_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def analyze_parcels_quality(self) -> Dict:
        """Analyze quality of parcels data."""
        parcels_file = self.data_dir / "ga_parcels" / "processed_parcels.json"

        if not parcels_file.exists():
            return {'status': 'no_data', 'message': 'No parcels data found'}

        try:
            with open(parcels_file, 'r') as f:
                parcels = json.load(f)

            if not parcels:
                return {'status': 'empty', 'message': 'Parcels file is empty'}

            # Analyze sample of parcels (first 1000)
            sample = parcels[:min(1000, len(parcels))]

            quality_metrics = {
                'total_records': len(parcels),
                'sample_size': len(sample),
                'completeness': self._calculate_completeness(sample),
                'geographic_coverage': self._analyze_geographic_coverage(sample),
                'data_freshness': self._analyze_data_freshness(sample),
                'field_quality': self._analyze_field_quality(sample)
            }

            return quality_metrics

        except Exception as e:
            return {'status': 'error', 'message': f'Failed to analyze parcels: {e}'}

    def analyze_addresses_quality(self) -> Dict:
        """Analyze quality of addresses data."""
        addresses_file = self.data_dir / "addresses.json"

        if not addresses_file.exists():
            return {'status': 'no_data', 'message': 'No addresses data found'}

        try:
            with open(addresses_file, 'r') as f:
                addresses = json.load(f)

            sample = addresses[:min(1000, len(addresses))]

            return {
                'total_records': len(addresses),
                'sample_size': len(sample),
                'address_completeness': self._calculate_address_completeness(sample),
                'geographic_distribution': self._analyze_address_distribution(sample),
                'format_consistency': self._analyze_address_format_consistency(sample)
            }

        except Exception as e:
            return {'status': 'error', 'message': f'Failed to analyze addresses: {e}'}

    def analyze_tax_data_quality(self) -> Dict:
        """Analyze quality of tax assessor data."""
        tax_dir = self.data_dir / "county_tax"

        if not tax_dir.exists():
            return {'status': 'no_data', 'message': 'No tax data found'}

        try:
            # Find the latest processed tax data
            processed_files = list(tax_dir.glob("processed_tax_data_chunk_*.json"))
            if not processed_files:
                return {'status': 'no_data', 'message': 'No processed tax data found'}

            # Load first chunk for analysis
            with open(processed_files[0], 'r') as f:
                tax_data = json.load(f)

            sample = tax_data[:min(500, len(tax_data))]

            return {
                'total_records': len(tax_data),
                'sample_size': len(sample),
                'counties_covered': len(set(r.get('county', 'Unknown') for r in tax_data)),
                'assessment_completeness': self._calculate_tax_completeness(sample),
                'value_distribution': self._analyze_value_distribution(sample)
            }

        except Exception as e:
            return {'status': 'error', 'message': f'Failed to analyze tax data: {e}'}

    def _calculate_completeness(self, records: List[Dict]) -> Dict:
        """Calculate field completeness across records."""
        if not records:
            return {}

        field_counts = {}
        total_records = len(records)

        for record in records:
            for field, value in record.items():
                if field not in field_counts:
                    field_counts[field] = 0
                if value is not None and value != '' and value != []:
                    field_counts[field] += 1

        completeness = {}
        for field, count in field_counts.items():
            completeness[field] = {
                'populated': count,
                'percentage': count / total_records,
                'status': 'good' if count / total_records >= QUALITY_THRESHOLDS['completeness']['min_required']
                         else 'warning' if count / total_records >= QUALITY_THRESHOLDS['completeness']['warning']
                         else 'critical'
            }

        return completeness

    def _calculate_address_completeness(self, addresses: List[Dict]) -> Dict:
        """Calculate address field completeness."""
        required_fields = ['number', 'street', 'city', 'state', 'postcode']
        return self._calculate_completeness(addresses)

    def _calculate_tax_completeness(self, tax_records: List[Dict]) -> Dict:
        """Calculate tax record completeness."""
        key_fields = ['parcel_id', 'owner_name', 'situs_address', 'assessed_value']
        return self._calculate_completeness(tax_records)

    def _analyze_geographic_coverage(self, records: List[Dict]) -> Dict:
        """Analyze geographic distribution of records."""
        coords = []
        for record in records:
            if 'lon' in record and 'lat' in record:
                try:
                    coords.append((float(record['lon']), float(record['lat'])))
                except (ValueError, TypeError):
                    continue

        if not coords:
            return {'status': 'no_coordinates', 'count': 0}

        # Basic bounds check for Georgia
        ga_bounds = {
            'lon_min': -85.6, 'lon_max': -80.8,
            'lat_min': 30.4, 'lat_max': 35.0
        }

        in_georgia = 0
        for lon, lat in coords:
            if (ga_bounds['lon_min'] <= lon <= ga_bounds['lon_max'] and
                ga_bounds['lat_min'] <= lat <= ga_bounds['lat_max']):
                in_georgia += 1

        return {
            'total_with_coords': len(coords),
            'in_georgia_bounds': in_georgia,
            'percentage_in_georgia': in_georgia / len(coords) if coords else 0,
            'status': 'good' if in_georgia / len(coords) >= 0.95 else 'warning'
        }

    def _analyze_address_distribution(self, addresses: List[Dict]) -> Dict:
        """Analyze geographic distribution of addresses."""
        cities = {}
        zipcodes = {}

        for addr in addresses:
            city = addr.get('city', 'Unknown')
            zipcode = addr.get('postcode', 'Unknown')

            cities[city] = cities.get(city, 0) + 1
            zipcodes[zipcode] = zipcodes.get(zipcode, 0) + 1

        return {
            'unique_cities': len(cities),
            'unique_zipcodes': len(zipcodes),
            'top_cities': sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_zipcodes': sorted(zipcodes.items(), key=lambda x: x[1], reverse=True)[:10]
        }

    def _analyze_data_freshness(self, records: List[Dict]) -> Dict:
        """Analyze how fresh the data is."""
        timestamps = []
        for record in records:
            if 'last_updated' in record:
                try:
                    # Try different timestamp formats
                    if isinstance(record['last_updated'], str):
                        if 'T' in record['last_updated']:
                            dt = datetime.fromisoformat(record['last_updated'].replace('Z', '+00:00'))
                        else:
                            dt = datetime.strptime(record['last_updated'], '%Y-%m-%d')
                        timestamps.append(dt)
                except (ValueError, TypeError):
                    continue

        if not timestamps:
            return {'status': 'no_timestamps', 'message': 'No timestamp data available'}

        now = datetime.now()
        ages = [(now - ts).days for ts in timestamps]
        avg_age = sum(ages) / len(ages)
        max_age = max(ages)
        min_age = min(ages)

        return {
            'average_age_days': avg_age,
            'max_age_days': max_age,
            'min_age_days': min_age,
            'freshness_status': 'good' if max_age <= QUALITY_THRESHOLDS['timeliness']['freshness_warning']
                              else 'warning' if max_age <= QUALITY_THRESHOLDS['timeliness']['max_age_days']
                              else 'stale'
        }

    def _analyze_field_quality(self, records: List[Dict]) -> Dict:
        """Analyze quality of individual fields."""
        quality_issues = {
            'null_values': 0,
            'empty_strings': 0,
            'invalid_formats': 0,
            'outliers': 0
        }

        for record in records:
            for field, value in record.items():
                if value is None:
                    quality_issues['null_values'] += 1
                elif isinstance(value, str) and value.strip() == '':
                    quality_issues['empty_strings'] += 1
                elif field in ['price', 'sqft', 'lot_size'] and isinstance(value, (int, float)):
                    if value < 0 or value > 100000000:  # Reasonable bounds
                        quality_issues['outliers'] += 1

        return quality_issues

    def _analyze_address_format_consistency(self, addresses: List[Dict]) -> Dict:
        """Analyze consistency of address formatting."""
        formats = {'standard': 0, 'missing_street': 0, 'missing_city': 0, 'incomplete': 0}

        for addr in addresses:
            number = addr.get('number')
            street = addr.get('street')
            city = addr.get('city')

            if number and street and city:
                formats['standard'] += 1
            elif not street:
                formats['missing_street'] += 1
            elif not city:
                formats['missing_city'] += 1
            else:
                formats['incomplete'] += 1

        total = sum(formats.values())
        return {
            'format_distribution': formats,
            'consistency_rate': formats['standard'] / total if total > 0 else 0,
            'status': 'good' if formats['standard'] / total >= QUALITY_THRESHOLDS['consistency']['format_consistency'] else 'needs_improvement'
        }

    def _analyze_value_distribution(self, tax_records: List[Dict]) -> Dict:
        """Analyze distribution of assessed values."""
        values = []
        for record in tax_records:
            value = record.get('assessed_value')
            if isinstance(value, (int, float)) and value > 0:
                values.append(value)

        if not values:
            return {'status': 'no_values', 'message': 'No assessed values found'}

        values.sort()
        total = len(values)

        return {
            'count': total,
            'min_value': values[0],
            'max_value': values[-1],
            'median_value': values[total // 2],
            'avg_value': sum(values) / total,
            'percentiles': {
                '25th': values[total // 4],
                '75th': values[3 * total // 4],
                '90th': values[9 * total // 10]
            }
        }

    def generate_comprehensive_report(self) -> Dict:
        """Generate comprehensive data quality report."""
        print("Generating comprehensive data quality report...")

        report = {
            'timestamp': datetime.now().isoformat(),
            'data_sources': {
                'parcels': self.analyze_parcels_quality(),
                'addresses': self.analyze_addresses_quality(),
                'tax_assessors': self.analyze_tax_data_quality()
            },
            'overall_quality_score': 0,  # Will be calculated
            'recommendations': []
        }

        # Calculate overall quality score
        quality_scores = []
        for source, metrics in report['data_sources'].items():
            if metrics.get('status') in ['good', 'completed']:
                quality_scores.append(0.9)  # Assume good quality
            elif metrics.get('status') == 'warning':
                quality_scores.append(0.7)
            elif metrics.get('status') == 'critical':
                quality_scores.append(0.5)
            else:
                quality_scores.append(0.3)  # No data or errors

        if quality_scores:
            report['overall_quality_score'] = sum(quality_scores) / len(quality_scores)

        # Generate recommendations
        if report['overall_quality_score'] < 0.8:
            report['recommendations'].append("Overall data quality needs improvement")
        if not report['data_sources']['parcels'].get('total_records'):
            report['recommendations'].append("Load GA GIO statewide parcels data")
        if not report['data_sources']['addresses'].get('total_records'):
            report['recommendations'].append("Load OpenAddresses Georgia data")
        if not report['data_sources']['tax_assessors'].get('total_records'):
            report['recommendations'].append("Load county tax assessor data")

        return report

    def save_report(self, report: Dict):
        """Save quality report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"quality_report_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # Also save latest report
        latest_file = self.reports_dir / "latest_quality_report.json"
        with open(latest_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Quality report saved to {report_file}")
        return report_file

def main():
    """Main function to generate data quality report."""
    monitor = DataQualityMonitor()
    report = monitor.generate_comprehensive_report()
    report_file = monitor.save_report(report)

    print("\n📊 Data Quality Report Summary:")
    print(f"Overall Quality Score: {report['overall_quality_score']:.2f}")
    print(f"Report saved: {report_file}")

    for source, metrics in report['data_sources'].items():
        status = metrics.get('status', 'unknown')
        records = metrics.get('total_records', 0)
        print(f"• {source}: {status} ({records:,} records)")

    if report['recommendations']:
        print("\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"• {rec}")

if __name__ == "__main__":
    main()