"""
Specialist Recommendation Service

This service orchestrates the entire specialist recommendation pipeline:
1. Patient data processing and synthesis
2. Multi-strategy retrieval from Pinecone
3. Intelligent ranking and scoring
4. Final recommendation generation
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.patient_data_processor import PatientDataProcessor
from ..services.retrieval_strategies import RetrievalStrategies
from ..services.specialist_ranking_service import SpecialistRankingService
from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpecialistRecommendationService:
    """
    Main service for specialist recommendations using LangChain and Pinecone.
    
    This service coordinates:
    - Patient data processing
    - Multi-strategy retrieval
    - Intelligent ranking
    - Recommendation generation
    """
    
    def __init__(self):
        """Initialize the specialist recommendation service."""
        self.pinecone_service = PineconeService()
        self.patient_processor = PatientDataProcessor()
        self.retrieval_strategies = RetrievalStrategies(self.pinecone_service)
        self.ranking_service = SpecialistRankingService()
        
        # Configuration
        self.default_top_k = 50  # Retrieve top 50 candidates initially
        self.final_recommendations_count = 10  # Return top 10 recommendations
        self.min_confidence_threshold = 0.3  # Minimum confidence for recommendations
        
        logger.info("SpecialistRecommendationService initialized successfully")
    
    async def get_specialist_recommendations(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        insurance_preference: Optional[str] = None,
        urgency_level: str = "medium",
        max_recommendations: int = 10
    ) -> RecommendationResponse:
        """
        Get specialist recommendations for a patient.
        
        Args:
            patient_input: Raw patient description (symptoms, conditions, etc.)
            location_preference: Preferred location for specialist
            insurance_preference: Insurance requirements
            urgency_level: Urgency of the case (low, medium, high, emergency)
            max_recommendations: Maximum number of recommendations to return
            
        Returns:
            RecommendationResponse with ranked specialist recommendations
        """
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
            
            # Step 2: Multi-strategy retrieval
            logger.info("Retrieving specialist candidates...")
            candidates = await self.retrieval_strategies.retrieve_specialists(
                patient_profile=patient_profile,
                top_k=self.default_top_k
            )
            
            # Step 3: Rank and score specialists
            logger.info("Ranking and scoring specialists...")
            ranked_recommendations = await self.ranking_service.rank_specialists(
                candidates=candidates,
                patient_profile=patient_profile,
                max_recommendations=max_recommendations
            )
            
            # Step 4: Filter by confidence threshold
            filtered_recommendations = [
                rec for rec in ranked_recommendations 
                if rec.confidence_score >= self.min_confidence_threshold
            ]
            
            # Step 5: Generate final response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = RecommendationResponse(
                patient_profile=patient_profile,
                recommendations=filtered_recommendations,
                total_candidates_found=len(candidates),
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=self.retrieval_strategies.get_used_strategies(),
                timestamp=datetime.now()
            )
            
            logger.info(f"Generated {len(filtered_recommendations)} recommendations in {processing_time:.2f}ms")
            return response
            
        except Exception as e:
            logger.error(f"Error generating specialist recommendations: {str(e)}")
            raise
    
    async def get_specialist_by_id(
        self,
        specialist_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific specialist.
        
        Args:
            specialist_id: Unique identifier for the specialist
            
        Returns:
            Specialist details or None if not found
        """
        try:
            # Query Pinecone for specific specialist
            index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
            
            # Use metadata filter to find by ID
            results = index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": "medical specialist"},
                    "top_k": 1,
                    "filter": {"id": specialist_id}
                },
                fields=["*"]
            )
            
            # Parse results from search response
            if hasattr(results, 'result') and hasattr(results.result, 'hits') and results.result.hits:
                return results.result.hits[0].fields
            elif hasattr(results, 'matches') and results.matches:
                return results.matches[0].metadata
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving specialist {specialist_id}: {str(e)}")
            return None
    
    async def search_specialists_by_specialty(
        self,
        specialty: str,
        location: Optional[str] = None,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for specialists by specialty and optional location.
        
        Args:
            specialty: Medical specialty to search for
            location: Optional location filter
            top_k: Number of results to return
            
        Returns:
            List of specialist records
        """
        try:
            # Build metadata filter
            filter_dict = {"specialty": specialty}
            if location:
                filter_dict["location"] = location
            
            # Query Pinecone
            index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
            
            results = index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": "medical specialist"},
                    "top_k": top_k,
                    "filter": filter_dict
                },
                fields=["*"]
            )
            
            # Parse results from search response
            candidates = []
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                # New search format
                for hit in results.result.hits:
                    candidates.append(hit.fields)
            elif hasattr(results, 'matches'):
                # Old query format
                for match in results.matches:
                    candidates.append(match.metadata)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error searching specialists by specialty: {str(e)}")
            return []
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the recommendation service.
        
        Returns:
            Dictionary with service statistics
        """
        try:
            # Get Pinecone index stats
            index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
            stats = index.describe_index_stats()
            
            return {
                "pinecone_index_name": self.pinecone_service.default_index_name,
                "total_vectors": stats.total_vector_count,
                "index_dimension": stats.dimension,
                "index_metric": stats.metric,
                "service_status": "healthy",
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting service stats: {str(e)}")
            return {
                "service_status": "error",
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }
