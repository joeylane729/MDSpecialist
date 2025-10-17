#!/usr/bin/env python3
"""
Show the actual affiliation text for all affiliations marked as "Other".

This script reads the detailed records and displays the raw affiliation text
for all entries that were classified as "Other".
"""

import xml.etree.ElementTree as ET
import argparse
import os
import re
from typing import List

def get_other_affiliation_texts(xml_file: str) -> List[dict]:
    """
    Parse XML file and extract affiliation text for entries marked as "Other".
    
    Args:
        xml_file: Path to PubMed XML file
        
    Returns:
        List of dictionaries with PMID, title, and affiliation text
    """
    print(f"Parsing {xml_file} to extract 'Other' affiliation texts...")
    
    other_affiliations = []
    total_articles = 0
    
    try:
        # Parse XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find all articles
        articles = root.findall('.//PubmedArticle')
        total_articles = len(articles)
        
        print(f"Found {total_articles} articles")
        
        for i, article in enumerate(articles):
            if i % 1000 == 0 and i > 0:
                print(f"Processed {i} articles...")
            
            # Get PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else f"unknown_{i}"
            
            # Get article title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else "No title"
            
            # Find affiliations
            affiliations = article.findall('.//Affiliation')
            
            if affiliations:
                for aff in affiliations:
                    aff_text = aff.text if aff.text else ""
                    
                    # Check if this affiliation would be classified as "Other"
                    # (no country patterns match)
                    if is_other_affiliation(aff_text):
                        other_affiliations.append({
                            'pmid': pmid,
                            'title': title[:100] + "..." if len(title) > 100 else title,
                            'affiliation': aff_text
                        })
    
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return other_affiliations
    except Exception as e:
        print(f"Error processing file: {e}")
        return other_affiliations
    
    print(f"Processing complete! Found {len(other_affiliations)} 'Other' affiliations")
    return other_affiliations

def is_other_affiliation(affiliation_text: str) -> bool:
    """
    Check if affiliation would be classified as "Other" using the same logic
    as the country breakdown script.
    
    Args:
        affiliation_text: Raw affiliation text
        
    Returns:
        True if would be classified as "Other"
    """
    if not affiliation_text:
        return True
    
    # Import the same country patterns from the original script
    from analyze_country_breakdown import COUNTRY_PATTERNS
    
    affiliation_lower = affiliation_text.lower()
    
    # Check each country pattern
    for country, patterns in COUNTRY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern.lower(), affiliation_lower):
                return False  # Found a match, not "Other"
    
    return True  # No matches found, would be "Other"

def show_other_affiliation_texts(other_affiliations: List[dict], limit: int = 50):
    """
    Display the affiliation texts.
    
    Args:
        other_affiliations: List of other affiliation data
        limit: Maximum number to display
    """
    print(f"\nShowing affiliation texts for 'Other' entries (limit: {limit})")
    print("=" * 100)
    
    shown_count = 0
    for i, entry in enumerate(other_affiliations):
        if shown_count >= limit:
            break
            
        print(f"\n{i+1}. PMID: {entry['pmid']}")
        print(f"   Title: {entry['title']}")
        print(f"   Affiliation: {entry['affiliation']}")
        print("-" * 100)
        
        shown_count += 1
    
    print(f"\n" + "=" * 100)
    print(f"Total 'Other' affiliations: {len(other_affiliations)}")
    print(f"Shown above: {shown_count}")
    
    if len(other_affiliations) > limit:
        print(f"Use --limit {len(other_affiliations)} to see all examples")

def save_to_file(other_affiliations: List[dict], output_file: str):
    """Save all other affiliation texts to a file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("PMID\tTitle\tAffiliation\n")
        for entry in other_affiliations:
            f.write(f"{entry['pmid']}\t{entry['title']}\t{entry['affiliation']}\n")
    
    print(f"\nAll {len(other_affiliations)} 'Other' affiliation texts saved to: {output_file}")

def main():
    
    parser = argparse.ArgumentParser(description='Show affiliation texts marked as Other')
    parser.add_argument('xml_file', help='Path to PubMed XML file')
    parser.add_argument('--limit', type=int, default=100, 
                       help='Maximum number of examples to display')
    parser.add_argument('--save', action='store_true',
                       help='Save all results to a file')
    parser.add_argument('--output', default='other_affiliation_texts.txt',
                       help='Output file name (when using --save)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xml_file):
        print(f"Error: File {args.xml_file} not found")
        return
    
    # Get other affiliation texts
    other_affiliations = get_other_affiliation_texts(args.xml_file)
    
    # Display results
    show_other_affiliation_texts(other_affiliations, args.limit)
    
    # Save to file if requested
    if args.save:
        save_to_file(other_affiliations, args.output)

if __name__ == "__main__":
    main()
