import os
import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from ..models.specialist_recommendation import PatientProfile

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MedicalAnalysisService:
    """Service for comprehensive medical analysis including specialty determination, ICD-10 coding, and diagnosis prediction."""
    
    def __init__(self, db: Session = None):
        self.llm = OpenAI(temperature=0.1)
        self.db = db
        
        # Patient processing prompt
        self.patient_prompt = PromptTemplate(
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
        
        self.patient_chain = LLMChain(llm=self.llm, prompt=self.patient_prompt)
        
        # Available subspecialties for GPT to choose from
        self.available_specialties = [
            "Family Medicine",
            "Internal Medicine", 
            "Cardiology",
            "Pulmonology",
            "Neurological Surgery",
            "Nuclear Medicine",
            "Obstetrics & Gynecology",
            "Ophthalmology",
            "Orthopaedic Surgery",
            "Otolaryngology",
            "Pediatric Otolaryngology",
            "Pediatrics",
            "Allergy & Immunology",
            "Anesthesiology",
            "Anatomic Pathology",
            "Clinical Pathology",
            "Emergency Medicine",
            "Colon & Rectal Surgery",
            "General Practice",
            "Thoracic Surgery",
            "Hospitalist",
            "Clinical Pharmacology",
            "Pain Medicine",
            "Interventional Pain Medicine"
        ]
    
    def set_db(self, db: Session):
        """Set the database session for ICD-10 lookups."""
        self.db = db
    
    async def process_patient_input(
        self,
        patient_input: str
    ) -> PatientProfile:
        """Process patient input using LangChain."""
        try:
            # Get LLM response
            response = await self.patient_chain.arun(patient_input=patient_input)
            
            # Parse JSON response
            data = json.loads(response.strip())
            
            # Create patient profile
            profile = PatientProfile(
                symptoms=data.get("symptoms", []),
                conditions=[],
                specialties_needed=data.get("specialties", []),
                urgency_level="medium",  # Default value
                location_preference=None,
                additional_notes=patient_input
            )
            
            logger.info(f"Processed patient input: {len(profile.symptoms)} symptoms, {len(profile.specialties_needed)} specialties")
            return profile
            
        except Exception as e:
            logger.error(f"Error processing patient input: {str(e)}")
            raise
    
    def lookup_icd10_description(self, code: str) -> Optional[str]:
        """
        Look up the description for an ICD-10 code from the database.
        
        Args:
            code: The ICD-10 code to look up
            
        Returns:
            The description for the code, or None if not found
        """
        if not self.db:
            print("Warning: No database session available for ICD-10 lookup")
            return None
            
        try:
            # Try the original code first
            result = self.db.execute(
                text("SELECT description FROM icd10_codes WHERE code = :code"),
                {"code": code}
            )
            row = result.fetchone()
            if row:
                return row[0]
            
            # If not found, try without the dot (GPT often returns codes with dots like "C71.9")
            code_without_dot = code.replace('.', '')
            if code_without_dot != code:
                result = self.db.execute(
                    text("SELECT description FROM icd10_codes WHERE code = :code"),
                    {"code": code_without_dot}
                )
                row = result.fetchone()
                if row:
                    print(f"Found description for normalized code '{code_without_dot}' (original: '{code}')")
                    return row[0]
            
            return None
        except Exception as e:
            print(f"Error looking up ICD-10 description: {e}")
            return None

    async def determine_specialty(self, diagnosis_text: str) -> Optional[str]:
        """
        Use GPT to determine the most relevant medical specialty based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant medical specialty as a string, or None if failed
        """
        try:
            prompt = PromptTemplate(
                input_variables=["diagnosis_text", "available_specialties"],
                template="""
                {diagnosis_text}
                Available specialties: {available_specialties}
                
                Based on the symptoms and diagnosis information above, determine the most appropriate medical specialty.
                Consider the symptoms carefully when choosing the specialty.
                
                Return ONLY the specialty name. No explanations.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            response = await chain.arun(
                diagnosis_text=diagnosis_text,
                available_specialties=', '.join(self.available_specialties)
            )
            
            # Extract the specialty from the response
            specialty = response.strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            specialty = specialty.replace('"', '').replace("'", "").strip()
            
            # Validate that the returned specialty is in our list
            if specialty in self.available_specialties:
                return specialty
            else:
                print(f"Warning: GPT returned '{specialty}' which is not in our specialty list")
                # Try to find a close match
                for available in self.available_specialties:
                    if specialty.lower() in available.lower() or available.lower() in specialty.lower():
                        return available
                
                # If no close match, return the first specialty as fallback
                print(f"Using fallback specialty: {self.available_specialties[0]}")
                return self.available_specialties[0]
                
        except Exception as e:
            print(f"Error in GPT service: {e}")
            return None

    async def predict_icd10_code(self, diagnosis_text: str) -> Optional[str]:
        """
        Use GPT to predict the most accurate ICD-10 code based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant ICD-10 code as a string, or None if failed
        """
        try:
            prompt = PromptTemplate(
                input_variables=["diagnosis_text"],
                template="""
                Diagnosis: {diagnosis_text}
                
                Return ONLY the ICD-10 code.
                Example: I21.9
                
                No other text.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            response = await chain.arun(diagnosis_text=diagnosis_text)
            
            # Extract the ICD-10 code from the response
            icd_code = response.strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            icd_code = icd_code.replace('"', '').replace("'", "").strip()
            
            # Basic validation that it looks like an ICD-10 code (letter followed by numbers)
            if len(icd_code) >= 3 and icd_code[0].isalpha() and any(c.isdigit() for c in icd_code):
                return icd_code
            else:
                print(f"Warning: GPT returned '{icd_code}' which doesn't look like a valid ICD-10 code")
                return None
                
        except Exception as e:
            print(f"Error in GPT ICD-10 prediction: {e}")
            return None

    async def predict_diagnoses(self, diagnosis_text: str) -> Dict[str, Any]:
        """
        Use GPT to predict both primary and differential diagnoses based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            Dictionary containing primary diagnosis and differential diagnoses
        """
        try:
            prompt = PromptTemplate(
                input_variables=["diagnosis_text"],
                template="""
                {diagnosis_text}
                
                Analyze the symptoms and diagnosis information above and provide:
                1. Primary diagnosis (most likely ICD-10 code and description based on symptoms and diagnosis)
                2. Differential diagnoses (3-5 alternative possibilities with ICD-10 codes that could explain the symptoms)
                
                Consider the symptoms carefully when determining the most likely diagnosis and alternatives.
                
                Return the response in this exact JSON format:
                {{
                    "primary": {{
                        "code": "ICD10_CODE",
                        "description": "Medical description"
                    }},
                    "differential": [
                        {{
                            "code": "ICD10_CODE",
                            "description": "Medical description"
                        }}
                    ]
                }}
                
                Only return valid JSON. No other text.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            response = await chain.arun(diagnosis_text=diagnosis_text)
            
            # Extract the JSON response
            response_text = response.strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Parse the JSON response
            diagnoses = json.loads(response_text)
            
            # Validate the response structure
            if 'primary' in diagnoses and 'differential' in diagnoses:
                # Look up descriptions for all codes from our database
                if self.db:
                    # Look up primary diagnosis description
                    if 'code' in diagnoses['primary']:
                        primary_desc = self.lookup_icd10_description(diagnoses['primary']['code'])
                        if primary_desc:
                            diagnoses['primary']['description'] = primary_desc
                    
                    # Look up differential diagnosis descriptions
                    for diff in diagnoses['differential']:
                        if 'code' in diff:
                            diff_desc = self.lookup_icd10_description(diff['code'])
                            if diff_desc:
                                diff['description'] = diff_desc
                
                return diagnoses
            else:
                print(f"Warning: GPT returned invalid response structure: {diagnoses}")
                return None
                
        except Exception as e:
            print(f"Error in GPT diagnosis prediction: {e}")
            return None
