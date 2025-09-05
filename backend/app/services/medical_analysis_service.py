import os
import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from ..models.specialist_recommendation import PatientProfile

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MedicalAnalysisService:
    """Service for comprehensive medical analysis including specialty determination, ICD-10 coding, and diagnosis prediction."""
    
    def __init__(self, db: Session = None):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        self.db = db
        
        # Patient processing prompt
        # No longer need complex patient processing - just pass through the input
        
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
    
    def _parse_patient_input(self, patient_input: str) -> Tuple[str, str, str, str, str, str]:
        """
        Parse the combined patient input string to extract individual fields.
        
        Args:
            patient_input: Combined patient input string
            
        Returns:
            Tuple of (symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content)
        """
        # Initialize with empty strings
        symptoms = ""
        diagnosis = ""
        medical_history = ""
        medications = ""
        surgical_history = ""
        pdf_content = ""
        
        # Split by sections
        sections = patient_input.split('\n\n')
        
        for section in sections:
            section = section.strip()
            if section.startswith('Symptoms:'):
                symptoms = section.replace('Symptoms:', '').strip()
            elif section.startswith('Diagnosis:'):
                diagnosis = section.replace('Diagnosis:', '').strip()
            elif section.startswith('Medical History:'):
                medical_history = section.replace('Medical History:', '').strip()
            elif section.startswith('Current Medications:'):
                medications = section.replace('Current Medications:', '').strip()
            elif section.startswith('Surgical History:'):
                surgical_history = section.replace('Surgical History:', '').strip()
            elif section.startswith('Additional Information from Files:'):
                # Extract PDF content from the files section
                pdf_content = section.replace('Additional Information from Files:', '').strip()
                # Remove the "(PDF uploaded)" notes and keep only actual content
                pdf_content = pdf_content.replace('(PDF uploaded)', '').strip()
        
        return symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content
    
    async def process_patient_input(
        self,
        patient_input: str
    ) -> PatientProfile:
        """Process patient input - just pass through the original input."""
        try:
            # Simply pass through the patient input without any processing
            profile = PatientProfile(
                symptoms=[],  # No longer extracting symptoms
                conditions=[],
                specialties_needed=[],  # No longer extracting specialties

                location_preference=None,
                additional_notes=patient_input  # Pass through the original input directly
            )
            
            logger.info(f"Passed through patient input: {len(patient_input)} characters")
            return profile
            
        except Exception as e:
            logger.error(f"Error processing patient input: {str(e)}")
            raise
    
    async def comprehensive_analysis(self, patient_input: str) -> Dict[str, Any]:
        """Perform comprehensive medical analysis including patient processing and medical analysis."""
        try:
            # Parse patient input to extract individual fields
            symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content = self._parse_patient_input(patient_input)
            
            # Get patient profile
            patient_profile = await self.process_patient_input(patient_input)
            
            # Perform medical analysis with individual fields including PDF content
            medical_analysis = {
                "predicted_icd10": await self.predict_icd10_code(symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content),
                "diagnoses": await self.predict_diagnoses(symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content)
            }
            
            # Add ICD-10 description if we have the code
            if medical_analysis["predicted_icd10"] and self.db:
                icd10_description = self.lookup_icd10_description(medical_analysis["predicted_icd10"])
                if icd10_description:
                    medical_analysis["icd10_description"] = icd10_description
            
            # Extract treatment options from diagnoses if available
            treatment_options = []
            if medical_analysis["diagnoses"] and "treatment_options" in medical_analysis["diagnoses"]:
                treatment_options = medical_analysis["diagnoses"]["treatment_options"]
                logger.info(f"🔍 DEBUG: Found {len(treatment_options)} treatment options in medical analysis")
                for i, option in enumerate(treatment_options):
                    logger.info(f"  {i+1}. {option.get('name', 'Unnamed')}")
            else:
                logger.warning("🔍 DEBUG: No treatment options found in medical analysis")
                logger.info(f"🔍 DEBUG: medical_analysis keys: {list(medical_analysis.keys())}")
                if "diagnoses" in medical_analysis:
                    logger.info(f"🔍 DEBUG: diagnoses keys: {list(medical_analysis['diagnoses'].keys())}")
            
            # Debug logging for diagnosis structure
            logger.info(f"🔍 DEBUG: medical_analysis['diagnoses'] type: {type(medical_analysis['diagnoses'])}")
            logger.info(f"🔍 DEBUG: medical_analysis['diagnoses'] content: {medical_analysis['diagnoses']}")
            
            # Extract and flatten diagnosis data for frontend compatibility
            differential_diagnoses = []
            if medical_analysis["diagnoses"] and "differential" in medical_analysis["diagnoses"]:
                differential_diagnoses = medical_analysis["diagnoses"]["differential"]
                logger.info(f"🔍 DEBUG: Found {len(differential_diagnoses)} differential diagnoses")
            else:
                logger.warning(f"🔍 DEBUG: No differential diagnoses found. diagnoses structure: {medical_analysis['diagnoses']}")
            
            # Use primary diagnosis from the diagnoses structure if available
            primary_icd10 = medical_analysis["predicted_icd10"]
            primary_description = medical_analysis.get("icd10_description")
            
            if medical_analysis["diagnoses"] and "primary" in medical_analysis["diagnoses"]:
                primary_icd10 = medical_analysis["diagnoses"]["primary"].get("code", primary_icd10)
                primary_description = medical_analysis["diagnoses"]["primary"].get("description", primary_description)
                logger.info(f"🔍 DEBUG: Using primary diagnosis from diagnoses structure: {primary_icd10} - {primary_description}")
            else:
                logger.warning(f"🔍 DEBUG: No primary diagnosis in diagnoses structure. Using fallback: {primary_icd10} - {primary_description}")
            
            # Combine patient profile and medical analysis into unified result
            comprehensive_result = {
                # Patient profile data
                "symptoms": patient_profile.symptoms,
                "conditions": patient_profile.conditions,
                "specialties_needed": patient_profile.specialties_needed,
                "location_preference": patient_profile.location_preference,
                "additional_notes": patient_profile.additional_notes,
                
                # Medical analysis data (flattened for frontend compatibility)
                "predicted_icd10": primary_icd10,
                "icd10_description": primary_description,
                "differential_diagnoses": differential_diagnoses,
                "treatment_options": treatment_options,
                
                # Keep original nested structure for backward compatibility
                "diagnoses": medical_analysis["diagnoses"]
            }
            
            logger.info(f"Comprehensive analysis completed: icd10={comprehensive_result['predicted_icd10']}")
            logger.info(f"🔍 DEBUG: Comprehensive result includes {len(treatment_options)} treatment options")
            logger.info(f"🔍 DEBUG: Comprehensive result keys: {list(comprehensive_result.keys())}")
            logger.info(f"🔍 DEBUG: differential_diagnoses count: {len(comprehensive_result.get('differential_diagnoses', []))}")
            logger.info(f"🔍 DEBUG: primary description: {comprehensive_result.get('icd10_description', 'None')}")
            return comprehensive_result
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {str(e)}")
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
        Determine specialty by first getting ICD-10 code, then looking up specialty from ICD-10.
        
        PROOF OF CONCEPT: Hard-coded to return "Neurological Surgery" for all cases
        to confine the proof of concept to only consider neurosurgeons.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant medical specialty as a string, or None if failed
        """
        # PROOF OF CONCEPT: Hard-coded to return Neurological Surgery
        # This confines the proof of concept to only consider neurosurgeons
        return "Neurological Surgery"
        
        # COMMENTED OUT: Original dynamic specialty determination logic
        # try:
        #     # First get the ICD-10 code
        #     icd10_code = await self.predict_icd10_code(diagnosis_text)
        #     if not icd10_code:
        #         return None
        #     
        #     # Then determine specialty based on ICD-10 code
        #     specialty = self._get_specialty_from_icd10(icd10_code)
        #     return specialty
        #             
        # except Exception as e:
        #     print(f"Error determining specialty: {e}")
        #     return None

    def _get_specialty_from_icd10(self, icd10_code: str) -> str:
        """
        Map ICD-10 codes to appropriate medical specialties.
        
        Args:
            icd10_code: The ICD-10 code
            
        Returns:
            The appropriate medical specialty
        """
        # Normalize the ICD-10 code (remove dots)
        normalized_code = icd10_code.replace('.', '')
        
        # Map ICD-10 code ranges to specialties
        if normalized_code.startswith(('G')):
            return "Neurological Surgery"  # Neurological conditions
        elif normalized_code.startswith(('I')):
            return "Cardiology"  # Cardiovascular conditions
        elif normalized_code.startswith(('J')):
            return "Pulmonology"  # Respiratory conditions
        elif normalized_code.startswith(('K')):
            return "Internal Medicine"  # Digestive conditions
        elif normalized_code.startswith(('M')):
            return "Orthopaedic Surgery"  # Musculoskeletal conditions
        elif normalized_code.startswith(('N')):
            return "Internal Medicine"  # Genitourinary conditions
        elif normalized_code.startswith(('O')):
            return "Obstetrics & Gynecology"  # Pregnancy/gynecological
        elif normalized_code.startswith(('P')):
            return "Pediatrics"  # Perinatal conditions
        elif normalized_code.startswith(('Q')):
            return "Pediatrics"  # Congenital conditions
        elif normalized_code.startswith(('R')):
            return "Internal Medicine"  # General symptoms
        elif normalized_code.startswith(('S', 'T')):
            return "Emergency Medicine"  # Injuries/poisoning
        elif normalized_code.startswith(('Z')):
            return "Family Medicine"  # Health status factors
        else:
            return "Family Medicine"  # Default fallback

    async def predict_icd10_code(
        self, 
        symptoms: str, 
        diagnosis: str, 
        medical_history: str = "", 
        medications: str = "", 
        surgical_history: str = "",
        pdf_content: str = ""
    ) -> Optional[str]:
        """
        Use GPT to predict the most accurate ICD-10 code based on patient information.
        
        Args:
            symptoms: Patient symptoms
            diagnosis: Patient diagnosis
            medical_history: Medical history (optional)
            medications: Current medications (optional)
            surgical_history: Surgical history (optional)
            pdf_content: Extracted content from uploaded PDF files (optional)
            
        Returns:
            The most relevant ICD-10 code as a string, or None if failed
        """
        try:
            prompt = PromptTemplate(
                input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                template="""
                Patient Information:
                Symptoms: {symptoms}
                Diagnosis: {diagnosis}
                Medical History: {medical_history}
                Current Medications: {medications}
                Surgical History: {surgical_history}
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Return ONLY the ICD-10 code.
                Example: I21.9
                
                No other text.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            response = await chain.arun(
                symptoms=symptoms,
                diagnosis=diagnosis,
                medical_history=medical_history,
                medications=medications,
                surgical_history=surgical_history,
                pdf_content=pdf_content
            )
            
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

    async def predict_diagnoses(
        self, 
        symptoms: str, 
        diagnosis: str, 
        medical_history: str = "", 
        medications: str = "", 
        surgical_history: str = "",
        pdf_content: str = ""
    ) -> Dict[str, Any]:
        """
        Use GPT to predict primary diagnosis, differential diagnoses, and treatment options based on patient information.
        
        Args:
            symptoms: Patient symptoms
            diagnosis: Patient diagnosis
            medical_history: Medical history (optional)
            medications: Current medications (optional)
            surgical_history: Surgical history (optional)
            pdf_content: Extracted content from uploaded PDF files (optional)
            
        Returns:
            Dictionary containing primary diagnosis, differential diagnoses, and exactly 3 treatment options
        """
        try:
            prompt = PromptTemplate(
                input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                template="""
                Patient Information:
                Symptoms: {symptoms}
                Diagnosis: {diagnosis}
                Medical History: {medical_history}
                Current Medications: {medications}
                Surgical History: {surgical_history}
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Analyze the symptoms and diagnosis information above and provide:
                1. Primary diagnosis (most likely ICD-10 code and description based on symptoms and diagnosis)
                2. Differential diagnoses (3-5 alternative possibilities with ICD-10 codes that could explain the symptoms)
                3. Treatment options (EXACTLY 3 treatment options with outcomes and complications)
                
                Consider the symptoms carefully when determining the most likely diagnosis and alternatives.
                For treatment options, provide exactly 3 evidence-based treatment approaches with realistic outcomes and complications.
                
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
                    ],
                    "treatment_options": [
                        {{
                            "name": "Treatment name",
                            "outcomes": "Expected outcomes and success rates",
                            "complications": "Potential complications and risks"
                        }},
                        {{
                            "name": "Treatment name",
                            "outcomes": "Expected outcomes and success rates",
                            "complications": "Potential complications and risks"
                        }},
                        {{
                            "name": "Treatment name",
                            "outcomes": "Expected outcomes and success rates",
                            "complications": "Potential complications and risks"
                        }}
                    ]
                }}
                
                IMPORTANT: Always provide exactly 3 treatment options. Only return valid JSON. No other text.
                """
            )
            
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            response = await chain.arun(
                symptoms=symptoms,
                diagnosis=diagnosis,
                medical_history=medical_history,
                medications=medications,
                surgical_history=surgical_history,
                pdf_content=pdf_content
            )
            
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
