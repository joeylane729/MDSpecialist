from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from ...database import get_db

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

@router.get("/search-providers")
async def search_providers_by_criteria(
    state: str = Query(..., description="State code (e.g., NY, CA)"),
    city: str = Query(..., description="City name"),
    taxonomy: str = Query(..., description="Taxonomy code"),
    limit: int = Query(20, le=500, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Search for providers by city, state, and taxonomy."""
    try:
        # Build the SQL query to search the npi_providers table
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
              AND (
                healthcare_provider_taxonomy_code_1 = :taxonomy OR
                healthcare_provider_taxonomy_code_2 = :taxonomy OR
                healthcare_provider_taxonomy_code_3 = :taxonomy OR
                healthcare_provider_taxonomy_code_4 = :taxonomy OR
                healthcare_provider_taxonomy_code_5 = :taxonomy OR
                healthcare_provider_taxonomy_code_6 = :taxonomy OR
                healthcare_provider_taxonomy_code_7 = :taxonomy OR
                healthcare_provider_taxonomy_code_8 = :taxonomy OR
                healthcare_provider_taxonomy_code_9 = :taxonomy OR
                healthcare_provider_taxonomy_code_10 = :taxonomy OR
                healthcare_provider_taxonomy_code_11 = :taxonomy OR
                healthcare_provider_taxonomy_code_12 = :taxonomy OR
                healthcare_provider_taxonomy_code_13 = :taxonomy OR
                healthcare_provider_taxonomy_code_14 = :taxonomy OR
                healthcare_provider_taxonomy_code_15 = :taxonomy
              )
              AND entity_type_code = '1'  -- Individual providers only
            ORDER BY provider_last_name, provider_first_name
            LIMIT :limit
        """
        
        result = db.execute(text(sql), {
            "state": state,
            "city": city,
            "taxonomy": taxonomy,
            "limit": limit
        })
        
        providers = result.fetchall()
        
        # Transform the results into a more user-friendly format
        formatted_providers = []
        for provider in providers:
            # Get the specialty description from the taxonomy code
            specialty = get_specialty_description(provider.healthcare_provider_taxonomy_code_1)
            
            formatted_provider = {
                "id": provider.npi,  # Use NPI as ID
                "npi": provider.npi,
                "name": f"{provider.provider_first_name or ''} {provider.provider_last_name or ''}".strip(),
                "specialty": specialty,
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
            formatted_providers.append(formatted_provider)
        
        return {
            "total_providers": len(formatted_providers),
            "providers": formatted_providers,
            "search_criteria": {
                "state": state,
                "city": city,
                "taxonomy": taxonomy
            }
        }
        
    except Exception as e:
        print(f"Error searching providers: {e}")
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
        '208000000X': 'Pediatrics'
    }
    return specialty_map.get(taxonomy_code, 'Medical Specialist')
