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
        logger.info("🚀 [Backend] Medical analysis endpoint called")
        logger.info(f"📝 [Backend] Received data: symptoms='{symptoms}', diagnosis='{diagnosis}'")
        logger.info(f"📝 [Backend] Optional fields: medical_history='{medical_history}', medications='{medications}', surgical_history='{surgical_history}'")
        logger.info(f"📁 [Backend] Files received: {len(files)} files")
        
        # Log endpoint call
        log_endpoint_call("Medical analysis", symptoms, diagnosis)
        
        # Initialize the medical analysis service with database session
        logger.info("🔧 [Backend] Initializing MedicalAnalysisService")
        medical_analysis_service = MedicalAnalysisService(db)
        
        # Build patient input using shared utility
        logger.info("📋 [Backend] Building patient input")
        patient_input = await build_patient_input(
            symptoms=symptoms,
            diagnosis=diagnosis,
            medical_history=medical_history,
            medications=medications,
            surgical_history=surgical_history,
            files=files
        )
        logger.info(f"📋 [Backend] Patient input built: {len(patient_input)} characters")
        
        # Get medical analysis
        logger.info("🧠 [Backend] Starting comprehensive analysis")
        analysis_results = await medical_analysis_service.comprehensive_analysis(patient_input)
        logger.info("✅ [Backend] Comprehensive analysis completed")
        
        # Log response information
        log_response_info("Medical analysis", analysis_results)
        
        response = {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
        logger.info("📤 [Backend] Medical analysis endpoint returning response")
        return response
        
    except Exception as e:
        logger.error(f"❌ [Backend] Error in medical analysis: {str(e)}")
        logger.error(f"❌ [Backend] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [Backend] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in medical analysis: {str(e)}")
