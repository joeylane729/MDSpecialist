from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from dataclasses import asdict
from ...database import get_db
from ...services.specialist_recommendation_service import SpecialistRecommendationService
from ...schemas.specialist_recommendation import SpecialistRecommendationRequestSchema, RecommendationResponseSchema
from ..utils.patient_input_processor import build_patient_input, log_endpoint_call, log_response_info
import logging
import json

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/specialist-recommendations")
async def get_specialist_recommendations(
    symptoms: str = Form(...),
    diagnosis: str = Form(...),
    medical_history: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
    surgical_history: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    cpt_codes_json: Optional[str] = Form(None),  # Optional JSON string of CPT codes to reuse
    treatment_options_json: Optional[str] = Form(None),  # Optional JSON string of treatment options to reuse
    predicted_icd10: Optional[str] = Form(None),  # Optional pre-determined ICD-10 code to reuse
    icd10_description: Optional[str] = Form(None),  # Optional pre-determined ICD-10 description to reuse
    search_query: Optional[str] = Form(None),  # Optional pre-generated search query to reuse
    determined_specialty: Optional[str] = Form(None),  # Optional pre-determined specialty to reuse
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered specialist recommendations.
    
    This endpoint processes patient information and returns intelligent
    specialist recommendations based on specialist data analysis.
    
    Args:
        cpt_codes_json: Optional JSON string of CPT codes to reuse from previous medical analysis.
                       This avoids duplicate GPT calls for CPT code prediction.
                       Format: [{"code": "12345", "description": "..."}, ...]
        treatment_options_json: Optional JSON string of treatment options to reuse from previous medical analysis.
                                Format: [{"name": "...", "outcomes": "...", "complications": "...", "category": "..."}, ...]
        predicted_icd10: Optional pre-determined ICD-10 code from previous medical analysis.
        icd10_description: Optional pre-determined ICD-10 description from previous medical analysis.
        search_query: Optional pre-generated search query from previous medical analysis.
        determined_specialty: Optional pre-determined specialty from previous medical analysis.
    """
    try:
        # Log endpoint call
        logger.info("🚀 [Backend] /api/v1/specialist-recommendations endpoint called")
        logger.info(f"🔍 [Backend] State parameter received: {state}")
        log_endpoint_call("Specialist recommendations", symptoms, diagnosis)
        
        # Parse optional CPT codes if provided
        cpt_codes = None
        if cpt_codes_json:
            try:
                cpt_codes = json.loads(cpt_codes_json)
                logger.info(f"♻️  [Backend] Received {len(cpt_codes)} pre-generated CPT codes to reuse")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  [Backend] Failed to parse CPT codes JSON: {e}. Will generate new CPT codes.")
        
        # Parse optional treatment options if provided
        treatment_options = None
        if treatment_options_json:
            try:
                treatment_options = json.loads(treatment_options_json)
                logger.info(f"♻️  [Backend] Received {len(treatment_options)} pre-generated treatment options to reuse")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  [Backend] Failed to parse treatment options JSON: {e}.")
        
        # Log medical analysis results being reused
        if predicted_icd10:
            logger.info(f"♻️  [Backend] Received pre-generated predicted_icd10: {predicted_icd10}")
        if icd10_description:
            logger.info(f"♻️  [Backend] Received pre-generated icd10_description")
        if search_query:
            logger.info(f"♻️  [Backend] Received pre-generated search_query")
        if determined_specialty:
            logger.info(f"♻️  [Backend] Received pre-generated determined_specialty: {determined_specialty}")
        
        # Initialize the specialist recommendation service with database session
        specialist_service = SpecialistRecommendationService(db)
        
        # Build patient input using shared utility (still needed for specialist information retrieval service)
        patient_input = await build_patient_input(
            symptoms=symptoms,
            diagnosis=diagnosis,
            medical_history=medical_history,
            medications=medications,
            surgical_history=surgical_history,
            files=files
        )
        
        # Get recommendations - pass medical analysis results to avoid re-running analysis
        recommendations = await specialist_service.get_specialist_recommendations(
            patient_input=patient_input,
            state=state,
            cpt_codes=cpt_codes,
            treatment_options=treatment_options,
            predicted_icd10=predicted_icd10,
            icd10_description=icd10_description,
            search_query=search_query,
            determined_specialty=determined_specialty
        )
        
        # Log response information
        logger.info("Python type of recommendations: %s", type(recommendations))
        logger.info("🔍 DEBUG: cms_data in recommendations: %s", hasattr(recommendations, 'cms_data'))
        if hasattr(recommendations, 'cms_data'):
            logger.info("🔍 DEBUG: cms_data value: %s", recommendations.cms_data)
            if recommendations.cms_data:
                logger.info("🔍 DEBUG: cms_data keys: %s", recommendations.cms_data.keys() if isinstance(recommendations.cms_data, dict) else "not a dict")
        
        # Log search_query information
        logger.info("🔍 DEBUG: search_query in recommendations: %s", hasattr(recommendations, 'search_query'))
        if hasattr(recommendations, 'search_query'):
            search_query_value = recommendations.search_query
            logger.info("🔍 DEBUG: search_query value: %s", search_query_value[:150] + '...' if search_query_value and len(search_query_value) > 150 else search_query_value or 'EMPTY/NONE')
        
        # Log patient_profile.search_query
        if hasattr(recommendations, 'patient_profile') and isinstance(recommendations.patient_profile, dict):
            patient_profile_sq = recommendations.patient_profile.get('search_query', 'NOT FOUND')
            logger.info("🔍 DEBUG: patient_profile.search_query: %s", patient_profile_sq[:150] + '...' if patient_profile_sq and isinstance(patient_profile_sq, str) and len(patient_profile_sq) > 150 else patient_profile_sq)
        
        # Convert dataclass to dict for serialization
        # This ensures all fields including cms_data are serialized
        recommendations_dict = asdict(recommendations)
        
        # Convert datetime to ISO format string for JSON serialization
        if 'timestamp' in recommendations_dict and recommendations_dict['timestamp']:
            recommendations_dict['timestamp'] = recommendations_dict['timestamp'].isoformat()
        
        logger.info("🔍 DEBUG: Converted to dict, cms_data present: %s", 'cms_data' in recommendations_dict)
        logger.info("✅ [Backend] /api/v1/specialist-recommendations returning response")
        log_response_info("Specialist recommendations", recommendations)
        
        # Return JSONResponse directly to bypass FastAPI's Pydantic validation
        # which was dropping the cms_data field
        return JSONResponse(content=recommendations_dict)
        
    except Exception as e:
        logger.error(f"Error getting specialist recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get specialist recommendations: {str(e)}"
        )