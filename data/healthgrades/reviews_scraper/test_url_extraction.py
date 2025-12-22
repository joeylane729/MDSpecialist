#!/usr/bin/env python3
"""
Test script to validate URL extraction for all doctors with written reviews.
This tests the extract_url_from_md_file function without running the full scraper.
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

# Import the extraction function
import sys
sys.path.insert(0, str(Path(__file__).parent))
from scrape_reviews import extract_url_from_md_file

# Paths
SCRAPED_PAGES_DIR = Path(__file__).parent.parent / "scraped_pages_healthgrades"
VERIFICATION_CSV = Path(__file__).parent.parent / "neuro_specialists_verification_results.csv"

def test_url_extraction():
    """Test URL extraction for all doctors"""
    
    print("=" * 70)
    print("🧪 TESTING URL EXTRACTION FOR ALL DOCTORS")
    print("=" * 70)
    print()
    
    results = {
        'total_doctors': 0,
        'with_md_file': 0,
        'with_written_reviews': 0,
        'url_extracted': 0,
        'url_missing': 0,
        'no_written_reviews': 0,
        'no_md_file': 0,
        'errors': []
    }
    
    doctors_with_reviews_no_url = []
    doctors_without_reviews_but_url = []
    
    # Read all doctors from CSV
    with open(VERIFICATION_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results['total_doctors'] += 1
            npi = row['npi']
            first_name = row['first_name']
            last_name = row['last_name']
            filename = row['filenames']
            
            # Skip if no filename
            if not filename or filename == "None" or "None" in filename:
                results['no_md_file'] += 1
                continue
            
            md_filepath = SCRAPED_PAGES_DIR / filename
            if not md_filepath.exists():
                results['no_md_file'] += 1
                continue
            
            results['with_md_file'] += 1
            
            # Check if doctor has written reviews
            try:
                with open(md_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                written_review_patterns = [
                    r'\d+\s+with\s+a\s+written\s+review',
                    r'\d+\s+written\s+review',
                    r'with\s+a\s+written\s+review',
                    r'written\s+review',
                ]
                
                has_written_reviews = False
                for pattern in written_review_patterns:
                    if re.search(pattern, content, re.I):
                        has_written_reviews = True
                        break
                
                if has_written_reviews:
                    results['with_written_reviews'] += 1
                    
                    # Try to extract URL
                    url = extract_url_from_md_file(md_filepath)
                    
                    if url:
                        results['url_extracted'] += 1
                    else:
                        results['url_missing'] += 1
                        doctors_with_reviews_no_url.append({
                            'name': f"{first_name} {last_name}",
                            'npi': npi,
                            'filename': filename
                        })
                else:
                    results['no_written_reviews'] += 1
                    
                    # Check if URL extraction would still work (shouldn't)
                    url = extract_url_from_md_file(md_filepath)
                    if url:
                        doctors_without_reviews_but_url.append({
                            'name': f"{first_name} {last_name}",
                            'npi': npi,
                            'filename': filename,
                            'url': url
                        })
                        
            except Exception as e:
                results['errors'].append({
                    'name': f"{first_name} {last_name}",
                    'npi': npi,
                    'error': str(e)
                })
    
    # Print results
    print("📊 RESULTS:")
    print("-" * 70)
    print(f"Total doctors in CSV: {results['total_doctors']}")
    print(f"  - With MD file: {results['with_md_file']}")
    print(f"  - No MD file: {results['no_md_file']}")
    print()
    print(f"Doctors with written reviews: {results['with_written_reviews']}")
    print(f"  - ✅ URL extracted: {results['url_extracted']}")
    print(f"  - ❌ URL missing: {results['url_missing']}")
    print()
    print(f"Doctors without written reviews: {results['no_written_reviews']}")
    print()
    
    success_rate = (results['url_extracted'] / results['with_written_reviews'] * 100) if results['with_written_reviews'] > 0 else 0
    print(f"✅ Success rate: {success_rate:.1f}% ({results['url_extracted']}/{results['with_written_reviews']})")
    print()
    
    # Show problems
    if doctors_with_reviews_no_url:
        print("=" * 70)
        print(f"⚠️  DOCTORS WITH WRITTEN REVIEWS BUT NO URL ({len(doctors_with_reviews_no_url)}):")
        print("=" * 70)
        for doc in doctors_with_reviews_no_url[:20]:
            print(f"  - {doc['name']} (NPI: {doc['npi']}, File: {doc['filename']})")
        if len(doctors_with_reviews_no_url) > 20:
            print(f"  ... and {len(doctors_with_reviews_no_url) - 20} more")
        print()
    
    if doctors_without_reviews_but_url:
        print("=" * 70)
        print(f"❌ DOCTORS WITHOUT WRITTEN REVIEWS BUT URL EXTRACTED ({len(doctors_without_reviews_but_url)}):")
        print("=" * 70)
        print("  This should NOT happen with the new logic!")
        for doc in doctors_without_reviews_but_url[:20]:
            print(f"  - {doc['name']} (NPI: {doc['npi']}, URL: {doc['url']})")
        if len(doctors_without_reviews_but_url) > 20:
            print(f"  ... and {len(doctors_without_reviews_but_url) - 20} more")
        print()
    
    if results['errors']:
        print("=" * 70)
        print(f"❌ ERRORS ({len(results['errors'])}):")
        print("=" * 70)
        for err in results['errors'][:10]:
            print(f"  - {err['name']} (NPI: {err['npi']}): {err['error']}")
        if len(results['errors']) > 10:
            print(f"  ... and {len(results['errors']) - 10} more errors")
        print()
    
    print("=" * 70)
    if results['url_missing'] == 0 and len(doctors_without_reviews_but_url) == 0:
        print("✅ ALL TESTS PASSED! URL extraction is working correctly.")
    else:
        print("⚠️  Some issues found. See details above.")
    print("=" * 70)

if __name__ == "__main__":
    test_url_extraction()

