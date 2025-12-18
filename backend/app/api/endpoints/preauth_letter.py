"""
Pre-authorization Letter Endpoint

This endpoint generates pre-authorization letters for insurance companies
using GPT, incorporating doctor qualifications and patient diagnosis information.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from ...database import get_db
from ...services.preauth_letter_service import PreAuthLetterService
import logging
import json

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class PreAuthLetterRequest(BaseModel):
    """Request model for pre-authorization letter generation."""
    provider_info: dict  # Provider information including name, npi, specialty, publications, etc.
    patient_diagnosis: str
    patient_symptoms: Optional[str] = None
    specificity_relevance: Optional[dict] = None  # Specificity/relevance data from scoreData

@router.post("/preauth-letter")
async def generate_preauth_letter(
    request: PreAuthLetterRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a pre-authorization letter for insurance approval.
    
    This endpoint uses GPT to generate a professional pre-authorization letter
    that includes:
    - Provider qualifications (publications, clinical volume, education, experience)
    - Patient diagnosis and symptoms
    - Specificity/relevance of the provider to the patient's condition
    """
    try:
        logger.info("🚀 [Backend] Pre-authorization letter endpoint called")
        logger.info(f"📝 [Backend] Provider NPI: {request.provider_info.get('npi', 'N/A')}")
        logger.info(f"📝 [Backend] Patient diagnosis: {request.patient_diagnosis}")
        
        # Initialize the pre-authorization letter service
        preauth_service = PreAuthLetterService()
        
        # Generate the letter
        logger.info("📝 [Backend] Generating pre-authorization letter...")
        letter = await preauth_service.generate_preauth_letter(
            provider_info=request.provider_info,
            patient_diagnosis=request.patient_diagnosis,
            patient_symptoms=request.patient_symptoms,
            specificity_relevance=request.specificity_relevance
        )
        
        logger.info("✅ [Backend] Pre-authorization letter generated successfully")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "letter": letter,
                "message": "Pre-authorization letter generated successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ [Backend] Error generating pre-authorization letter: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating pre-authorization letter: {str(e)}")

