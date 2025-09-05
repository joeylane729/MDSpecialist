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
from ..utils.patient_input_processor import build_patient_input, log_endpoint_call, log_response_info
import logging

# Set up logging
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
    db: Session = Depends(get_db)
):
    """
    Get medical analysis including diagnosis prediction, ICD-10 coding, and treatment options.
    
    This endpoint provides comprehensive medical analysis without specialist retrieval.
    """
    try:
        # Log endpoint call
        log_endpoint_call("Medical analysis", symptoms, diagnosis)
        
        # Initialize the medical analysis service with database session
        medical_analysis_service = MedicalAnalysisService(db)
        
        # Build patient input using shared utility
        patient_input = await build_patient_input(
            symptoms=symptoms,
            diagnosis=diagnosis,
            medical_history=medical_history,
            medications=medications,
            surgical_history=surgical_history,
            files=files
        )
        
        # Get medical analysis
        analysis_results = await medical_analysis_service.comprehensive_analysis(patient_input)
        
        # Log response information
        log_response_info("Medical analysis", analysis_results)
        
        return {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in medical analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in medical analysis: {str(e)}")
