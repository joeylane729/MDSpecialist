import logging
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from ...database import get_db
from ...services.medical_analysis_service import MedicalAnalysisService
import PyPDF2
import io
import math
import re
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

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

def is_within_search_radius(provider_state: str, search_state: str, proximity: str) -> bool:
    """
    Determine if a provider is within the search radius based on proximity setting.
    Returns True for 'statewide' if same state, True for 'US-wide' always.
    """
    if proximity.lower() == 'us-wide':
        return True
    elif proximity.lower() == 'statewide':
        return provider_state.upper() == search_state.upper()
    else:
        # Default to statewide if unknown proximity
        return provider_state.upper() == search_state.upper()

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

# Initialize GPT service
gpt_service = MedicalAnalysisService()

@router.get("/test")
async def test_database_connection(db: Session = Depends(get_db)):
    """Test database connection and return basic info."""
    try:
        # Test a simple query
        result = db.execute(text("SELECT COUNT(*) FROM npi_providers"))
        count = result.scalar()
        
        return {
            "status": "success",
            "message": "Connected to PostgreSQL successfully",
            "total_providers": count,
            "database_type": "PostgreSQL"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}",
            "error_type": type(e).__name__
        }

@router.get("/simple-stats")
async def get_simple_stats(db: Session = Depends(get_db)):
    """Get simple database statistics."""
    try:
        # Get total providers
        result = db.execute(text("SELECT COUNT(*) FROM npi_providers"))
        total = result.scalar()
        
        # Get sample provider
        result = db.execute(text("SELECT npi, provider_first_name, provider_last_name FROM npi_providers LIMIT 1"))
        sample = result.fetchone()
        
        return {
            "total_providers": total,
            "sample_provider": {
                "npi": sample[0] if sample else None,
                "name": f"{sample[1]} {sample[2]}" if sample else None
            },
            "database": "PostgreSQL"
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }

@router.post("/search-providers")
async def search_providers_by_criteria(
    state: str = Form(...),
    city: str = Form(...),
    zipCode: str = Form(...),
    proximity: str = Form(...),
    diagnosis: str = Form(...),
    symptoms: str = Form(...),
    search_query: Optional[str] = Form(None),  # Pre-generated search query from medical analysis
    limit: int = Form(10000),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """Search for providers by city, state, and diagnosis/specialty with file analysis."""
    try:
        # Set the database session for the GPT service
        gpt_service.set_db(db)
        
        # Process uploaded files to extract text
        file_contents = []
        print(f"Processing {len(files)} uploaded files")
        for file in files:
            print(f"Processing file: {file.filename}, content_type: {file.content_type}")
            if file.content_type == "application/pdf":
                try:
                    # Read PDF content
                    pdf_content = await file.read()
                    print(f"PDF file size: {len(pdf_content)} bytes")
                    
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
                    print(f"PDF has {len(pdf_reader.pages)} pages")
                    
                    # Extract text from all pages
                    text_content = ""
                    for i, page in enumerate(pdf_reader.pages):
                        page_text = page.extract_text()
                        print(f"Page {i+1} extracted {len(page_text)} characters: '{page_text[:100]}...'")
                        text_content += page_text + " "
                    
                    file_contents.append(f"File {file.filename}: {text_content.strip()}")
                    print(f"Successfully processed PDF file: {file.filename}, total text: {len(text_content)} characters")
                except Exception as e:
                    print(f"Error processing PDF file {file.filename}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"Skipping non-PDF file: {file.filename}")
        
        print(f"Final file_contents: {file_contents}")
        
        # Combine symptoms, diagnosis text, and file contents for GPT analysis
        print(f"Original symptoms: '{symptoms}'")
        print(f"Original diagnosis text: '{diagnosis}'")
        combined_input = f"Symptoms: {symptoms}\n\nDiagnosis: {diagnosis}"
        if file_contents:
            combined_input += "\n\nAdditional information from uploaded files:\n" + "\n".join(file_contents)
            print(f"Combined input for GPT: {len(combined_input)} characters")
            print(f"Combined input preview: '{combined_input[:300]}...'")
        else:
            print("No file contents to combine")
        
        # Use GPT to determine the specialty from the combined input
        print(f"Using GPT to determine specialty for combined input: '{combined_input[:200]}...'")
        determined_specialty = await gpt_service.determine_specialty(combined_input)
        
        if not determined_specialty:
            print("GPT failed to determine specialty, using fallback")
            determined_specialty = "Unknown"  
        
        print(f"GPT determined specialty: '{determined_specialty}'")
        
        # Use GPT to predict primary diagnosis from the combined input
        print(f"Using GPT to predict diagnosis for combined input: '{combined_input[:200]}...'")
        predicted_diagnoses = await gpt_service.predict_diagnoses(symptoms, diagnosis)
        
        predicted_icd10 = None
        icd10_description = None
        
        if predicted_diagnoses:
            print(f"GPT predicted diagnoses: {predicted_diagnoses}")
            
            # Extract primary diagnosis
            if 'primary' in predicted_diagnoses and 'code' in predicted_diagnoses['primary']:
                predicted_icd10 = predicted_diagnoses['primary']['code']
                icd10_description = predicted_diagnoses['primary'].get('description', 'Description not available')
                print(f"Primary diagnosis: {predicted_icd10} - {icd10_description}")
        else:
            print("GPT failed to predict diagnoses, falling back to single code prediction")
            # Fallback to the old method
            predicted_icd10 = await gpt_service.predict_icd10_code(combined_input)
            if predicted_icd10:
                icd10_description = gpt_service.lookup_icd10_description(predicted_icd10)
        

        
        # Get taxonomy codes for the determined specialty
        taxonomy_codes = get_taxonomy_codes_for_specialty(determined_specialty)
        
        if not taxonomy_codes:
            print(f"No taxonomy codes found for specialty: '{determined_specialty}'")
            return {
                "error": f"No taxonomy codes found for specialty: {determined_specialty}",
                "total_providers": 0,
                "providers": []
            }
        
        print(f"Filtering providers by determined specialty: '{determined_specialty}' using taxonomy codes: {taxonomy_codes}")
        
        # Build database-level filtering query
        taxonomy_conditions = []
        for i in range(1, 16):
            for code in taxonomy_codes:
                taxonomy_conditions.append(f"healthcare_provider_taxonomy_code_{i} = '{code}'")
        
        if taxonomy_conditions:
            # Build location filtering conditions
            location_conditions = []
            
            # Add state filtering based on proximity setting
            state_abbrev = None
            if state and proximity and proximity.lower() == 'statewide':
                state_abbrev = convert_state_name_to_abbreviation(state)
                location_conditions.append(f"provider_business_practice_location_address_state_name = '{state_abbrev}'")
            # For US-wide searches, we don't filter by state in SQL - we'll get all providers
            
            location_filter = ""
            if location_conditions:
                location_filter = f"AND ({' AND '.join(location_conditions)})"
            
            # Add taxonomy filtering to the SQL query
            sql = f"""
                SELECT 
                    npi,
                    provider_first_name,
                    provider_last_name,
                    provider_business_practice_location_address_city_name,
                    provider_business_practice_location_address_state_name,
                    provider_business_practice_location_address_postal_code,
                    provider_first_line_business_practice_location_address,
                    provider_second_line_business_practice_location_address,
                    provider_business_practice_location_address_telephone_number,
                    healthcare_provider_taxonomy_code_1,
                    healthcare_provider_taxonomy_code_2,
                    healthcare_provider_taxonomy_code_3,
                    healthcare_provider_taxonomy_code_4,
                    healthcare_provider_taxonomy_code_5,
                    healthcare_provider_taxonomy_code_6,
                    healthcare_provider_taxonomy_code_7,
                    healthcare_provider_taxonomy_code_8,
                    healthcare_provider_taxonomy_code_9,
                    healthcare_provider_taxonomy_code_10,
                    healthcare_provider_taxonomy_code_11,
                    healthcare_provider_taxonomy_code_12,
                    healthcare_provider_taxonomy_code_13,
                    healthcare_provider_taxonomy_code_14,
                    healthcare_provider_taxonomy_code_15,
                    provider_first_line_business_practice_location_address,
                    provider_second_line_business_practice_location_address
                FROM npi_providers 
                WHERE entity_type_code = '1'  -- Individual providers only
                  AND ({' OR '.join(taxonomy_conditions)})  -- Match any taxonomy code
                  {location_filter}
                ORDER BY provider_last_name, provider_first_name
                LIMIT {limit * 3}  -- Get more results for distance filtering
            """
            
            result = db.execute(text(sql))
            providers = result.fetchall()
        
        filtered_providers = []
        for provider in providers:
            # Apply proximity-based filtering
            if proximity and provider.provider_business_practice_location_address_state_name:
                # For US-wide searches, we don't need state_abbrev since we accept all states
                search_state_for_filtering = state_abbrev if proximity.lower() == 'statewide' else state
                if not is_within_search_radius(provider.provider_business_practice_location_address_state_name, search_state_for_filtering, proximity):
                    continue  # Skip this provider if it's outside the search area
            
            # Get the primary specialty for display
            primary_specialty = get_specialty_description(provider.healthcare_provider_taxonomy_code_1)
            
            # Fetch education from US News with Healthgrades fallback (per field)
            edu_med_school = None
            edu_residency = None
            edu_fellowship = None
            edu_certifications = None

            try:
                # US News first
                usnews_sql = text("""
                    SELECT medical_school, residency, fellowship, certifications
                    FROM usnews_data
                    WHERE npi = :npi
                    LIMIT 1
                """)
                us_row = db.execute(usnews_sql, {"npi": provider.npi}).fetchone()
                if us_row:
                    edu_med_school = us_row.medical_school
                    edu_residency = us_row.residency
                    edu_fellowship = us_row.fellowship
                    edu_certifications = us_row.certifications

                # Healthgrades fallback per field
                if not (edu_med_school and str(edu_med_school).strip() and str(edu_med_school) != 'None') or \
                   not (edu_residency and str(edu_residency).strip() and str(edu_residency) != 'None') or \
                   not (edu_fellowship and str(edu_fellowship).strip() and str(edu_fellowship) != 'None') or \
                   not (edu_certifications and str(edu_certifications).strip() and str(edu_certifications) != 'None'):
                    hg_sql = text("""
                        SELECT medical_school, residency, fellowship, certifications
                        FROM healthgrades_data
                        WHERE npi = :npi
                        LIMIT 1
                    """)
                    hg_row = db.execute(hg_sql, {"npi": provider.npi}).fetchone()
                    if hg_row:
                        if not (edu_med_school and str(edu_med_school).strip() and str(edu_med_school) != 'None'):
                            edu_med_school = hg_row.medical_school
                        if not (edu_residency and str(edu_residency).strip() and str(edu_residency) != 'None'):
                            edu_residency = hg_row.residency
                        if not (edu_fellowship and str(edu_fellowship).strip() and str(edu_fellowship) != 'None'):
                            edu_fellowship = hg_row.fellowship
                        if not (edu_certifications and str(edu_certifications).strip() and str(edu_certifications) != 'None'):
                            edu_certifications = hg_row.certifications
            except Exception as e:
                logger.error(f"Error enriching education for NPI {provider.npi}: {e}")

            graduation_year = extract_latest_year_from_residency(edu_residency)
            years_experience = None
            if graduation_year:
                current_year = datetime.utcnow().year
                if graduation_year <= current_year:
                    years_experience = max(0, current_year - graduation_year)

            # Check if provider is in exclusions table (by NPI or name)
            is_excluded = False
            try:
                # First check by NPI (only if NPI is valid, not "0000000000" or empty)
                provider_npi = str(provider.npi).strip() if provider.npi else ''
                if provider_npi and provider_npi != '0000000000' and len(provider_npi) == 10:
                    excl_npi_check = text("""
                        SELECT COUNT(*) FROM exclusions 
                        WHERE npi = :npi AND (reindate IS NULL OR reindate = '' OR reindate = '00000000')
                    """)
                    npi_result = db.execute(excl_npi_check, {"npi": provider_npi}).fetchone()
                    
                    if npi_result and npi_result[0] > 0:
                        is_excluded = True
                
                # If not found by NPI, check by first name + last name
                if not is_excluded and provider.provider_first_name and provider.provider_last_name:
                    excl_name_check = text("""
                        SELECT COUNT(*) FROM exclusions 
                        WHERE UPPER(TRIM(FIRSTNAME)) = UPPER(TRIM(:firstname))
                          AND UPPER(TRIM(LASTNAME)) = UPPER(TRIM(:lastname))
                          AND (reindate IS NULL OR reindate = '' OR reindate = '00000000')
                    """)
                    name_result = db.execute(excl_name_check, {
                        "firstname": provider.provider_first_name.strip(),
                        "lastname": provider.provider_last_name.strip()
                    }).fetchone()
                    
                    if name_result and name_result[0] > 0:
                        is_excluded = True
            except Exception as e:
                logger.error(f"Error checking exclusions for NPI {provider.npi}: {e}")

            formatted_provider = {
                "id": provider.npi,  # Use NPI as ID
                "npi": provider.npi,
                "name": f"{provider.provider_first_name or ''} {provider.provider_last_name or ''}".strip(),
                "specialty": primary_specialty,
                "address": provider.provider_first_line_business_practice_location_address or '',
                "city": provider.provider_business_practice_location_address_city_name or '',
                "state": provider.provider_business_practice_location_address_state_name or '',
                "zip": provider.provider_business_practice_location_address_postal_code or '',
                "phone": provider.provider_business_practice_location_address_telephone_number or '',
                "rating": 5.0,  # Default rating
                "yearsExperience": years_experience,
                "boardCertified": None,  # No certification data available
                "acceptingPatients": True,  # Default to accepting patients
                "isExcluded": is_excluded,  # Flag for excluded providers
                "languages": [],  # No language data available
                "insurance": [],  # No insurance data available
                "education": {
                    "medicalSchool": edu_med_school if (edu_med_school and str(edu_med_school) != 'None') else None,
                    "residency": edu_residency if (edu_residency and str(edu_residency) != 'None') else None,
                    "fellowship": edu_fellowship if (edu_fellowship and str(edu_fellowship) != 'None') else None,
                    "certifications": edu_certifications if (edu_certifications and str(edu_certifications) != 'None') else None
                }
            }
            filtered_providers.append(formatted_provider)
        
        # Apply limit after filtering
        if limit and len(filtered_providers) > limit:
            filtered_providers = filtered_providers[:limit]
        
        print(f"Database filtering results: {len(filtered_providers)} providers found for specialty '{determined_specialty}'")
        
        return {
            "total_providers": len(filtered_providers),
            "providers": filtered_providers,
            "search_criteria": {
                "state": state,
                "city": city,
                "zipCode": zipCode,
                "proximity": proximity,
                "diagnosis": diagnosis,
                "determined_specialty": determined_specialty,
                "predicted_icd10": predicted_icd10,
                "icd10_description": icd10_description
            }
        }
        
    except Exception as e:
        logger.error(f"Error searching providers: {e}")
        return {
            "error": str(e),
            "total_providers": 0,
            "providers": []
        }

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
