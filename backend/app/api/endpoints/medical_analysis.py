"""
Medical Analysis Endpoint

This endpoint provides medical analysis including diagnosis prediction, ICD-10 coding,
and treatment options without specialist retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.medical_analysis_service import MedicalAnalysisService
from ..utils.patient_input_processor import build_patient_input
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/medical-analysis")
async def get_medical_analysis(
    symptoms: str = Form(...),
    diagnosis: str = Form(...),
    medical_history: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
    surgical_history: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    custom_diagnoses_prompt: Optional[str] = Form(None),  # Optional custom prompt for diagnosis/treatment generation
    db: Session = Depends(get_db)
):
    """
    Get medical analysis including diagnosis prediction, ICD-10 coding, and treatment options.
    
    This endpoint provides comprehensive medical analysis without specialist retrieval.
    """
    try:
        # Build patient input from form data and files
        patient_input = await build_patient_input(
            symptoms=symptoms,
            diagnosis=diagnosis,
            medical_history=medical_history,
            medications=medications,
            surgical_history=surgical_history,
            files=files
        )
        
        # Initialize service and perform analysis
        medical_analysis_service = MedicalAnalysisService(db)
        analysis_results = await medical_analysis_service.comprehensive_analysis(
            patient_input, 
            custom_diagnoses_prompt=custom_diagnoses_prompt
        )
        
        return analysis_results
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        logger.error(f"Error in medical analysis endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Medical analysis failed: {str(e)}"
        )


@router.post("/medical-analysis/cpt-codes")
async def generate_cpt_codes(
    search_query: str = Form(...),
    treatment_options_json: str = Form(...),  # JSON array of treatment options
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    db: Session = Depends(get_db)
):
    """
    Generate CPT codes based on search query and treatment options.
    
    This endpoint is called separately after the initial medical analysis to generate CPT codes.
    It requires the search_query and treatment_options from the previous step.
    """
    try:
        # Parse treatment options JSON
        try:
            treatment_options = json.loads(treatment_options_json)
            if not isinstance(treatment_options, list):
                raise ValueError("treatment_options_json must be a JSON array")
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid treatment_options_json: {str(e)}"
            )
        
        # Initialize service and generate CPT codes
        medical_analysis_service = MedicalAnalysisService(db)
        cpt_codes, cpt_prompt_text = await medical_analysis_service.generate_cpt_codes_from_analysis(
            search_query=search_query,
            treatment_options=treatment_options,
            custom_prompt=custom_prompt
        )
        
        return {
            "cpt_codes": cpt_codes,
            "cpt_prompt_text": cpt_prompt_text,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating CPT codes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating CPT codes: {str(e)}"
        )
