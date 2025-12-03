#!/usr/bin/env python3
"""
Script to find all neurosurgeons in the exclusions list (UPDATED.csv).

Neurosurgeons are identified by matching first + last names from data/usnews/mapping/npi_verification_results.csv
against names in data/exclusions/UPDATED.csv
"""

import csv
import os
from pathlib import Path

def normalize_name(name):
    """Normalize name: remove quotes, strip whitespace, uppercase"""
    if name:
        name = str(name).strip().strip('"').upper()
        # Remove extra whitespace
        name = ' '.join(name.split())
        return name if name else None
    return None

def normalize_npi(npi):
    """Normalize NPI: remove quotes, strip whitespace, handle leading zeros"""
    if npi:
        npi = str(npi).strip().strip('"')
        # Remove leading zeros if it's a string of zeros or normalize to string
        if npi == "0000000000" or npi == "":
            return None
        # Ensure NPI is properly formatted (should be 10 digits)
        return npi.zfill(10) if len(npi) < 10 else npi
    return None

def load_neurosurgon_names(verification_file):
    """Load all neurosurgeon names and NPIs from the verification results file"""
    neurosurgeon_names = {}  # (first_name, last_name) -> npi
    
    with open(verification_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            first_name = normalize_name(row.get('first_name', ''))
            last_name = normalize_name(row.get('last_name', ''))
            npi = normalize_npi(row.get('npi', ''))
            
            if first_name and last_name:
                name_key = (first_name, last_name)
                # Store NPI if available, otherwise just track the name
                if name_key not in neurosurgeon_names:
                    neurosurgeon_names[name_key] = []
                if npi:
                    neurosurgeon_names[name_key].append(npi)
    
    print(f"✅ Loaded {len(neurosurgeon_names)} unique neurosurgeon names from verification file")
    return neurosurgeon_names

def find_neurosurgeons_in_exclusions(exclusions_file, neurosurgeon_names):
    """Find all neurosurgeons in the exclusions list by matching first + last names"""
    neurosurgeons = []
    
    with open(exclusions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            first_name = normalize_name(row.get('FIRSTNAME', ''))
            last_name = normalize_name(row.get('LASTNAME', ''))
            
            if first_name and last_name:
                name_key = (first_name, last_name)
                if name_key in neurosurgeon_names:
                    # Match found - get verification NPIs
                    verification_npis = neurosurgeon_names[name_key]
                    exclusion_npi = normalize_npi(row.get('NPI', ''))
                    
                    neurosurgeons.append({
                        'exclusion_npi': exclusion_npi or '',
                        'verification_npi': ', '.join(verification_npis) if verification_npis else '',
                        'lastname': row.get('LASTNAME', '').strip('"'),
                        'firstname': row.get('FIRSTNAME', '').strip('"'),
                        'midname': row.get('MIDNAME', '').strip('"'),
                        'busname': row.get('BUSNAME', '').strip('"'),
                        'specialty': row.get('SPECIALTY', '').strip('"'),
                        'city': row.get('CITY', '').strip('"'),
                        'state': row.get('STATE', '').strip('"'),
                        'zip': row.get('ZIP', '').strip('"'),
                        'excltype': row.get('EXCLTYPE', '').strip('"'),
                        'excldate': row.get('EXCLDATE', '').strip('"'),
                        'address': row.get('ADDRESS', '').strip('"'),
                    })
    
    return neurosurgeons

def main():
    # Get the script directory
    script_dir = Path(__file__).parent
    
    # Define file paths
    verification_file = script_dir.parent / 'usnews' / 'mapping' / 'npi_verification_results.csv'
    # Try UPDATED.csv first, fall back to exclusions.csv
    exclusions_file = script_dir / 'UPDATED.csv'
    if not exclusions_file.exists():
        exclusions_file = script_dir / 'exclusions.csv'
    output_file = script_dir / 'neurosurgeons_in_exclusions_by_name.csv'
    
    # Check if files exist
    if not verification_file.exists():
        print(f"❌ Error: Neurosurgeon verification file not found: {verification_file}")
        return
    
    if not exclusions_file.exists():
        print(f"❌ Error: Exclusions file not found: {exclusions_file}")
        return
    
    print(f"🔍 Loading neurosurgeon names from: {verification_file}")
    neurosurgeon_names = load_neurosurgon_names(verification_file)
    
    print(f"\n🔍 Searching for neurosurgeons in exclusions file (matching by name): {exclusions_file}")
    neurosurgeons = find_neurosurgeons_in_exclusions(exclusions_file, neurosurgeon_names)
    
    print(f"\n📊 Results:")
    print(f"   Found {len(neurosurgeons)} neurosurgeons in the exclusions list")
    
    if neurosurgeons:
        # Write results to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['exclusion_npi', 'verification_npi', 'lastname', 'firstname', 'midname', 'busname', 'specialty', 
                         'city', 'state', 'zip', 'excltype', 'excldate', 'address']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(neurosurgeons)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        # Print summary
        print(f"\n📋 Summary:")
        print(f"   Total neurosurgeons in exclusions: {len(neurosurgeons)}")
        
        # Count by state
        states = {}
        for ns in neurosurgeons:
            state = ns['state'] or 'Unknown'
            states[state] = states.get(state, 0) + 1
        
        if states:
            print(f"\n   By state:")
            for state, count in sorted(states.items(), key=lambda x: x[1], reverse=True):
                print(f"      {state}: {count}")
        
        # Count by exclusion type
        excl_types = {}
        for ns in neurosurgeons:
            excl_type = ns['excltype'] or 'Unknown'
            excl_types[excl_type] = excl_types.get(excl_type, 0) + 1
        
        if excl_types:
            print(f"\n   By exclusion type:")
            for excl_type, count in sorted(excl_types.items(), key=lambda x: x[1], reverse=True):
                print(f"      {excl_type}: {count}")
        
        # Show first 10 examples
        print(f"\n   First 10 neurosurgeons found:")
        for i, ns in enumerate(neurosurgeons[:10], 1):
            name = f"{ns['firstname']} {ns['lastname']}".strip() or ns['busname'] or 'N/A'
            excl_npi = ns['exclusion_npi'] or 'N/A'
            verif_npi = ns['verification_npi'] or 'N/A'
            print(f"      {i}. {name} (Exclusion NPI: {excl_npi}, Verification NPI: {verif_npi}, State: {ns['state']}, Type: {ns['excltype']})")
        
        if len(neurosurgeons) > 10:
            print(f"      ... and {len(neurosurgeons) - 10} more (see {output_file} for full list)")
    else:
        print("\n✅ No neurosurgeons found in the exclusions list")

if __name__ == '__main__':
    main()

