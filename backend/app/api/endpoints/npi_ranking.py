"""
NPI Provider Ranking Endpoint

This endpoint takes NPI providers and patient information, then uses LangChain
to rank the providers based on Pinecone specialist data.
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ...database import get_db
from ...services.langchain_specialist_recommendation_service import LangChainSpecialistRecommendationService
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

class NPIRankingRequest(BaseModel):
    npi_providers: List[Dict[str, Any]]
    patient_input: str
    shared_specialist_information: Optional[Dict[str, Any]] = None
    cms_data: Optional[Dict[str, Any]] = None  # CMS data for clinical volume bonus

@router.post("/rank-npi-providers")
async def rank_npi_providers(
    request: NPIRankingRequest = Body(...),
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
    logger.info("🔍 [NPI Ranking] ===== ENDPOINT CALLED =====")
    logger.info(f"📝 [NPI Ranking] Patient input length: {len(request.patient_input) if request.patient_input else 0} chars")
    logger.info(f"📥 [NPI Ranking] Received {len(request.npi_providers)} NPI providers")
    
    try:
        # Get shared Pinecone data if provided
        shared_data = request.shared_specialist_information
        if shared_data:
            if isinstance(shared_data, dict):
                logger.info(f"📊 [NPI Ranking] Received dict with {len(shared_data)} treatment groups: {list(shared_data.keys())}")
            elif isinstance(shared_data, list):
                logger.info(f"📊 [NPI Ranking] Received list with {len(shared_data)} items")
            else:
                logger.warning(f"⚠️ [NPI Ranking] Unexpected type: {type(shared_data)}")
        else:
            logger.info("⚠️ [NPI Ranking] No shared specialist information provided")
        
        # Extract top 25 NPIs from CMS results for clinical volume bonus
        top_cms_npis = None
        if request.cms_data and isinstance(request.cms_data, dict):
            cms_providers = request.cms_data.get('results', [])
            if cms_providers and isinstance(cms_providers, list):
                # Extract NPIs from top 25 CMS providers (already sorted by total services)
                top_cms_npis = set()
                for provider in cms_providers[:25]:  # Top 25 providers
                    npi = provider.get('Rndrng_NPI')
                    if npi:
                        top_cms_npis.add(str(npi))  # Normalize to string for comparison
                if top_cms_npis:
                    logger.info(f"🏥 [NPI Ranking] Extracted {len(top_cms_npis)} NPIs from top 25 CMS results for clinical volume bonus")
        
        # Initialize the LangChain service
        langchain_service = LangChainSpecialistRecommendationService(db)
        
        # Rank the NPI providers using shared data if available
        ranking_result = await langchain_service.rank_npi_providers_with_pinecone(
            npi_providers=request.npi_providers,
            patient_input=request.patient_input,
            shared_specialist_information=shared_data,
            top_cms_npis=top_cms_npis
        )
        
        treatment_rankings = ranking_result['treatment_rankings']
        total_treatments = ranking_result['total_treatments']
        
        logger.info(f"✅ Successfully ranked NPI providers for {total_treatments} treatments")
        return {
            "status": "success",
            "treatment_rankings": treatment_rankings,
            "total_treatments": total_treatments,
            "message": f"Successfully ranked NPI providers for {total_treatments} treatments"
        }
        
    except ValueError as e:
        logger.error(f"❌ [NPI Ranking] Value error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid data: {e}")
    except Exception as e:
        logger.error(f"❌ [NPI Ranking] Unexpected error: {str(e)}")
        logger.error(f"❌ [NPI Ranking] Error type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [NPI Ranking] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error ranking NPI providers: {str(e)}")
