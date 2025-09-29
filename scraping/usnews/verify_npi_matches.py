#!/usr/bin/env python3
"""Verify that each doctor's NPI matches the correct markdown file"""

import os, sys, csv, re
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app.database import get_db
from sqlalchemy import text

load_dotenv()

def extract_npi_from_markdown(filepath):
    """Extract NPI number from a markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for "Provider NPI:" followed by the NPI number
        npi_match = re.search(r'Provider NPI:\s*\n\s*(\d+)', content)
        if npi_match:
            return npi_match.group(1)
        return None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def main():
    print("🔍 Verifying NPI matches between doctors and markdown files...")
    
    # Get all neurosurgeons from database
    db = next(get_db())
    try:
        result = db.execute(text("""
            SELECT npi, provider_first_name, provider_last_name
            FROM npi_providers 
            WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
        """))
        
        neurosurgeons = [{'npi': r.npi, 'first_name': r.provider_first_name, 'last_name': r.provider_last_name} for r in result]
        print(f"📊 Found {len(neurosurgeons)} neurosurgeons in database")
        
        # Get all markdown files
        markdown_files = []
        for filename in os.listdir('scraped_pages'):
            if filename.endswith('.md'):
                markdown_files.append(filename)
        
        print(f"📄 Found {len(markdown_files)} markdown files")
        
        # Create NPI to filename mapping
        npi_to_file = {}
        for filename in markdown_files:
            filepath = os.path.join('scraped_pages', filename)
            npi = extract_npi_from_markdown(filepath)
            if npi:
                npi_to_file[npi] = filename
        
        print(f"🔗 Found NPI numbers in {len(npi_to_file)} markdown files")
        
        # Match doctors to their files
        results = []
        matched_count = 0
        
        for doctor in neurosurgeons:
            npi = str(doctor['npi'])
            filename = npi_to_file.get(npi, "None exists")
            
            if filename != "None exists":
                matched_count += 1
            
            results.append({
                'npi': npi,
                'first_name': doctor['first_name'],
                'last_name': doctor['last_name'],
                'markdown_file': filename
            })
        
        # Save results to CSV
        output_file = 'npi_verification_results.csv'
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['npi', 'first_name', 'last_name', 'markdown_file']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ Verification complete!")
        print(f"📊 Matched {matched_count}/{len(neurosurgeons)} doctors ({matched_count/len(neurosurgeons):.1%})")
        print(f"📄 Results saved to {output_file}")
        
        # Show some examples
        print(f"\n🔍 Sample matches:")
        for i, result in enumerate(results[:5]):
            status = "✅" if result['markdown_file'] != "None exists" else "❌"
            print(f"  {status} {result['first_name']} {result['last_name']} (NPI: {result['npi']}) -> {result['markdown_file']}")
        
        if matched_count < len(neurosurgeons):
            print(f"\n❌ Sample non-matches:")
            non_matches = [r for r in results if r['markdown_file'] == "None exists"][:5]
            for result in non_matches:
                print(f"  ❌ {result['first_name']} {result['last_name']} (NPI: {result['npi']}) -> {result['markdown_file']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()

