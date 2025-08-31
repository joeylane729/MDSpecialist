"""
LangChain Specialist Recommendation Service
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.langchain_retrieval_strategies import LangChainRetrievalStrategies
from ..services.medical_analysis_service import MedicalAnalysisService
from ..services.langchain_ranking_service import LangChainRankingService

from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

logger = logging.getLogger(__name__)

class LangChainSpecialistRecommendationService:
    """LangChain-powered specialist recommendation service."""
    
    def __init__(self, db=None):
        self.pinecone_service = PineconeService()
        self.retrieval_strategies = LangChainRetrievalStrategies(self.pinecone_service)
        self.medical_analysis = MedicalAnalysisService(db)
        self.ranking_service = LangChainRankingService()

        logger.info("LangChainSpecialistRecommendationService initialized successfully")
    
    async def get_specialist_recommendations(
        self,
        patient_input: str
    ) -> RecommendationResponse:
        """Get specialist recommendations using LangChain."""
        start_time = datetime.now()
        
        try:
            # Step 1: Comprehensive medical analysis and patient processing
            logger.info("Performing comprehensive medical analysis with LangChain...")
            medical_analysis_results = await self.medical_analysis.comprehensive_analysis(patient_input)
            
            # Step 2: LLM-powered retrieval of specialist information
            logger.info("Retrieving specialist information with LangChain...")
            specialist_information = await self.retrieval_strategies.retrieve_specialist_information(
                patient_profile=medical_analysis_results,
                top_k=200  # Use same value as NPI ranking
            )
            
            # Step 3: Convert specialist information directly to recommendations (skip ranking)
            logger.info("Converting specialist information to recommendations...")
            recommendations = []
            for i, info in enumerate(specialist_information):
                # Extract specialist name from featuring field
                featuring = info.get('featuring', '')
                specialist_name = featuring.split(',')[0].strip() if featuring else f"Specialist {i+1}"
                
                # Calculate scores that stay positive (0.9 down to 0.1)
                max_score = 0.9
                min_score = 0.1
                total_items = len(specialist_information)
                if total_items > 1:
                    score = max_score - (i * (max_score - min_score) / (total_items - 1))
                else:
                    score = max_score
                
                recommendation = SpecialistRecommendation(
                    specialist_id=info.get('id', info.get('_id', f"specialist_{i}")),
                    name=specialist_name,
                    specialty=info.get('specialty', 'Medical Specialist'),
                    relevance_score=score,
                    confidence_score=score,
                    reasoning=f"Found in medical content: {info.get('title', 'Medical video')}",
                    metadata=info
                )
                recommendations.append(recommendation)
            
            # Step 4: Generate response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = RecommendationResponse(
                patient_profile=medical_analysis_results,
                recommendations=recommendations,
                total_candidates_found=len(specialist_information),
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=["langchain_vector_search"],
                timestamp=datetime.now(),
                shared_specialist_information=specialist_information
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations in {processing_time:.2f}ms using LangChain")
            return response
            
        except Exception as e:
            logger.error(f"Error generating LangChain recommendations: {str(e)}")
            raise
    
    async def rank_npi_providers_with_pinecone(
        self,
        npi_providers: List[Dict[str, Any]],
        patient_input: str,
        shared_specialist_information: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Rank NPI providers based on Pinecone specialist information.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            patient_input: Patient description for medical analysis
            shared_specialist_information: Optional pre-fetched specialist information to ensure consistency
            
        Returns:
            List of NPI numbers in ranked order (most relevant first)
        """
        try:
            logger.info(f"🔍 SPECIALIST SERVICE: Starting NPI ranking with {len(npi_providers)} providers")
            
            # Step 1: Get medical analysis
            logger.info("Performing medical analysis for NPI ranking...")
            medical_analysis_results = await self.medical_analysis.comprehensive_analysis(patient_input)
            
            # Step 2: Use shared Pinecone specialist information (required)
            if not shared_specialist_information:
                raise ValueError("shared_specialist_information is required for NPI ranking. No fallback Pinecone calls allowed.")
            
            logger.info(f"🔍 SPECIALIST SERVICE: Using {len(shared_specialist_information)} shared specialist records")
            specialist_information = shared_specialist_information
            
            # Step 3: Use ranking service to rank NPI providers
            logger.info("Ranking NPI providers based on Pinecone data...")
            ranking_result = await self.ranking_service.rank_npi_providers(
                npi_providers=npi_providers,
                pinecone_data=specialist_information,
                patient_profile=medical_analysis_results
            )
            
            ranked_npis = ranking_result['ranking']
            explanation = ranking_result['explanation']
            provider_links = ranking_result.get('provider_links', {})
            
            logger.info(f"Successfully ranked {len(ranked_npis)} NPI providers")
            logger.info(f"Ranking explanation: {explanation}")
            logger.info(f"Provider links: {provider_links}")
            return {
                'ranking': ranked_npis,
                'explanation': explanation,
                'provider_links': provider_links
            }
            
        except Exception as e:
            logger.error(f"Error ranking NPI providers: {str(e)}")
            raise
    

