"""
Simple Specialist Ranking Service
"""

import logging
from typing import List, Dict, Any
from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation

logger = logging.getLogger(__name__)

class SpecialistRankingService:
    """Simple specialist ranking service."""
    
    def __init__(self):
        logger.info("SpecialistRankingService initialized successfully")
    
    async def rank_specialists(
        self,
        candidates: List[Dict[str, Any]],
        patient_profile: PatientProfile,
        top_n: int = 3
    ) -> List[SpecialistRecommendation]:
        """Simple ranking based on basic relevance."""
        recommendations = []
        
        for candidate in candidates[:top_n]:
            # Simple relevance score based on specialty match
            relevance_score = 0.5
            if candidate.get("specialty"):
                if any(specialty in candidate["specialty"].lower() for specialty in patient_profile.specialties_needed):
                    relevance_score = 0.8
            
            # Simple confidence score
            confidence_score = relevance_score * 0.5 + 0.3  # Basic scoring
            
            # Create recommendation
            recommendation = SpecialistRecommendation(
                specialist_id=candidate.get("id", candidate.get("_id", "")),
                name=candidate.get("featuring", candidate.get("author", candidate.get("name", "Unknown"))),
                specialty=candidate.get("specialty", "Unknown"),
                relevance_score=relevance_score,
                confidence_score=confidence_score,
                reasoning="Moderately relevant to your case.",
                metadata=candidate
            )
            
            recommendations.append(recommendation)
        
        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        
        logger.info(f"Ranked {len(recommendations)} candidates, returning top {min(top_n, len(recommendations))}")
        return recommendations[:top_n]