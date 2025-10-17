#!/usr/bin/env python3
"""
Analyze country breakdown in PubMed XML affiliations data.

This script parses PubMed XML files and extracts country information
from affiliation sections to provide a breakdown by country.
"""

import xml.etree.ElementTree as ET
import re
from collections import Counter, defaultdict
import argparse
import os
from typing import Dict, List, Set, Tuple

# Common country patterns and mappings
COUNTRY_PATTERNS = {
    'United States': [
        r'\bUSA\b', r'\bUS\b', r'\bUnited States\b'
    ],
    'China': [
        r'\bChina\b', r'\bBeijing\b', r'\bShanghai\b', r'\bTsinghua\b',
        r'\bPeking\b', r'\bFudan\b', r'\bChinese\b'
    ],
    'Japan': [
        r'\bJapan\b', r'\bTokyo\b', r'\bOsaka\b', r'\bKyoto\b',
        r'\bJapanese\b'
    ],
    'Germany': [
        r'\bGermany\b', r'\bBerlin\b', r'\bMunich\b', r'\bGerman\b',
        r'\bMax Planck\b', r'\bLMU\b'
    ],
    'United Kingdom': [
        r'\bUK\b', r'\bUnited Kingdom\b', r'\bEngland\b', r'\bScotland\b',
        r'\bWales\b', r'\bOxford\b', r'\bCambridge\b', r'\bImperial\b',
        r'\bUCL\b', r'\bKing\'s College\b'
    ],
    'France': [
        r'\bFrance\b', r'\bParis\b', r'\bFrench\b', r'\bSorbonne\b',
        r'\bCNRS\b', r'\bINSERM\b'
    ],
    'Italy': [
        r'\bItaly\b', r'\bItalian\b', r'\bRome\b', r'\bMilan\b',
        r'\bBologna\b'
    ],
    'Canada': [
        r'\bCanada\b', r'\bCanadian\b', r'\bToronto\b', r'\bMcGill\b',
        r'\bUBC\b', r'\bWaterloo\b'
    ],
    'Australia': [
        r'\bAustralia\b', r'\bAustralian\b', r'\bSydney\b', r'\bMelbourne\b',
        r'\bANU\b', r'\bUNSW\b'
    ],
    'South Korea': [
        r'\bSouth Korea\b', r'\bKorea\b', r'\bSeoul\b', r'\bKorean\b',
        r'\bKAIST\b', r'\bSNU\b'
    ],
    'India': [
        r'\bIndia\b', r'\bIndian\b', r'\bIIT\b', r'\bDelhi\b',
        r'\bMumbai\b', r'\bBangalore\b'
    ],
    'Brazil': [
        r'\bBrazil\b', r'\bBrazilian\b', r'\bSão Paulo\b', r'\bRio de Janeiro\b'
    ],
    'Spain': [
        r'\bSpain\b', r'\bSpanish\b', r'\bMadrid\b', r'\bBarcelona\b',
        r'\bCSIC\b'
    ],
    'Netherlands': [
        r'\bNetherlands\b', r'\bDutch\b', r'\bAmsterdam\b', r'\bDelft\b',
        r'\bErasmus\b'
    ],
    'Switzerland': [
        r'\bSwitzerland\b', r'\bSwiss\b', r'\bETH\b', r'\bZurich\b',
        r'\bBasel\b'
    ],
    'Sweden': [
        r'\bSweden\b', r'\bSwedish\b', r'\bStockholm\b', r'\bKarolinska\b'
    ],
    'Israel': [
        r'\bIsrael\b', r'\bIsraeli\b', r'\bHebrew\b', r'\bTel Aviv\b',
        r'\bWeizmann\b'
    ],
    'Singapore': [
        r'\bSingapore\b', r'\bNUS\b', r'\bNTU\b'
    ],
    'Russia': [
        r'\bRussia\b', r'\bRussian\b', r'\bMoscow\b', r'\bSt\. Petersburg\b'
    ],
    'Belgium': [
        r'\bBelgium\b', r'\bBelgian\b', r'\bBrussels\b', r'\bLeuven\b',
        r'\bGhent\b'
    ],
    'Norway': [
        r'\bNorway\b', r'\bNorwegian\b', r'\bOslo\b', r'\bBergen\b'
    ],
    'Denmark': [
        r'\bDenmark\b', r'\bDanish\b', r'\bCopenhagen\b', r'\bAarhus\b'
    ],
    'Finland': [
        r'\bFinland\b', r'\bFinnish\b', r'\bHelsinki\b', r'\bTampere\b'
    ],
    'Austria': [
        r'\bAustria\b', r'\bAustrian\b', r'\bVienna\b', r'\bSalzburg\b'
    ],
    'Poland': [
        r'\bPoland\b', r'\bPolish\b', r'\bWarsaw\b', r'\bKrakow\b'
    ],
    'Czech Republic': [
        r'\bCzech Republic\b', r'\bCzech\b', r'\bPrague\b', r'\bBrno\b'
    ],
    'Hungary': [
        r'\bHungary\b', r'\bHungarian\b', r'\bBudapest\b'
    ],
    'Portugal': [
        r'\bPortugal\b', r'\bPortuguese\b', r'\bLisbon\b', r'\bPorto\b'
    ],
    'Ireland': [
        r'\bIreland\b', r'\bIrish\b', r'\bDublin\b', r'\bCork\b'
    ],
    'Greece': [
        r'\bGreece\b', r'\bGreek\b', r'\bAthens\b', r'\bThessaloniki\b'
    ],
    'Turkey': [
        r'\bTurkey\b', r'\bTurkish\b', r'\bIstanbul\b', r'\bAnkara\b'
    ],
    'Iran': [
        r'\bIran\b', r'\bIranian\b', r'\bTehran\b', r'\bShiraz\b'
    ],
    'Saudi Arabia': [
        r'\bSaudi Arabia\b', r'\bSaudi\b', r'\bRiyadh\b', r'\bJeddah\b'
    ],
    'Egypt': [
        r'\bEgypt\b', r'\bEgyptian\b', r'\bCairo\b', r'\bAlexandria\b'
    ],
    'South Africa': [
        r'\bSouth Africa\b', r'\bCape Town\b', r'\bJohannesburg\b'
    ],
    'Nigeria': [
        r'\bNigeria\b', r'\bNigerian\b', r'\bLagos\b', r'\bAbuja\b'
    ],
    'Thailand': [
        r'\bThailand\b', r'\bThai\b', r'\bBangkok\b', r'\bChiang Mai\b'
    ],
    'Malaysia': [
        r'\bMalaysia\b', r'\bMalaysian\b', r'\bKuala Lumpur\b', r'\bPenang\b'
    ],
    'Indonesia': [
        r'\bIndonesia\b', r'\bIndonesian\b', r'\bJakarta\b', r'\bBandung\b'
    ],
    'Philippines': [
        r'\bPhilippines\b', r'\bFilipino\b', r'\bManila\b', r'\bQuezon\b'
    ],
    'Vietnam': [
        r'\bVietnam\b', r'\bVietnamese\b', r'\bHo Chi Minh\b', r'\bHanoi\b'
    ],
    'Pakistan': [
        r'\bPakistan\b', r'\bPakistani\b', r'\bKarachi\b', r'\bLahore\b'
    ],
    'Bangladesh': [
        r'\bBangladesh\b', r'\bBangladeshi\b', r'\bDhaka\b', r'\bChittagong\b'
    ],
    'Sri Lanka': [
        r'\bSri Lanka\b', r'\bColombo\b', r'\bKandy\b'
    ],
    'Mexico': [
        r'\bMexico\b', r'\bMexican\b', r'\bMexico City\b', r'\bGuadalajara\b'
    ],
    'Argentina': [
        r'\bArgentina\b', r'\bArgentine\b', r'\bBuenos Aires\b', r'\bCordoba\b'
    ],
    'Chile': [
        r'\bChile\b', r'\bChilean\b', r'\bSantiago\b', r'\bValparaiso\b'
    ],
    'Colombia': [
        r'\bColombia\b', r'\bColombian\b', r'\bBogota\b', r'\bMedellin\b'
    ],
    'Peru': [
        r'\bPeru\b', r'\bPeruvian\b', r'\bLima\b', r'\bArequipa\b'
    ],
    'Venezuela': [
        r'\bVenezuela\b', r'\bVenezuelan\b', r'\bCaracas\b', r'\bMaracaibo\b'
    ],
    'Ukraine': [
        r'\bUkraine\b', r'\bUkrainian\b', r'\bKiev\b', r'\bKharkiv\b'
    ]
}

def extract_country_from_affiliation(affiliation_text: str) -> str:
    """
    Extract country from affiliation text using pattern matching.
    
    Args:
        affiliation_text: Raw affiliation text
        
    Returns:
        Country name or 'Other' if not found
    """
    if not affiliation_text:
        return 'Other'
    
    affiliation_lower = affiliation_text.lower()
    
    # Check each country pattern
    for country, patterns in COUNTRY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern.lower(), affiliation_lower):
                return country
    
    return 'Other'

def parse_pubmed_xml(file_path: str) -> Tuple[Dict[str, int], List[Dict]]:
    """
    Parse PubMed XML file and extract country information from affiliations.
    
    Args:
        file_path: Path to PubMed XML file
        
    Returns:
        Tuple of (country_counts, detailed_records)
    """
    print(f"Parsing {file_path}...")
    
    country_counts = Counter()
    detailed_records = []
    total_articles = 0
    articles_with_affiliations = 0
    articles_without_affiliations = 0
    
    try:
        # Parse XML file
        tree = ET.parse(file_path)
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
                articles_with_affiliations += 1
                countries_in_article = set()
                
                for aff in affiliations:
                    aff_text = aff.text if aff.text else ""
                    country = extract_country_from_affiliation(aff_text)
                    countries_in_article.add(country)
                    country_counts[country] += 1
                
                detailed_records.append({
                    'pmid': pmid,
                    'title': title[:100] + "..." if len(title) > 100 else title,
                    'countries': list(countries_in_article),
                    'affiliation_count': len(affiliations)
                })
            else:
                # No affiliation info available for this publication
                articles_without_affiliations += 1
                country_counts['No Affiliation Info'] += 1
                
                detailed_records.append({
                    'pmid': pmid,
                    'title': title[:100] + "..." if len(title) > 100 else title,
                    'countries': ['No Affiliation Info'],
                    'affiliation_count': 0
                })
    
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return country_counts, detailed_records
    except Exception as e:
        print(f"Error processing file: {e}")
        return country_counts, detailed_records
    
    print(f"Processing complete!")
    print(f"Total articles: {total_articles}")
    print(f"Articles with affiliations: {articles_with_affiliations}")
    print(f"Articles without affiliations: {articles_without_affiliations}")
    print(f"Total affiliations analyzed: {sum(country_counts.values())}")
    
    return country_counts, detailed_records

def print_country_breakdown(country_counts: Dict[str, int], top_n: int = 20):
    """Print formatted country breakdown."""
    print(f"\n{'='*60}")
    print(f"COUNTRY BREAKDOWN (Top {top_n})")
    print(f"{'='*60}")
    
    total_affiliations = sum(country_counts.values())
    
    for i, (country, count) in enumerate(country_counts.most_common(top_n), 1):
        percentage = (count / total_affiliations) * 100
        print(f"{i:2d}. {country:<20} {count:>8,} ({percentage:5.1f}%)")
    
    print(f"{'='*60}")
    print(f"Total affiliations: {total_affiliations:,}")

def save_detailed_results(country_counts: Dict[str, int], detailed_records: List[Dict], output_dir: str):
    """Save detailed results to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save country counts
    with open(os.path.join(output_dir, 'country_counts.txt'), 'w') as f:
        f.write("Country,Count,Percentage\n")
        total = sum(country_counts.values())
        for country, count in country_counts.most_common():
            percentage = (count / total) * 100
            f.write(f"{country},{count},{percentage:.2f}\n")
    
    # Save detailed records
    with open(os.path.join(output_dir, 'detailed_records.txt'), 'w') as f:
        f.write("PMID\tTitle\tCountries\tAffiliation_Count\n")
        for record in detailed_records:
            countries_str = "; ".join(record['countries'])
            f.write(f"{record['pmid']}\t{record['title']}\t{countries_str}\t{record['affiliation_count']}\n")
    
    print(f"\nDetailed results saved to {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description='Analyze country breakdown in PubMed XML affiliations')
    parser.add_argument('xml_file', help='Path to PubMed XML file')
    parser.add_argument('--top-n', type=int, default=20, help='Number of top countries to display')
    parser.add_argument('--output-dir', default='analysis_results', help='Directory to save detailed results')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xml_file):
        print(f"Error: File {args.xml_file} not found")
        return
    
    # Parse XML and extract country information
    country_counts, detailed_records = parse_pubmed_xml(args.xml_file)
    
    # Print results
    print_country_breakdown(country_counts, args.top_n)
    
    # Save detailed results
    save_detailed_results(country_counts, detailed_records, args.output_dir)

if __name__ == "__main__":
    main()
