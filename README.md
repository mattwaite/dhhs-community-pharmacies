# DHHS Community Pharmacies

A tool for downloading and parsing the Nebraska Department of Health and Human Services (DHHS) Community Pharmacy Roster into structured CSV data.

## Data Source

The [Community Pharmacy Roster PDF](https://dhhs.ne.gov/licensure/Documents/CommunityPharmacyRoster.pdf) is published by the Nebraska DHHS Division of Public Health, Licensure Unit. It contains all active community pharmacy licenses in Nebraska.

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.9+.

## Usage

```bash
python3 parse_pharmacy_roster.py
```

This will:
1. Download the current PDF to `pdf/CommunityPharmacyRoster_YYYY-MM-DD.pdf`
2. Parse all pharmacy records
3. Save structured data to `data/community_pharmacies_YYYY-MM-DD.csv`

## Output Schema

| Column | Description |
|--------|-------------|
| `license_no` | License number |
| `license_type` | License type (Community Pharmacy License) |
| `licensee_name` | Pharmacy name |
| `dba` | Doing business as (if different) |
| `address` | Full original address |
| `street` | Parsed street address |
| `city` | Parsed city |
| `state` | State code |
| `zip` | ZIP code |
| `ssn_fein` | SSN/FEIN (typically not provided) |
| `issue_date` | Original license date (YYYY-MM-DD) |
| `exp_date` | Expiration date (YYYY-MM-DD) |

## Notes

- PDFs are archived with date stamps to track changes over time
- Address parsing achieves ~97.5% accuracy; edge cases include unusual street names (Avenue B, Road 1625) and corporate mail routing codes
- Dates are converted to ISO 8601 format (YYYY-MM-DD) for analysis compatibility
