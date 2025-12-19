#!/usr/bin/env python3
"""Simple script to fetch doctor license info from docinfo.org API."""

import json
import csv
import urllib.parse
from pathlib import Path
import time
import re
import sys
import cloudscraper

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.database import get_db
from sqlalchemy import text

def normalize_name(name):
    """Normalize name for comparison - remove punctuation, dashes, apostrophes, whitespace, convert to lowercase."""
    if not name:
        return ""
    # Remove punctuation, dashes, apostrophes, and whitespace, convert to lowercase
    normalized = re.sub(r'[^\w]', '', name.lower())
    return normalized

def names_match(first_name1, last_name1, first_name2, last_name2):
    """Check if two names match (flexible matching for dashes, apostrophes, etc.)."""
    norm_first1 = normalize_name(first_name1)
    norm_last1 = normalize_name(last_name1)
    norm_first2 = normalize_name(first_name2)
    norm_last2 = normalize_name(last_name2)
    
    return norm_first1 == norm_first2 and norm_last1 == norm_last2

def search_doctor(name, scraper):
    """Search for a doctor and return all matching results."""
    encoded_name = urllib.parse.quote(name)
    url = f"https://www.docinfo.org/Search?docname={encoded_name}&pracType=Physician&licstate=all&from=0"
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'referer': f'https://www.docinfo.org/search-results?docname={encoded_name}&pracType=Physician&licstate=all&from=0&size=30',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }
    
    try:
        response = scraper.get(url, headers=headers)
        if response.status_code != 200:
            print(f"  ❌ HTTP error: {response.status_code}")
            return []
        response_data = response.text
        if not response_data:
            print(f"  ⚠️  Empty response from API")
            return []
        data = json.loads(response_data)
        return data.get('hits', [])
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON decode error: {e}")
        print(f"  Response preview: {response_data[:200] if 'response_data' in locals() else 'N/A'}")
    except Exception as e:
        print(f"  ❌ Search error: {e}")
    return []

def get_profile(profile_id, scraper):
    """Get full profile using the _id."""
    url = f"https://www.docinfo.org/GetProfile?id={profile_id}"
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'referer': 'https://www.docinfo.org/',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }
    
    try:
        response = scraper.get(url, headers=headers)
        if response.status_code != 200:
            print(f"  ❌ HTTP error: {response.status_code}")
            return None
        response_data = response.text
        if not response_data:
            return None
        return json.loads(response_data)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON decode error: {e}")
    except Exception as e:
        print(f"  ❌ Profile error: {e}")
    return None

def format_profile_data(profile):
    """Format profile data according to the expected structure."""
    if not profile or '_source' not in profile:
        return None
    
    source = profile.get('_source', {})
    
    return {
        '_id': profile.get('_id', ''),
        'fullName': source.get('fullName', ''),
        'graduationYear': source.get('graduationYear', ''),
        'medicalSchoolName': source.get('medicalSchoolName', ''),
        'degreeCode': source.get('degreeCode', ''),
        'licensures': source.get('licensures', []),
        'certifications': source.get('certifications', []),
        'locations': source.get('locations', []),
        'boardsActionsByState': source.get('boardsActionsByState', [])
    }

def main():
    # Get neurosurgeons from database
    print("📊 Querying neurosurgeons from database...")
    db = next(get_db())
    
    result = db.execute(text("""
        SELECT npi, provider_first_name, provider_last_name
        FROM npi_providers 
        WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
        ORDER BY provider_last_name, provider_first_name
        LIMIT 50
    """)).fetchall()
    
    neurosurgeons = [{
        'npi': r[0],
        'first_name': r[1] or '',
        'last_name': r[2] or ''
    } for r in result]
    
    print(f"✅ Loaded {len(neurosurgeons)} neurosurgeons from database")
    print(f"🔍 Fetching license info...\n")
    
    # Create cloudscraper instance with browser-like settings
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'desktop': True
        },
        delay=10
    )
    
    # Set cookies from browser session (extract from browser dev tools)
    # Format: "cookie1=value1; cookie2=value2; ..."
    cookies_str = "visid_incap_2587692=TEnlKJFzS5q2THK/bqHzdgYdrmgAAAAAQkIPAAAAAACAnqK+AWi8qk5gBqsB8BHPCyslfEhhG/VU; _ga=GA1.1.1849530726.1756241165; incap_ses_230_2587692=Z39PZ9H8t1IXoawkSCAxA/3tLWkAAAAA/VcO8WuW3dERF878Mpn88A==; nlbi_2587692=cWDyPPltyBqPVl0trfoPlAAAAABWjNd/KqAMaOI3WG8Ca+Lc; incap_ses_1362_2587692=adBiBmsPE1SIV19vP8zmEgTuLWkAAAAAWCh6TNh45SkkUsvdtStB1A==; incap_ses_1432_2587692=E0GqXN/JJVCmwIUs13zfE10wM2kAAAAA+GNvBFWgSjgmNaHceU++LA==; reese84=3:eUr3+lZVa7zr77i/eT/Vjw==:eRGmup3M/qDvz9MrmQegfV/VHIZhK7jiqrGmSrNxGn+E9eP1/VqiUqolLSw8624eu7khnCa5qgGKEEbthdAxRAgETRf80idkSlF0ajLQ4ATBd4nIsq4FqX4j7ALWkDWAEwDYwdzkjyIei2iqbdbupnIXI5g3+7Nn2BcBf2CW90jv7alcEkLSvkF7jNUKGMCm0H09h5y9lM+hKWReXpAODBecCh7ryp+DdvIYZ8LuMPNl99K5kGa/usX9TwL5oAl3YCJql/ZcvSVW4y3yrQnWiv+SxN7mkwBbTwxvAIkweIWyAKuxZfRU5/opby4zXOelzseMXqcdh7AUh+mH4PhDp9nztw7GFVap8X544ImoxDLGX3sK8cl5wc1Sa+onmgBl7H/hw9HRzUbucgoCmdHvCAbEvzIYScuDiKy/P3q9BaP7rd8hF5CvABRSAPvDjZk3H9lzb8tQIINAn8jV8szRYgPHCTb02P/gfVNp6gNAuUY=:68wrqi9Bhls4agVaRDz6HRwPV8YBSIPCdZoWqnfKFlw=; _ga_XQZXCXD37X=GS2.1.s1764962476$o6$g1$t1764965825$j60$l0$h0; nlbi_2587692_2147483392=Ez28bM2wXlrQPrDorfoPlAAAAAD3p7ofno4/J3d+uepgia7+"
    
    # Parse cookies and add to scraper
    if cookies_str:
        cookies_dict = {}
        for cookie in cookies_str.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies_dict[key] = value
        scraper.cookies.update(cookies_dict)
        print("🍪 Cookies loaded\n")
    
    # Visit main page first to establish session and bypass bot protection
    print("🌐 Establishing session with docinfo.org...")
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }
    try:
        scraper.get("https://www.docinfo.org/", headers=headers)
        print("✅ Session established\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not establish session: {e}\n")
    
    output_file = Path(__file__).parent / 'license_info_results.json'
    results = []
    
    for i, doctor in enumerate(neurosurgeons, 1):
        first_name = doctor['first_name'].strip()
        last_name = doctor['last_name'].strip()
        npi = str(doctor['npi']).strip()
        full_name = f"{first_name} {last_name}".strip()
        
        print(f"[{i}/{len(neurosurgeons)}] {full_name} (NPI: {npi})...")
        
        # Search for doctor
        hits = search_doctor(full_name, scraper)
        if not hits:
            print(f"  ⚠️  No search results found")
            results.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'matches': [],
                'error': 'No search results'
            })
            continue
        
        print(f"  📋 Found {len(hits)} search results, checking for name matches...")
        
        # Filter results that match both first and last name
        matching_profiles = []
        for hit in hits:
            hit_name = hit.get('_source', {}).get('fullName', '')
            # Parse the full name - assume format is "First Last" or "First Middle Last"
            name_parts = hit_name.split()
            if len(name_parts) >= 2:
                hit_first = name_parts[0]
                hit_last = name_parts[-1]  # Last part is always the last name
                
                if names_match(first_name, last_name, hit_first, hit_last):
                    profile_id = hit.get('_id')
                    print(f"    ✅ Match found: {hit_name} (ID: {profile_id})")
                    
                    # Get profile
                    profile_raw = get_profile(profile_id, scraper)
                    if profile_raw:
                        profile_formatted = format_profile_data(profile_raw)
                        if profile_formatted:
                            matching_profiles.append(profile_formatted)
                        else:
                            print(f"    ⚠️  Profile data missing required fields")
                            matching_profiles.append({
                                'profile_id': profile_id,
                                'docinfo_name': hit_name,
                                'profile': profile_raw,
                                'error': 'Profile data missing required fields'
                            })
                    else:
                        print(f"    ❌ Failed to get profile for {profile_id}")
                        matching_profiles.append({
                            'profile_id': profile_id,
                            'docinfo_name': hit_name,
                            'error': 'Failed to retrieve profile'
                        })
        
        if matching_profiles:
            print(f"  ✅ Found {len(matching_profiles)} matching profile(s)")
            results.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'matches': matching_profiles,
                'error': None
            })
        else:
            print(f"  ⚠️  No matching profiles found")
            results.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'matches': [],
                'error': 'No name matches found in search results'
            })
        
        # Be nice to the API - small delay between requests
        time.sleep(0.5)
    
    # Save results to CSV
    csv_file = Path(__file__).parent / 'license_info_results.csv'
    print(f"\n💾 Saving results to: {csv_file}")
    
    # Flatten results for CSV - one row per match
    csv_rows = []
    for result in results:
        npi = result['npi']
        first_name = result['first_name']
        last_name = result['last_name']
        full_name = result['full_name']
        
        if result.get('matches'):
            for match in result['matches']:
                # Format locations as semicolon-separated string
                locations_list = match.get('locations', [])
                if isinstance(locations_list, list):
                    locations_str = '; '.join([f"{loc.get('city', '')}, {loc.get('state', '')}" for loc in locations_list])
                else:
                    locations_str = ''
                
                # Format licensures as semicolon-separated string
                licensures_list = match.get('licensures', [])
                licensures_str = '; '.join(licensures_list) if isinstance(licensures_list, list) else ''
                
                # Format certifications as semicolon-separated string
                certs_list = match.get('certifications', [])
                certifications_str = '; '.join(certs_list) if isinstance(certs_list, list) else ''
                
                # Format board actions
                board_actions = []
                boards_actions_list = match.get('boardsActionsByState', [])
                if isinstance(boards_actions_list, list):
                    for state_action in boards_actions_list:
                        state = state_action.get('state', '')
                        orders = state_action.get('orders', [])
                        if isinstance(orders, list):
                            for order in orders:
                                order_date = order.get('orderDate', '')
                                action = order.get('action', '')
                                board_actions.append(f"{state}: {order_date} - {action}")
                board_actions_str = '; '.join(board_actions) if board_actions else ''
                
                csv_rows.append({
                    'npi': npi,
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': full_name,
                    'docinfo_id': match.get('_id', ''),
                    'docinfo_full_name': match.get('fullName', ''),
                    'graduation_year': match.get('graduationYear', ''),
                    'medical_school_name': match.get('medicalSchoolName', ''),
                    'degree_code': match.get('degreeCode', ''),
                    'licensures': licensures_str,
                    'certifications': certifications_str,
                    'locations': locations_str,
                    'board_actions': board_actions_str
                })
        else:
            # No matches - still create a row
            csv_rows.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'docinfo_id': '',
                'docinfo_full_name': '',
                'graduation_year': '',
                'medical_school_name': '',
                'degree_code': '',
                'licensures': '',
                'certifications': '',
                'locations': '',
                'board_actions': result.get('error', '')
            })
    
    # Write to CSV
    fieldnames = ['npi', 'first_name', 'last_name', 'full_name', 'docinfo_id', 'docinfo_full_name', 
                  'graduation_year', 'medical_school_name', 'degree_code', 'licensures', 
                  'certifications', 'locations', 'board_actions']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    
    # Also save JSON backup
    json_file = Path(__file__).parent / 'license_info_results.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    total_matches = sum(len(r['matches']) for r in results if r['matches'])
    doctors_with_matches = sum(1 for r in results if r['matches'])
    print(f"\n📊 Summary:")
    print(f"   Total doctors: {len(results)}")
    print(f"   Doctors with matches: {doctors_with_matches}")
    print(f"   Total profile matches: {total_matches}")
    print(f"   Doctors without matches: {len(results) - doctors_with_matches}")
    print(f"   Total CSV rows: {len(csv_rows)}")

if __name__ == '__main__':
    main()

