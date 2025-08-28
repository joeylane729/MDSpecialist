"""
LangChain Specialist Recommendation Service
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.langchain_patient_processor import LangChainPatientProcessor
from ..services.langchain_retrieval_strategies import LangChainRetrievalStrategies
from ..services.langchain_ranking_service import LangChainRankingService
from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

logger = logging.getLogger(__name__)

class LangChainSpecialistRecommendationService:
    """LangChain-powered specialist recommendation service."""
    
    def __init__(self):
        self.pinecone_service = PineconeService()
        self.patient_processor = LangChainPatientProcessor()
        self.retrieval_strategies = LangChainRetrievalStrategies(self.pinecone_service)
        self.ranking_service = LangChainRankingService()
        logger.info("LangChainSpecialistRecommendationService initialized successfully")
    
    async def get_specialist_recommendations(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        urgency_level: str = "medium",
        max_recommendations: int = 3
    ) -> RecommendationResponse:
        """Get specialist recommendations using LangChain."""
        start_time = datetime.now()
        
        try:
            # Step 1: LLM-powered patient data processing
            logger.info("Processing patient data with LangChain...")
            patient_profile = await self.patient_processor.process_patient_input(
                patient_input=patient_input,
                location_preference=location_preference,
                urgency_level=urgency_level
            )
            
            # Step 2: LLM-powered retrieval of specialist information
            logger.info("Retrieving specialist information with LangChain...")
            specialist_information = await self.retrieval_strategies.retrieve_specialist_information(
                patient_profile=patient_profile,
                top_k=50
            )
            
            # Step 3: LLM-powered ranking based on specialist information
            logger.info("Ranking specialists based on information with LangChain...")
            recommendations = await self.ranking_service.rank_specialists_from_information(
                specialist_information=specialist_information,
                patient_profile=patient_profile,
                top_n=max_recommendations
            )
            
            # Step 4: Generate response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = RecommendationResponse(
                patient_profile=patient_profile,
                recommendations=recommendations,
                total_candidates_found=len(specialist_information),
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=["langchain_vector_search"],
                timestamp=datetime.now()
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations in {processing_time:.2f}ms using LangChain")
            return response
            
        except Exception as e:
            logger.error(f"Error generating LangChain recommendations: {str(e)}")
            raise
