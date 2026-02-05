# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This project downloads and parses the Nebraska DHHS Community Pharmacy Roster PDF into structured CSV data for tracking pharmacy licenses over time.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the parser (downloads PDF and generates CSV)
python3 parse_pharmacy_roster.py
```

## Architecture

**Single-script design**: `parse_pharmacy_roster.py` handles the complete pipeline:
1. Downloads PDF from DHHS website to `pdf/` with date stamp
2. Extracts pharmacy records using pdfplumber word-level positioning
3. Parses addresses into components (street, city, state, zip)
4. Outputs CSV to `data/` with date stamp

**PDF Parsing Approach**: The DHHS PDF lacks proper table structure, so parsing relies on:
- `COLUMNS` dict defines x-coordinate boundaries for each field
- Records are identified by license numbers in the first column
- Multi-line records are grouped by vertical position (`top` coordinate)
- Address parsing uses street suffix detection and pattern matching

**Known Limitations**: ~2.5% of addresses have parsing edge cases (Avenue B/I type streets, rural road numbers, corporate mail codes) that would require a street database to resolve.

## Data Files

- `pdf/CommunityPharmacyRoster_YYYY-MM-DD.pdf` - Archived source PDFs
- `data/community_pharmacies_YYYY-MM-DD.csv` - Parsed output with ISO dates
