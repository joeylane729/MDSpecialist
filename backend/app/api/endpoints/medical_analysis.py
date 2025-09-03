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
        logger.info("🔍 DEBUG: Medical analysis endpoint called")
        logger.info(f"🔍 DEBUG: Symptoms: {symptoms}")
        logger.info(f"🔍 DEBUG: Diagnosis: {diagnosis}")
        
        # Initialize the medical analysis service with database session
        medical_analysis_service = MedicalAnalysisService(db)
        
        # Combine all patient information into a single input
        patient_input = f"Symptoms: {symptoms}\n\nDiagnosis: {diagnosis}"
        
        if medical_history:
            patient_input += f"\n\nMedical History: {medical_history}"
        if medications:
            patient_input += f"\n\nCurrent Medications: {medications}"
        if surgical_history:
            patient_input += f"\n\nSurgical History: {surgical_history}"
        
        # Process uploaded files (if any)
        if files:
            patient_input += "\n\nAdditional Information from Files:"
            for file in files:
                if file.content_type == "application/pdf":
                    try:
                        # For now, just note that files were uploaded
                        # In a full implementation, you'd extract text from PDFs
                        patient_input += f"\n- {file.filename} (PDF uploaded)"
                    except Exception as e:
                        logger.warning(f"Could not process file {file.filename}: {e}")
        
        # Get medical analysis
        analysis_results = await medical_analysis_service.comprehensive_analysis(patient_input)
        
        # Debug logging for response
        logger.info("🔍 DEBUG: Medical analysis endpoint returning response")
        logger.info(f"🔍 DEBUG: Analysis results keys: {list(analysis_results.keys())}")
        if "treatment_options" in analysis_results:
            logger.info(f"🔍 DEBUG: Found {len(analysis_results['treatment_options'])} treatment options")
        else:
            logger.info("🔍 DEBUG: No treatment options found")
        
        return {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in medical analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in medical analysis: {str(e)}")
