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
            input_variables=["symptoms", "specialties", "urgency", "candidates"],
            template="""
            Symptoms: {symptoms}
            Specialties: {specialties}
            Urgency: {urgency}
            
            Specialists:
            {candidates}
            
            Return the top 3 specialist names, one per line:
            """
        )
        
        self.ranking_chain = LLMChain(llm=self.llm, prompt=self.ranking_prompt)
        logger.info("LangChainRankingService initialized successfully")
    
    async def rank_specialists_from_information(
        self,
        specialist_information: List[Dict[str, Any]],
        patient_profile: PatientProfile,
        top_n: int = 3
    ) -> List[SpecialistRecommendation]:
        """Rank specialists based on specialist information using LangChain."""
        try:
            # Prepare specialist information for LLM
            information_text = self._format_specialist_information(specialist_information[:10])  # Limit to top 10 for LLM
            
            # Prepare patient profile for LLM
            patient_input = {
                "symptoms": ", ".join(patient_profile.symptoms),
                "specialties": ", ".join(patient_profile.specialties_needed),
                "urgency": patient_profile.urgency_level
            }
            
            # Get LLM ranking
            response = await self.ranking_chain.arun(
                **patient_input,
                candidates=information_text
            )
            
            # Parse LLM response - expect simple text with specialist names
            response_clean = response.strip()
            specialist_names = []
            
            # Split by lines and extract names
            lines = response_clean.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('*'):
                    # Extract name from line (remove numbers, bullets, etc.)
                    name = line
                    # Remove common prefixes
                    for prefix in ['1.', '2.', '3.', '-', '*', '•']:
                        if name.startswith(prefix):
                            name = name[len(prefix):].strip()
                    if name:
                        specialist_names.append(name)
            
            # Create simple recommendations from the names
            llm_recommendations = []
            for i, name in enumerate(specialist_names[:top_n]):
                llm_recommendations.append({
                    "name": name,
                    "specialty": "Medical Specialist",
                    "confidence": 0.8 - (i * 0.1),
                    "reasoning": f"Recommended by AI analysis"
                })
            
            # Convert to SpecialistRecommendation objects
            recommendations = []
            for rec in llm_recommendations[:top_n]:
                # Find matching specialist information
                matching_info = self._find_matching_specialist_info(rec["name"], specialist_information)
                
                if matching_info:
                    recommendation = SpecialistRecommendation(
                        specialist_id=matching_info.get("id", matching_info.get("_id", "")),
                        name=rec["name"],
                        specialty=rec["specialty"],
                        relevance_score=rec.get("confidence", 0.5),
                        confidence_score=rec.get("confidence", 0.5),
                        reasoning=rec.get("reasoning", "Recommended based on your case."),
                        metadata=matching_info
                    )
                    recommendations.append(recommendation)
            
            # Ensure we have recommendations
            if not recommendations:
                raise ValueError("LLM failed to generate any recommendations")
            
            logger.info(f"LangChain ranked {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in LangChain ranking: {str(e)}")
            raise
    
    def _format_specialist_information(self, specialist_info: List[Dict[str, Any]]) -> str:
        """Format specialist information for LLM input."""
        formatted = []
        for i, info in enumerate(specialist_info, 1):
            name = info.get("featuring", info.get("author", "Unknown"))
            specialty = info.get("specialty", "Unknown")
            title = info.get("title", "")
            content = info.get("chunk_text", "")[:200]  # First 200 chars of content
            
            formatted.append(f"{i}. {name} - {specialty}")
            formatted.append(f"   Title: {title}")
            formatted.append(f"   Content: {content}...")
            formatted.append("")  # Empty line for readability
        
        return "\n".join(formatted)
    
    def _find_matching_specialist_info(self, name: str, specialist_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find specialist information that matches the LLM-recommended name."""
        name_lower = name.lower()
        
        for info in specialist_info:
            featuring = info.get("featuring", "").lower()
            author = info.get("author", "").lower()
            
            if name_lower in featuring or name_lower in author:
                return info
        
        # Return first info if no match found
        return specialist_info[0] if specialist_info else {}
    

