#!/usr/bin/env python3
"""Find pediatric neurosurgeons from CSV who didn't match any NPIs"""

import csv
from pathlib import Path

script_dir = Path(__file__).parent.resolve()

def read_matched_csv(matched_csv_path):
    """Read the matched CSV and extract all matched CSV names"""
    matched_names = set()
    
    with open(matched_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_name = row.get('Name (CSV)', '').strip()
            if csv_name:
                # Normalize name for comparison (remove quotes, lowercase)
                normalized_name = csv_name.strip('"').lower().strip()
                matched_names.add(normalized_name)
    
    return matched_names

def read_original_csv(original_csv_path):
    """Read the original pediatric neurosurgeons CSV"""
    entries = []
    
    with open(original_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
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

def find_unmatched():
    """Find unmatched entries from the original CSV"""
    
    # Read the matched CSV to see which entries were matched
    matched_csv_path = script_dir / "pediatric_neurosurgeons_npi_matched.csv"
    print(f"Reading matched CSV from {matched_csv_path}...")
    matched_names = read_matched_csv(matched_csv_path)
    print(f"Found {len(matched_names)} matched names")
    
    # Read the original CSV
    original_csv_path = script_dir / "Pediatric Neurosurgeons - Sheet1.csv"
    print(f"Reading original CSV from {original_csv_path}...")
    original_entries = read_original_csv(original_csv_path)
    print(f"Found {len(original_entries)} entries in original CSV")
    
    # Find unmatched entries
    unmatched_entries = []
    for entry in original_entries:
        name = entry.get('Name', '').strip()
        # Normalize name for comparison
        normalized_name = name.strip('"').lower().strip()
        
        if normalized_name not in matched_names:
            unmatched_entries.append(entry)
    
    # Write unmatched entries to new CSV
    output_path = script_dir / "pediatric_neurosurgeons_unmatched.csv"
    print(f"\nWriting unmatched entries to {output_path}...")
    
    if unmatched_entries:
        fieldnames = ['Name', 'City', 'State / Province', 'Country', 
                     'Certificate #', 'Year Certified/Re-Certified', 'Certified Through']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unmatched_entries)
        
        print(f"✓ Output written successfully!")
        print(f"  Total unmatched entries: {len(unmatched_entries)}")
        print(f"  Matched entries: {len(original_entries) - len(unmatched_entries)}")
    else:
        print("No unmatched entries found")

if __name__ == "__main__":
    find_unmatched()

