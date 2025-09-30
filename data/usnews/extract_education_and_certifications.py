#!/usr/bin/env python3
"""Extract both Medical School & Residency and Certifications & Licensure information into one CSV"""

import os, sys, csv, re
from dotenv import load_dotenv

def extract_medical_education(markdown_file):
    """Extract Medical School & Residency section from markdown file"""
    if markdown_file == "None exists":
        return "None exists"
    
    filepath = os.path.join('scraped_pages', markdown_file)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the Medical School & Residency section
        pattern = r'### Medical School & Residency\s*\n(.*?)(?=\n###|\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            education_text = match.group(1).strip()
            education_text = re.sub(r'\n\s*\n', '\n', education_text)
            education_text = education_text.strip()
            return education_text if education_text else "No education info found"
        else:
            return "No education section found"
            
    except Exception as e:
        return f"Error reading file: {e}"

def extract_certifications(markdown_file):
    """Extract Certifications & Licensure section from markdown file"""
    if markdown_file == "None exists":
        return "None exists"
    
    filepath = os.path.join('scraped_pages', markdown_file)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the Certifications & Licensure section
        pattern = r'### Certifications & Licensure\s*\n(.*?)(?=\n###|\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            cert_text = match.group(1).strip()
            cert_text = re.sub(r'\n\s*\n', '\n', cert_text)
            cert_text = cert_text.strip()
            return cert_text if cert_text else "No certifications info found"
        else:
            return "No certifications section found"
            
    except Exception as e:
        return f"Error reading file: {e}"

def main():
    print("🎓🏥 Extracting both Medical Education and Certifications information...")
    
    # Read the verification results
    results = []
    with open('mapping/npi_verification_results.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    
    print(f"📊 Processing {len(results)} doctors...")
    
    # Add both education and certifications to each result
    for i, result in enumerate(results):
        if i % 1000 == 0:
            print(f"   Processing {i}/{len(results)}...")
        
        medical_education = extract_medical_education(result['markdown_file'])
        certifications = extract_certifications(result['markdown_file'])
        
        result['medical_education'] = medical_education
        result['certifications'] = certifications
    
    # Save combined results
    output_file = 'mapping/npi_verification_with_education_and_certifications.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['npi', 'first_name', 'last_name', 'markdown_file', 'medical_education', 'certifications']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    # Statistics
    with_education = sum(1 for r in results if r['medical_education'] not in ["None exists", "No education section found", "No education info found"] and not r['medical_education'].startswith("Error"))
    with_certifications = sum(1 for r in results if r['certifications'] not in ["None exists", "No certifications section found", "No certifications info found"] and not r['certifications'].startswith("Error"))
    with_files = sum(1 for r in results if r['markdown_file'] != "None exists")
    
    print(f"✅ Extraction complete!")
    print(f"📊 Combined CSV saved to {output_file}")
    print(f"📊 {with_education}/{with_files} doctors with markdown files have education info ({with_education/with_files:.1%})")
    print(f"📊 {with_certifications}/{with_files} doctors with markdown files have certifications info ({with_certifications/with_files:.1%})")
    
    # Overall statistics
    total_doctors = len(results)
    overall_education = sum(1 for r in results if r['medical_education'] not in ["None exists", "No education section found", "No education info found"] and not r['medical_education'].startswith("Error"))
    overall_certifications = sum(1 for r in results if r['certifications'] not in ["None exists", "No certifications section found", "No certifications info found"] and not r['certifications'].startswith("Error"))
    
    print(f"\n📊 Overall Coverage:")
    print(f"   Medical Education: {overall_education}/{total_doctors} ({overall_education/total_doctors:.1%})")
    print(f"   Certifications: {overall_certifications}/{total_doctors} ({overall_certifications/total_doctors:.1%})")
    
    # Show some examples
    print(f"\n🎓🏥 Sample extractions:")
    examples = [r for r in results if r['medical_education'] not in ["None exists", "No education section found", "No education info found"] and not r['medical_education'].startswith("Error")][:2]
    for example in examples:
        print(f"\n  {example['first_name']} {example['last_name']} (NPI: {example['npi']}):")
        education_preview = example['medical_education'][:150] + "..." if len(example['medical_education']) > 150 else example['medical_education']
        cert_preview = example['certifications'][:150] + "..." if len(example['certifications']) > 150 else example['certifications']
        print(f"    Education: {education_preview}")
        print(f"    Certifications: {cert_preview}")

if __name__ == "__main__":
    main()

