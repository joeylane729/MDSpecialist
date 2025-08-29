"""
NPI Provider Ranking Endpoint

This endpoint takes NPI providers and patient information, then uses LangChain
to rank the providers based on Pinecone specialist data.
"""

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ...database import get_db
from ...services.langchain_specialist_recommendation_service import LangChainSpecialistRecommendationService
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/rank-npi-providers")
async def rank_npi_providers(
    npi_providers: str = Form(...),
    patient_input: str = Form(...),
    shared_specialist_information: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Rank NPI providers based on Pinecone specialist information.
    
    Args:
        npi_providers: List of NPI provider dictionaries
        patient_input: Patient description for medical analysis
        
    Returns:
        List of NPI numbers in ranked order (most relevant first)
    """
    try:
        # Parse the JSON strings
        import json
        npi_providers_list = json.loads(npi_providers)
        
        # Parse shared Pinecone data if provided
        shared_data = None
        if shared_specialist_information:
            shared_data = json.loads(shared_specialist_information)
        
        # Initialize the LangChain service
        langchain_service = LangChainSpecialistRecommendationService(db)
        
        # Rank the NPI providers using shared data if available
        ranking_result = await langchain_service.rank_npi_providers_with_pinecone(
            npi_providers=npi_providers_list,
            patient_input=patient_input,
            shared_specialist_information=shared_data
        )
        
        ranked_npis = ranking_result['ranking']
        explanation = ranking_result['explanation']
        provider_links = ranking_result.get('provider_links', {})
        
        return {
            "status": "success",
            "ranked_npis": ranked_npis,
            "explanation": explanation,
            "provider_links": provider_links,
            "total_providers": len(ranked_npis),
            "message": f"Successfully ranked {len(ranked_npis)} NPI providers"
        }
        
    except Exception as e:
        logger.error(f"Error ranking NPI providers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error ranking NPI providers: {str(e)}")
