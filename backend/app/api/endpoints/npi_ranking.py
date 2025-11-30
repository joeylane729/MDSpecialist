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
        
        # Extract CMS Tot_Srvcs data for percentage-based clinical volume scoring
        cms_tot_srvcs = None
        if request.cms_data and isinstance(request.cms_data, dict):
            logger.info(f"🏥 [NPI Ranking] CMS data received - keys: {list(request.cms_data.keys())}")
            cms_providers = request.cms_data.get('results', [])
            logger.info(f"🏥 [NPI Ranking] CMS providers count: {len(cms_providers) if isinstance(cms_providers, list) else 'not a list'}")
            if cms_providers and isinstance(cms_providers, list):
                # Extract NPIs and Tot_Srvcs from ALL CMS providers (not just top 25)
                cms_tot_srvcs = {}
                extracted_count = 0
                for i, provider in enumerate(cms_providers):
                    npi = provider.get('Rndrng_NPI')
                    tot_srvcs = provider.get('Tot_Srvcs', 0)
                    if npi:
                        try:
                            tot_srvcs_int = int(tot_srvcs) if tot_srvcs else 0
                        except (ValueError, TypeError):
                            tot_srvcs_int = 0
                        
                        npi_str = str(npi)
                        cms_tot_srvcs[npi_str] = tot_srvcs_int
                        extracted_count += 1
                        
                        # Log first 5 for debugging
                        if i < 5:
                            logger.info(f"🏥 [NPI Ranking] CMS provider {i+1} NPI: {npi_str}, Tot_Srvcs: {tot_srvcs_int} (from {provider.get('Rndrng_Prvdr_First_Name', '')} {provider.get('Rndrng_Prvdr_Last_Org_Name', '')})")
                        # Check if this is Theodore Schwartz
                        first_name = provider.get('Rndrng_Prvdr_First_Name', '').upper()
                        last_name = provider.get('Rndrng_Prvdr_Last_Org_Name', '').upper()
                        if 'THEODORE' in first_name and 'SCHWARTZ' in last_name:
                            logger.info(f"✅ [NPI Ranking] FOUND THEODORE SCHWARTZ at position {i+1} with NPI: {npi_str}, Tot_Srvcs: {tot_srvcs_int}")
                    else:
                        logger.warning(f"⚠️ [NPI Ranking] Provider at position {i+1} has no Rndrng_NPI field")
                if cms_tot_srvcs:
                    logger.info(f"🏥 [NPI Ranking] Extracted {len(cms_tot_srvcs)} NPIs with Tot_Srvcs from CMS results for clinical volume scoring")
                    max_tot_srvcs = max(cms_tot_srvcs.values()) if cms_tot_srvcs.values() else 0
                    logger.info(f"🏥 [NPI Ranking] Max Tot_Srvcs in CMS results: {max_tot_srvcs}")
                else:
                    logger.warning(f"⚠️ [NPI Ranking] No NPIs extracted from CMS providers!")
            else:
                logger.warning(f"⚠️ [NPI Ranking] CMS providers is not a list or is empty")
        else:
            logger.warning(f"⚠️ [NPI Ranking] No CMS data provided or not a dict")
        
        # Initialize the LangChain service
        langchain_service = LangChainSpecialistRecommendationService(db)
        
        # Rank the NPI providers using shared data if available
        ranking_result = await langchain_service.rank_npi_providers_with_pinecone(
            npi_providers=request.npi_providers,
            patient_input=request.patient_input,
            shared_specialist_information=shared_data,
            cms_tot_srvcs=cms_tot_srvcs
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
