#!/usr/bin/env python3
"""Unified US News verification: match NPIs to markdown files and extract education/certifications.

Outputs a single CSV with columns:
  npi, first_name, last_name, markdown_file, medical_school, residency, fellowship, certifications

Strict parsing rules (no fallbacks):
  - Medical education is read from the "### Medical School & Residency" section only
  - Institutions appear on their own line, followed by a line specifying the type
    Examples of type lines:
      "Medical School"
      "Residency, Neurological Surgery, 1988-1995"
      "Fellowship, Clinical Neurophysiology, 2002-2003"
      "Internship, ..." (ignored)
  - We map the most recent institution line to the subsequent type line
  - If a type line does not match one of: Medical School | Residency | Fellowship, it is ignored

We do not attempt to infer types if they are missing.
"""

import os
import sys
import csv
import re
from pathlib import Path
from typing import Optional, Tuple, List

# Ensure backend is importable for DB access
sys.path.append(str(Path(__file__).parent.parent / 'backend'))
from app.database import get_db
from sqlalchemy import text


def extract_npi_from_markdown(filepath: str) -> Optional[str]:
    """Extract NPI number from a markdown file (US News format)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'Provider NPI:\s*\n\s*(\d+)', content)
        return match.group(1) if match else None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def extract_med_school_residency_section(filepath: str) -> Optional[str]:
    """Return the raw text of the '### Medical School & Residency' section, or None."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Capture up to next ### or ## header or end of file
        pattern = r'### Medical School & Residency\s*\n(.*?)(?=\n###|\n##|\Z)'
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            return None
        section = m.group(1).strip()
        # Normalize excess blank lines
        section = re.sub(r'\n\s*\n', '\n', section).strip()
        return section if section else None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def parse_education_strict(section_text: str) -> Tuple[List[str], List[str], List[str]]:
    """Strictly parse the Medical School & Residency section into categories.

    - Only classify lines explicitly labeled as:
        * 'Medical School'
        * 'Residency,' ...
        * 'Fellowship,' ...
      preceded by an institution line.
    - Ignore 'Internship' and any other types.
    - No inference/fallbacks.
    """
    if not section_text:
        return [], [], []

    lines = [line.strip() for line in section_text.split('\n') if line.strip()]
    medical_schools: List[str] = []
    residencies: List[str] = []
    fellowships: List[str] = []

    last_institution: Optional[str] = None

    for line in lines:
        # Type lines we care about
        if line.startswith('Medical School'):
            if last_institution:
                medical_schools.append(f"{last_institution} ({line})")
            last_institution = None
            continue

        # Treat MD/M.D. degree-only lines as Medical School when following an institution
        if re.match(r'^(M\.?D\.?)($|[\s,])', line):
            if last_institution:
                medical_schools.append(f"{last_institution} ({line})")
            last_institution = None
            continue

        if line.startswith('Residency,'):
            if last_institution:
                residencies.append(f"{last_institution} ({line})")
            last_institution = None
            continue

        if line.startswith('Fellowship,'):
            if last_institution:
                fellowships.append(f"{last_institution} ({line})")
            last_institution = None
            continue

        if line.startswith('Internship,'):
            # Explicitly ignore internships per requirements
            last_institution = None
            continue

        # Otherwise, treat as institution line
        last_institution = line

    return medical_schools, residencies, fellowships


def extract_certifications_section(filepath: str) -> Optional[str]:
    """Extract the text of the '### Certifications & Licensure' section, or None."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r'### Certifications & Licensure\s*\n(.*?)(?=\n###|\n##|\Z)'
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            return None
        section = m.group(1).strip()
        section = re.sub(r'\n\s*\n', '\n', section).strip()
        return section if section else None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None


def main():
    print("🔍 US News: matching NPIs to markdown and extracting education/certifications (strict parsing)...")

    # Query neurosurgeons
    db = next(get_db())
    try:
        result = db.execute(text(
            """
            SELECT npi, provider_first_name, provider_last_name
            FROM npi_providers
            WHERE entity_type_code = '1' AND healthcare_provider_taxonomy_code_1 = '207T00000X'
            """
        ))

        doctors = [{'npi': r.npi, 'first_name': r.provider_first_name, 'last_name': r.provider_last_name} for r in result]
        print(f"📊 Found {len(doctors)} neurosurgeons in database")

        # Scan markdown files and map NPI -> filename
        scraped_dir = 'scraped_pages'
        markdown_files = [f for f in os.listdir(scraped_dir) if f.endswith('.md')]
        print(f"📄 Found {len(markdown_files)} markdown files")

        npi_to_file: dict[str, str] = {}
        for filename in markdown_files:
            filepath = os.path.join(scraped_dir, filename)
            npi = extract_npi_from_markdown(filepath)
            if npi:
                npi_to_file[npi] = filename

        print(f"🔗 Found NPI numbers in {len(npi_to_file)} markdown files")

        # Build results
        rows: List[dict] = []
        for doc in doctors:
            npi_str = str(doc['npi'])
            filename = npi_to_file.get(npi_str, 'None exists')

            medical_school_list: List[str] = []
            residency_list: List[str] = []
            fellowship_list: List[str] = []
            certifications_text: str = ''

            if filename != 'None exists':
                filepath = os.path.join(scraped_dir, filename)
                edu_section = extract_med_school_residency_section(filepath)
                ms, rs, fs = parse_education_strict(edu_section or '')
                medical_school_list = ms
                residency_list = rs
                fellowship_list = fs

                cert_section = extract_certifications_section(filepath)
                certifications_text = cert_section or ''

            rows.append({
                'npi': npi_str,
                'first_name': doc['first_name'],
                'last_name': doc['last_name'],
                'markdown_file': filename,
                'medical_school': ' | '.join(medical_school_list) if medical_school_list else '',
                'residency': ' | '.join(residency_list) if residency_list else '',
                'fellowship': ' | '.join(fellowship_list) if fellowship_list else '',
                'certifications': certifications_text,
            })

        # Write output (non-destructive new file to review before replacing originals)
        output_file = 'mapping/npi_verification_results_enhanced.csv'
        os.makedirs('mapping', exist_ok=True)
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['npi', 'first_name', 'last_name', 'markdown_file', 'medical_school', 'residency', 'fellowship', 'certifications']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"💾 Prepared (not run on your request yet) → {output_file}")

    finally:
        db.close()


if __name__ == '__main__':
    main()


