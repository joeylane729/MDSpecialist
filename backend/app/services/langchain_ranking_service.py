"""
LangChain Ranking Service
"""

import logging
import json
from typing import List, Dict, Any
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation

logger = logging.getLogger(__name__)

class LangChainRankingService:
    """LangChain-powered specialist ranking service."""
    
    def __init__(self):
        self.llm = OpenAI(temperature=0.1)
        
        self.ranking_prompt = PromptTemplate(
            input_variables=["patient_profile", "candidates"],
            template="""
            Rank these medical specialists for this patient:
            
            Patient:
            - Symptoms: {symptoms}
            - Specialties needed: {specialties}
            - Urgency: {urgency}
            
            Specialists:
            {candidates}
            
            Return JSON with ranked recommendations:
            {{
                "recommendations": [
                    {{
                        "name": "doctor name",
                        "specialty": "specialty",
                        "confidence": 0.85,
                        "reasoning": "explanation"
                    }}
                ]
            }}
            """
        )
        
        self.ranking_chain = LLMChain(llm=self.llm, prompt=self.ranking_prompt)
        logger.info("LangChainRankingService initialized successfully")
    
    async def rank_specialists(
        self,
        candidates: List[Dict[str, Any]],
        patient_profile: PatientProfile,
        top_n: int = 3
    ) -> List[SpecialistRecommendation]:
        """Rank specialists using LangChain."""
        try:
            # Prepare candidates for LLM
            candidates_text = self._format_candidates(candidates[:10])  # Limit to top 10 for LLM
            
            # Prepare patient profile for LLM
            patient_input = {
                "symptoms": ", ".join(patient_profile.symptoms),
                "specialties": ", ".join(patient_profile.specialties_needed),
                "urgency": patient_profile.urgency_level
            }
            
            # Get LLM ranking
            response = await self.ranking_chain.arun(
                **patient_input,
                candidates=candidates_text
            )
            
            # Parse LLM response
            try:
                data = json.loads(response.strip())
                llm_recommendations = data.get("recommendations", [])
            except json.JSONDecodeError:
                llm_recommendations = []
            
            # Convert to SpecialistRecommendation objects
            recommendations = []
            for rec in llm_recommendations[:top_n]:
                # Find matching candidate
                matching_candidate = self._find_matching_candidate(rec["name"], candidates)
                
                if matching_candidate:
                    recommendation = SpecialistRecommendation(
                        specialist_id=matching_candidate.get("id", matching_candidate.get("_id", "")),
                        name=rec["name"],
                        specialty=rec["specialty"],
                        relevance_score=rec.get("confidence", 0.5),
                        confidence_score=rec.get("confidence", 0.5),
                        reasoning=rec.get("reasoning", "Recommended based on your case."),
                        metadata=matching_candidate
                    )
                    recommendations.append(recommendation)
            
            # If LLM fails, use fallback
            if not recommendations:
                recommendations = self._fallback_ranking(candidates, patient_profile, top_n)
            
            logger.info(f"LangChain ranked {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in LangChain ranking: {str(e)}")
            return self._fallback_ranking(candidates, patient_profile, top_n)
    
    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> str:
        """Format candidates for LLM input."""
        formatted = []
        for i, candidate in enumerate(candidates, 1):
            name = candidate.get("featuring", candidate.get("author", "Unknown"))
            specialty = candidate.get("specialty", "Unknown")
            title = candidate.get("title", "")
            
            formatted.append(f"{i}. {name} - {specialty} ({title})")
        
        return "\n".join(formatted)
    
    def _find_matching_candidate(self, name: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find candidate that matches the LLM-recommended name."""
        name_lower = name.lower()
        
        for candidate in candidates:
            featuring = candidate.get("featuring", "").lower()
            author = candidate.get("author", "").lower()
            
            if name_lower in featuring or name_lower in author:
                return candidate
        
        # Return first candidate if no match found
        return candidates[0] if candidates else {}
    
    def _fallback_ranking(
        self,
        candidates: List[Dict[str, Any]],
        patient_profile: PatientProfile,
        top_n: int
    ) -> List[SpecialistRecommendation]:
        """Fallback simple ranking if LangChain fails."""
        recommendations = []
        
        for candidate in candidates[:top_n]:
            # Simple relevance score
            relevance_score = 0.5
            if candidate.get("specialty"):
                if any(specialty in candidate["specialty"].lower() for specialty in patient_profile.specialties_needed):
                    relevance_score = 0.8
            
            confidence_score = relevance_score * 0.5 + 0.3
            
            recommendation = SpecialistRecommendation(
                specialist_id=candidate.get("id", candidate.get("_id", "")),
                name=candidate.get("featuring", candidate.get("author", "Unknown")),
                specialty=candidate.get("specialty", "Unknown"),
                relevance_score=relevance_score,
                confidence_score=confidence_score,
                reasoning="Recommended based on your case.",
                metadata=candidate
            )
            
            recommendations.append(recommendation)
        
        logger.info(f"Fallback ranking created {len(recommendations)} recommendations")
        return recommendations
