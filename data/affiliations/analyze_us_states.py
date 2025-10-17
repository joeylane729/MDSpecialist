#!/usr/bin/env python3
"""
Analyze US state mentions in PubMed XML affiliations data.

This script identifies affiliations that mention US states but don't
explicitly mention "US", "USA", or "United States".
"""

import xml.etree.ElementTree as ET
import re
from collections import Counter, defaultdict
import argparse
import os
from typing import Dict, List, Set, Tuple

# US States patterns
US_STATES = {
    'Alabama': [r'\bAlabama\b', r'\bAL\b'],
    'Alaska': [r'\bAlaska\b', r'\bAK\b'],
    'Arizona': [r'\bArizona\b', r'\bAZ\b'],
    'Arkansas': [r'\bArkansas\b', r'\bAR\b'],
    'California': [r'\bCalifornia\b', r'\bCA\b', r'\bCalif\b'],
    'Colorado': [r'\bColorado\b', r'\bCO\b'],
    'Connecticut': [r'\bConnecticut\b', r'\bCT\b'],
    'Delaware': [r'\bDelaware\b', r'\bDE\b'],
    'Florida': [r'\bFlorida\b', r'\bFL\b'],
    'Georgia': [r'\bGeorgia\b', r'\bGA\b'],
    'Hawaii': [r'\bHawaii\b', r'\bHI\b'],
    'Idaho': [r'\bIdaho\b', r'\bID\b'],
    'Illinois': [r'\bIllinois\b', r'\bIL\b'],
    'Indiana': [r'\bIndiana\b', r'\bIN\b'],
    'Iowa': [r'\bIowa\b', r'\bIA\b'],
    'Kansas': [r'\bKansas\b', r'\bKS\b'],
    'Kentucky': [r'\bKentucky\b', r'\bKY\b'],
    'Louisiana': [r'\bLouisiana\b', r'\bLA\b'],
    'Maine': [r'\bMaine\b', r'\bME\b'],
    'Maryland': [r'\bMaryland\b', r'\bMD\b'],
    'Massachusetts': [r'\bMassachusetts\b', r'\bMA\b'],
    'Michigan': [r'\bMichigan\b', r'\bMI\b'],
    'Minnesota': [r'\bMinnesota\b', r'\bMN\b'],
    'Mississippi': [r'\bMississippi\b', r'\bMS\b'],
    'Missouri': [r'\bMissouri\b', r'\bMO\b'],
    'Montana': [r'\bMontana\b', r'\bMT\b'],
    'Nebraska': [r'\bNebraska\b', r'\bNE\b'],
    'Nevada': [r'\bNevada\b', r'\bNV\b'],
    'New Hampshire': [r'\bNew Hampshire\b', r'\bNH\b'],
    'New Jersey': [r'\bNew Jersey\b', r'\bNJ\b'],
    'New Mexico': [r'\bNew Mexico\b', r'\bNM\b'],
    'New York': [r'\bNew York\b', r'\bNY\b'],
    'North Carolina': [r'\bNorth Carolina\b', r'\bNC\b'],
    'North Dakota': [r'\bNorth Dakota\b', r'\bND\b'],
    'Ohio': [r'\bOhio\b', r'\bOH\b'],
    'Oklahoma': [r'\bOklahoma\b', r'\bOK\b'],
    'Oregon': [r'\bOregon\b', r'\bOR\b'],
    'Pennsylvania': [r'\bPennsylvania\b', r'\bPA\b'],
    'Rhode Island': [r'\bRhode Island\b', r'\bRI\b'],
    'South Carolina': [r'\bSouth Carolina\b', r'\bSC\b'],
    'South Dakota': [r'\bSouth Dakota\b', r'\bSD\b'],
    'Tennessee': [r'\bTennessee\b', r'\bTN\b'],
    'Texas': [r'\bTexas\b', r'\bTX\b'],
    'Utah': [r'\bUtah\b', r'\bUT\b'],
    'Vermont': [r'\bVermont\b', r'\bVT\b'],
    'Virginia': [r'\bVirginia\b', r'\bVA\b'],
    'Washington': [r'\bWashington\b', r'\bWA\b'],
    'West Virginia': [r'\bWest Virginia\b', r'\bWV\b'],
    'Wisconsin': [r'\bWisconsin\b', r'\bWI\b'],
    'Wyoming': [r'\bWyoming\b', r'\bWY\b']
}

# Major US cities and institutions that might indicate US without explicit country mention
US_INDICATORS = [
    r'\bHarvard\b', r'\bStanford\b', r'\bMIT\b', r'\bUCLA\b', r'\bUC Berkeley\b',
    r'\bJohns Hopkins\b', r'\bMayo Clinic\b', r'\bNIH\b', r'\bCDC\b',
    r'\bLos Angeles\b', r'\bChicago\b', r'\bBoston\b', r'\bSeattle\b',
    r'\bSan Francisco\b', r'\bDenver\b', r'\bAtlanta\b', r'\bMiami\b',
    r'\bLas Vegas\b', r'\bPhoenix\b', r'\bDetroit\b', r'\bPhiladelphia\b'
]

def extract_state_from_affiliation(affiliation_text: str) -> Tuple[str, bool]:
    """
    Extract US state from affiliation text and check if it mentions explicit US indicators.
    
    Args:
        affiliation_text: Raw affiliation text
        
    Returns:
        Tuple of (state_name, has_explicit_us_mention)
    """
    if not affiliation_text:
        return None, False
    
    affiliation_lower = affiliation_text.lower()
    
    # Check for explicit US mentions
    explicit_us_patterns = [r'\bus\b', r'\busa\b', r'\bunited states\b', r'\bamerica\b']
    has_explicit_us = any(re.search(pattern, affiliation_lower) for pattern in explicit_us_patterns)
    
    # Check for US state mentions
    for state, patterns in US_STATES.items():
        for pattern in patterns:
            if re.search(pattern.lower(), affiliation_lower):
                return state, has_explicit_us
    
    return None, has_explicit_us

def has_us_indicators(affiliation_text: str) -> bool:
    """
    Check if affiliation has US indicators (cities, institutions) without explicit country mention.
    
    Args:
        affiliation_text: Raw affiliation text
        
    Returns:
        True if has US indicators, False otherwise
    """
    if not affiliation_text:
        return False
    
    affiliation_lower = affiliation_text.lower()
    return any(re.search(pattern.lower(), affiliation_lower) for pattern in US_INDICATORS)

def parse_pubmed_xml_for_states(file_path: str) -> Dict:
    """
    Parse PubMed XML file and analyze US state mentions.
    
    Args:
        file_path: Path to PubMed XML file
        
    Returns:
        Dictionary with analysis results
    """
    print(f"Parsing {file_path} for US state analysis...")
    
    results = {
        'state_mentions': Counter(),
        'state_without_explicit_us': Counter(),
        'state_with_explicit_us': Counter(),
        'us_indicators_without_explicit': Counter(),
        'detailed_records': [],
        'total_articles': 0,
        'articles_with_affiliations': 0,
        'total_affiliations': 0
    }
    
    try:
        # Parse XML file
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Find all articles
        articles = root.findall('.//PubmedArticle')
        results['total_articles'] = len(articles)
        
        print(f"Found {results['total_articles']} articles")
        
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
                results['articles_with_affiliations'] += 1
                results['total_affiliations'] += len(affiliations)
                
                for aff in affiliations:
                    aff_text = aff.text if aff.text else ""
                    state, has_explicit_us = extract_state_from_affiliation(aff_text)
                    has_indicators = has_us_indicators(aff_text)
                    
                    if state:
                        results['state_mentions'][state] += 1
                        
                        if has_explicit_us:
                            results['state_with_explicit_us'][state] += 1
                        else:
                            results['state_without_explicit_us'][state] += 1
                            
                        results['detailed_records'].append({
                            'pmid': pmid,
                            'title': title[:100] + "..." if len(title) > 100 else title,
                            'state': state,
                            'has_explicit_us': has_explicit_us,
                            'has_indicators': has_indicators,
                            'affiliation': aff_text[:200] + "..." if len(aff_text) > 200 else aff_text
                        })
                    
                    # Track US indicators without explicit country mention
                    if has_indicators and not has_explicit_us:
                        # Extract the indicator that matched
                        affiliation_lower = aff_text.lower()
                        for indicator in US_INDICATORS:
                            if re.search(indicator.lower(), affiliation_lower):
                                results['us_indicators_without_explicit'][indicator.replace(r'\b', '').replace(r'\b', '')] += 1
                                break
    
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return results
    except Exception as e:
        print(f"Error processing file: {e}")
        return results
    
    print(f"Processing complete!")
    print(f"Total articles: {results['total_articles']}")
    print(f"Articles with affiliations: {results['articles_with_affiliations']}")
    print(f"Total affiliations analyzed: {results['total_affiliations']}")
    
    return results

def print_state_analysis(results: Dict):
    """Print formatted state analysis."""
    print(f"\n{'='*80}")
    print(f"US STATE ANALYSIS")
    print(f"{'='*80}")
    
    print(f"\n📊 SUMMARY:")
    print(f"Total state mentions: {sum(results['state_mentions'].values())}")
    print(f"State mentions WITHOUT explicit US/USA/United States: {sum(results['state_without_explicit_us'].values())}")
    print(f"State mentions WITH explicit US/USA/United States: {sum(results['state_with_explicit_us'].values())}")
    print(f"US indicators (cities/institutions) without explicit country: {sum(results['us_indicators_without_explicit'].values())}")
    
    print(f"\n🗺️  TOP STATES WITHOUT EXPLICIT US MENTION:")
    print(f"{'State':<20} {'Count':<10} {'Percentage':<10}")
    print(f"{'-'*40}")
    
    total_state_mentions = sum(results['state_mentions'].values())
    for state, count in results['state_without_explicit_us'].most_common(15):
        percentage = (count / total_state_mentions) * 100 if total_state_mentions > 0 else 0
        print(f"{state:<20} {count:<10} {percentage:>8.1f}%")
    
    print(f"\n🏛️  US INDICATORS WITHOUT EXPLICIT COUNTRY MENTION:")
    for indicator, count in results['us_indicators_without_explicit'].most_common(10):
        print(f"{indicator:<30} {count:>6}")

def save_detailed_results(results: Dict, output_dir: str):
    """Save detailed results to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save state analysis
    with open(os.path.join(output_dir, 'us_state_analysis.txt'), 'w') as f:
        f.write("State,Total_Mentions,Without_Explicit_US,With_Explicit_US\n")
        for state in results['state_mentions']:
            total = results['state_mentions'][state]
            without = results['state_without_explicit_us'][state]
            with_explicit = results['state_with_explicit_us'][state]
            f.write(f"{state},{total},{without},{with_explicit}\n")
    
    # Save detailed records
    with open(os.path.join(output_dir, 'state_detailed_records.txt'), 'w') as f:
        f.write("PMID\tTitle\tState\tHas_Explicit_US\tHas_Indicators\tAffiliation\n")
        for record in results['detailed_records']:
            f.write(f"{record['pmid']}\t{record['title']}\t{record['state']}\t{record['has_explicit_us']}\t{record['has_indicators']}\t{record['affiliation']}\n")
    
    print(f"\nDetailed results saved to {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description='Analyze US state mentions in PubMed XML affiliations')
    parser.add_argument('xml_file', help='Path to PubMed XML file')
    parser.add_argument('--output-dir', default='state_analysis_results', help='Directory to save detailed results')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xml_file):
        print(f"Error: File {args.xml_file} not found")
        return
    
    # Parse XML and analyze US states
    results = parse_pubmed_xml_for_states(args.xml_file)
    
    # Print results
    print_state_analysis(results)
    
    # Save detailed results
    save_detailed_results(results, args.output_dir)

if __name__ == "__main__":
    main()
