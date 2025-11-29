"""
Medical Analysis Endpoint

This endpoint provides medical analysis including diagnosis prediction, ICD-10 coding,
and treatment options without specialist retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.medical_analysis_service import MedicalAnalysisService
from ..utils.patient_input_processor import build_patient_input, log_endpoint_call, log_response_info
import logging
import json

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
        
        # Get medical analysis (CPT codes are not generated here - they must be generated separately)
        logger.info("🧠 [Backend] Starting comprehensive analysis")
        analysis_results = await medical_analysis_service.comprehensive_analysis(patient_input)
        logger.info("✅ [Backend] Comprehensive analysis completed")
        
        # Log response information
        log_response_info("Medical analysis", analysis_results)
        
        # Log response size and structure for debugging
        try:
            response_size = len(json.dumps(analysis_results))
            logger.info(f"📊 [Backend] Analysis results size: {response_size} bytes")
            logger.debug(f"📊 [Backend] Analysis results keys: {list(analysis_results.keys()) if isinstance(analysis_results, dict) else 'Not a dict'}")
        except Exception as e:
            logger.warning(f"⚠️ [Backend] Could not calculate response size: {e}")
        
        response = {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
        # Validate response is JSON serializable before returning
        try:
            json.dumps(response)  # Test serialization
            logger.info("📤 [Backend] Medical analysis endpoint returning response (validated JSON serializable)")
        except (TypeError, ValueError) as json_error:
            logger.error(f"❌ [Backend] Response is not JSON serializable: {json_error}")
            logger.error(f"❌ [Backend] Problematic data: {str(response)[:500]}")
            raise HTTPException(status_code=500, detail=f"Response serialization error: {str(json_error)}")
        
        # Use JSONResponse to ensure proper serialization and headers
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"❌ [Backend] Error in medical analysis: {str(e)}")
        logger.error(f"❌ [Backend] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [Backend] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in medical analysis: {str(e)}")


@router.post("/medical-analysis/cpt-codes")
async def generate_cpt_codes(
    search_query: str = Form(...),
    treatment_options_json: str = Form(...),  # JSON array of treatment options
    db: Session = Depends(get_db)
):
    """
    Generate CPT codes based on search query and treatment options.
    
    This endpoint is called separately after the initial medical analysis to generate CPT codes.
    It requires the search_query and treatment_options from the previous step.
    """
    try:
        logger.info("🚀 [Backend] CPT code generation endpoint called")
        logger.info(f"🔍 [Backend] Search query: {search_query[:100]}{'...' if len(search_query) > 100 else ''}")
        
        # Parse treatment options JSON
        try:
            treatment_options = json.loads(treatment_options_json)
            if not isinstance(treatment_options, list):
                raise ValueError("treatment_options_json must be a JSON array")
            logger.info(f"📋 [Backend] Received {len(treatment_options)} treatment options")
        except json.JSONDecodeError as e:
            logger.error(f"❌ [Backend] Failed to parse treatment_options_json: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid treatment_options_json: {str(e)}")
        
        # Initialize the medical analysis service with database session
        medical_analysis_service = MedicalAnalysisService(db)
        
        # Generate CPT codes
        logger.info("🔍 [Backend] Generating CPT codes...")
        cpt_codes, cpt_prompt_text = await medical_analysis_service.generate_cpt_codes_from_analysis(
            search_query=search_query,
            treatment_options=treatment_options
        )
        logger.info(f"✅ [Backend] Generated {len(cpt_codes)} CPT codes")
        
        response = {
            "status": "success",
            "cpt_codes": cpt_codes,
            "cpt_prompt_text": cpt_prompt_text,
            "message": f"Successfully generated {len(cpt_codes)} CPT codes"
        }
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [Backend] Error generating CPT codes: {str(e)}")
        logger.error(f"❌ [Backend] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [Backend] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating CPT codes: {str(e)}")
