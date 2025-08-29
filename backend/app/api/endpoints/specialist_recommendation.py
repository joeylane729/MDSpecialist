from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.langchain_specialist_recommendation_service import LangChainSpecialistRecommendationService
from ...schemas.specialist_recommendation import SpecialistRecommendationRequestSchema, RecommendationResponseSchema
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
    max_recommendations: int = Form(50),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered specialist recommendations using LangChain.
    
    This endpoint processes patient information and returns intelligent
    specialist recommendations based on Pinecone data analysis.
    """
    try:
        # Initialize the LangChain service with database session
        langchain_service = LangChainSpecialistRecommendationService(db)
        
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
        
        # Get recommendations
        recommendations = await langchain_service.get_specialist_recommendations(
            patient_input=patient_input,
            max_recommendations=max_recommendations
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error getting specialist recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get specialist recommendations: {str(e)}"
        )