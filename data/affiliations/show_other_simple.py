#!/usr/bin/env python3
"""
Show the actual affiliation text for all affiliations marked as "Other".

This script directly reads the existing analysis results and extracts
the raw affiliation text from the XML for "Other" entries.
"""

import xml.etree.ElementTree as ET
import argparse
import os

def get_affiliation_texts_for_other_entries(xml_file: str, detailed_records_file: str, limit: int = 50):
    """
    Get affiliation texts for entries marked as "Other".
    
    Args:
        xml_file: Path to PubMed XML file
        detailed_records_file: Path to detailed_records.txt
        limit: Maximum number to show
    """
    
    # First, get the PMIDs that have "Other" entries
    other_pmids = set()
    
    if not os.path.exists(detailed_records_file):
        print(f"Error: {detailed_records_file} not found")
        return
    
    print(f"Reading 'Other' entries from {detailed_records_file}...")
    
    with open(detailed_records_file, 'r', encoding='utf-8') as f:
        # Skip header
        next(f)
        
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                pmid = parts[0]
                countries = parts[2]
                
                if 'Other' in countries:
                    other_pmids.add(pmid)
    
    print(f"Found {len(other_pmids)} unique PMIDs with 'Other' entries")
    
    # Now get the actual affiliation texts from XML
    print(f"Extracting affiliation texts from {xml_file}...")
    
    affiliation_texts = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        articles = root.findall('.//PubmedArticle')
        print(f"Processing {len(articles)} articles...")
        
        for i, article in enumerate(articles):
            if i % 1000 == 0 and i > 0:
                print(f"Processed {i} articles...")
            
            # Get PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            if pmid in other_pmids:
                # Get article title
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "No title"
                
                # Get affiliations
                affiliations = article.findall('.//Affiliation')
                
                for aff in affiliations:
                    aff_text = aff.text if aff.text else ""
                    if aff_text.strip():  # Only non-empty affiliations
                        affiliation_texts.append({
                            'pmid': pmid,
                            'title': title[:100] + "..." if len(title) > 100 else title,
                            'affiliation': aff_text
                        })
    
    except Exception as e:
        print(f"Error processing XML: {e}")
        return
    
    # Display results
    print(f"\n{'='*100}")
    print(f"AFFILIATION TEXTS FOR 'OTHER' ENTRIES (showing {min(limit, len(affiliation_texts))} of {len(affiliation_texts)})")
    print(f"{'='*100}")
    
    shown_count = 0
    for i, entry in enumerate(affiliation_texts):
        if shown_count >= limit:
            break
            
        print(f"\n{i+1}. PMID: {entry['pmid']}")
        print(f"   Title: {entry['title']}")
        print(f"   Affiliation: {entry['affiliation']}")
        print("-" * 100)
        
        shown_count += 1
    
    print(f"\n{'='*100}")
    print(f"Total 'Other' affiliation texts found: {len(affiliation_texts)}")
    print(f"Shown above: {shown_count}")
    
    # Save to file
    output_file = "other_affiliation_texts.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("PMID\tTitle\tAffiliation\n")
        for entry in affiliation_texts:
            # Escape tabs in affiliation text
            aff_escaped = entry['affiliation'].replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            f.write(f"{entry['pmid']}\t{entry['title']}\t{aff_escaped}\n")
    
    print(f"\nAll {len(affiliation_texts)} 'Other' affiliation texts saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Show affiliation texts for Other entries')
    parser.add_argument('xml_file', help='Path to PubMed XML file')
    parser.add_argument('--records', default='analysis_results/detailed_records.txt',
                       help='Path to detailed_records.txt file')
    parser.add_argument('--limit', type=int, default=100,
                       help='Maximum number to display')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xml_file):
        print(f"Error: {args.xml_file} not found")
        return
    
    get_affiliation_texts_for_other_entries(args.xml_file, args.records, args.limit)

if __name__ == "__main__":
    main()
