from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from dataclasses import asdict
from ...database import get_db
from ...services.specialist_recommendation_service import SpecialistRecommendationService
from ..utils.patient_input_processor import build_patient_input
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

def parse_optional_json(json_str: Optional[str]) -> Optional[Any]:
    """Parse optional JSON string, return None on failure."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

@router.post("/specialist-recommendations")
async def get_specialist_recommendations(
    diagnosis: str = Form(...),
    state: Optional[str] = Form(None),
    cpt_codes_json: str = Form(...),  # Required JSON string of CPT codes (must be generated first)
    treatment_options_json: str = Form(...),  # Required JSON string of treatment options from medical analysis
    predicted_icd10: str = Form(...),  # Required pre-determined ICD-10 code from medical analysis
    search_query: str = Form(...),  # Required pre-generated search query from medical analysis
    icd10_description: Optional[str] = Form(None),  # Optional ICD-10 description from medical analysis
    determined_specialty: Optional[str] = Form(None),  # Optional pre-determined specialty from medical analysis
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered specialist recommendations.
    
    This endpoint processes patient information and returns intelligent
    specialist recommendations based on specialist data analysis.
    
    Args:
        cpt_codes_json: Required JSON string of CPT codes (must be generated first via /medical-analysis/cpt-codes).
        treatment_options_json: Required JSON string of treatment options from medical analysis step.
        predicted_icd10: Required ICD-10 code from medical analysis step.
        search_query: Required pre-generated search query from medical analysis step.
        icd10_description: Optional ICD-10 description from medical analysis step.
        determined_specialty: Optional pre-determined specialty from medical analysis step.
    """
    try:
        # Parse required CPT codes
        try:
            cpt_codes = json.loads(cpt_codes_json)
            if not isinstance(cpt_codes, list) or len(cpt_codes) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="cpt_codes_json must be a non-empty JSON array"
                )
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cpt_codes_json: {str(e)}"
            )
        
        # Parse required treatment options
        try:
            treatment_options = json.loads(treatment_options_json)
            if not isinstance(treatment_options, list) or len(treatment_options) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="treatment_options_json must be a non-empty JSON array"
                )
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid treatment_options_json: {str(e)}"
            )
        
        # Build patient input (only diagnosis needed)
        patient_input = await build_patient_input(
            diagnosis=diagnosis,
            files=files
        )
        
        # Get specialist recommendations
        specialist_service = SpecialistRecommendationService(db)
        recommendations = await specialist_service.get_specialist_recommendations(
            patient_input=patient_input,
            cpt_codes=cpt_codes,
            treatment_options=treatment_options,
            predicted_icd10=predicted_icd10,
            search_query=search_query,
            state=state,
            icd10_description=icd10_description,
            determined_specialty=determined_specialty
        )
        
        # Convert dataclass to dict and format datetime
        recommendations_dict = asdict(recommendations)
        if 'timestamp' in recommendations_dict and recommendations_dict['timestamp']:
            recommendations_dict['timestamp'] = recommendations_dict['timestamp'].isoformat()
        
        return JSONResponse(content=recommendations_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting specialist recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get specialist recommendations"
        )