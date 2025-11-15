#!/usr/bin/env python3
"""Scrape certificationmatters.org for all neurosurgeons"""

import os
import sys
import csv
import time
import re
from firecrawl import Firecrawl
from dotenv import load_dotenv
from collections import defaultdict
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from backend.app.database import get_db

load_dotenv()

def has_certification_proof(db, npi):
    """Check if we already have proof of certification in usnews_data or healthgrades_data"""
    try:
        result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT npi FROM usnews_data 
                WHERE npi = :npi 
                AND certifications LIKE '%American Board of Neurological Surgery%'
                UNION
                SELECT npi FROM healthgrades_data 
                WHERE npi = :npi 
                AND certifications LIKE '%American Board of Neurological Surgery%'
            ) combined
        """), {"npi": npi})
        row = result.fetchone()
        return row.count > 0 if row else False
    except Exception as e:
        print(f"   ⚠️  Error checking certification proof for NPI {npi}: {e}")
        return False  # If error, assume no proof and proceed with scraping

def get_neurosurgeons():
    """Get all neurosurgeons from database"""
    db = next(get_db())
    try:
        result = db.execute(text("""
            SELECT npi,
                   provider_first_name,
                   provider_last_name,
                   provider_business_practice_location_address_state_name,
                   provider_business_practice_location_address_city_name
            FROM npi_providers 
            WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
        """))
        return [{
            'npi': r.npi,
            'first_name': r.provider_first_name or '',
            'last_name': r.provider_last_name or '',
            'state': r.provider_business_practice_location_address_state_name or '',
            'npi_city': r.provider_business_practice_location_address_city_name or ''
        } for r in result]
    finally:
        db.close()

def build_url(doctor, use_state=False):
    """Build certificationmatters.org URL"""
    base_url = "https://www.certificationmatters.org/find-my-doctor/"
    params = {
        'dsearch': '1',
        'lname': doctor['last_name'].lower(),
        'fname': doctor['first_name'].lower(),
        'specialty': 'neurological-surgery'
    }
    # Always omit state from the search URL per updated requirement
    
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"

def extract_results_data(filepath):
    """Extract results count, doctor URLs, reported locations, and specialties from the MD file"""
    if not filepath or not os.path.exists(filepath):
        return None, [], [], []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results_count = None
        doctor_urls = []
        reported_locations = []
        specialties = []
        
        # Find the "Physician Search **Results**" header
        results_header = "## Physician Search **Results**"
        if results_header in content:
            header_index = content.find(results_header)
            
            # Get the text after the header
            after_header = content[header_index + len(results_header):header_index + len(results_header) + 2000]
            
            # Extract results count
            count_match = re.search(r'[_\*]?(\d+)\s+results?\s+were\s+found', after_header, re.IGNORECASE)
            if count_match:
                results_count = int(count_match.group(1))
            
            # If results count is 0, return early
            if results_count == 0:
                return results_count, [], [], []
            
            # Find table rows (markdown table format: | col1 | col2 | col3 | col4 |)
            # Skip header row and separator row (they contain "Doctor Name" or "---")
            lines = after_header.split('\n')
            in_table = False
            for line in lines:
                # Check if this is the table header row
                if '| Doctor Name |' in line or '|---|' in line or '| --- |' in line:
                    in_table = True
                    continue
                
                # Skip if we haven't reached the table yet
                if not in_table:
                    continue
                
                # Check if we've left the table (empty line or different content)
                if not line.strip() or not line.strip().startswith('|'):
                    if in_table and doctor_urls:  # We've processed at least one row
                        break
                    continue
                
                # Parse table row: | [Name](URL) | Location | Specialty | [View Profile](URL) |
                # Extract columns (split by | and trim)
                columns = [col.strip() for col in line.split('|') if col.strip()]
                
                if len(columns) >= 4:
                    # Column 1: Doctor Name with URL [Name](URL)
                    name_col = columns[0]
                    url_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', name_col)
                    if url_match:
                        doctor_urls.append(url_match.group(2))
                    
                    # Column 2: Reported Location
                    location = columns[1].strip()
                    # Remove any trailing explanation text in parentheses or italics
                    location = re.sub(r'\s*_[^_]*_[^_]*_$', '', location)  # Remove trailing italic explanations
                    reported_locations.append(location)
                    
                    # Column 3: Certifications/Specialties (format: "- Specialty Name – Specialty")
                    specialty_text = columns[2].strip()
                    # Remove leading dashes and extract specialty names
                    specialty_text = re.sub(r'^-\s*', '', specialty_text)  # Remove leading dash
                    specialty_text = re.sub(r'\s*–\s*Specialty$', '', specialty_text)  # Remove trailing "– Specialty"
                    specialties.append(specialty_text)
        
        return results_count, doctor_urls, reported_locations, specialties
    except Exception as e:
        print(f"   ⚠️  Error extracting results data from {filepath}: {e}")
        return None, [], [], []

def parse_city_state(location_text: str):
    """
    Parse a reported location like 'New York, NY' into (city, state_code).
    Returns (city, state) or ('','') if parsing fails.
    """
    if not location_text:
        return '', ''
    # Expect format "City, ST" - take first segment if multiple separated by ';'
    first = location_text.split(';')[0].strip()
    if ',' in first:
        city, state = first.split(',', 1)
        return city.strip(), state.strip()
    return first.strip(), ''

def scrape_doctor(firecrawl, doctor, use_state, output_dir):
    """Scrape a single doctor's page"""
    url = build_url(doctor, use_state)
    filename = f"{doctor['npi']}_{doctor['first_name']}_{doctor['last_name']}.md"
    filepath = os.path.join(output_dir, filename)
    
    # Skip if already scraped
    already_exists = os.path.exists(filepath)
    if already_exists:
        return filepath, True, None, [], [], []
    
    try:
        result = firecrawl.scrape(url, formats=['markdown'])
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result.markdown)
        
        # Extract all results data from the scraped file
        results_count, doctor_urls, reported_locations, specialties = extract_results_data(filepath)
        return filepath, True, results_count, doctor_urls, reported_locations, specialties
    except Exception as e:
        print(f"   ❌ Error scraping {doctor['first_name']} {doctor['last_name']}: {e}")
        return None, False, None, [], [], []

def main():
    print("🏥 Starting Certification Matters Scraper...")
    
    # Setup
    script_dir = os.path.dirname(os.path.abspath(__file__))
    firecrawl = Firecrawl(api_key=os.getenv('FIRECRAWL_API_KEY'))
    output_dir = os.path.join(script_dir, 'scraped_pages')
    os.makedirs(output_dir, exist_ok=True)
    
    # Get database connection for certification checks
    db = next(get_db())
    
    # Get all neurosurgeons
    neurosurgeons = get_neurosurgeons()
    print(f"📊 Found {len(neurosurgeons)} neurosurgeons")
    
    # Scrape each doctor
    results = []
    skipped_with_proof = 0
    firecrawl_requests_made = 0
    MAX_FIRECRAWL_REQUESTS = 10
    
    for i, doctor in enumerate(neurosurgeons, 1):
        npi = doctor['npi']
        first_name = doctor['first_name']
        last_name = doctor['last_name']
        
        # Check if we already have certification proof
        has_proof = has_certification_proof(db, npi)
        
        if has_proof:
            print(f"[{i}/{len(neurosurgeons)}] ⏭️  {first_name} {last_name} - Already have certification proof, skipping...")
            skipped_with_proof += 1
            # Still add to results but mark as skipped
            results.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'state': doctor['state'],
                'npi_city': doctor.get('npi_city', ''),
                'results_count': '',
                'doctor_urls': '',
                'reported_location': '',
                'reported_city': '',
                'reported_state': '',
                'state_match': '',
                'city_match': '',
                'specialty': '',
                'md_file': '',
                'search_url': '',
                'skipped_reason': 'Already have certification proof'
            })
            continue
        
        print(f"[{i}/{len(neurosurgeons)}] Scraping {first_name} {last_name}...", end=' ')
        
        # Check if file already exists before making request
        # Build filepath the same way scrape_doctor does
        filename = f"{doctor['npi']}_{doctor['first_name']}_{doctor['last_name']}.md"
        filepath = os.path.join(output_dir, filename)
        file_exists = os.path.exists(filepath)
        
        # Only count as a firecrawl request if we're actually going to make one
        if not file_exists:
            firecrawl_requests_made += 1
            
            # Check if we've reached the firecrawl request limit AFTER incrementing
            if firecrawl_requests_made > MAX_FIRECRAWL_REQUESTS:
                print(f"\n⏹️  Reached limit of {MAX_FIRECRAWL_REQUESTS} firecrawl requests. Stopping...")
                print(f"   Processed {i-1} doctors, {MAX_FIRECRAWL_REQUESTS} firecrawl requests made")
                # Add remaining doctors to CSV with skipped_reason
                for remaining_doctor in neurosurgeons[i-1:]:
                    results.append({
                        'npi': remaining_doctor['npi'],
                        'first_name': remaining_doctor['first_name'],
                        'last_name': remaining_doctor['last_name'],
                        'state': remaining_doctor['state'],
                        'npi_city': remaining_doctor.get('npi_city', ''),
                        'results_count': '',
                        'doctor_urls': '',
                        'reported_location': '',
                        'reported_city': '',
                        'reported_state': '',
                        'state_match': '',
                        'city_match': '',
                        'specialty': '',
                        'md_file': '',
                        'search_url': '',
                        'skipped_reason': 'Not processed - firecrawl request limit reached'
                    })
                break
        
        filepath, success, results_count, doctor_urls, reported_locations, specialties = scrape_doctor(firecrawl, doctor, False, output_dir)
        
        # If file already existed, extract results data now
        if success and filepath and results_count is None:
            results_count, doctor_urls, reported_locations, specialties = extract_results_data(filepath)
        
        if success:
            # Join multiple values with semicolon for CSV (if multiple results found)
            doctor_urls_str = '; '.join(doctor_urls) if doctor_urls else ''
            reported_locations_str = '; '.join(reported_locations) if reported_locations else ''
            specialties_str = '; '.join(specialties) if specialties else ''

            # Derive reported city/state from ALL reported locations (semicolon-separated)
            reported_cities = []
            reported_states = []
            state_matches = []
            city_matches = []
            
            if reported_locations:
                for location in reported_locations:
                    city, state = parse_city_state(location)
                    reported_cities.append(city)
                    reported_states.append(state)
                    
                    # Compute state match (case-insensitive) against NPI provider state code
                    if state and doctor['state']:
                        state_matches.append('TRUE' if state.upper() == doctor['state'].upper() else 'FALSE')
                    else:
                        state_matches.append('')
                    
                    # Compute city match (case-insensitive) against NPI provider city
                    if city and doctor.get('npi_city'):
                        city_matches.append('TRUE' if city.strip().lower() == doctor['npi_city'].strip().lower() else 'FALSE')
                    else:
                        city_matches.append('')
            
            # Join all results with semicolons
            reported_city = '; '.join(reported_cities) if reported_cities else ''
            reported_state = '; '.join(reported_states) if reported_states else ''
            state_match = '; '.join(state_matches) if state_matches else ''
            city_match = '; '.join(city_matches) if city_matches else ''
            
            results.append({
                'npi': doctor['npi'],
                'first_name': doctor['first_name'],
                'last_name': doctor['last_name'],
                'state': doctor['state'],
                'npi_city': doctor.get('npi_city', ''),
                'results_count': results_count if results_count is not None else '',
                'doctor_urls': doctor_urls_str,
                'reported_location': reported_locations_str,
                'reported_city': reported_city,
                'reported_state': reported_state,
                'state_match': state_match,
                'city_match': city_match,
                'specialty': specialties_str,
                'md_file': filepath if filepath else '',
                'search_url': build_url(doctor, False),
                'skipped_reason': ''
            })
            count_text = f" ({results_count} results)" if results_count is not None else ""
            print(f"✅{count_text}")
        else:
            print("❌")
            results.append({
                'npi': doctor['npi'],
                'first_name': doctor['first_name'],
                'last_name': doctor['last_name'],
                'state': doctor['state'],
                'npi_city': doctor.get('npi_city', ''),
                'results_count': '',
                'doctor_urls': '',
                'reported_location': '',
                'reported_city': '',
                'reported_state': '',
                'state_match': '',
                'city_match': '',
                'specialty': '',
                'md_file': '',
                'search_url': build_url(doctor, False),
                'skipped_reason': ''
            })
        
        # Rate limiting
        time.sleep(1)
    
    # Close database connection
    db.close()
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   Total neurosurgeons in DB: {len(neurosurgeons)}")
    print(f"   Processed: {len(results)}")
    print(f"   Skipped (already have proof): {skipped_with_proof}")
    print(f"   Firecrawl requests made: {firecrawl_requests_made}")
    
    # Save CSV mapping
    csv_path = os.path.join(script_dir, 'npi_to_md_mapping.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'npi',
                'first_name',
                'last_name',
                'state',
                'npi_city',
                'results_count',
                'doctor_urls',
                'reported_location',
                'reported_city',
                'reported_state',
                'state_match',
                'city_match',
                'specialty',
                'md_file',
                'search_url',
                'skipped_reason'
            ]
        )
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Complete! Scraped {len([r for r in results if r['md_file']])} pages")
    print(f"📄 MD files saved to: {output_dir}/")
    print(f"📊 CSV mapping saved to: {csv_path}")

if __name__ == "__main__":
    main()
