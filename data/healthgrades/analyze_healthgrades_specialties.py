#!/usr/bin/env python3
"""Analyze specialties and subspecialties from Healthgrades scraped markdown files"""

import os
import re
import csv
from collections import defaultdict, Counter

def extract_specialties_from_healthgrades_markdown(filepath):
    """Extract specialties and subspecialties from a Healthgrades markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Look for "### Specialties*" section (Healthgrades format)
        in_specialties = False
        specialties = []
        subspecialties = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Start of specialties section (Healthgrades format)
            if line == "### Specialties*" or line == "### Specialties\\*":
                in_specialties = True
                continue
            
            # End of specialties section (next major section)
            if in_specialties and line.startswith("### ") and line not in ["### Specialties*", "### Specialties\\*"]:
                break
            
            if in_specialties:
                # Look for specialty items (bulleted list format: "- Specialty Name")
                if line.startswith("- "):
                    specialty = line.replace("- ", "").strip()
                    if specialty and not specialty.startswith("*Healthgrades"):
                        specialties.append(specialty)
        
        return specialties, subspecialties
        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return [], []

def main():
    print("🔍 Analyzing specialties and subspecialties from Healthgrades scraped markdown files...")
    
    # Get all markdown files from scraped_pages_healthgrades directory
    scraped_pages_dir = 'scraped_pages_healthgrades'
    if not os.path.exists(scraped_pages_dir):
        print(f"❌ Directory {scraped_pages_dir} not found")
        return
    
    markdown_files = [f for f in os.listdir(scraped_pages_dir) if f.endswith('.md')]
    print(f"📄 Found {len(markdown_files)} Healthgrades markdown files to analyze")
    
    # Counters for analysis
    specialty_counter = Counter()
    subspecialty_counter = Counter()
    doctor_specialties = []
    
    # Process each file
    processed_count = 0
    for filename in markdown_files:
        filepath = os.path.join(scraped_pages_dir, filename)
        specialties, subspecialties = extract_specialties_from_healthgrades_markdown(filepath)
        
        if specialties or subspecialties:
            processed_count += 1
            
            # Extract doctor info from filename
            # Format: hg_000001_FIRSTNAME_LASTNAME.md
            name_part = filename.replace('.md', '')
            parts = name_part.split('_')
            
            if len(parts) >= 3:
                match_id = parts[0] + "_" + parts[1]  # hg_000001
                doctor_name = f"{parts[2]} {parts[3]}" if len(parts) > 3 else parts[2]
            else:
                match_id = "unknown"
                doctor_name = name_part
            
            # Count specialties and subspecialties
            for specialty in specialties:
                specialty_counter[specialty] += 1
            
            for subspecialty in subspecialties:
                subspecialty_counter[subspecialty] += 1
            
            # Store doctor's specialties
            doctor_specialties.append({
                'filename': filename,
                'match_id': match_id,
                'doctor_name': doctor_name,
                'specialties': ', '.join(specialties),
                'subspecialties': ', '.join(subspecialties),
                'specialty_count': len(specialties),
                'subspecialty_count': len(subspecialties)
            })
    
    print(f"✅ Processed {processed_count} files with specialty information")
    
    # Print summary statistics
    print(f"\n📊 SUMMARY STATISTICS:")
    print(f"   Total files analyzed: {len(markdown_files)}")
    print(f"   Files with specialties: {processed_count}")
    print(f"   Unique specialties found: {len(specialty_counter)}")
    print(f"   Unique subspecialties found: {len(subspecialty_counter)}")
    
    # Print top specialties
    print(f"\n🏥 TOP 10 SPECIALTIES:")
    for i, (specialty, count) in enumerate(specialty_counter.most_common(10), 1):
        print(f"   {i:2d}. {specialty}: {count} doctors")
    
    # Print top subspecialties
    print(f"\n🔬 TOP 10 SUBSPECIALTIES:")
    for i, (subspecialty, count) in enumerate(subspecialty_counter.most_common(10), 1):
        print(f"   {i:2d}. {subspecialty}: {count} doctors")
    
    # Save detailed results to CSV
    csv_file = 'healthgrades_specialty_analysis_results.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['filename', 'match_id', 'doctor_name', 'specialties', 'subspecialties', 'specialty_count', 'subspecialty_count']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(doctor_specialties)
    
    print(f"\n💾 Detailed results saved to {csv_file}")
    
    # Save specialty counts to CSV
    specialty_csv = 'healthgrades_specialty_counts.csv'
    with open(specialty_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['specialty', 'count'])
        for specialty, count in specialty_counter.most_common():
            writer.writerow([specialty, count])
    
    print(f"💾 Specialty counts saved to {specialty_csv}")
    
    # Save subspecialty counts to CSV
    subspecialty_csv = 'healthgrades_subspecialty_counts.csv'
    with open(subspecialty_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['subspecialty', 'count'])
        for subspecialty, count in subspecialty_counter.most_common():
            writer.writerow([subspecialty, count])
    
    print(f"💾 Subspecialty counts saved to {subspecialty_csv}")

if __name__ == "__main__":
    main()
