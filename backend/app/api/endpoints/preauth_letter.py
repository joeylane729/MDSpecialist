"""
Pre-authorization Letter Endpoint

This endpoint generates pre-authorization letters for insurance companies
using GPT, incorporating doctor qualifications and patient diagnosis information.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from ...database import get_db
from ...services.preauth_letter_service import PreAuthLetterService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class PreAuthLetterRequest(BaseModel):
    """Request model for pre-authorization letter generation."""
    provider_info: dict  # Provider information including name, npi, specialty, publications, etc.
    patient_diagnosis: str
    patient_symptoms: Optional[str] = None
    specificity_relevance: Optional[dict] = None  # Specificity/relevance data from scoreData
    user_first_name: Optional[str] = ""
    user_last_name: Optional[str] = ""
    insurance_company_name: Optional[str] = ""
    insurance_company_email: Optional[str] = ""
    custom_prompt: Optional[str] = None  # Custom prompt text if user wants to edit and re-run

@router.post("/preauth-letter")
async def generate_preauth_letter(
    request: PreAuthLetterRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a pre-authorization letter for insurance approval.
    
    Uses GPT to generate a professional pre-authorization letter that includes:
    - Provider qualifications (publications, clinical volume, education, experience)
    - Patient diagnosis and symptoms
    - Specificity/relevance of the provider to the patient's condition
    """
    try:
        preauth_service = PreAuthLetterService()
        letter, prompt_text = await preauth_service.generate_preauth_letter(
            provider_info=request.provider_info,
            patient_diagnosis=request.patient_diagnosis,
            patient_symptoms=request.patient_symptoms,
            specificity_relevance=request.specificity_relevance,
            user_first_name=request.user_first_name,
            user_last_name=request.user_last_name,
            insurance_company_name=request.insurance_company_name,
            insurance_company_email=request.insurance_company_email,
            custom_prompt=request.custom_prompt
        )
        
        return {
            "status": "success",
            "letter": letter,
            "prompt_text": prompt_text,
            "message": "Pre-authorization letter generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error generating pre-authorization letter: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating pre-authorization letter")

