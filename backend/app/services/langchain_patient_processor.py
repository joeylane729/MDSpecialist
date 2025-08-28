"""
LangChain Patient Data Processor
"""

import logging
import json
from typing import List, Optional
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from ..models.specialist_recommendation import PatientProfile

logger = logging.getLogger(__name__)

class LangChainPatientProcessor:
    """LangChain-powered patient data processor."""
    
    def __init__(self):
        self.llm = OpenAI(temperature=0.1)
        
        self.prompt = PromptTemplate(
            input_variables=["patient_input"],
            template="""
            Extract medical information from this patient description:
            "{patient_input}"
            
            Return a JSON object with:
            - symptoms: list of symptoms mentioned
            - specialties: list of medical specialties needed
            - urgency: one of "low", "medium", "high", "emergency"
            
            Example output:
            {{"symptoms": ["chest pain", "shortness of breath"], "specialties": ["cardiology", "pulmonology"], "urgency": "high"}}
            """
        )
        
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
        logger.info("LangChainPatientProcessor initialized successfully")
    
    async def process_patient_input(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        urgency_level: str = "medium"
    ) -> PatientProfile:
        """Process patient input using LangChain."""
        try:
            # Get LLM response
            response = await self.chain.arun(patient_input=patient_input)
            
            # Parse JSON response
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                data = {
                    "symptoms": ["pain"],
                    "specialties": ["cardiology", "pulmonology"],
                    "urgency": urgency_level
                }
            
            # Create patient profile
            profile = PatientProfile(
                symptoms=data.get("symptoms", []),
                conditions=[],
                specialties_needed=data.get("specialties", []),
                urgency_level=data.get("urgency", urgency_level),
                location_preference=location_preference,
                additional_notes=patient_input
            )
            
            logger.info(f"Processed patient input: {len(profile.symptoms)} symptoms, {len(profile.specialties_needed)} specialties")
            return profile
            
        except Exception as e:
            logger.error(f"Error processing patient input: {str(e)}")
            # Fallback to simple processing
            return self._fallback_processing(patient_input, location_preference, urgency_level)
    
    def _fallback_processing(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        urgency_level: str = "medium"
    ) -> PatientProfile:
        """Fallback simple processing if LangChain fails."""
        text = patient_input.lower()
        
        # Simple extraction
        symptoms = []
        if "pain" in text:
            symptoms.append("pain")
        if "chest" in text:
            symptoms.append("chest")
        if "breath" in text:
            symptoms.append("breathing")
            
        specialties = []
        if any(word in text for word in ["heart", "cardiac", "chest"]):
            specialties.append("cardiology")
        if any(word in text for word in ["lung", "breath", "respiratory"]):
            specialties.append("pulmonology")
        if not specialties:
            specialties = ["cardiology", "pulmonology"]
            
        return PatientProfile(
            symptoms=symptoms,
            conditions=[],
            specialties_needed=specialties,
            urgency_level=urgency_level,
            location_preference=location_preference,
            additional_notes=patient_input
        )
