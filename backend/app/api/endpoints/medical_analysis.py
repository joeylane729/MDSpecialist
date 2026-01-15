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
from ..utils.patient_input_processor import extract_pdf_content
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/medical-analysis")
async def get_medical_analysis(
    diagnosis: str = Form(...),
    files: List[UploadFile] = File([]),
    custom_diagnoses_prompt: Optional[str] = Form(None),  # Optional custom prompt for diagnosis/treatment generation
    custom_search_query_prompt: Optional[str] = Form(None),  # Optional custom prompt for search query generation
    db: Session = Depends(get_db)
):
    """
    Get medical analysis including diagnosis prediction, ICD-10 coding, and treatment options.
    
    This endpoint provides comprehensive medical analysis without specialist retrieval.
    """
    try:
        # Extract PDF content from uploaded files
        pdf_content = await extract_pdf_content(files)
        
        # Initialize service and perform analysis
        medical_analysis_service = MedicalAnalysisService(db)
        analysis_results = await medical_analysis_service.comprehensive_analysis(
            diagnosis=diagnosis,
            medical_history="",
            medications="",
            surgical_history="",
            pdf_content=pdf_content,
            custom_diagnoses_prompt=custom_diagnoses_prompt,
            custom_search_query_prompt=custom_search_query_prompt
        )
        
        # Wrap response in expected structure for frontend
        return {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        logger.error(f"Error in medical analysis endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Medical analysis failed: {str(e)}"
        )


@router.post("/medical-analysis/search-query")
async def generate_search_query(
    icd10_description: str = Form(...),
    user_diagnosis: str = Form(...),
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    db: Session = Depends(get_db)
):
    """
    Generate search query based on ICD-10 description and user diagnosis.
    
    This endpoint is called separately after the initial medical analysis to regenerate the search query.
    It requires the icd10_description and user_diagnosis from the previous step.
    """
    try:
        # Initialize service and generate search query
        medical_analysis_service = MedicalAnalysisService(db)
        search_query, search_query_prompt_text = await medical_analysis_service.generate_search_query(
            icd10_description=icd10_description,
            user_diagnosis=user_diagnosis,
            custom_prompt=custom_prompt
        )
        
        return {
            "search_query": search_query,
            "search_query_prompt_text": search_query_prompt_text,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating search query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating search query: {str(e)}"
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
