#!/usr/bin/env python3
"""
Show all affiliations that were marked as "Other" in the country breakdown.

This script reads the detailed records from the country analysis and
displays all affiliations that were classified as "Other".
"""

import argparse
import os

def show_other_affiliations(detailed_records_file: str, limit: int = 50):
    """
    Show affiliations marked as "Other".
    
    Args:
        detailed_records_file: Path to detailed_records.txt
        limit: Maximum number of examples to show
    """
    if not os.path.exists(detailed_records_file):
        print(f"Error: File {detailed_records_file} not found")
        return
    
    print(f"Showing affiliations marked as 'Other' (limit: {limit})")
    print("=" * 80)
    
    other_count = 0
    shown_count = 0
    
    with open(detailed_records_file, 'r', encoding='utf-8') as f:
        # Skip header
        next(f)
        
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                pmid = parts[0]
                title = parts[1]
                countries = parts[2]
                affiliation_count = parts[3]
                
                # Check if "Other" is in the countries list
                if 'Other' in countries:
                    other_count += 1
                    
                    if shown_count < limit:
                        print(f"\nPMID: {pmid}")
                        print(f"Title: {title}")
                        print(f"Countries: {countries}")
                        print(f"Affiliation Count: {affiliation_count}")
                        shown_count += 1
    
    print(f"\n" + "=" * 80)
    print(f"Total affiliations marked as 'Other': {other_count}")
    print(f"Shown above: {shown_count}")
    
    if other_count > limit:
        print(f"Use --limit {other_count} to see all examples")

def main():
    parser = argparse.ArgumentParser(description='Show affiliations marked as Other')
    parser.add_argument('--file', default='analysis_results/detailed_records.txt', 
                       help='Path to detailed_records.txt file')
    parser.add_argument('--limit', type=int, default=50, 
                       help='Maximum number of examples to show')
    
    args = parser.parse_args()
    
    show_other_affiliations(args.file, args.limit)

if __name__ == "__main__":
    main()
