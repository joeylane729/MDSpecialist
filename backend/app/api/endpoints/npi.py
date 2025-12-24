import logging
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from ...database import get_db
from ..utils.npi_utils import (
    convert_state_name_to_abbreviation,
    extract_latest_year_from_residency,
    get_specialty_description,
    get_taxonomy_codes_for_specialty
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

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
    determined_specialty: str = Form(...),  # Required: Pre-determined specialty from medical analysis
    predicted_icd10: Optional[str] = Form(None),  # Pre-determined ICD-10 code from medical analysis
    icd10_description: Optional[str] = Form(None),  # Pre-determined ICD-10 description from medical analysis
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """Search for providers by city, state, and diagnosis/specialty with file analysis.
    
    Note: This endpoint requires values from the medical analysis step (determined_specialty, predicted_icd10, icd10_description).
    These values should always be provided to avoid duplicate GPT API calls.
    """
    try:
        # Use pre-determined values from medical analysis (no fallback - always required)
        logger.info(f"✅ Using pre-determined specialty from medical analysis: '{determined_specialty}'")
        specialty_to_use = determined_specialty
        
        # Use pre-determined diagnosis information from medical analysis
        predicted_icd10_to_use = predicted_icd10
        icd10_description_to_use = icd10_description
        
        if predicted_icd10_to_use and icd10_description_to_use:
            logger.info(f"✅ Using pre-determined diagnosis from medical analysis: {predicted_icd10_to_use} - {icd10_description_to_use}")
        else:
            logger.warning(f"⚠️  Missing diagnosis information: predicted_icd10={predicted_icd10_to_use}, icd10_description={icd10_description_to_use}")
            # Continue anyway since specialty is the main filtering criteria
        

        
        # Get taxonomy codes for the determined specialty
        taxonomy_codes = get_taxonomy_codes_for_specialty(specialty_to_use)
        
        if not taxonomy_codes:
            logger.error(f"No taxonomy codes found for specialty: '{specialty_to_use}'")
            return {
                "error": f"No taxonomy codes found for specialty: {specialty_to_use}",
                "total_providers": 0,
                "providers": []
            }
        
        logger.info(f"Filtering providers by determined specialty: '{specialty_to_use}' using taxonomy codes: {taxonomy_codes}")
        
        # Build database-level filtering query
        taxonomy_conditions = []
        for i in range(1, 16):
            for code in taxonomy_codes:
                taxonomy_conditions.append(f"healthcare_provider_taxonomy_code_{i} = '{code}'")
        
        if taxonomy_conditions:
            # Build location filtering conditions
            location_conditions = []
            
            # Add state filtering based on proximity setting
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
            """
            
            result = db.execute(text(sql))
            providers = result.fetchall()
        
        # Batch fetch all education and exclusion data to avoid N+1 queries
        npis = [str(p.npi).strip() for p in providers if p.npi]
        valid_npis = [npi for npi in npis if npi and npi != '0000000000' and len(npi) == 10]
        
        # Batch fetch US News data
        usnews_map = {}
        if valid_npis:
            try:
                # Use parameterized IN clause with tuple unpacking (works with PostgreSQL)
                placeholders = ','.join([':npi' + str(i) for i in range(len(valid_npis))])
                usnews_sql = text(f"""
                    SELECT npi, medical_school, residency, fellowship, certifications
                    FROM usnews_data
                    WHERE npi IN ({placeholders})
                """)
                params = {f'npi{i}': npi for i, npi in enumerate(valid_npis)}
                usnews_rows = db.execute(usnews_sql, params).fetchall()
                for row in usnews_rows:
                    usnews_map[str(row.npi)] = {
                        'medical_school': row.medical_school,
                        'residency': row.residency,
                        'fellowship': row.fellowship,
                        'certifications': row.certifications
                    }
                logger.info(f"Batch fetched {len(usnews_map)} US News records for {len(valid_npis)} NPIs")
            except Exception as e:
                logger.error(f"Error batch fetching US News data: {e}")
        
        # Batch fetch Healthgrades data
        healthgrades_map = {}
        if valid_npis:
            try:
                placeholders = ','.join([':npi' + str(i) for i in range(len(valid_npis))])
                hg_sql = text(f"""
                    SELECT npi, medical_school, residency, fellowship, certifications
                    FROM healthgrades_data
                    WHERE npi IN ({placeholders})
                """)
                params = {f'npi{i}': npi for i, npi in enumerate(valid_npis)}
                hg_rows = db.execute(hg_sql, params).fetchall()
                for row in hg_rows:
                    healthgrades_map[str(row.npi)] = {
                        'medical_school': row.medical_school,
                        'residency': row.residency,
                        'fellowship': row.fellowship,
                        'certifications': row.certifications
                    }
                logger.info(f"Batch fetched {len(healthgrades_map)} Healthgrades records for {len(valid_npis)} NPIs")
            except Exception as e:
                logger.error(f"Error batch fetching Healthgrades data: {e}")
        
        # Batch fetch exclusions by NPI
        excluded_npis = set()
        if valid_npis:
            try:
                placeholders = ','.join([':npi' + str(i) for i in range(len(valid_npis))])
                excl_npi_sql = text(f"""
                    SELECT DISTINCT npi FROM exclusions 
                    WHERE npi IN ({placeholders})
                      AND (reindate IS NULL OR reindate = '' OR reindate = '00000000')
                """)
                params = {f'npi{i}': npi for i, npi in enumerate(valid_npis)}
                excl_npi_rows = db.execute(excl_npi_sql, params).fetchall()
                excluded_npis = {str(row[0]) for row in excl_npi_rows if row[0]}
                logger.info(f"Batch found {len(excluded_npis)} excluded NPIs")
            except Exception as e:
                logger.error(f"Error batch fetching exclusions by NPI: {e}")
        
        # Batch fetch exclusions by name (collect unique name combinations)
        name_pairs = list(set([(p.provider_first_name.strip().upper(), p.provider_last_name.strip().upper()) 
                      for p in providers 
                      if p.provider_first_name and p.provider_last_name]))
        excluded_names = set()
        if name_pairs:
            try:
                # Build OR conditions for name matching
                name_conditions = []
                params = {}
                for i, (first, last) in enumerate(name_pairs):
                    name_conditions.append(f"(UPPER(TRIM(FIRSTNAME)) = :first{i} AND UPPER(TRIM(LASTNAME)) = :last{i})")
                    params[f'first{i}'] = first
                    params[f'last{i}'] = last
                
                if name_conditions:
                    excl_name_sql = text(f"""
                        SELECT DISTINCT UPPER(TRIM(FIRSTNAME)) as firstname, UPPER(TRIM(LASTNAME)) as lastname
                        FROM exclusions 
                        WHERE ({' OR '.join(name_conditions)})
                          AND (reindate IS NULL OR reindate = '' OR reindate = '00000000')
                    """)
                    excl_name_rows = db.execute(excl_name_sql, params).fetchall()
                    excluded_names = {(row.firstname, row.lastname) for row in excl_name_rows}
                    logger.info(f"Batch found {len(excluded_names)} excluded name combinations")
            except Exception as e:
                logger.error(f"Error batch fetching exclusions by name: {e}")
        
        # Now process providers using in-memory lookups
        filtered_providers = []
        for provider in providers:
            # Get the primary specialty for display
            primary_specialty = get_specialty_description(provider.healthcare_provider_taxonomy_code_1)
            
            # Fetch education from US News with Healthgrades fallback (per field) using batch data
            provider_npi_str = str(provider.npi).strip() if provider.npi else ''
            edu_med_school = None
            edu_residency = None
            edu_fellowship = None
            edu_certifications = None

            try:
                # US News first (from batch data)
                if provider_npi_str in usnews_map:
                    us_data = usnews_map[provider_npi_str]
                    edu_med_school = us_data['medical_school']
                    edu_residency = us_data['residency']
                    edu_fellowship = us_data['fellowship']
                    edu_certifications = us_data['certifications']

                # Healthgrades fallback per field (from batch data)
                if not (edu_med_school and str(edu_med_school).strip() and str(edu_med_school) != 'None') or \
                   not (edu_residency and str(edu_residency).strip() and str(edu_residency) != 'None') or \
                   not (edu_fellowship and str(edu_fellowship).strip() and str(edu_fellowship) != 'None') or \
                   not (edu_certifications and str(edu_certifications).strip() and str(edu_certifications) != 'None'):
                    if provider_npi_str in healthgrades_map:
                        hg_data = healthgrades_map[provider_npi_str]
                        if not (edu_med_school and str(edu_med_school).strip() and str(edu_med_school) != 'None'):
                            edu_med_school = hg_data['medical_school']
                        if not (edu_residency and str(edu_residency).strip() and str(edu_residency) != 'None'):
                            edu_residency = hg_data['residency']
                        if not (edu_fellowship and str(edu_fellowship).strip() and str(edu_fellowship) != 'None'):
                            edu_fellowship = hg_data['fellowship']
                        if not (edu_certifications and str(edu_certifications).strip() and str(edu_certifications) != 'None'):
                            edu_certifications = hg_data['certifications']
            except Exception as e:
                logger.error(f"Error enriching education for NPI {provider.npi}: {e}")

            graduation_year = extract_latest_year_from_residency(edu_residency)
            years_experience = None
            if graduation_year:
                current_year = datetime.utcnow().year
                if graduation_year <= current_year:
                    years_experience = max(0, current_year - graduation_year)

            # Check if provider is in exclusions using batch data
            is_excluded = False
            try:
                # Check by NPI first (from batch data)
                if provider_npi_str in excluded_npis:
                    is_excluded = True
                
                # If not found by NPI, check by name (from batch data)
                if not is_excluded and provider.provider_first_name and provider.provider_last_name:
                    first_upper = provider.provider_first_name.strip().upper()
                    last_upper = provider.provider_last_name.strip().upper()
                    if (first_upper, last_upper) in excluded_names:
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
        
        logger.info(f"Database filtering results: {len(filtered_providers)} providers found for specialty '{specialty_to_use}'")
        
        return {
            "total_providers": len(filtered_providers),
            "providers": filtered_providers,
            "search_criteria": {
                "state": state,
                "city": city,
                "zipCode": zipCode,
                "proximity": proximity,
                "diagnosis": diagnosis,
                "determined_specialty": specialty_to_use,
                "predicted_icd10": predicted_icd10_to_use,
                "icd10_description": icd10_description_to_use
            }
        }
        
    except Exception as e:
        logger.error(f"Error searching providers: {e}")
        return {
            "error": str(e),
            "total_providers": 0,
            "providers": []
        }

