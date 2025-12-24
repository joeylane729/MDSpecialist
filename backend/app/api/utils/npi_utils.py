"""
NPI-related utility functions.

Helper functions for NPI provider data processing, specialty mapping,
and state conversions.
"""

from typing import Optional
import re
from datetime import datetime


def convert_state_name_to_abbreviation(state_name: str) -> str:
    """Convert full state name to abbreviation for database lookup."""
    state_mapping = {
        'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
        'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
        'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
        'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
        'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
        'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
        'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
        'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
        'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
        'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
        'District of Columbia': 'DC'
    }
    return state_mapping.get(state_name, state_name)


def extract_latest_year_from_residency(residency_text: Optional[str]) -> Optional[int]:
    """Extract the most recent 4-digit year from residency text."""
    if not residency_text:
        return None
    # Find all 4-digit years (handles ranges like 1982-1987)
    year_matches = re.findall(r'(?:19|20)\d{2}', residency_text)
    if not year_matches:
        return None
    current_year = datetime.utcnow().year + 1  # allow upcoming completions
    valid_years = [int(year) for year in year_matches if 1900 <= int(year) <= current_year]
    if not valid_years:
        return None
    return max(valid_years)


def get_specialty_description(taxonomy_code: str) -> str:
    """Convert taxonomy code to readable specialty description."""
    specialty_map = {
        '207Q00000X': 'Family Medicine',
        '207R00000X': 'Internal Medicine',
        '207T00000X': 'Neurological Surgery',
        '207U00000X': 'Nuclear Medicine',
        '207V00000X': 'Obstetrics & Gynecology',
        '207W00000X': 'Ophthalmology',
        '207X00000X': 'Orthopaedic Surgery',
        '207Y00000X': 'Otolaryngology',
        '207ZP0102X': 'Pediatric Otolaryngology',
        '208000000X': 'Pediatrics',
        '207K00000X': 'Allergy & Immunology',
        '207L00000X': 'Anesthesiology',
        '207M00000X': 'Anatomic Pathology',
        '207N00000X': 'Clinical Pathology',
        '207P00000X': 'Emergency Medicine',
        '208C00000X': 'Colon & Rectal Surgery',
        '208D00000X': 'General Practice',
        '208G00000X': 'Thoracic Surgery',
        '208M00000X': 'Hospitalist',
        '208U00000X': 'Clinical Pharmacology',
        '208VP0000X': 'Pain Medicine',
        '208VP0014X': 'Interventional Pain Medicine'
    }
    return specialty_map.get(taxonomy_code, 'Medical Specialist')


def get_taxonomy_codes_for_specialty(specialty_name: str) -> list:
    """Convert specialty name back to taxonomy codes for database filtering."""
    specialty_to_codes = {
        'Family Medicine': ['207Q00000X'],
        'Internal Medicine': ['207R00000X'],
        'Neurological Surgery': ['207T00000X'],
        'Nuclear Medicine': ['207U00000X'],
        'Obstetrics & Gynecology': ['207V00000X'],
        'Ophthalmology': ['207W00000X'],
        'Orthopaedic Surgery': ['207X00000X'],
        'Otolaryngology': ['207Y00000X'],
        'Pediatric Otolaryngology': ['207ZP0102X'],
        'Pediatrics': ['208000000X'],
        'Allergy & Immunology': ['207K00000X'],
        'Anesthesiology': ['207L00000X'],
        'Anatomic Pathology': ['207M00000X'],
        'Clinical Pathology': ['207N00000X'],
        'Emergency Medicine': ['207P00000X'],
        'Colon & Rectal Surgery': ['208C00000X'],
        'General Practice': ['208D00000X'],
        'Thoracic Surgery': ['208G00000X'],
        'Hospitalist': ['208M00000X'],
        'Clinical Pharmacology': ['208U00000X'],
        'Pain Medicine': ['208VP0000X'],
        'Interventional Pain Medicine': ['208VP0014X']
    }
    return specialty_to_codes.get(specialty_name, [])

