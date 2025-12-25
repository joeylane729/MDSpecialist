"""
NPI Provider Ranking Endpoint

This endpoint ranks NPI providers algorithmically based on specialist data
(PubMed articles, VuMedi videos, medical school rankings, CMS clinical volumes, etc.).
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ...database import get_db
from ...services.specialist_recommendation_service import SpecialistRecommendationService
from ..utils.cms_utils import extract_cms_tot_srvcs
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class NPIRankingRequest(BaseModel):
    npi_providers: List[Dict[str, Any]]
    patient_input: str
    shared_specialist_information: Optional[Dict[str, Any]] = None
    cms_data: Optional[Dict[str, Any]] = None  # CMS data for clinical volume bonus
    search_query: Optional[str] = None  # Pre-generated search query from medical analysis

@router.post("/rank-npi-providers")
async def rank_npi_providers(
    request: NPIRankingRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Rank NPI providers algorithmically based on specialist information.
    
    Ranking considers:
    - PubMed article matches
    - VuMedi video matches  
    - Medical school rankings
    - Board certifications
    - CMS clinical volumes
    - Years of experience
    
    Args:
        request: Contains npi_providers, patient_input, shared_specialist_information, cms_data, search_query
        
    Returns:
        Dictionary with treatment_rankings and total_treatments
    """
    try:
        # Extract CMS clinical volume data for scoring
        cms_tot_srvcs = extract_cms_tot_srvcs(request.cms_data)
        
        # Initialize service and rank providers
        specialist_service = SpecialistRecommendationService(db)
        ranking_result = await specialist_service.rank_npi_providers_with_specialist_data(
            npi_providers=request.npi_providers,
            patient_input=request.patient_input,
            shared_specialist_information=request.shared_specialist_information,
            cms_tot_srvcs=cms_tot_srvcs,
            search_query=request.search_query
        )
        
        return {
            "status": "success",
            "treatment_rankings": ranking_result['treatment_rankings'],
            "total_treatments": ranking_result['total_treatments'],
            "message": f"Successfully ranked NPI providers for {ranking_result['total_treatments']} treatments"
        }
        
    except ValueError as e:
        logger.error(f"Value error in NPI ranking: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid request data")
    except Exception as e:
        logger.error(f"Error ranking NPI providers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error ranking NPI providers")
