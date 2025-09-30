#!/usr/bin/env python3
"""Map neurosurgeons to Healthgrades URLs using Firecrawl with optimized parallel processing"""

import os, sys, csv, re, time, json
from firecrawl import Firecrawl
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.database import get_db
from sqlalchemy import text

load_dotenv()

CHECKPOINT_FILE = 'mapping/healthgrades_doctor_mapping_checkpoint.jsonl'

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        for doctor_id, urls in data.items():
            f.write(json.dumps({doctor_id: urls}) + '\n')

def load_checkpoint():
    data = {}
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line.strip())
                    data.update(entry)
    return data

def map_doctor(firecrawl_client, doctor):
    """Map a specific doctor by full name"""
    first_name = doctor['first_name'].lower().strip()
    last_name = doctor['last_name'].lower().strip()
    
    # Clean names for URL - replace spaces and special chars with hyphens
    first_name_clean = re.sub(r'[^a-z0-9]+', '-', first_name).strip('-')
    last_name_clean = re.sub(r'[^a-z0-9]+', '-', last_name).strip('-')
    
    full_name = f"{first_name_clean}-{last_name_clean}"
    npi = doctor['npi']
    doctor_id = f"{npi}_{first_name}_{last_name}"
    
    urls = []
    print(f"   🔍 Searching for: {first_name} {last_name} -> dr-{full_name}")
    try:
        result = firecrawl_client.map(url=f"https://www.healthgrades.com/physician/dr-{full_name}", limit=100000)
        urls = [link.url for link in getattr(result, 'links', [])]
    except Exception as e:
        msg = str(e)
        # Basic retry for rate limits
        if "Rate limit" in msg or "Rate Limit" in msg:
            print(f"   ⏳ Rate limited for {first_name} {last_name} -> {full_name} (NPI: {npi}). Retrying in 30s...")
            time.sleep(30)
            try:
                result = firecrawl_client.map(url=f"https://www.healthgrades.com/physician/dr-{full_name}", limit=100000)
                urls = [link.url for link in getattr(result, 'links', [])]
            except Exception as e2:
                print(f"   ❌ Retry failed for {first_name} {last_name} -> {full_name} (NPI: {npi}): {e2}")
        else:
            print(f"   ❌ Error mapping {first_name} {last_name} -> {full_name} (NPI: {npi}): {e}")
    return doctor_id, urls

def main():
    print("🏥 Starting Direct Doctor URL Mapping...")
    
    firecrawl = Firecrawl(api_key=os.getenv('FIRECRAWL_API_KEY'))
    db = next(get_db())
    
    try:
        # Get neurosurgeons
        result = db.execute(text("""
            SELECT npi, provider_first_name, provider_last_name
            FROM npi_providers 
            WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
        """))
        
        neurosurgeons = [{'npi': r.npi, 'first_name': r.provider_first_name, 'last_name': r.provider_last_name} for r in result]
        
        print(f"Found {len(neurosurgeons)} neurosurgeons to process")
        
        # Load existing mapped URLs from checkpoint
        doctor_urls = load_checkpoint()
        processed_doctors = set(doctor_urls.keys())
        
        # Create doctor IDs for comparison
        doctor_ids = [f"{d['npi']}_{d['first_name'].lower()}_{d['last_name'].lower()}" for d in neurosurgeons]
        remaining_doctors = [d for d in neurosurgeons if f"{d['npi']}_{d['first_name'].lower()}_{d['last_name'].lower()}" not in processed_doctors]
        
        print(f"Already processed: {len(processed_doctors)} doctors")
        print(f"Remaining: {len(remaining_doctors)} doctors")
        
        # Process remaining doctors in parallel
        if remaining_doctors:
            print(f"🚀 Processing {len(remaining_doctors)} doctors in parallel...")
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = {executor.submit(map_doctor, firecrawl, doctor): doctor for doctor in remaining_doctors}
                
                for i, future in enumerate(as_completed(futures), 1):
                    doctor_id, urls = future.result()
                    doctor_urls[doctor_id] = urls
                    print(f"   ✅ {doctor_id}: {len(urls)} urls ({i}/{len(remaining_doctors)})")
                    
                    # Save checkpoint periodically
                    if i % 10 == 0:
                        save_checkpoint(doctor_urls)
                        print(f"   💾 Checkpoint saved after {len(doctor_urls)} doctors.")
            save_checkpoint(doctor_urls)
            print(f"   💾 Final checkpoint saved after {len(doctor_urls)} doctors.")
        else:
            print("All doctors already processed in mapping phase.")

        # Show the mapping results
        print("🔗 Mapping Results:")
        total_urls = 0
        for doctor_id, urls in doctor_urls.items():
            npi, first_name, last_name = doctor_id.split('_', 2)
            print(f"   {first_name.title()} {last_name.title()} (NPI: {npi}): {len(urls)} URLs")
            total_urls += len(urls)
            for url in urls[:3]:  # Show first 3 URLs as examples
                print(f"      - {url}")
            if len(urls) > 3:
                print(f"      ... and {len(urls) - 3} more")
        
        print(f"📊 Total URLs found: {total_urls}")
        print("✅ Mapping phase complete!")
        
        # Create matches for scraping
        print("🔗 Creating doctor matches for scraping...")
        matches = []
        match_id = 1
        
        for doctor in neurosurgeons:
            doctor_id = f"{doctor['npi']}_{doctor['first_name'].lower()}_{doctor['last_name'].lower()}"
            urls = doctor_urls.get(doctor_id, [])
            
            if urls:
                # Filter for valid doctor URLs - must have unique identifier after name
                # Valid: /physician/dr-name-xxxxx (where xxxxx is letters/numbers)
                # Invalid: /physician/dr-name (no identifier)
                doctor_urls_filtered = []
                for url in urls:
                    if '/sitemap.xml' not in url and '/physician/dr-' in url:
                        # Check if URL has identifier after the name (pattern: dr-name-xxxxx)
                        # Must have at least one hyphen in the name, then another hyphen, then identifier
                        # Pattern: /physician/dr-firstname-lastname-identifier
                        if re.search(r'/physician/dr-[a-z]+-[a-z]+-[a-z0-9]+/?$', url):
                            doctor_urls_filtered.append(url)
                            print(f"      ✅ Valid: {url}")
                        else:
                            print(f"      ❌ Invalid: {url}")
                
                for url in doctor_urls_filtered:
                    matches.append({
                        'match_id': f"hg_{match_id:06d}",
                        'npi': doctor['npi'],
                        'first_name': doctor['first_name'],
                        'last_name': doctor['last_name'],
                        'url': url
                    })
                    match_id += 1
            else:
                # Add a "Not found" entry for doctors with no URLs
                matches.append({
                    'match_id': f"hg_{match_id:06d}",
                    'npi': doctor['npi'],
                    'first_name': doctor['first_name'],
                    'last_name': doctor['last_name'],
                    'url': "Not found"
                })
                match_id += 1
        
        print(f"📊 Created {len(matches)} matches for {len(neurosurgeons)} doctors")
        
        # Save matches to CSV
        csv_file = 'mapping/healthgrades_neurosurgeon_all_matches.csv'
        os.makedirs('mapping', exist_ok=True)
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['match_id', 'npi', 'first_name', 'last_name', 'url']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matches)
        print(f"💾 Matches saved to {csv_file}")
        
        # Scrape markdown for found URLs in parallel
        found_count = len([m for m in matches if m['url'] != "Not found"])
        if found_count > 0:
            print(f"🔍 Scraping {found_count} doctor pages in parallel...")
            os.makedirs('scraped_pages_healthgrades', exist_ok=True)
            
            def scrape_doctor(doctor):
                # Use match_id for unique filenames when there are multiple matches
                filename = f"scraped_pages_healthgrades/{doctor['match_id']}_{doctor['first_name']}_{doctor['last_name']}.md"
                
                # Skip if already scraped
                if os.path.exists(filename):
                    return f"⏭️  {doctor['first_name']} {doctor['last_name']} -> Already exists"
                
                try:
                    result = firecrawl.scrape(doctor['url'], formats=['markdown'])
                    
                    # Save markdown file
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(result.markdown)
                    
                    return f"✅ {doctor['first_name']} {doctor['last_name']} -> {filename}"
                except Exception as e:
                    return f"❌ Failed {doctor['first_name']} {doctor['last_name']}: {e}"
            
            # Scrape in parallel with 10 workers
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(scrape_doctor, doctor): doctor for doctor in [r for r in matches if r['url'] != "Not found"]}
                
                scraped_count = 0
                for i, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    print(f"   {result} ({i}/{found_count})")
                    if "✅" in result:
                        scraped_count += 1
            
            print(f"📄 Scraped {scraped_count}/{found_count} pages to scraped_pages_healthgrades/ folder")
        else:
            print("❌ No valid URLs found for scraping")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()