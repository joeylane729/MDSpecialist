#!/usr/bin/env python3
"""Match pediatric neurosurgeons CSV with NPI providers database"""

import os
import sys
import csv
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import from backend
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / 'backend' / '.env')

# Import from backend directly
from backend.app.database import SessionLocal
from sqlalchemy import text

def normalize_name(name):
    """Normalize name for comparison: lowercase, strip, remove extra spaces"""
    if not name:
        return ""
    return " ".join(name.lower().strip().split())

def parse_csv_name(name_str):
    """Parse CSV name format 'Last, First Middle' into first and last name"""
    if not name_str:
        return None, None
    
    # Remove quotes if present
    name_str = name_str.strip().strip('"')
    
    # Split by comma
    parts = [p.strip() for p in name_str.split(',')]
    
    if len(parts) < 2:
        # No comma - might be "First Last" format, try to parse
        name_parts = name_str.split()
        if len(name_parts) >= 2:
            return normalize_name(name_parts[0]), normalize_name(" ".join(name_parts[1:]))
        return None, None
    
    last_name = parts[0]
    first_and_middle = parts[1]
    
    # Extract first name (first word of first_and_middle)
    first_name = first_and_middle.split()[0] if first_and_middle.split() else ""
    
    return normalize_name(first_name), normalize_name(last_name)

def read_pediatric_csv(csv_path):
    """Read the pediatric neurosurgeons CSV and return a list of entries"""
    entries = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Use csv.DictReader to handle multiline entries properly
        # csv.DictReader automatically handles quoted multiline fields
        reader = csv.DictReader(f)
        
        for row in reader:
            # Clean up the row - remove leading/trailing whitespace
            entry = {
                'Name': row.get('Name', '').strip(),
                'City': row.get('City', '').strip(),
                'State / Province': row.get('State / Province', '').strip(),
                'Country': row.get('Country', '').strip(),
                'Certificate #': row.get('Certificate #', '').strip(),
                'Year Certified/Re-Certified': row.get('Year Certified/Re-Certified', '').strip(),
                'Certified Through': row.get('Certified Through', '').strip(),
            }
            
            # Only add if we have a name
            if entry['Name']:
                entries.append(entry)
    
    return entries

def match_providers_to_csv():
    """Match all NPI providers with pediatric neurosurgeons CSV"""
    
    # Read CSV
    csv_path = script_dir / "Pediatric Neurosurgeons - Sheet1.csv"
    print(f"Reading CSV from {csv_path}...")
    csv_entries = read_pediatric_csv(csv_path)
    print(f"Found {len(csv_entries)} entries in CSV")
    
    # Parse CSV entries and create lookup
    csv_lookup = {}
    for entry in csv_entries:
        first_name, last_name = parse_csv_name(entry.get('Name', ''))
        if first_name and last_name:
            key = (first_name, last_name)
            # Store all matching entries (in case of duplicates)
            if key not in csv_lookup:
                csv_lookup[key] = []
            csv_lookup[key].append(entry)
    
    print(f"Created lookup for {len(csv_lookup)} unique names")
    
    # Connect to database
    print("Connecting to database...")
    db = SessionLocal()
    
    try:
        # Query all individual providers from npi_providers
        print("Querying all providers from npi_providers...")
        result = db.execute(text("""
            SELECT 
                npi,
                provider_first_name,
                provider_last_name
            FROM npi_providers 
            WHERE entity_type_code = '1'
            ORDER BY provider_last_name, provider_first_name
        """))
        
        providers = result.fetchall()
        print(f"Found {len(providers)} providers in database")
        
        # Match providers to CSV entries
        matched_output = []
        
        for provider in providers:
            npi = provider.npi
            db_first = normalize_name(provider.provider_first_name or "")
            db_last = normalize_name(provider.provider_last_name or "")
            
            # Try exact match first
            match_key = (db_first, db_last)
            matched_csv_entry = None
            
            if match_key in csv_lookup:
                # Found exact match - use first one if multiple
                matched_csv_entry = csv_lookup[match_key][0]
            else:
                # Try fuzzy matching - check if first name matches when split
                # Some CSV entries might have middle names in first name position
                for csv_key, csv_entries_list in csv_lookup.items():
                    csv_first, csv_last = csv_key
                    
                    # Check if last name matches and first name is similar
                    if csv_last == db_last:
                        # Check if first name starts match (for middle name variations)
                        if (db_first and csv_first and 
                            (db_first.startswith(csv_first) or csv_first.startswith(db_first))):
                            matched_csv_entry = csv_entries_list[0]
                            break
                        # Also try exact first name match with any last name
                        if db_first == csv_first:
                            matched_csv_entry = csv_entries_list[0]
                            break
            
            # Prepare output row
            if matched_csv_entry:
                output_row = {
                    'NPI': npi,
                    'First Name (DB)': provider.provider_first_name or "",
                    'Last Name (DB)': provider.provider_last_name or "",
                    'Matched': 'Yes',
                    'Name (CSV)': matched_csv_entry.get('Name', ''),
                    'City': matched_csv_entry.get('City', ''),
                    'State / Province': matched_csv_entry.get('State / Province', ''),
                    'Country': matched_csv_entry.get('Country', ''),
                    'Certificate #': matched_csv_entry.get('Certificate #', ''),
                    'Year Certified/Re-Certified': matched_csv_entry.get('Year Certified/Re-Certified', ''),
                    'Certified Through': matched_csv_entry.get('Certified Through', ''),
                }
            else:
                output_row = {
                    'NPI': npi,
                    'First Name (DB)': provider.provider_first_name or "",
                    'Last Name (DB)': provider.provider_last_name or "",
                    'Matched': 'No',
                    'Name (CSV)': '',
                    'City': '',
                    'State / Province': '',
                    'Country': '',
                    'Certificate #': '',
                    'Year Certified/Re-Certified': '',
                    'Certified Through': '',
                }
            
            matched_output.append(output_row)
        
        # Write output CSV
        output_path = script_dir / "pediatric_neurosurgeons_npi_matched.csv"
        print(f"\nWriting results to {output_path}...")
        
        if matched_output:
            fieldnames = ['NPI', 'First Name (DB)', 'Last Name (DB)', 'Matched', 
                         'Name (CSV)', 'City', 'State / Province', 'Country', 
                         'Certificate #', 'Year Certified/Re-Certified', 'Certified Through']
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(matched_output)
            
            matched_count = sum(1 for row in matched_output if row['Matched'] == 'Yes')
            print(f"✓ Output written successfully!")
            print(f"  Total providers: {len(matched_output)}")
            print(f"  Matched: {matched_count}")
            print(f"  Unmatched: {len(matched_output) - matched_count}")
        else:
            print("No output to write")
            
    finally:
        db.close()

if __name__ == "__main__":
    match_providers_to_csv()

