"""
Patient Data Processor

This service processes raw patient input and extracts structured information
for specialist matching, including symptoms, conditions, and specialty needs.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from ..models.specialist_recommendation import PatientProfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PatientDataProcessor:
    """
    Processes patient input to extract structured medical information.
    
    This service:
    - Extracts symptoms and conditions from free text
    - Maps to medical specialties
    - Determines urgency levels
    - Standardizes medical terminology
    """
    
    def __init__(self):
        """Initialize the patient data processor."""
        # Medical specialty mappings
        self.specialty_keywords = {
            "cardiology": [
                "heart", "cardiac", "chest pain", "hypertension", "high blood pressure",
                "arrhythmia", "heart attack", "stroke", "coronary", "angina"
            ],
            "dermatology": [
                "skin", "rash", "mole", "acne", "eczema", "psoriasis", "dermatitis",
                "lesion", "wart", "fungal", "allergic reaction"
            ],
            "endocrinology": [
                "diabetes", "thyroid", "hormone", "insulin", "metabolism", "weight",
                "blood sugar", "glucose", "hypoglycemia", "hyperglycemia"
            ],
            "gastroenterology": [
                "stomach", "digestive", "bowel", "intestine", "liver", "gallbladder",
                "nausea", "vomiting", "diarrhea", "constipation", "ibs", "crohn"
            ],
            "neurology": [
                "brain", "nerve", "headache", "migraine", "seizure", "epilepsy",
                "parkinson", "alzheimer", "dementia", "stroke", "paralysis"
            ],
            "orthopedics": [
                "bone", "joint", "fracture", "arthritis", "back pain", "knee",
                "hip", "shoulder", "spine", "muscle", "tendon", "ligament"
            ],
            "psychiatry": [
                "mental health", "depression", "anxiety", "bipolar", "ptsd",
                "panic", "mood", "behavior", "therapy", "counseling"
            ],
            "pulmonology": [
                "lung", "breathing", "asthma", "copd", "pneumonia", "bronchitis",
                "respiratory", "chest", "cough", "shortness of breath"
            ],
            "urology": [
                "kidney", "bladder", "urinary", "prostate", "incontinence",
                "urination", "kidney stone", "uti", "urinary tract"
            ],
            "oncology": [
                "cancer", "tumor", "malignancy", "chemotherapy", "radiation",
                "metastasis", "biopsy", "oncology", "carcinoma"
            ]
        }
        
        # Urgency level indicators
        self.urgency_indicators = {
            "emergency": [
                "emergency", "urgent", "severe", "critical", "life-threatening",
                "chest pain", "difficulty breathing", "unconscious", "bleeding"
            ],
            "high": [
                "severe pain", "high fever", "worsening", "concerning", "alarming"
            ],
            "medium": [
                "moderate", "persistent", "ongoing", "chronic", "recurring"
            ],
            "low": [
                "mild", "minor", "routine", "checkup", "preventive"
            ]
        }
        
        # Common symptom patterns
        self.symptom_patterns = [
            r"pain in (?:my )?(\w+)",
            r"(\w+) hurts?",
            r"(\w+) ache",
            r"(\w+) discomfort",
            r"(\w+) problem",
            r"(\w+) issue",
            r"(\w+) condition",
            r"(\w+) disease"
        ]
        
        logger.info("PatientDataProcessor initialized successfully")
    
    async def process_patient_input(
        self,
        patient_input: str,
        location_preference: Optional[str] = None,
        insurance_preference: Optional[str] = None,
        urgency_level: str = "medium"
    ) -> PatientProfile:
        """
        Process raw patient input into structured patient profile.
        
        Args:
            patient_input: Raw patient description
            location_preference: Preferred location
            insurance_preference: Insurance requirements
            urgency_level: Urgency level
            
        Returns:
            Structured PatientProfile
        """
        try:
            # Clean and normalize input
            cleaned_input = self._clean_input(patient_input)
            
            # Extract symptoms and conditions
            symptoms = self._extract_symptoms(cleaned_input)
            conditions = self._extract_conditions(cleaned_input)
            
            # Determine specialties needed
            specialties_needed = self._determine_specialties(cleaned_input, symptoms, conditions)
            
            # Determine urgency level if not provided
            if urgency_level == "medium":
                urgency_level = self._determine_urgency(cleaned_input, symptoms, conditions)
            
            # Create patient profile
            profile = PatientProfile(
                symptoms=symptoms,
                conditions=conditions,
                specialties_needed=specialties_needed,
                urgency_level=urgency_level,
                location_preference=location_preference,
                insurance_preference=insurance_preference,
                additional_notes=cleaned_input
            )
            
            logger.info(f"Processed patient input: {len(symptoms)} symptoms, {len(conditions)} conditions, {len(specialties_needed)} specialties")
            return profile
            
        except Exception as e:
            logger.error(f"Error processing patient input: {str(e)}")
            raise
    
    def _clean_input(self, text: str) -> str:
        """Clean and normalize patient input text."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common filler words
        filler_words = ["um", "uh", "like", "you know", "i mean"]
        for word in filler_words:
            text = text.replace(word, "")
        
        return text.strip()
    
    def _extract_symptoms(self, text: str) -> List[str]:
        """Extract symptoms from patient input."""
        symptoms = []
        
        # Common symptom keywords
        symptom_keywords = [
            "pain", "ache", "hurt", "discomfort", "sore", "tender",
            "swelling", "inflammation", "redness", "rash", "itch",
            "nausea", "vomiting", "diarrhea", "constipation",
            "headache", "dizziness", "fatigue", "weakness",
            "fever", "chills", "sweating", "cough", "sneezing"
        ]
        
        # Extract symptoms using patterns
        for pattern in self.symptom_patterns:
            matches = re.findall(pattern, text)
            symptoms.extend(matches)
        
        # Extract direct symptom mentions
        for keyword in symptom_keywords:
            if keyword in text:
                symptoms.append(keyword)
        
        # Remove duplicates and clean
        symptoms = list(set(symptoms))
        symptoms = [s for s in symptoms if len(s) > 2]  # Remove very short words
        
        return symptoms
    
    def _extract_conditions(self, text: str) -> List[str]:
        """Extract medical conditions from patient input."""
        conditions = []
        
        # Common condition keywords
        condition_keywords = [
            "diabetes", "hypertension", "asthma", "arthritis", "depression",
            "anxiety", "migraine", "epilepsy", "parkinson", "alzheimer",
            "cancer", "tumor", "infection", "inflammation", "allergy"
        ]
        
        # Extract conditions
        for keyword in condition_keywords:
            if keyword in text:
                conditions.append(keyword)
        
        return conditions
    
    def _determine_specialties(self, text: str, symptoms: List[str], conditions: List[str]) -> List[str]:
        """Determine which medical specialties are needed based on input."""
        specialties = []
        
        # Combine all text for analysis
        all_text = " ".join([text] + symptoms + conditions)
        
        # Check each specialty
        for specialty, keywords in self.specialty_keywords.items():
            for keyword in keywords:
                if keyword in all_text:
                    specialties.append(specialty)
                    break  # Found match, move to next specialty
        
        # Remove duplicates
        specialties = list(set(specialties))
        
        # If no specialties found, try to infer from symptoms
        if not specialties:
            specialties = self._infer_specialties_from_symptoms(symptoms)
        
        return specialties
    
    def _infer_specialties_from_symptoms(self, symptoms: List[str]) -> List[str]:
        """Infer specialties from symptoms when direct mapping fails."""
        specialties = []
        
        # Simple symptom-to-specialty mapping
        symptom_specialty_map = {
            "chest": "cardiology",
            "heart": "cardiology",
            "skin": "dermatology",
            "rash": "dermatology",
            "headache": "neurology",
            "brain": "neurology",
            "bone": "orthopedics",
            "joint": "orthopedics",
            "stomach": "gastroenterology",
            "digestive": "gastroenterology",
            "lung": "pulmonology",
            "breathing": "pulmonology",
            "kidney": "urology",
            "urinary": "urology"
        }
        
        for symptom in symptoms:
            for keyword, specialty in symptom_specialty_map.items():
                if keyword in symptom:
                    specialties.append(specialty)
        
        return list(set(specialties))
    
    def _determine_urgency(self, text: str, symptoms: List[str], conditions: List[str]) -> str:
        """Determine urgency level from patient input."""
        all_text = " ".join([text] + symptoms + conditions)
        
        # Check for emergency indicators
        for indicator in self.urgency_indicators["emergency"]:
            if indicator in all_text:
                return "emergency"
        
        # Check for high urgency indicators
        for indicator in self.urgency_indicators["high"]:
            if indicator in all_text:
                return "high"
        
        # Check for low urgency indicators
        for indicator in self.urgency_indicators["low"]:
            if indicator in all_text:
                return "low"
        
        # Default to medium
        return "medium"
    
    def get_specialty_keywords(self) -> Dict[str, List[str]]:
        """Get the specialty keyword mappings."""
        return self.specialty_keywords.copy()
    
    def add_specialty_keywords(self, specialty: str, keywords: List[str]) -> None:
        """Add new keywords for a specialty."""
        if specialty not in self.specialty_keywords:
            self.specialty_keywords[specialty] = []
        
        self.specialty_keywords[specialty].extend(keywords)
        self.specialty_keywords[specialty] = list(set(self.specialty_keywords[specialty]))
        
        logger.info(f"Added {len(keywords)} keywords for specialty: {specialty}")
    
    def validate_patient_profile(self, profile: PatientProfile) -> bool:
        """Validate a patient profile for completeness."""
        if not profile.symptoms and not profile.conditions:
            return False
        
        if not profile.specialties_needed:
            return False
        
        if profile.urgency_level not in ["low", "medium", "high", "emergency"]:
            return False
        
        return True
