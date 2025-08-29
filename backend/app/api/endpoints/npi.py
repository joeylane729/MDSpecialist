import logging
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from ...database import get_db
from ...services.medical_analysis_service import MedicalAnalysisService
import PyPDF2
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

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
    diagnosis: str = Form(...),
    symptoms: str = Form(...),
    limit: int = Form(20),
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
            determined_specialty = "Internal Medicine"  # Fallback specialty
        
        print(f"GPT determined specialty: '{determined_specialty}'")
        
        # Use GPT to predict both primary and differential diagnoses from the combined input
        print(f"Using GPT to predict diagnoses for combined input: '{combined_input[:200]}...'")
        predicted_diagnoses = await gpt_service.predict_diagnoses(combined_input)
        
        predicted_icd10 = None
        icd10_description = None
        differential_diagnoses = []
        
        if predicted_diagnoses:
            print(f"GPT predicted diagnoses: {predicted_diagnoses}")
            
            # Extract primary diagnosis
            if 'primary' in predicted_diagnoses and 'code' in predicted_diagnoses['primary']:
                predicted_icd10 = predicted_diagnoses['primary']['code']
                icd10_description = predicted_diagnoses['primary'].get('description', 'Description not available')
                print(f"Primary diagnosis: {predicted_icd10} - {icd10_description}")
            
            # Extract differential diagnoses
            if 'differential' in predicted_diagnoses:
                differential_diagnoses = predicted_diagnoses['differential']
                print(f"Found {len(differential_diagnoses)} differential diagnoses")
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
                ORDER BY provider_last_name, provider_first_name
                LIMIT {limit}
            """
            
            result = db.execute(text(sql))
            providers = result.fetchall()
        
        filtered_providers = []
        for provider in providers:
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
        
        print(f"Database filtering results: {len(filtered_providers)} providers found for specialty '{determined_specialty}'")
        
        return {
            "total_providers": len(filtered_providers),
            "providers": filtered_providers,
            "search_criteria": {
                "state": state,
                "city": city,
                "diagnosis": diagnosis,
                "determined_specialty": determined_specialty,
                "predicted_icd10": predicted_icd10,
                "icd10_description": icd10_description,
                "differential_diagnoses": differential_diagnoses
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
