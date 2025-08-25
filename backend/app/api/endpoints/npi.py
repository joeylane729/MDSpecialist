import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from ...database import get_db
from ...services.gpt_service import GPTService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize GPT service
gpt_service = GPTService()

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

@router.get("/search-providers")
async def search_providers_by_criteria(
    state: str = Query(..., description="State code (e.g., NY, CA)"),
    city: str = Query(..., description="City name"),
    diagnosis: str = Query(..., description="Diagnosis/medical specialty description"),
    limit: int = Query(20, le=500, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Search for providers by city, state, and diagnosis/specialty."""
    try:
        # Use GPT to determine the specialty from the diagnosis text
        print(f"Using GPT to determine specialty for diagnosis: '{diagnosis}'")
        determined_specialty = gpt_service.determine_specialty(diagnosis)
        
        if not determined_specialty:
            print("GPT failed to determine specialty, using fallback")
            determined_specialty = "Internal Medicine"  # Fallback specialty
        
        print(f"GPT determined specialty: '{determined_specialty}'")
        
        # Build the SQL query to search the npi_providers table
        # Now searching by specialty text instead of taxonomy codes
        sql = """
            SELECT 
                npi,
                provider_first_name,
                provider_last_name,
                provider_business_practice_location_address_city_name,
                provider_business_practice_location_address_state_name,
                provider_business_practice_location_address_postal_code,
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
            WHERE provider_business_practice_location_address_state_name = :state
              AND LOWER(provider_business_practice_location_address_city_name) = LOWER(:city)
              AND entity_type_code = '1'  -- Individual providers only
            ORDER BY provider_last_name, provider_first_name
        """
        
        result = db.execute(text(sql), {
            "state": state,
            "city": city
        })
        
        providers = result.fetchall()
        
        # Filter providers by specialty text matching the determined specialty
        specialty_lower = determined_specialty.lower()
        filtered_providers = []
        
        for provider in providers:
            # Get specialty descriptions from all taxonomy codes
            specialties = []
            taxonomy_codes = []
            for i in range(1, 16):
                taxonomy_code = getattr(provider, f'healthcare_provider_taxonomy_code_{i}', None)
                if taxonomy_code:
                    taxonomy_codes.append(taxonomy_code)
                    specialty_desc = get_specialty_description(taxonomy_code)
                    specialties.append(specialty_desc)
            
            # Check if any specialty matches the determined specialty
            specialty_matches = any(
                specialty_lower in specialty.lower() or 
                specialty.lower() in specialty_lower
                for specialty in specialties
            )
            
            if specialty_matches:
                # Get the primary specialty for display
                primary_specialty = get_specialty_description(provider.healthcare_provider_taxonomy_code_1)
                
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
                    "yearsExperience": None,  # No experience data available
                    "boardCertified": None,  # No certification data available
                    "acceptingPatients": True,  # Default to accepting patients
                    "languages": [],  # No language data available
                    "insurance": [],  # No insurance data available
                    "education": {
                        "medicalSchool": None,  # No medical school data available
                        "graduationYear": None,  # No graduation year data available
                        "residency": None  # No residency data available
                    }
                }
                filtered_providers.append(formatted_provider)
        
        # Apply limit after filtering
        if limit and len(filtered_providers) > limit:
            filtered_providers = filtered_providers[:limit]
        
        return {
            "total_providers": len(filtered_providers),
            "providers": filtered_providers,
            "search_criteria": {
                "state": state,
                "city": city,
                "diagnosis": diagnosis,
                "determined_specialty": determined_specialty
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
        '208C00000X': 'Colon & Rectal Surgery',
        '208D00000X': 'General Practice',
        '208G00000X': 'Thoracic Surgery',
        '208M00000X': 'Hospitalist',
        '208U00000X': 'Clinical Pharmacology',
        '208VP0000X': 'Pain Medicine',
        '208VP0014X': 'Interventional Pain Medicine',
        '208D00000X': 'General Practice',
        '208G00000X': 'Thoracic Surgery',
        '208M00000X': 'Hospitalist',
        '208U00000X': 'Clinical Pharmacology',
        '208VP0000X': 'Pain Medicine',
        '208VP0014X': 'Interventional Pain Medicine'
    }
    return specialty_map.get(taxonomy_code, 'Medical Specialist')
