#!/usr/bin/env python3
"""
Download and parse Nebraska DHHS Community Pharmacy Roster PDF into CSV.
"""

import csv
import re
import requests
import pdfplumber
from datetime import datetime
from pathlib import Path

PDF_URL = "https://dhhs.ne.gov/licensure/Documents/CommunityPharmacyRoster.pdf"
BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "pdf"
OUTPUT_DIR = BASE_DIR / "data"

# Common street suffixes to help identify where street ends and city begins
STREET_SUFFIXES = {
    "st", "st.", "street", "ave", "ave.", "avenue", "rd", "rd.", "road",
    "dr", "dr.", "drive", "ln", "ln.", "lane", "ct", "ct.", "court",
    "blvd", "blvd.", "boulevard", "way", "pl", "pl.", "place", "cir",
    "cir.", "circle", "hwy", "hwy.", "highway", "pkwy", "pkwy.", "parkway",
    "ter", "ter.", "terrace", "trl", "trl.", "trail", "ste", "suite",
    "unit", "apt", "apt.", "floor", "fl", "fl.", "room", "rm", "rm.",
    "#",
}

# Column boundaries based on PDF analysis
COLUMNS = {
    "license_no": (0, 90),
    "license_type": (90, 250),
    "licensee_name": (250, 375),
    "dba": (375, 495),
    "address": (495, 640),
    "ssn_fein": (640, 715),
    "dates": (715, 800),
}


def download_pdf(url: str) -> Path:
    """Download PDF and save with date stamp in pdf folder."""
    PDF_DIR.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"CommunityPharmacyRoster_{today}.pdf"
    filepath = PDF_DIR / filename

    response = requests.get(url)
    response.raise_for_status()

    filepath.write_bytes(response.content)
    print(f"Downloaded PDF to: {filepath}")

    return filepath


def get_column_value(words: list, col_range: tuple) -> str:
    """Extract text from words falling within a column range."""
    col_words = [w for w in words if col_range[0] <= w["x0"] < col_range[1]]
    return " ".join(w["text"] for w in col_words)


def parse_address(address: str) -> dict:
    """Parse address into street, city, state, and zip components."""
    result = {"street": "", "city": "", "state": "", "zip": ""}

    if not address:
        return result

    # Pattern to extract state and zip from end of address
    # Matches: [state 2-letter] [zip 5-digit or 5+4]
    state_zip_pattern = re.compile(r"\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")
    match = state_zip_pattern.search(address)

    if not match:
        # No standard state/zip found, return address as street
        result["street"] = address
        return result

    result["state"] = match.group(1)
    result["zip"] = match.group(2)

    # Everything before state/zip is street + city
    street_city = address[: match.start()].strip()

    # Handle addresses with ATTN/MC mail routing info
    # Pattern: "Street ATTN/Attn: [name/mail code] City" or "Street MC#### City"
    attn_mc_match = re.search(r"\s+(ATTN|Attn:?|MC\s*\d)", street_city, re.IGNORECASE)
    if attn_mc_match:
        # Street is everything before ATTN/MC
        result["street"] = street_city[: attn_mc_match.start()].strip()
        # City is the last word (place name, not mail code)
        words = street_city.split()
        # Find last word that's a valid city (not mail code, not punctuation-heavy)
        for word in reversed(words):
            if re.match(r"^[A-Z][a-z]+$", word):  # Simple capitalized word
                result["city"] = word
                return result
        # Fallback: last word
        result["city"] = words[-1]
        return result

    # Handle PO Box or Box pattern: "Street Address [PO] Box XXX City"
    box_pattern = re.compile(r"^(.*?)\s*((?:PO\s+)?Box\s+\d+)\s+(.+)$", re.IGNORECASE)
    box_match = box_pattern.match(street_city)

    if box_match:
        street_part = box_match.group(1).strip()
        box_part = box_match.group(2)
        city_part = box_match.group(3).strip()

        # Combine street and Box for the street field
        if street_part:
            result["street"] = f"{street_part} {box_part}"
        else:
            result["street"] = box_part
        result["city"] = city_part
        return result

    # Find where street ends and city begins
    # Look for the last street suffix, city is everything after
    words = street_city.split()
    street_end_idx = -1

    for i, word in enumerate(words):
        word_lower = word.lower().rstrip(",.")
        if word_lower in STREET_SUFFIXES:
            street_end_idx = i
        # Handle "Ste 110", "Suite A", "#2100", "Hwy 15", etc.
        if word_lower in ("ste", "suite", "unit", "apt", "room", "rm", "floor", "fl", "hwy", "highway", "route", "rt"):
            # Include the number/letter after it (e.g., "Ste A", "Suite 100", "Hwy 15")
            # Match: digits, #digits, single letter, or short alphanumeric (e.g., "2A", "100B")
            if i + 1 < len(words) and re.match(r"^(#?\d+[A-Za-z]?|[A-Za-z])$", words[i + 1]):
                street_end_idx = i + 1

    if street_end_idx >= 0 and street_end_idx < len(words) - 1:
        result["street"] = " ".join(words[: street_end_idx + 1])
        result["city"] = " ".join(words[street_end_idx + 1 :])
    else:
        # Fallback: assume last word before state is city
        if len(words) > 1:
            result["street"] = " ".join(words[:-1])
            result["city"] = words[-1]
        else:
            result["city"] = street_city

    return result


def format_date(date_str: str) -> str:
    """Convert date from MM/DD/YYYY to YYYY-MM-DD format."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def extract_pharmacy_records(pdf_path: Path) -> list[dict]:
    """Extract pharmacy records from PDF."""
    records = []
    date_pattern = re.compile(r"\d{2}/\d{2}/\d{4}")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()

            # Skip header area (top ~130 units on first page, less on others)
            header_cutoff = 130 if page.page_number == 1 else 50

            # Filter words below header
            content_words = [w for w in words if w["top"] >= header_cutoff]

            # Find record start positions (license numbers in first column)
            record_starts = []
            for word in content_words:
                if (
                    COLUMNS["license_no"][0] <= word["x0"] < COLUMNS["license_no"][1]
                    and word["text"].isdigit()
                ):
                    record_starts.append(word["top"])

            record_starts.sort()

            # For each record, gather all words until the next record starts
            for i, start_top in enumerate(record_starts):
                # End boundary is start of next record or end of page
                if i + 1 < len(record_starts):
                    end_top = record_starts[i + 1]
                else:
                    end_top = float("inf")

                # Gather words for this record (with small tolerance for start)
                record_words = [
                    w for w in content_words
                    if start_top - 2 <= w["top"] < end_top
                ]

                # Separate first line (within ~5 units of start) from continuation
                first_line_words = [
                    w for w in record_words if w["top"] < start_top + 5
                ]
                continuation_words = [
                    w for w in record_words if w["top"] >= start_top + 5
                ]

                # Build record from first line
                record = {
                    "license_no": get_column_value(
                        first_line_words, COLUMNS["license_no"]
                    ),
                    "license_type": get_column_value(
                        first_line_words, COLUMNS["license_type"]
                    ),
                    "licensee_name": get_column_value(
                        first_line_words, COLUMNS["licensee_name"]
                    ),
                    "dba": get_column_value(first_line_words, COLUMNS["dba"]),
                    "address": get_column_value(first_line_words, COLUMNS["address"]),
                    "ssn_fein": get_column_value(first_line_words, COLUMNS["ssn_fein"]),
                    "issue_date": "",
                    "exp_date": "",
                }

                # Extract issue date from first line
                dates_text = get_column_value(first_line_words, COLUMNS["dates"])
                dates = date_pattern.findall(dates_text)
                if dates:
                    record["issue_date"] = dates[0]

                # Process continuation lines
                for word in continuation_words:
                    col_name = None
                    for name, (x_min, x_max) in COLUMNS.items():
                        if x_min <= word["x0"] < x_max:
                            col_name = name
                            break

                    if col_name == "address":
                        record["address"] += " " + word["text"]
                    elif col_name == "dba" and not record["dba"]:
                        record["dba"] = (
                            record["dba"] + " " + word["text"]
                            if record["dba"]
                            else word["text"]
                        )
                    elif col_name == "dates":
                        date_match = date_pattern.search(word["text"])
                        if date_match and not record["exp_date"]:
                            record["exp_date"] = date_match.group()

                # Clean up address - remove footer text
                address = " ".join(record["address"].split())
                # Remove "Total Licenses:" footer if present
                if "Total Licenses:" in address:
                    address = address.split("Total Licenses:")[0].strip()
                record["address"] = address

                # Parse address into components
                addr_parts = parse_address(address)
                record["street"] = addr_parts["street"]
                record["city"] = addr_parts["city"]
                record["state"] = addr_parts["state"]
                record["zip"] = addr_parts["zip"]

                # Convert dates to YYYY-MM-DD format
                record["issue_date"] = format_date(record["issue_date"])
                record["exp_date"] = format_date(record["exp_date"])

                records.append(record)

    return records


def save_to_csv(records: list[dict], output_path: Path):
    """Save extracted data to CSV."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    fieldnames = [
        "license_no",
        "license_type",
        "licensee_name",
        "dba",
        "address",
        "street",
        "city",
        "state",
        "zip",
        "ssn_fein",
        "issue_date",
        "exp_date",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved CSV to: {output_path}")


def main():
    # Download the PDF
    pdf_path = download_pdf(PDF_URL)

    # Extract pharmacy records
    print("\nExtracting pharmacy records...")
    records = extract_pharmacy_records(pdf_path)
    print(f"Extracted {len(records)} records")

    # Show first few records
    print("\nFirst 5 records:")
    for rec in records[:5]:
        print(f"  {rec['license_no']}: {rec['licensee_name']} - {rec['address']}")

    # Save to CSV with date stamp
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"community_pharmacies_{today}.csv"
    save_to_csv(records, output_path)


if __name__ == "__main__":
    main()
