"""
Simple Patient Data Processor
"""

import logging
from typing import List, Optional
from ..models.specialist_recommendation import PatientProfile

logger = logging.getLogger(__name__)

class PatientDataProcessor:
    """Simple patient data processor."""
    
    def __init__(self):
        logger.info("PatientDataProcessor initialized successfully")
    
    async def process_patient_input(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        urgency_level: str = "medium"
    ) -> PatientProfile:
        """Simple patient input processing."""
        # Basic extraction - just split on common words
        text = patient_input.lower()
        
        # Simple symptom extraction
        symptoms = []
        if "pain" in text:
            symptoms.append("pain")
        if "chest" in text:
            symptoms.append("chest")
        if "breath" in text:
            symptoms.append("breathing")
            
        # Simple specialty mapping
        specialties = []
        if any(word in text for word in ["heart", "cardiac", "chest"]):
            specialties.append("cardiology")
        if any(word in text for word in ["lung", "breath", "respiratory"]):
            specialties.append("pulmonology")
        if any(word in text for word in ["brain", "head", "nerve"]):
            specialties.append("neurology")
            
        # Default specialties if none found
        if not specialties:
            specialties = ["cardiology", "pulmonology"]
            
        profile = PatientProfile(
            symptoms=symptoms,
            conditions=[],
            specialties_needed=specialties,
            urgency_level=urgency_level,
            location_preference=location_preference,
            additional_notes=patient_input
        )
        
        logger.info(f"Processed patient input: {len(symptoms)} symptoms, {len(specialties)} specialties")
        return profile
    

