"""
Specialist Ranking Service

This service ranks and scores specialist candidates based on multiple criteria
including relevance, expertise, availability, and patient preferences.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RankingCriteria:
    """Configuration for ranking criteria weights."""
    relevance_weight: float = 0.4
    expertise_weight: float = 0.3
    availability_weight: float = 0.1
    location_weight: float = 0.1
    patient_preference_weight: float = 0.1

class SpecialistRankingService:
    """
    Ranks and scores specialist candidates based on multiple criteria.
    
    Ranking factors include:
    - Relevance to patient symptoms/conditions
    - Specialist expertise and credentials
    - Availability and scheduling
    - Location proximity
    - Patient preferences
    """
    
    def __init__(self):
        """Initialize the specialist ranking service."""
        self.ranking_criteria = RankingCriteria()
        
        # Expertise scoring factors
        self.expertise_factors = {
            "years_experience": 0.3,
            "education_quality": 0.2,
            "publications": 0.2,
            "awards": 0.1,
            "board_certification": 0.2
        }
        
        # Relevance scoring factors
        self.relevance_factors = {
            "symptom_match": 0.4,
            "condition_match": 0.3,
            "specialty_match": 0.2,
            "content_relevance": 0.1
        }
        
        logger.info("SpecialistRankingService initialized successfully")
    
    async def rank_specialists(
        self,
        candidates: List[Dict[str, Any]],
        patient_profile: PatientProfile,
        max_recommendations: int = 10
    ) -> List[SpecialistRecommendation]:
        """
        Rank specialist candidates and return top recommendations.
        
        Args:
            candidates: List of specialist candidates from retrieval
            patient_profile: Patient profile for matching
            max_recommendations: Maximum number of recommendations to return
            
        Returns:
            List of ranked SpecialistRecommendation objects
        """
        try:
            recommendations = []
            
            for candidate in candidates:
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(candidate, patient_profile)
                
                # Calculate expertise score
                expertise_score = self._calculate_expertise_score(candidate)
                
                # Calculate availability score
                availability_score = self._calculate_availability_score(candidate)
                
                # Calculate location score
                location_score = self._calculate_location_score(candidate, patient_profile)
                
                # Calculate patient preference score
                preference_score = self._calculate_preference_score(candidate, patient_profile)
                
                # Calculate overall confidence score
                confidence_score = self._calculate_confidence_score(
                    relevance_score, expertise_score, availability_score,
                    location_score, preference_score
                )
                
                # Generate reasoning
                reasoning = self._generate_reasoning(
                    candidate, relevance_score, expertise_score,
                    availability_score, location_score, preference_score
                )
                
                # Create recommendation
                recommendation = SpecialistRecommendation(
                    specialist_id=candidate.get("id", candidate.get("_id", "")),
                    name=candidate.get("featuring", candidate.get("author", candidate.get("name", "Unknown"))),
                    specialty=candidate.get("specialty", "Unknown"),
                    relevance_score=relevance_score,
                    confidence_score=confidence_score,
                    reasoning=reasoning,
                    metadata=candidate
                )
                
                recommendations.append(recommendation)
            
            # Sort by confidence score
            recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
            
            # Return top recommendations
            top_recommendations = recommendations[:max_recommendations]
            
            logger.info(f"Ranked {len(candidates)} candidates, returning top {len(top_recommendations)}")
            return top_recommendations
            
        except Exception as e:
            logger.error(f"Error ranking specialists: {str(e)}")
            raise
    
    def _calculate_relevance_score(
        self,
        candidate: Dict[str, Any],
        patient_profile: PatientProfile
    ) -> float:
        """Calculate relevance score based on symptom/condition matching."""
        score = 0.0
        
        # Get candidate content
        content_text = f"{candidate.get('title', '')} {candidate.get('author', '')} {candidate.get('featuring', '')}"
        content_text = content_text.lower()
        
        # Symptom matching
        symptom_matches = 0
        for symptom in patient_profile.symptoms:
            if symptom.lower() in content_text:
                symptom_matches += 1
        
        if patient_profile.symptoms:
            symptom_score = symptom_matches / len(patient_profile.symptoms)
            score += symptom_score * self.relevance_factors["symptom_match"]
        
        # Condition matching
        condition_matches = 0
        for condition in patient_profile.conditions:
            if condition.lower() in content_text:
                condition_matches += 1
        
        if patient_profile.conditions:
            condition_score = condition_matches / len(patient_profile.conditions)
            score += condition_score * self.relevance_factors["condition_match"]
        
        # Specialty matching
        candidate_specialty = candidate.get("specialty", "").lower()
        specialty_matches = 0
        for needed_specialty in patient_profile.specialties_needed:
            if needed_specialty.lower() in candidate_specialty:
                specialty_matches += 1
        
        if patient_profile.specialties_needed:
            specialty_score = specialty_matches / len(patient_profile.specialties_needed)
            score += specialty_score * self.relevance_factors["specialty_match"]
        
        # Content relevance
        content_relevance = self._calculate_content_relevance(content_text, patient_profile)
        score += content_relevance * self.relevance_factors["content_relevance"]
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_expertise_score(self, candidate: Dict[str, Any]) -> float:
        """Calculate expertise score based on credentials and experience."""
        score = 0.0
        
        # Years of experience (if available)
        years_experience = candidate.get("years_experience", 0)
        if years_experience > 0:
            experience_score = min(years_experience / 20, 1.0)  # Cap at 20 years
            score += experience_score * self.expertise_factors["years_experience"]
        
        # Education quality (if available)
        education = candidate.get("education", "")
        if education:
            education_score = self._score_education_quality(education)
            score += education_score * self.expertise_factors["education_quality"]
        
        # Publications (if available)
        publications = candidate.get("publications", 0)
        if publications > 0:
            publication_score = min(publications / 50, 1.0)  # Cap at 50 publications
            score += publication_score * self.expertise_factors["publications"]
        
        # Awards (if available)
        awards = candidate.get("awards", 0)
        if awards > 0:
            award_score = min(awards / 10, 1.0)  # Cap at 10 awards
            score += award_score * self.expertise_factors["awards"]
        
        # Board certification (if available)
        board_certified = candidate.get("board_certified", False)
        if board_certified:
            score += 1.0 * self.expertise_factors["board_certification"]
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_availability_score(self, candidate: Dict[str, Any]) -> float:
        """Calculate availability score based on scheduling information."""
        # For now, return a default score since we don't have real availability data
        # In a real system, this would check appointment availability, wait times, etc.
        return 0.8  # Default high availability
    
    def _calculate_location_score(
        self,
        candidate: Dict[str, Any],
        patient_profile: PatientProfile
    ) -> float:
        """Calculate location score based on proximity to patient."""
        if not patient_profile.location_preference:
            return 0.5  # Neutral score if no location preference
        
        candidate_location = candidate.get("location", "").lower()
        patient_location = patient_profile.location_preference.lower()
        
        # Simple location matching
        if patient_location in candidate_location:
            return 1.0
        elif any(word in candidate_location for word in patient_location.split()):
            return 0.7
        else:
            return 0.3
    
    def _calculate_preference_score(
        self,
        candidate: Dict[str, Any],
        patient_profile: PatientProfile
    ) -> float:
        """Calculate score based on patient preferences."""
        score = 0.5  # Base score
        
        # Insurance preference
        if patient_profile.insurance_preference:
            candidate_insurance = candidate.get("insurance_accepted", [])
            if patient_profile.insurance_preference in candidate_insurance:
                score += 0.3
        
        # Urgency level consideration
        if patient_profile.urgency_level == "emergency":
            # Prefer specialists with emergency availability
            emergency_available = candidate.get("emergency_available", False)
            if emergency_available:
                score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_confidence_score(
        self,
        relevance_score: float,
        expertise_score: float,
        availability_score: float,
        location_score: float,
        preference_score: float
    ) -> float:
        """Calculate overall confidence score using weighted criteria."""
        confidence = (
            relevance_score * self.ranking_criteria.relevance_weight +
            expertise_score * self.ranking_criteria.expertise_weight +
            availability_score * self.ranking_criteria.availability_weight +
            location_score * self.ranking_criteria.location_weight +
            preference_score * self.ranking_criteria.patient_preference_weight
        )
        
        return min(confidence, 1.0)
    
    def _calculate_content_relevance(self, content_text: str, patient_profile: PatientProfile) -> float:
        """Calculate content relevance score."""
        if not content_text:
            return 0.0
        
        # Count relevant terms
        relevant_terms = 0
        total_terms = len(content_text.split())
        
        # Check for patient symptoms and conditions
        all_patient_terms = patient_profile.symptoms + patient_profile.conditions + patient_profile.specialties_needed
        
        for term in all_patient_terms:
            if term.lower() in content_text:
                relevant_terms += 1
        
        if total_terms == 0:
            return 0.0
        
        return min(relevant_terms / total_terms, 1.0)
    
    def _score_education_quality(self, education: str) -> float:
        """Score education quality based on institution reputation."""
        education = education.lower()
        
        # Top-tier medical schools
        top_tier = ["harvard", "stanford", "johns hopkins", "mayo clinic", "ucla", "ucsf"]
        if any(school in education for school in top_tier):
            return 1.0
        
        # Good medical schools
        good_tier = ["university", "medical school", "college of medicine"]
        if any(school in education for school in good_tier):
            return 0.8
        
        # Default score
        return 0.6
    
    def _generate_reasoning(
        self,
        candidate: Dict[str, Any],
        relevance_score: float,
        expertise_score: float,
        availability_score: float,
        location_score: float,
        preference_score: float
    ) -> str:
        """Generate human-readable reasoning for the recommendation."""
        reasoning_parts = []
        
        # Relevance reasoning
        if relevance_score > 0.7:
            reasoning_parts.append("Highly relevant to your symptoms and conditions")
        elif relevance_score > 0.4:
            reasoning_parts.append("Moderately relevant to your case")
        
        # Expertise reasoning
        if expertise_score > 0.8:
            reasoning_parts.append("Highly experienced and qualified specialist")
        elif expertise_score > 0.6:
            reasoning_parts.append("Well-qualified specialist")
        
        # Location reasoning
        if location_score > 0.8:
            reasoning_parts.append("Located in your preferred area")
        elif location_score > 0.5:
            reasoning_parts.append("Located nearby")
        
        # Availability reasoning
        if availability_score > 0.8:
            reasoning_parts.append("Good availability for appointments")
        
        # Combine reasoning
        if reasoning_parts:
            return ". ".join(reasoning_parts) + "."
        else:
            return "Specialist with relevant expertise in your area of need."
    
    def update_ranking_criteria(self, criteria: RankingCriteria) -> None:
        """Update ranking criteria weights."""
        self.ranking_criteria = criteria
        logger.info("Updated ranking criteria")
    
    def get_ranking_stats(self) -> Dict[str, Any]:
        """Get statistics about the ranking service."""
        return {
            "ranking_criteria": {
                "relevance_weight": self.ranking_criteria.relevance_weight,
                "expertise_weight": self.ranking_criteria.expertise_weight,
                "availability_weight": self.ranking_criteria.availability_weight,
                "location_weight": self.ranking_criteria.location_weight,
                "patient_preference_weight": self.ranking_criteria.patient_preference_weight
            },
            "expertise_factors": self.expertise_factors,
            "relevance_factors": self.relevance_factors
        }
