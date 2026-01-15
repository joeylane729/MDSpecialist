#!/usr/bin/env python3
"""Verify neurosurgeons and neurologists from Healthgrades scraped markdown files with intelligent file matching"""

import os
import re
import csv
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import from backend
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / 'backend' / '.env')

# Import from backend directly
from backend.app.database import get_db
from backend.app.models.npi_provider import NPIProvider
from sqlalchemy.orm import Session
from sqlalchemy import text

def extract_specialties_from_markdown(filepath):
    """Extract specialties from a Healthgrades markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Look for "### Specialties*" section (Healthgrades format)
        in_specialties = False
        specialties = []
        
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
        
        return specialties
        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def extract_education_from_markdown(filepath):
    """Extract education information from a Healthgrades markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Look for "### Education" section
        in_education = False
        education_items = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Start of education section
            if line == "### Education":
                in_education = True
                continue
            
            # End of education section (next major section)
            if in_education and line.startswith("### ") and line != "### Education":
                break
            
            if in_education:
                # Look for education items (bulleted list format: "- Institution Name")
                if line.startswith("- "):
                    education_item = line.replace("- ", "").strip()
                    if education_item:
                        education_items.append(education_item)
                # Also capture non-bulleted lines that are part of education
                elif line and not line.startswith("### ") and in_education:
                    education_items.append(line)
        
        return education_items
        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def parse_education_into_categories(education_items):
    """Parse education items into medical school, residency, and fellowship categories"""
    medical_schools = []
    residencies = []
    fellowships = []
    
    # Join all education items and split by pipe separator
    education_text = ' | '.join(education_items)
    
    # Split by pipe to get institution-type pairs
    entries = [entry.strip() for entry in education_text.split('|')]
    
    # Process pairs of entries (institution, type)
    for i in range(0, len(entries), 2):
        if i + 1 < len(entries):
            institution = entries[i].strip()
            type_info = entries[i + 1].strip()
            
            # Parse the type information
            if 'Medical School' in type_info:
                medical_schools.append(f"{institution} ({type_info})")
            elif 'Residency' in type_info:
                residencies.append(f"{institution} ({type_info})")
            elif 'Fellowship' in type_info:
                fellowships.append(f"{institution} ({type_info})")
    
    return medical_schools, residencies, fellowships

def extract_certifications_from_markdown(filepath):
    """Extract board certifications from a Healthgrades markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Look for "### Board Certifications" section
        in_certifications = False
        certifications = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Start of certifications section
            if line == "### Board Certifications":
                in_certifications = True
                continue
            
            # End of certifications section (next major section)
            if in_certifications and line.startswith("### ") and line != "### Board Certifications":
                break
            
            if in_certifications:
                # Look for certification items
                if line and not line.startswith("### ") and not line.startswith("-") and line != "":
                    # Skip the "Learn more about board certification" line
                    if "Learn more about board certification" not in line:
                        certifications.append(line)
        
        return certifications
        
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def search_in_markdown(filepath, search_terms):
    """Search for terms in a markdown file, ignoring irrelevant content sections"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the '## Affiliated Hospitals' section and truncate content after it
        affiliated_hospitals_index = content.find('## Affiliated Hospitals')
        if affiliated_hospitals_index != -1:
            content = content[:affiliated_hospitals_index]
        else:
            # If no Affiliated Hospitals section, try other fallback filters
            # Look for "Compare Dr. ____ with ___ from" pattern
            compare_pattern = re.search(r'Compare Dr\. [^"]+ with [^"]+ from', content)
            if compare_pattern:
                content = content[:compare_pattern.start()]
            else:
                # If no compare pattern, look for "You May Also Like" section
                you_may_also_like_index = content.find('## You May Also Like')
                if you_may_also_like_index != -1:
                    content = content[:you_may_also_like_index]
        
        content = content.lower()
        
        matches = []
        for term in search_terms:
            if term and term.strip():
                if term.lower() in content:
                    matches.append(term)
        
        return matches
    except Exception as e:
        print(f'Error reading {filepath}: {e}')
        return []

def files_are_identical(file1_path, file2_path):
    """Check if two files are identical using diff"""
    try:
        result = subprocess.run(['diff', file1_path, file2_path], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f'Error comparing files {file1_path} and {file2_path}: {e}')
        return False

def find_best_matching_file(doctor, matching_files, scraped_pages_dir):
    """Find the best matching file using city/phone matching with duplicate detection"""
    npi = doctor['npi']
    first_name = doctor['first_name']
    last_name = doctor['last_name']
    practice_city = doctor.get('practice_city', '')
    practice_phone = doctor.get('practice_phone', '')
    
    # If there's exactly 1 file, return it immediately
    if len(matching_files) == 1:
        return matching_files[0], 'single_file', 'Single file found - no matching needed'
    
    # Prepare search terms
    city_terms = [practice_city] if practice_city else []
    phone_terms = [practice_phone] if practice_phone else []
    
    # Try city matching first
    city_matches = []
    if city_terms:
        for filename in matching_files:
            filepath = scraped_pages_dir / filename if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / filename
            if filepath.exists():
                matches = search_in_markdown(str(filepath), city_terms)
                if matches:
                    city_matches.append(filename)
    
    if len(city_matches) == 1:
        # Perfect city match
        return city_matches[0], 'city', 'Single city match found'
    
    # Check if multiple city matches are duplicates
    if len(city_matches) == 2:
        file1_path = scraped_pages_dir / city_matches[0] if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / city_matches[0]
        file2_path = scraped_pages_dir / city_matches[1] if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / city_matches[1]
        
        if files_are_identical(str(file1_path), str(file2_path)):
            # Files are identical, return either one
            return city_matches[0], 'city_duplicate', 'Multiple city matches but files are identical - using first match'
    
    # Try phone matching as fallback
    phone_matches = []
    if phone_terms and len(city_matches) != 1:
        for filename in matching_files:
            filepath = scraped_pages_dir / filename if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / filename
            if filepath.exists():
                matches = search_in_markdown(str(filepath), phone_terms)
                if matches:
                    phone_matches.append(filename)
    
    if len(phone_matches) == 1:
        # Perfect phone match
        return phone_matches[0], 'phone', 'Single phone match found'
    
    # Check if multiple phone matches are duplicates
    if len(phone_matches) == 2:
        file1_path = scraped_pages_dir / phone_matches[0] if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / phone_matches[0]
        file2_path = scraped_pages_dir / phone_matches[1] if isinstance(scraped_pages_dir, Path) else Path(scraped_pages_dir) / phone_matches[1]
        
        if files_are_identical(str(file1_path), str(file2_path)):
            # Files are identical, return either one
            return phone_matches[0], 'phone_duplicate', 'Multiple phone matches but files are identical - using first match'
    
    # No single match found - return None to indicate no clear match
    return None, 'none', f'No single match found (city: {len(city_matches)}, phone: {len(phone_matches)})'

def is_neuro_specialist(specialties):
    """Check if the doctor is a neurosurgeon or neurologist"""
    specialties_lower = [s.lower() for s in specialties]
    
    # Check for neurosurgery OR neurological (for cases like 'Neurological Spine Surgery')
    has_neurosurgery = any('neurosurgery' in s or 'neurological' in s for s in specialties_lower)
    
    # Check for neurology (but not neurosurgery or neurological)
    has_neurology = any('neurology' in s for s in specialties_lower)
    # Exclude if it's neurological surgery (that's neurosurgery, not neurology)
    has_neurosurgery_in_neurology = any(
        ('neurosurgery' in s or 'neurological' in s) 
        for s in specialties_lower 
        if 'neurology' in s
    )
    
    # Is neurosurgeon if has neurosurgery or neurological surgery
    is_neurosurgeon = has_neurosurgery
    
    # Is neurologist if has neurology but not neurosurgery/neurological
    is_neurologist = has_neurology and not has_neurosurgery_in_neurology
    
    return is_neurosurgeon or is_neurologist

def main():
    print("🔍 Verifying neurosurgeons and neurologists from Healthgrades scraped markdown files with intelligent file matching...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Query neurosurgeons from the database with location information for matching
        result = db.execute(text("""
            SELECT npi, provider_first_name, provider_last_name,
                   provider_business_practice_location_address_city_name,
                   provider_business_practice_location_address_telephone_number
            FROM npi_providers 
            WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
        """)).fetchall()
        
        print(f"📊 Found {len(result)} doctors in database")
        
        # Create list of doctors with their info including location data
        doctors = []
        for r in result:
            doctors.append({
                'npi': r[0],  # npi
                'first_name': r[1],  # provider_first_name
                'last_name': r[2],  # provider_last_name
                'practice_city': r[3] if r[3] else '',  # city
                'practice_phone': r[4] if r[4] else ''  # phone
            })
        
        print(f"🔍 Processing {len(doctors)} doctors...")
        
        # Process each doctor
        all_results = []
        processed_count = 0
        neuro_specialists_count = 0
        matching_stats = {
            'single_file': 0,
            'city_matches': 0,
            'city_duplicates': 0,
            'phone_matches': 0,
            'phone_duplicates': 0,
            'no_matches': 0,
            'no_files': 0
        }
        
        for doctor in doctors:
            npi = doctor['npi']
            first_name = doctor['first_name']
            last_name = doctor['last_name']
            
            print(f"🔍 Processing {first_name} {last_name} (NPI: {npi})")
            
            # Look for matching markdown files
            # Use absolute path based on script location
            script_dir = Path(__file__).parent.resolve()
            scraped_pages_dir = script_dir / 'scraped_pages_healthgrades'
            matching_files = []
            
            if scraped_pages_dir.exists():
                for filename in os.listdir(scraped_pages_dir):
                    if filename.endswith('.md'):
                        # Check if this file matches the doctor
                        # Format: hg_XXXXXX_FIRSTNAME_LASTNAME.md
                        if f"_{first_name.upper()}_{last_name.upper()}.md" in filename:
                            matching_files.append(filename)
            
            if matching_files:
                # Filter files to only include those with neuro specialties
                neuro_files = []
                for filename in matching_files:
                    filepath = scraped_pages_dir / filename
                    specialties = extract_specialties_from_markdown(str(filepath))
                    if is_neuro_specialist(specialties):
                        neuro_files.append(filename)
                
                if neuro_files:
                    # Use intelligent file matching to find the best file
                    best_file, match_method, match_notes = find_best_matching_file(doctor, neuro_files, scraped_pages_dir)
                    
                    if best_file:
                        # Found a single best match
                        processed_count += 1
                        neuro_specialists_count += 1
                        
                        # Extract data from the best matching file
                        filepath = scraped_pages_dir / best_file
                        specialties = extract_specialties_from_markdown(str(filepath))
                        education_items = extract_education_from_markdown(str(filepath))
                        medical_schools, residencies, fellowships = parse_education_into_categories(education_items)
                        certifications = extract_certifications_from_markdown(str(filepath))
                        
                        # Update matching statistics
                        if match_method == 'single_file':
                            matching_stats['single_file'] += 1
                        elif match_method == 'city':
                            matching_stats['city_matches'] += 1
                        elif match_method == 'city_duplicate':
                            matching_stats['city_duplicates'] += 1
                        elif match_method == 'phone':
                            matching_stats['phone_matches'] += 1
                        elif match_method == 'phone_duplicate':
                            matching_stats['phone_duplicates'] += 1
                        
                        all_results.append({
                            'npi': npi,
                            'first_name': first_name,
                            'last_name': last_name,
                            'filenames': best_file,
                            'specialties': ', '.join(specialties),
                            'medical_school': ' | '.join(medical_schools),
                            'residency': ' | '.join(residencies),
                            'fellowship': ' | '.join(fellowships),
                            'certifications': ' | '.join(certifications),
                            'matching_method': match_method,
                            'matching_notes': match_notes
                        })
                        print(f"   ✅ {match_method}: {best_file}")
                    else:
                        # Multiple files but no clear single match
                        processed_count += 1
                        matching_stats['no_matches'] += 1
                        
                        all_results.append({
                            'npi': npi,
                            'first_name': first_name,
                            'last_name': last_name,
                            'filenames': f'Multiple files ({len(neuro_files)}) - no clear match',
                            'specialties': 'Multiple files - no clear match',
                            'medical_school': 'Multiple files - no clear match',
                            'residency': 'Multiple files - no clear match',
                            'fellowship': 'Multiple files - no clear match',
                            'certifications': 'Multiple files - no clear match',
                            'matching_method': 'multiple_no_match',
                            'matching_notes': match_notes
                        })
                        print(f"   ❌ {match_notes}")
                else:
                    # Found files but none with neuro specialties
                    processed_count += 1
                    matching_stats['no_matches'] += 1
                    
                    all_results.append({
                        'npi': npi,
                        'first_name': first_name,
                        'last_name': last_name,
                        'filenames': 'None with neuro specialties',
                        'specialties': 'None',
                        'medical_school': 'None',
                        'residency': 'None',
                        'fellowship': 'None',
                        'certifications': 'None',
                        'matching_method': 'no_neuro_specialties',
                        'matching_notes': 'Files found but none contain neuro specialties'
                    })
                    print(f"   ❌ No neuro specialties in any files")
            else:
                # No matching files found
                matching_stats['no_files'] += 1
                
                all_results.append({
                    'npi': npi,
                    'first_name': first_name,
                    'last_name': last_name,
                    'filenames': 'None exists',
                    'specialties': 'None',
                    'medical_school': 'None',
                    'residency': 'None',
                    'fellowship': 'None',
                    'certifications': 'None',
                    'matching_method': 'no_files',
                    'matching_notes': 'No matching files found'
                })
                print(f"   ❌ No matching files found")
        
        print(f"✅ Processed {len(doctors)} doctors")
        print(f"🧠 Found {neuro_specialists_count} neurosurgeons/neurologists with Healthgrades profiles")
        
        # Save results to CSV (use script directory)
        script_dir = Path(__file__).parent.resolve()
        csv_file = script_dir / 'neuro_specialists_verification_results.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['npi', 'first_name', 'last_name', 'filenames', 'specialties', 'medical_school', 'residency', 'fellowship', 'certifications', 'matching_method', 'matching_notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"💾 Results saved to {csv_file}")
        
        # Print detailed summary
        print(f"\n📊 DETAILED SUMMARY:")
        print(f"   Total doctors in database: {len(doctors)}")
        print(f"   Doctors with neuro Healthgrades profiles: {neuro_specialists_count}")
        print(f"   Doctors with non-neuro Healthgrades profiles: {processed_count - neuro_specialists_count}")
        print(f"   Doctors with no Healthgrades profiles: {len(doctors) - processed_count}")
        print(f"   Percentage with neuro Healthgrades profiles: {(neuro_specialists_count/len(doctors)*100):.1f}%")
        
        print(f"\n🎯 INTELLIGENT MATCHING RESULTS:")
        print(f"   Single file: {matching_stats['single_file']}")
        print(f"   City matches: {matching_stats['city_matches']}")
        print(f"   City duplicates: {matching_stats['city_duplicates']}")
        print(f"   Phone matches: {matching_stats['phone_matches']}")
        print(f"   Phone duplicates: {matching_stats['phone_duplicates']}")
        print(f"   No matches: {matching_stats['no_matches']}")
        print(f"   No files: {matching_stats['no_files']}")
        
        total_successful_matches = (matching_stats['single_file'] + matching_stats['city_matches'] + 
                                  matching_stats['city_duplicates'] + matching_stats['phone_matches'] + 
                                  matching_stats['phone_duplicates'])
        success_rate = (total_successful_matches / len(doctors) * 100) if len(doctors) > 0 else 0
        print(f"   Success rate: {success_rate:.1f}%")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
