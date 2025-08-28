"""
Retrieval Strategies Service

This service implements multiple retrieval strategies for finding relevant specialists
from the Pinecone vector database, including vector similarity, metadata filtering,
and hybrid approaches.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from ..models.specialist_recommendation import PatientProfile
from .pinecone_service import PineconeService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    """Result from a retrieval strategy."""
    strategy_name: str
    candidates: List[Dict[str, Any]]
    confidence_scores: List[float]
    metadata: Dict[str, Any]

class RetrievalStrategies:
    """
    Implements multiple retrieval strategies for specialist matching.
    
    Strategies include:
    - Vector similarity search
    - Metadata filtering
    - Hybrid search
    - Query expansion
    - Specialty-specific search
    """
    
    def __init__(self, pinecone_service: PineconeService):
        """Initialize retrieval strategies with Pinecone service."""
        self.pinecone_service = pinecone_service
        self.index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
        
        # Strategy configuration
        self.vector_search_weight = 0.6
        self.metadata_filter_weight = 0.4
        self.specialty_boost_factor = 1.2
        
        # Track used strategies
        self.used_strategies = []
        
        logger.info("RetrievalStrategies initialized successfully")
    
    async def retrieve_specialists(
        self,
        patient_profile: PatientProfile,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve specialist candidates using multiple strategies.
        
        Args:
            patient_profile: Structured patient profile
            top_k: Number of candidates to retrieve
            
        Returns:
            List of specialist candidates with metadata
        """
        try:
            # Reset used strategies tracking
            self.used_strategies = []
            
            # Strategy 1: Vector similarity search
            vector_results = await self._vector_similarity_search(patient_profile, top_k)
            self.used_strategies.append("vector_similarity")
            
            # Strategy 2: Metadata filtering
            metadata_results = await self._metadata_filter_search(patient_profile, top_k)
            self.used_strategies.append("metadata_filter")
            
            # Strategy 3: Specialty-specific search
            specialty_results = await self._specialty_specific_search(patient_profile, top_k)
            self.used_strategies.append("specialty_specific")
            
            # Strategy 4: Hybrid search
            hybrid_results = await self._hybrid_search(patient_profile, top_k)
            self.used_strategies.append("hybrid")
            
            # Combine and deduplicate results
            all_candidates = self._combine_results([
                vector_results, metadata_results, specialty_results, hybrid_results
            ])
            
            # Rank and return top candidates
            ranked_candidates = self._rank_combined_results(all_candidates, patient_profile)
            
            logger.info(f"Retrieved {len(ranked_candidates)} candidates using {len(self.used_strategies)} strategies")
            return ranked_candidates[:top_k]
            
        except Exception as e:
            logger.error(f"Error retrieving specialists: {str(e)}")
            raise
    
    async def _vector_similarity_search(
        self,
        patient_profile: PatientProfile,
        top_k: int
    ) -> RetrievalResult:
        """Perform vector similarity search using patient description."""
        try:
            # Create search query from patient profile
            search_query = self._create_search_query(patient_profile)
            
            # For integrated embeddings, we need to use search with text
            results = self.index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": search_query},
                    "top_k": top_k
                },
                fields=["*"]
            )
            
            # Parse results from search response
            candidates = []
            confidence_scores = []
            
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                # New search format
                for hit in results.result.hits:
                    candidates.append(hit.fields)
                    confidence_scores.append(hit._score)
                logger.info(f"Vector similarity search found {len(candidates)} candidates")
            elif hasattr(results, 'matches'):
                # Old query format
                for match in results.matches:
                    candidates.append(match.metadata)
                    confidence_scores.append(match.score)
                logger.info(f"Vector similarity search found {len(candidates)} candidates (old format)")
            else:
                logger.warning(f"Unexpected results format: {type(results)}")
            
            return RetrievalResult(
                strategy_name="vector_similarity",
                candidates=candidates,
                confidence_scores=confidence_scores,
                metadata={"query": search_query, "top_k": top_k}
            )
            
        except Exception as e:
            logger.error(f"Error in vector similarity search: {str(e)}")
            return RetrievalResult("vector_similarity", [], [], {"error": str(e)})
    
    async def _metadata_filter_search(
        self,
        patient_profile: PatientProfile,
        top_k: int
    ) -> RetrievalResult:
        """Perform metadata filtering search based on specialties and location."""
        try:
            # Build metadata filter
            filter_dict = {}
            
            # Filter by specialties
            if patient_profile.specialties_needed:
                filter_dict["specialty"] = {"$in": patient_profile.specialties_needed}
            
            # Filter by location if specified (exact match for now)
            if patient_profile.location_preference:
                filter_dict["location"] = patient_profile.location_preference
            
            # For integrated embeddings, we need to use search with a generic query
            # and apply metadata filters
            results = self.index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": "medical specialist doctor"},
                    "top_k": top_k,
                    "filter": filter_dict
                },
                fields=["*"]
            )
            
            # Parse results from search response
            candidates = []
            confidence_scores = []
            
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                # New search format
                for hit in results.result.hits:
                    candidates.append(hit.fields)
                    confidence_scores.append(1.0)  # High confidence for exact matches
                logger.info(f"Metadata filter search found {len(candidates)} candidates")
            elif hasattr(results, 'matches'):
                # Old query format
                for match in results.matches:
                    candidates.append(match.metadata)
                    confidence_scores.append(1.0)  # High confidence for exact matches
                logger.info(f"Metadata filter search found {len(candidates)} candidates (old format)")
            else:
                logger.warning(f"Unexpected results format: {type(results)}")
            
            return RetrievalResult(
                strategy_name="metadata_filter",
                candidates=candidates,
                confidence_scores=confidence_scores,
                metadata={"filter": filter_dict, "top_k": top_k}
            )
            
        except Exception as e:
            logger.error(f"Error in metadata filter search: {str(e)}")
            return RetrievalResult("metadata_filter", [], [], {"error": str(e)})
    
    async def _specialty_specific_search(
        self,
        patient_profile: PatientProfile,
        top_k: int
    ) -> RetrievalResult:
        """Perform specialty-specific search with boosted relevance."""
        try:
            candidates = []
            confidence_scores = []
            
            # Search for each specialty separately
            for specialty in patient_profile.specialties_needed:
                # Create specialty-specific query
                specialty_query = f"{specialty} specialist {patient_profile.additional_notes}"
                
                # Perform vector search using search
                results = self.index.search(
                    namespace="__default__",
                    query={
                        "inputs": {"text": specialty_query},
                        "top_k": top_k // len(patient_profile.specialties_needed) + 1,
                        "filter": {"specialty": specialty}
                    },
                    fields=["*"]
                )
                
                # Add results with specialty boost
                if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                    # New search format
                    for hit in results.result.hits:
                        candidates.append(hit.fields)
                        confidence_scores.append(hit._score * self.specialty_boost_factor)
                elif hasattr(results, 'matches'):
                    # Old query format
                    for match in results.matches:
                        candidates.append(match.metadata)
                        confidence_scores.append(match.score * self.specialty_boost_factor)
                
                logger.info(f"Specialty-specific search for {specialty} found {len(results.result.hits) if hasattr(results, 'result') and hasattr(results.result, 'hits') else len(results.matches) if hasattr(results, 'matches') else 0} candidates")
            
            return RetrievalResult(
                strategy_name="specialty_specific",
                candidates=candidates,
                confidence_scores=confidence_scores,
                metadata={"specialties": patient_profile.specialties_needed, "boost_factor": self.specialty_boost_factor}
            )
            
        except Exception as e:
            logger.error(f"Error in specialty-specific search: {str(e)}")
            return RetrievalResult("specialty_specific", [], [], {"error": str(e)})
    
    async def _hybrid_search(
        self,
        patient_profile: PatientProfile,
        top_k: int
    ) -> RetrievalResult:
        """Perform hybrid search combining vector similarity and metadata filtering."""
        try:
            # Create search query
            search_query = self._create_search_query(patient_profile)
            
            # Build metadata filter
            filter_dict = {}
            if patient_profile.specialties_needed:
                filter_dict["specialty"] = {"$in": patient_profile.specialties_needed}
            
            # Perform hybrid search using search
            results = self.index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": search_query},
                    "top_k": top_k,
                    "filter": filter_dict
                },
                fields=["*"]
            )
            
            # Parse results from search response
            candidates = []
            confidence_scores = []
            
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                # New search format
                for hit in results.result.hits:
                    candidates.append(hit.fields)
                    confidence_scores.append(hit._score)
                logger.info(f"Hybrid search found {len(candidates)} candidates")
            elif hasattr(results, 'matches'):
                # Old query format
                for match in results.matches:
                    candidates.append(match.metadata)
                    confidence_scores.append(match.score)
                logger.info(f"Hybrid search found {len(candidates)} candidates (old format)")
            else:
                logger.warning(f"Unexpected results format: {type(results)}")
            
            return RetrievalResult(
                strategy_name="hybrid",
                candidates=candidates,
                confidence_scores=confidence_scores,
                metadata={"query": search_query, "filter": filter_dict, "top_k": top_k}
            )
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return RetrievalResult("hybrid", [], [], {"error": str(e)})
    
    def _create_search_query(self, patient_profile: PatientProfile) -> str:
        """Create search query from patient profile."""
        query_parts = []
        
        # Add symptoms
        if patient_profile.symptoms:
            query_parts.extend(patient_profile.symptoms)
        
        # Add conditions
        if patient_profile.conditions:
            query_parts.extend(patient_profile.conditions)
        
        # Add specialties
        if patient_profile.specialties_needed:
            query_parts.extend(patient_profile.specialties_needed)
        
        # Add additional notes
        if patient_profile.additional_notes:
            query_parts.append(patient_profile.additional_notes)
        
        return " ".join(query_parts)
    
    def _combine_results(self, results: List[RetrievalResult]) -> List[Dict[str, Any]]:
        """Combine results from multiple strategies and deduplicate."""
        all_candidates = []
        seen_ids = set()
        
        for result in results:
            for i, candidate in enumerate(result.candidates):
                # Create a unique ID from available fields (Vumedi data doesn't have an id field)
                candidate_id = candidate.get("id", candidate.get("_id", ""))
                if not candidate_id:
                    # Use link as unique identifier for Vumedi data
                    candidate_id = candidate.get("link", f"{candidate.get('title', '')}_{candidate.get('author', '')}")
                
                if candidate_id and candidate_id not in seen_ids:
                    # Add strategy information to candidate
                    candidate["retrieval_strategy"] = result.strategy_name
                    candidate["retrieval_confidence"] = result.confidence_scores[i] if i < len(result.confidence_scores) else 0.0
                    
                    all_candidates.append(candidate)
                    seen_ids.add(candidate_id)
        
        logger.info(f"Combined {len(all_candidates)} unique candidates from {len(results)} strategies")
        return all_candidates
    
    def _rank_combined_results(
        self,
        candidates: List[Dict[str, Any]],
        patient_profile: PatientProfile
    ) -> List[Dict[str, Any]]:
        """Rank combined results based on multiple factors."""
        def calculate_score(candidate):
            score = 0.0
            
            # Base retrieval confidence
            score += candidate.get("retrieval_confidence", 0.0) * 0.4
            
            # Specialty match bonus
            candidate_specialty = candidate.get("specialty", "").lower()
            for needed_specialty in patient_profile.specialties_needed:
                if needed_specialty.lower() in candidate_specialty:
                    score += 0.3
                    break
            
            # Location match bonus
            if patient_profile.location_preference:
                candidate_location = candidate.get("location", "").lower()
                if patient_profile.location_preference.lower() in candidate_location:
                    score += 0.2
            
            # Content relevance bonus
            content_text = f"{candidate.get('title', '')} {candidate.get('author', '')} {candidate.get('featuring', '')}"
            content_text = content_text.lower()
            
            for symptom in patient_profile.symptoms:
                if symptom.lower() in content_text:
                    score += 0.1
            
            return score
        
        # Sort by calculated score
        ranked_candidates = sorted(candidates, key=calculate_score, reverse=True)
        
        return ranked_candidates
    
    def get_used_strategies(self) -> List[str]:
        """Get list of strategies used in the last retrieval."""
        return self.used_strategies.copy()
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics about retrieval strategies."""
        return {
            "available_strategies": [
                "vector_similarity", "metadata_filter", 
                "specialty_specific", "hybrid"
            ],
            "last_used_strategies": self.used_strategies,
            "vector_search_weight": self.vector_search_weight,
            "metadata_filter_weight": self.metadata_filter_weight,
            "specialty_boost_factor": self.specialty_boost_factor
        }
