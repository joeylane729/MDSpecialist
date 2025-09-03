from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.langchain_specialist_recommendation_service import LangChainSpecialistRecommendationService
from ...schemas.specialist_recommendation import SpecialistRecommendationRequestSchema, RecommendationResponseSchema
from ..utils.patient_input_processor import build_patient_input, log_endpoint_call, log_response_info
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/specialist-recommendations", response_model=RecommendationResponseSchema)
async def get_specialist_recommendations(
    symptoms: str = Form(...),
    diagnosis: str = Form(...),
    medical_history: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
    surgical_history: Optional[str] = Form(None),

    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered specialist recommendations using LangChain.
    
    This endpoint processes patient information and returns intelligent
    specialist recommendations based on Pinecone data analysis.
    """
    try:
        # Log endpoint call
        log_endpoint_call("Specialist recommendations", symptoms, diagnosis)
        
        # Initialize the LangChain service with database session
        langchain_service = LangChainSpecialistRecommendationService(db)
        
        # Build patient input using shared utility
        patient_input = build_patient_input(
            symptoms=symptoms,
            diagnosis=diagnosis,
            medical_history=medical_history,
            medications=medications,
            surgical_history=surgical_history,
            files=files
        )
        
        # Get recommendations
        recommendations = await langchain_service.get_specialist_recommendations(
            patient_input=patient_input
        )
        
        # Log response information
        log_response_info("Specialist recommendations", recommendations)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error getting specialist recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get specialist recommendations: {str(e)}"
        )