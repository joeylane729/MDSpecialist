#!/usr/bin/env python3
"""Map neurosurgeons to US News URLs using Firecrawl with optimized parallel processing"""

import os, sys, csv, re, time, json
from firecrawl import Firecrawl
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.database import get_db
from sqlalchemy import text

load_dotenv()

CHECKPOINT_FILE = 'mapping/mapping_checkpoint.jsonl'

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        for name, urls in data.items():
            f.write(json.dumps({name: urls}) + '\n')

def load_checkpoint():
    data = {}
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line.strip())
                    data.update(entry)
    return data

def map_name(firecrawl_client, name, name_type="first"):
    urls = []
    try:
        result = firecrawl_client.map(url=f"https://health.usnews.com/doctors/{name}", limit=50)
        urls = [link.url for link in getattr(result, 'links', [])]
    except Exception as e:
        msg = str(e)
        # Basic retry for rate limits
        if "Rate limit" in msg or "Rate Limit" in msg:
            print(f"   ⏳ Rate limited for {name} ({name_type}). Retrying in 30s...")
            time.sleep(30)
            try:
                result = firecrawl_client.map(url=f"https://health.usnews.com/doctors/{name}", limit=50)
                urls = [link.url for link in getattr(result, 'links', [])]
            except Exception as e2:
                print(f"   ❌ Retry failed for {name} ({name_type}): {e2}")
        else:
            print(f"   ❌ Error mapping {name} ({name_type}): {e}")
    return name, urls

def main():
    print("🏥 Starting Optimized Neurosurgeon URL Mapping...")
    
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
        all_first_names = sorted(list(set(d['first_name'].lower() for d in neurosurgeons if d['first_name'])))
        
        print(f"Found {len(neurosurgeons)} neurosurgeons, {len(all_first_names)} unique first names")
        
        # Load existing mapped URLs from checkpoint
        first_name_urls = load_checkpoint()
        processed_names = set(first_name_urls.keys())
        
        remaining_names = [name for name in all_first_names if name not in processed_names]
        
        print(f"Already processed: {len(processed_names)} names")
        print(f"Remaining: {len(remaining_names)} names")
        
        # Process remaining first names in parallel
        if remaining_names:
            print(f"🚀 Processing {len(remaining_names)} first names in parallel...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(map_name, firecrawl, name, "first"): name for name in remaining_names}
                
                for i, future in enumerate(as_completed(futures), 1):
                    name, urls = future.result()
                    first_name_urls[name] = urls
                    print(f"   ✅ {name}: {len(urls)} urls ({i}/{len(remaining_names)})")
                    
                    # Save checkpoint periodically
                    if i % 50 == 0:
                        save_checkpoint(first_name_urls)
                        print(f"   💾 Checkpoint saved after {len(first_name_urls)} names.")
            save_checkpoint(first_name_urls)
            print(f"   💾 Final checkpoint saved after {len(first_name_urls)} names.")
        else:
            print("All unique first names already processed in mapping phase.")

        print("🔗 Loading ALL matches from CSV...")
        results = []
        with open('mapping/neurosurgeon_all_matches.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
        
        print(f"📊 Loaded {len(results)} total matches from CSV")
        print(f"📊 Found {len(results)} matches for {len(set(r['npi'] for r in results))} unique doctors")
        
        # Skip the matching logic since we already have the results
        
        found_count = len(results)
        print(f"✅ Complete! Found {found_count} total matches for {len(set(r['npi'] for r in results))} unique doctors")
        
        # Scrape markdown for found URLs in parallel
        if found_count > 0:
            print(f"🔍 Scraping {found_count} doctor pages in parallel...")
            os.makedirs('scraped_pages', exist_ok=True)
            
            def scrape_doctor(doctor):
                # Use match_id for unique filenames when there are multiple matches
                if 'match_id' in doctor:
                    filename = f"scraped_pages/{doctor['match_id']}_{doctor['first_name']}_{doctor['last_name']}.md"
                else:
                    filename = f"scraped_pages/{doctor['npi']}_{doctor['first_name']}_{doctor['last_name']}.md"
                
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
                futures = {executor.submit(scrape_doctor, doctor): doctor for doctor in [r for r in results if r['url'] != "Not found"]}
                
                scraped_count = 0
                for i, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    print(f"   {result} ({i}/{found_count})")
                    if "✅" in result:
                        scraped_count += 1
            
            print(f"📄 Scraped {scraped_count}/{found_count} pages to scraped_pages/ folder")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
