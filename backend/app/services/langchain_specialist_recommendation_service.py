"""
LangChain Specialist Recommendation Service
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.langchain_retrieval_strategies import LangChainRetrievalStrategies
from ..services.medical_analysis_service import MedicalAnalysisService

from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

logger = logging.getLogger(__name__)

class LangChainSpecialistRecommendationService:
    """LangChain-powered specialist recommendation service."""
    
    def __init__(self, db=None):
        self.pinecone_service = PineconeService()
        self.retrieval_strategies = LangChainRetrievalStrategies(self.pinecone_service)
        self.medical_analysis = MedicalAnalysisService(db)

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
            # Step 1: LLM-powered patient data processing and medical analysis
            logger.info("Processing patient data and performing medical analysis with LangChain...")
            patient_profile = await self.medical_analysis.process_patient_input(
                patient_input=patient_input,
                location_preference=location_preference,
                urgency_level=urgency_level
            )
            
            # Perform comprehensive medical analysis
            medical_analysis_results = {
                "determined_specialty": await self.medical_analysis.determine_specialty(patient_input),
                "predicted_icd10": await self.medical_analysis.predict_icd10_code(patient_input),
                "diagnoses": await self.medical_analysis.predict_diagnoses(patient_input)
            }
            
            # Step 2: LLM-powered retrieval of specialist information
            logger.info("Retrieving specialist information with LangChain...")
            specialist_information = await self.retrieval_strategies.retrieve_specialist_information(
                patient_profile=patient_profile,
                top_k=50
            )
            
            # Step 3: Convert specialist information directly to recommendations (skip ranking)
            logger.info("Converting specialist information to recommendations...")
            recommendations = []
            for i, info in enumerate(specialist_information[:max_recommendations]):
                # Extract specialist name from featuring field
                featuring = info.get('featuring', '')
                specialist_name = featuring.split(',')[0].strip() if featuring else f"Specialist {i+1}"
                
                recommendation = SpecialistRecommendation(
                    specialist_id=info.get('id', info.get('_id', f"specialist_{i}")),
                    name=specialist_name,
                    specialty=info.get('specialty', 'Medical Specialist'),
                    relevance_score=0.8 - (i * 0.1),  # Simple decreasing score
                    confidence_score=0.8 - (i * 0.1),
                    reasoning=f"Found in medical content: {info.get('title', 'Medical video')}",
                    metadata=info
                )
                recommendations.append(recommendation)
            
            # Step 4: Generate response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = RecommendationResponse(
                patient_profile=patient_profile,
                recommendations=recommendations,
                total_candidates_found=len(specialist_information),
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=["langchain_vector_search"],
                timestamp=datetime.now(),
                medical_analysis=medical_analysis_results
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations in {processing_time:.2f}ms using LangChain")
            return response
            
        except Exception as e:
            logger.error(f"Error generating LangChain recommendations: {str(e)}")
            raise
    

