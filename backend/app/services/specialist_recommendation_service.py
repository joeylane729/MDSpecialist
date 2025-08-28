"""
Simple Specialist Recommendation Service
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.patient_data_processor import PatientDataProcessor
from ..services.retrieval_strategies import RetrievalStrategies
from ..services.specialist_ranking_service import SpecialistRankingService
from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

logger = logging.getLogger(__name__)

class SpecialistRecommendationService:
    """Simple specialist recommendation service."""
    
    def __init__(self):
        self.pinecone_service = PineconeService()
        self.patient_processor = PatientDataProcessor()
        self.retrieval_strategies = RetrievalStrategies(self.pinecone_service)
        self.ranking_service = SpecialistRankingService()
        logger.info("SpecialistRecommendationService initialized successfully")
    
    async def get_specialist_recommendations(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        insurance_preference: Optional[str] = None,
        urgency_level: str = "medium",
        max_recommendations: int = 3
    ) -> RecommendationResponse:
        """Simple specialist recommendations."""
        start_time = datetime.now()
        
        try:
            # Step 1: Process patient data
            logger.info("Processing patient data...")
            patient_profile = await self.patient_processor.process_patient_input(
                patient_input=patient_input,
                location_preference=location_preference,
                insurance_preference=insurance_preference,
                urgency_level=urgency_level
            )
            
            # Step 2: Retrieve candidates
            logger.info("Retrieving specialist candidates...")
            candidates = await self.retrieval_strategies.retrieve_specialists(
                patient_profile=patient_profile,
                top_k=50
            )
            
            # Step 3: Rank specialists
            logger.info("Ranking and scoring specialists...")
            recommendations = await self.ranking_service.rank_specialists(
                candidates=candidates,
                patient_profile=patient_profile,
                top_n=max_recommendations
            )
            
            # Step 4: Generate response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = RecommendationResponse(
                patient_profile=patient_profile,
                recommendations=recommendations,
                total_candidates_found=len(candidates),
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=["vector_similarity"],
                timestamp=datetime.now()
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations in {processing_time:.2f}ms")
            return response
            
        except Exception as e:
            logger.error(f"Error generating specialist recommendations: {str(e)}")
            raise