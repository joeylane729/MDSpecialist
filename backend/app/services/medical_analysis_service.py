import os
import json
import logging
import asyncio
import httpx
from typing import List, Optional, Tuple, Dict, Any
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from ..models.specialist_recommendation import PatientProfile

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MedicalAnalysisService:
    """Service for comprehensive medical analysis including specialty determination, ICD-10 coding, and diagnosis prediction."""
    
    def __init__(self, db: Session = None):
        self.llm = ChatOpenAI(model="gpt-5.1", temperature=0.1)
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
    
    async def comprehensive_analysis(self, patient_input: str, custom_diagnoses_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Perform comprehensive medical analysis including patient processing and medical analysis.
        CPT codes are NOT generated in this step - they must be generated separately via generate_cpt_codes_from_analysis().
        
        Args:
            patient_input: Patient input string containing symptoms, diagnosis, etc.
            custom_diagnoses_prompt: Optional custom prompt to override default for diagnosis/treatment generation
        """
        try:
            # Parse patient input to extract individual fields
            symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content = self._parse_patient_input(patient_input)
            
            # Get patient profile
            patient_profile = await self.process_patient_input(patient_input)
            
            # Perform medical analysis with individual fields including PDF content
            diagnoses_result, diagnoses_prompt_text = await self.predict_diagnoses(
                symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content,
                custom_prompt=custom_diagnoses_prompt
            )
            
            medical_analysis = {
                "predicted_icd10": await self.predict_icd10_code(symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content),
                "diagnoses": diagnoses_result
            }
            
            # Ensure diagnoses is not None
            if medical_analysis["diagnoses"] is None:
                logger.warning("⚠️  predict_diagnoses returned None, setting to empty dict")
                medical_analysis["diagnoses"] = {}
            
            # Add ICD-10 description if we have the code
            if medical_analysis["predicted_icd10"] and self.db:
                logger.info(f"🔍 Looking up ICD-10 description for: {medical_analysis['predicted_icd10']}")
                icd10_description = self.lookup_icd10_description(medical_analysis["predicted_icd10"])
                if icd10_description:
                    medical_analysis["icd10_description"] = icd10_description
                    logger.info(f"✅ Added ICD-10 description: {icd10_description[:50]}...")
                else:
                    logger.warning(f"⚠️  Could not find ICD-10 description for: {medical_analysis['predicted_icd10']}")
            
            # Extract treatment options from diagnoses if available (needed for CPT code prediction)
            treatment_options = []
            if medical_analysis["diagnoses"] and "treatment_options" in medical_analysis["diagnoses"]:
                treatment_options = medical_analysis["diagnoses"]["treatment_options"]
                logger.info(f"📋 Found {len(treatment_options)} treatment options:")
                for i, option in enumerate(treatment_options):
                    logger.info(f"   {i+1}. {option.get('name', 'Unnamed')}")
            else:
                logger.warning("⚠️  No treatment options found in medical analysis")
                logger.debug(f"🔍 Available keys: {list(medical_analysis.keys())}")
                if "diagnoses" in medical_analysis:
                    logger.debug(f"🔍 Diagnoses keys: {list(medical_analysis['diagnoses'].keys())}")
            
            # Generate search query for Pinecone using the same prompt as LangChainRetrievalStrategies
            search_query = ""
            if medical_analysis.get("icd10_description") and diagnosis:
                logger.info(f"🔍 Generating search query for Pinecone...")
                search_query = await self.generate_search_query(
                    medical_analysis.get("icd10_description", ""),
                    diagnosis
                )
                logger.info(f"✅ Generated search query: {search_query[:100]}{'...' if len(search_query) > 100 else ''}")
            else:
                logger.warning("⚠️  Cannot generate search query - missing ICD-10 description or user diagnosis")
            
            # CPT codes are NOT generated in this step - they must be generated separately
            # This is part of the step-by-step flow where diagnosis/treatment options come first
            cpt_codes = []
            cpt_prompt_text = ""
            logger.info("⏭️  Skipping CPT code generation (step-by-step flow - generate separately)")
            
            # Log diagnosis structure for debugging
            logger.debug(f"🔍 Diagnosis structure type: {type(medical_analysis['diagnoses'])}")
            if medical_analysis.get("diagnoses"):
                logger.debug(f"🔍 Diagnosis content: {medical_analysis['diagnoses']}")
            
            # Extract diagnosis data for frontend compatibility
            
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
                
                # User input fields
                "user_diagnosis": diagnosis,  # User-entered diagnosis text
                
                # Medical analysis data (flattened for frontend compatibility)
                "predicted_icd10": primary_icd10,
                "icd10_description": primary_description,
                "treatment_options": treatment_options,
                "cpt_codes": cpt_codes,  # Relevant CPT codes for the diagnosis
                "cpt_prompt_text": cpt_prompt_text,  # Actual GPT prompt used to generate CPT codes
                "diagnoses_prompt_text": diagnoses_prompt_text,  # Actual GPT prompt used to generate diagnoses/treatment options
                "search_query": search_query,  # Pre-generated search query for Pinecone
                
                # Keep original nested structure for backward compatibility
                "diagnoses": medical_analysis["diagnoses"]
            }
            
            logger.info(f"✅ Comprehensive analysis completed: ICD-10={comprehensive_result['predicted_icd10']}")
            logger.info(f"📋 Analysis includes {len(treatment_options)} treatment options")
            logger.debug(f"🔍 Analysis result keys: {list(comprehensive_result.keys())}")
            logger.debug(f"🔍 Primary description: {comprehensive_result.get('icd10_description', 'None')}")
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
            logger.warning("⚠️  No database session available for ICD-10 lookup")
            return None
            
        try:
            logger.debug(f"🔍 Looking up ICD-10 code: {code}")
            
            # Try the original code first
            query = text("SELECT description FROM icd10_codes WHERE code = :code")
            query_params = {"code": code}
            
            # Log the exact SQL query being executed
            query_sql = str(query.compile(compile_kwargs={"literal_binds": False}))
            logger.info(f"📋 ICD-10 Query SQL:\n{query_sql}")
            logger.info(f"📋 Query Parameters: {query_params}")
            
            result = self.db.execute(query, query_params)
            row = result.fetchone()
            if row:
                logger.debug(f"✅ Found description for {code}: {row[0][:50]}...")
                return row[0]
            
            # If not found, try without the dot (GPT often returns codes with dots like "C71.9")
            code_without_dot = code.replace('.', '')
            if code_without_dot != code:
                logger.debug(f"🔄 Trying normalized code: {code_without_dot}")
                query = text("SELECT description FROM icd10_codes WHERE code = :code")
                query_params = {"code": code_without_dot}
                
                # Log the exact SQL query being executed
                query_sql = str(query.compile(compile_kwargs={"literal_binds": False}))
                logger.info(f"📋 ICD-10 Query SQL (normalized):\n{query_sql}")
                logger.info(f"📋 Query Parameters: {query_params}")
                
                result = self.db.execute(query, query_params)
                row = result.fetchone()
                if row:
                    logger.info(f"✅ Found description for normalized code '{code_without_dot}' (original: '{code}')")
                    return row[0]
            
            logger.warning(f"❌ No description found for ICD-10 code: {code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error looking up ICD-10 description for {code}: {e}")
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
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "symptoms": symptoms,
                "diagnosis": diagnosis,
                "medical_history": medical_history,
                "medications": medications,
                "surgical_history": surgical_history,
                "pdf_content": pdf_content
            })
            
            # Extract the ICD-10 code from the response - LCEL returns AIMessage object
            icd_code = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            icd_code = icd_code.replace('"', '').replace("'", "").strip()
            
            # Basic validation that it looks like an ICD-10 code (letter followed by numbers)
            if len(icd_code) >= 3 and icd_code[0].isalpha() and any(c.isdigit() for c in icd_code):
                return icd_code
            else:
                logger.warning(f"GPT returned '{icd_code}' which doesn't look like a valid ICD-10 code")
                return None
                
        except Exception as e:
            logger.error(f"Error in GPT ICD-10 prediction: {e}")
            return None

    async def generate_search_query(
        self,
        icd10_description: str,
        user_diagnosis: str
    ) -> str:
        """
        Generate a search query for Pinecone using the exact same prompt as LangChainRetrievalStrategies.
        
        Args:
            icd10_description: Medical analysis diagnosis description
            user_diagnosis: User-entered diagnosis
            
        Returns:
            Search query string with OR-separated variations
        """
        try:
            prompt = PromptTemplate(
                input_variables=["icd10_description", "user_diagnosis"],
                template="""Generate a concise search query to find PubMed articles and medical lectures from our vector database using both the user-entered diagnosis and the medical analysis diagnosis:

Medical Analysis Diagnosis: {icd10_description}
User-Entered Diagnosis: {user_diagnosis}

The query should include the most important variations (maximum 5-7 terms) separated by the OR operator. Focus on the most common medical terms and synonyms.

Example: term1 OR term2 OR term3 OR term4 OR term5

IMPORTANT: Keep the query concise to avoid payload size limits. Return ONLY the search query string itself with NO explanations, NO markdown, NO code blocks, NO additional text. Just the query."""
            )
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "icd10_description": icd10_description,
                "user_diagnosis": user_diagnosis
            })
            
            # Extract the query response
            query = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if query.startswith('```json'):
                query = query.replace('```json', '').replace('```', '').strip()
            elif query.startswith('```'):
                query = query.replace('```', '').strip()
            
            logger.info(f"🔍 Generated search query: {query}")
            return query
            
        except Exception as e:
            logger.error(f"Error generating search query: {e}")
            return ""

    async def predict_cpt_codes(
        self,
        search_query_terms: List[str],
        treatment_options: Optional[List[Dict[str, str]]] = None,
        custom_prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Use GPT to predict relevant CPT codes that a neurosurgeon would use to treat the given diagnosis terms and treatment options.
        
        Args:
            search_query_terms: List of diagnosis terms/descriptions from the search query (e.g., ["acoustic neuroma", "vestibular schwannoma", ...])
            treatment_options: Optional list of treatment options with name, outcomes, and complications
            
        Returns:
            Tuple of (List of dictionaries containing CPT code and description, rendered prompt text with actual values)
        """
        try:
            # Format the terms as a readable list
            terms_text = "\n".join([f"- {term.strip()}" for term in search_query_terms if term.strip()])
            
            # Format treatment options for the prompt
            treatment_options_text = ""
            if treatment_options and len(treatment_options) > 0:
                treatment_lines = []
                for i, option in enumerate(treatment_options, 1):
                    name = option.get('name', f'Treatment {i}')
                    treatment_lines.append(f"{i}. {name}")
                treatment_options_text = "\n".join(treatment_lines)
            else:
                treatment_options_text = "None specified"
            
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                # Escape all curly braces except for our template variables to prevent LangChain from parsing them
                escaped_prompt = custom_prompt
                # Temporarily replace our template variables with placeholders
                escaped_prompt = escaped_prompt.replace("{diagnosis_terms}", "__DIAGNOSIS_TERMS__")
                escaped_prompt = escaped_prompt.replace("{treatment_options}", "__TREATMENT_OPTIONS__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS_TERMS__}}", "{diagnosis_terms}")
                escaped_prompt = escaped_prompt.replace("{{__TREATMENT_OPTIONS__}}", "{treatment_options}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if "{diagnosis_terms}" in custom_prompt or "{treatment_options}" in custom_prompt:
                    try:
                        rendered_prompt = custom_prompt.format(
                            diagnosis_terms=terms_text,
                            treatment_options=treatment_options_text
                        )
                    except KeyError as e:
                        # If formatting fails, log and use as-is
                        logger.warning(f"⚠️  Could not format custom prompt with variables: {e}")
                        rendered_prompt = custom_prompt
                else:
                    # If custom prompt doesn't have these variables, use it as-is
                    rendered_prompt = custom_prompt
            else:
                prompt_template = """Give an exhaustive list of primary CPT codes that could possibly be used by a neurosurgeon to treat patients with any of these diagnoses:
{diagnosis_terms}

Only consider CPT codes that could be used for the following treatment options: 
{treatment_options}

IMPORTANT: 
- Do not include any add-on CPT codes
- Do not include codes that start with 99XXX or 6178X
- Escape all quotes in descriptions (use \\" for quotes inside strings)
- Keep descriptions concise (under 100 characters)
- Do NOT include newlines in description strings
- Ensure all strings are properly closed

Return the response in this exact JSON format:
[
    {{
        "code": "CPT_CODE",
        "description": "Procedure description"
    }},
    {{
        "code": "CPT_CODE",
        "description": "Procedure description"
    }}
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text."""
                
                # Render the prompt with actual values to capture what was sent to GPT
                rendered_prompt = prompt_template.format(
                    diagnosis_terms=terms_text,
                    treatment_options=treatment_options_text
                )
            
            # Create prompt template with variables only if custom prompt uses them
            if custom_prompt:
                # Try to detect if the custom prompt uses the variables
                if "{diagnosis_terms}" in custom_prompt or "{treatment_options}" in custom_prompt:
                    prompt = PromptTemplate(
                        input_variables=["diagnosis_terms", "treatment_options"],
                        template=prompt_template
                    )
                else:
                    # If no variables, create a simple template without variables
                    prompt = PromptTemplate(
                        input_variables=[],
                        template=prompt_template
                    )
            else:
                prompt = PromptTemplate(
                    input_variables=["diagnosis_terms", "treatment_options"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            # Invoke with variables only if they're expected
            if custom_prompt and "{diagnosis_terms}" not in custom_prompt and "{treatment_options}" not in custom_prompt:
                response = await chain.ainvoke({})
                # For custom prompts without variables, the rendered prompt is the prompt itself
                if not rendered_prompt:
                    rendered_prompt = prompt_template
            else:
                response = await chain.ainvoke({
                    "diagnosis_terms": terms_text,
                    "treatment_options": treatment_options_text
                })
            
            # Extract the JSON response
            response_text = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Try to extract JSON array if response contains other text
            # Look for the first '[' and last ']' to extract just the JSON array
            first_bracket = response_text.find('[')
            last_bracket = response_text.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
                response_text = response_text[first_bracket:last_bracket + 1]
            
            # Try to fix common JSON issues
            # Fix unescaped quotes in description fields (but not in code fields)
            # This is a simple heuristic - look for patterns like "description": "text with "quote" here"
            # We'll try to escape quotes that appear inside description values
            try:
                # First attempt: parse as-is
                cpt_codes = json.loads(response_text)
            except json.JSONDecodeError as json_error:
                logger.warning(f"⚠️  Initial JSON parse failed: {json_error}. Attempting to fix...")
                logger.debug(f"Response length: {len(response_text)} chars")
                
                # Strategy 1: Try to find the last complete JSON object and extract valid portion
                # Look for complete objects by finding closing braces followed by commas or closing brackets
                cpt_codes = []
                
                # Strategy 1: Binary search to find the largest valid prefix
                # This is more efficient than removing fixed chunks
                left, right = 0, len(response_text)
                best_valid = None
                
                for attempt in range(10):  # Max 10 binary search attempts
                    mid = (left + right) // 2
                    test_text = response_text[:mid]
                    
                    # Close any open brackets/braces
                    open_brackets = test_text.count('[') - test_text.count(']')
                    open_braces = test_text.count('{') - test_text.count('}')
                    test_text += '}' * open_braces + ']' * open_brackets
                    
                    try:
                        parsed = json.loads(test_text)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            best_valid = parsed
                            left = mid  # Try to get more
                        else:
                            right = mid  # Too much, reduce
                    except json.JSONDecodeError:
                        right = mid  # Invalid, reduce
                
                if best_valid:
                    cpt_codes = best_valid
                    logger.info(f"✅ Extracted {len(cpt_codes)} valid CPT codes from partial JSON (response was {len(response_text)} chars)")
                else:
                    # Strategy 2: Try to extract individual valid JSON objects using regex
                    # This is a fallback if binary search fails
                    import re
                    # Find all complete JSON objects: { "code": "...", "description": "..." }
                    object_pattern = r'\{\s*"code"\s*:\s*"[^"]*"\s*,\s*"description"\s*:\s*"[^"]*"\s*\}'
                    matches = re.findall(object_pattern, response_text)
                    
                    if matches:
                        # Try to parse each match as JSON
                        valid_objects = []
                        for match in matches:
                            try:
                                obj = json.loads(match)
                                valid_objects.append(obj)
                            except json.JSONDecodeError:
                                continue
                        
                        if valid_objects:
                            cpt_codes = valid_objects
                            logger.info(f"✅ Extracted {len(cpt_codes)} valid CPT codes using regex pattern matching")
                        else:
                            logger.error(f"❌ Could not extract any valid CPT codes. Error: {json_error}")
                            logger.error(f"Problematic JSON (first 1000 chars): {response_text[:1000]}")
                            return []
                    else:
                        logger.error(f"❌ Could not extract valid CPT codes. Error: {json_error}")
                        logger.error(f"Problematic JSON (first 1000 chars): {response_text[:1000]}")
                        return []
            
            logger.info(f"✅ Predicted {len(cpt_codes)} CPT codes for {len(search_query_terms)} diagnosis terms")
            return cpt_codes, rendered_prompt
        except Exception as e:
            logger.error(f"Error predicting CPT codes: {e}")
            return [], ""
    
    async def generate_cpt_codes_from_analysis(
        self,
        search_query: str,
        treatment_options: List[Dict[str, str]],
        custom_prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Generate CPT codes from search query and treatment options.
        This is a convenience method for the separate CPT code generation endpoint.
        
        Args:
            search_query: Search query string (typically from generate_search_query)
            treatment_options: List of treatment options with name, outcomes, and complications
            
        Returns:
            Tuple of (List of dictionaries containing CPT code and description, rendered prompt text)
        """
        if not search_query:
            logger.warning("⚠️  Cannot generate CPT codes - no search query provided")
            return [], ""
        
        # Parse search query to extract individual terms (split by " OR ")
        search_terms = [term.strip() for term in search_query.split(" OR ") if term.strip()]
        logger.info(f"🔍 Generating CPT codes for {len(search_terms)} diagnosis terms: {', '.join(search_terms[:3])}{'...' if len(search_terms) > 3 else ''}")
        
        if custom_prompt:
            logger.info("📝 Using custom prompt for CPT code generation")
        
        return await self.predict_cpt_codes(search_terms, treatment_options, custom_prompt=custom_prompt)

    async def query_cms_api(
        self,
        cpt_codes: List[Dict[str, str]],
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query the CMS public API using CPT codes from the medical analysis.
        Aggregates data across the most recent 5 years (2023-2019).
        If more than 100 CPT codes, splits into multiple API calls per year.
        If state is provided, filters results by state before selecting top 25.
        Groups results by provider (Rndrng_NPI) and sums Total Services across all years.
        Returns top 25 providers by total services.
        
        Args:
            cpt_codes: List of dictionaries containing CPT codes and descriptions
            state: Optional state filter (2-letter abbreviation or full name)
            
        Returns:
            Dictionary with 'url', 'urls', 'results' (grouped by provider), and metadata
        """
        if not cpt_codes or len(cpt_codes) == 0:
            logger.warning("⚠️  No CPT codes provided for CMS API query")
            return {
                "url": None,
                "urls": [],
                "results": [],
                "total_results": 0,
                "total_providers": 0,
                "cpt_codes_searched": [],
                "error": "No CPT codes provided"
            }
        
        try:
            # Extract just the CPT code values
            cpt_code_values = [cpt['code'] for cpt in cpt_codes if 'code' in cpt]
            
            logger.info(f"🔍 Querying CMS API with {len(cpt_code_values)} CPT codes across 5 years (2023-2019)")
            
            # CMS dataset UUIDs for each year (most recent 5 years)
            year_uuids = {
                2023: "0e9f2f2b-7bf9-451a-912c-e02e654dd725",
                2022: "e650987d-01b7-4f09-b75e-b0b075afbf98",
                2021: "31dc2c47-f297-4948-bfb4-075e1bec3a02",
                2020: "c957b49e-1323-49e7-8678-c09da387551d",
                2019: "867b8ac7-ccb7-4cc9-873d-b24340d89e32"
            }
            
            # Split CPT codes into chunks of 100 if needed
            chunk_size = 100
            cpt_chunks = [
                cpt_code_values[i:i + chunk_size] 
                for i in range(0, len(cpt_code_values), chunk_size)
            ]
            
            # Calculate total API calls: 5 years × number of chunks
            total_calls = len(year_uuids) * len(cpt_chunks)
            logger.info(f"📦 Making {total_calls} API calls ({len(year_uuids)} years × {len(cpt_chunks)} chunk(s) per year)")
            
            # Make API calls for all years and chunks
            all_results = []
            urls_used = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Create all API call tasks
                tasks = []
                for year, uuid in sorted(year_uuids.items(), reverse=True):  # Start with most recent
                    base_url = f"https://data.cms.gov/data-api/v1/dataset/{uuid}/data"
                    
                    for chunk_idx, cpt_chunk in enumerate(cpt_chunks):
                        # Build the full URL with CPT code filters
                        filter_params = "&".join([
                            f"filter[hcpcs][condition][value][]={code}" 
                            for code in cpt_chunk
                        ])
                        
                        full_url = (
                            f"{base_url}?"
                            f"filter[hcpcs][condition][path]=HCPCS_Cd&"
                            f"filter[hcpcs][condition][operator]=IN&"
                            f"{filter_params}"
                        )
                        
                        urls_used.append(full_url)
                        
                        # Create async task for this API call
                        async def make_api_call(url: str, year: int, chunk_idx: int, total_chunks: int, chunk_size: int):
                            try:
                                logger.info(f"🌐 CMS API call for {year} (chunk {chunk_idx + 1}/{total_chunks}): {chunk_size} CPT codes")
                                response = await client.get(url)
                                response.raise_for_status()
                                
                                cms_data = response.json()
                                chunk_results = cms_data if isinstance(cms_data, list) else [cms_data]
                                
                                # Add year metadata to each result for tracking
                                for result in chunk_results:
                                    result['_year'] = year
                                
                                logger.info(f"✅ {year} chunk {chunk_idx + 1} returned {len(chunk_results)} results")
                                return chunk_results
                            except Exception as e:
                                logger.error(f"❌ Error in API call for {year} chunk {chunk_idx + 1}: {e}")
                                return []
                        
                        tasks.append(make_api_call(full_url, year, chunk_idx, len(cpt_chunks), len(cpt_chunk)))
                
                # Execute all API calls in parallel
                results_list = await asyncio.gather(*tasks)
                
                # Flatten all results
                for results in results_list:
                    all_results.extend(results)
            
            # Log summary by year
            year_counts = {}
            for result in all_results:
                year = result.get('_year', 'unknown')
                year_counts[year] = year_counts.get(year, 0) + 1
            
            logger.info(f"📊 Total raw results collected: {len(all_results)}")
            for year in sorted(year_counts.keys(), reverse=True):
                logger.info(f"   📅 {year}: {year_counts[year]} results")
            
            # Group results by provider (Rndrng_NPI) and sum Total Services
            provider_totals: Dict[str, Dict[str, Any]] = {}
            
            for result in all_results:
                npi = result.get('Rndrng_NPI')
                if not npi:
                    continue
                
                tot_srvcs = result.get('Tot_Srvcs', 0)
                try:
                    tot_srvcs_int = int(tot_srvcs) if tot_srvcs else 0
                except (ValueError, TypeError):
                    tot_srvcs_int = 0
                
                if npi not in provider_totals:
                    provider_totals[npi] = {
                        'Rndrng_NPI': npi,
                        'Rndrng_Prvdr_First_Name': result.get('Rndrng_Prvdr_First_Name', ''),
                        'Rndrng_Prvdr_Last_Org_Name': result.get('Rndrng_Prvdr_Last_Org_Name', ''),
                        'Rndrng_Prvdr_City': result.get('Rndrng_Prvdr_City', ''),
                        'Rndrng_Prvdr_State_Abrvtn': result.get('Rndrng_Prvdr_State_Abrvtn', ''),
                        'Tot_Srvcs': 0,
                        'HCPCS_Codes': set(),  # Track unique CPT codes
                        'HCPCS_Code_Descriptions': {}  # Track descriptions per CPT code: {code: (description, year)}
                    }
                
                provider_totals[npi]['Tot_Srvcs'] += tot_srvcs_int
                
                # Track CPT codes and descriptions (keep most recent description per code)
                hcpcs_cd = result.get('HCPCS_Cd', '')
                hcpcs_desc = result.get('HCPCS_Desc', '')
                result_year = result.get('_year', 0)  # Get year from result metadata
                
                if hcpcs_cd:
                    provider_totals[npi]['HCPCS_Codes'].add(hcpcs_cd)
                    if hcpcs_desc:
                        # Track descriptions per CPT code, keeping only the most recent one
                        if hcpcs_cd not in provider_totals[npi]['HCPCS_Code_Descriptions']:
                            # First time seeing this code, store description and year
                            provider_totals[npi]['HCPCS_Code_Descriptions'][hcpcs_cd] = (hcpcs_desc, result_year)
                        else:
                            # Already have a description for this code, keep the most recent one
                            existing_desc, existing_year = provider_totals[npi]['HCPCS_Code_Descriptions'][hcpcs_cd]
                            if result_year > existing_year:
                                provider_totals[npi]['HCPCS_Code_Descriptions'][hcpcs_cd] = (hcpcs_desc, result_year)
            
            # Convert to list and sort by Tot_Srvcs descending
            grouped_results = list(provider_totals.values())
            grouped_results.sort(key=lambda x: x['Tot_Srvcs'], reverse=True)
            
            # Filter by state if provided, then take top 25
            state_abbrev = None
            filtered_count = None
            if state:
                logger.info(f"🔍 Filtering CMS results by state: {state}")
                # Convert state to 2-letter abbreviation if needed
                state_abbrev = state.upper().strip()
                if len(state_abbrev) > 2:
                    # State name to abbreviation mapping
                    state_map = {
                        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
                        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
                        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
                        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
                        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
                        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
                        'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
                        'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
                        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
                        'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
                        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
                        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
                        'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC'
                    }
                    state_abbrev = state_map.get(state_abbrev, state_abbrev)
                
                # Filter by state
                filtered_by_state = [
                    p for p in grouped_results 
                    if (p.get('Rndrng_Prvdr_State_Abrvtn') or '').upper().strip() == state_abbrev
                ]
                logger.info(f"🔍 Filtered {len(filtered_by_state)} providers in state {state_abbrev} (from {len(grouped_results)} total)")
                top_25_providers = filtered_by_state[:25]
                filtered_count = len(filtered_by_state)
            else:
                # No state filter, just take top 25
                top_25_providers = grouped_results[:25]
            
            # Convert sets to lists and build descriptions list matching CPT codes
            for provider in top_25_providers:
                provider['HCPCS_Codes'] = sorted(list(provider['HCPCS_Codes']))
                # Build HCPCS_Descriptions list: one description per CPT code (most recent)
                descriptions = []
                code_descriptions = provider.get('HCPCS_Code_Descriptions', {})
                for code in provider['HCPCS_Codes']:
                    if code in code_descriptions:
                        desc, _ = code_descriptions[code]
                        descriptions.append(desc)
                provider['HCPCS_Descriptions'] = descriptions
                # Remove internal tracking dict
                provider.pop('HCPCS_Code_Descriptions', None)
            
            if state and filtered_count is not None and state_abbrev:
                logger.info(f"✅ Grouped into {len(provider_totals)} total providers, filtered to {filtered_count} in state {state_abbrev}, returning top {len(top_25_providers)}")
            else:
                logger.info(f"✅ Grouped into {len(provider_totals)} providers, returning top {len(top_25_providers)}")
            
            result = {
                "url": urls_used[0] if urls_used else None,  # Primary URL for display (first one)
                "urls": urls_used,  # All URLs used (all years and chunks)
                "results": top_25_providers,
                "total_results": len(all_results),  # Total raw results across all years
                "total_providers": len(provider_totals),  # Total unique providers
                "cpt_codes_searched": cpt_code_values,
                "years_queried": sorted(year_uuids.keys(), reverse=True),  # Years included in aggregation
                "error": None
            }
            
            return result
                
        except httpx.TimeoutException as e:
            logger.error(f"❌ CMS API request timed out: {e}")
            return {
                "url": None,
                "urls": [],
                "results": [],
                "total_results": 0,
                "total_providers": 0,
                "cpt_codes_searched": [],
                "error": f"Request timed out: {str(e)}"
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ CMS API HTTP error: {e.response.status_code} - {e}")
            return {
                "url": None,
                "urls": [],
                "results": [],
                "total_results": 0,
                "total_providers": 0,
                "cpt_codes_searched": [],
                "error": f"HTTP {e.response.status_code}: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Error querying CMS API: {e}")
            return {
                "url": None,
                "urls": [],
                "results": [],
                "total_results": 0,
                "total_providers": 0,
                "cpt_codes_searched": [],
                "error": str(e)
            }

    async def predict_diagnoses(
        self, 
        symptoms: str, 
        diagnosis: str, 
        medical_history: str = "", 
        medications: str = "", 
        surgical_history: str = "",
        pdf_content: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], str]:
        """
        Use GPT to predict primary diagnosis and treatment options based on patient information.
        
        Args:
            symptoms: Patient symptoms
            diagnosis: Patient diagnosis
            medical_history: Medical history (optional)
            medications: Current medications (optional)
            surgical_history: Surgical history (optional)
            pdf_content: Extracted content from uploaded PDF files (optional)
            custom_prompt: Optional custom prompt to override default
            
        Returns:
            Tuple of (Dictionary containing primary diagnosis and treatment options, rendered prompt text)
        """
        try:
            default_template = """
                Patient Information:
                Symptoms: {symptoms}
                Diagnosis: {diagnosis}
                Medical History: {medical_history}
                Current Medications: {medications}
                Surgical History: {surgical_history}
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Analyze the information above and provide:
                1. Primary diagnosis (most likely ICD-10 code and description based on symptoms and diagnosis)
                2. Treatment options

                Provide all relevant treatment options based on the diagnosis.
                                
                Return the response in this exact JSON format:
                {{
                    "primary": {{
                        "code": "ICD10_CODE",
                        "description": "Medical description"
                    }},
                    "treatment_options": [
                        {{
                            "name": "Treatment name",
                            "outcomes": "Expected outcomes and success rates",
                            "complications": "Potential complications and risks"
                        }}
                    ]
                }}
                                
                """
            
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                # Escape all curly braces except for our template variables to prevent LangChain from parsing them
                escaped_prompt = custom_prompt
                # Temporarily replace our template variables with placeholders
                escaped_prompt = escaped_prompt.replace("{symptoms}", "__SYMPTOMS__")
                escaped_prompt = escaped_prompt.replace("{diagnosis}", "__DIAGNOSIS__")
                escaped_prompt = escaped_prompt.replace("{medical_history}", "__MEDICAL_HISTORY__")
                escaped_prompt = escaped_prompt.replace("{medications}", "__MEDICATIONS__")
                escaped_prompt = escaped_prompt.replace("{surgical_history}", "__SURGICAL_HISTORY__")
                escaped_prompt = escaped_prompt.replace("{pdf_content}", "__PDF_CONTENT__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__SYMPTOMS__}}", "{symptoms}")
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS__}}", "{diagnosis}")
                escaped_prompt = escaped_prompt.replace("{{__MEDICAL_HISTORY__}}", "{medical_history}")
                escaped_prompt = escaped_prompt.replace("{{__MEDICATIONS__}}", "{medications}")
                escaped_prompt = escaped_prompt.replace("{{__SURGICAL_HISTORY__}}", "{surgical_history}")
                escaped_prompt = escaped_prompt.replace("{{__PDF_CONTENT__}}", "{pdf_content}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if any(var in custom_prompt for var in ["{symptoms}", "{diagnosis}", "{medical_history}", "{medications}", "{surgical_history}", "{pdf_content}"]):
                    # Variables are present, use LangChain PromptTemplate
                    prompt = PromptTemplate(
                        input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                        template=prompt_template
                    )
                    rendered_prompt = prompt.format(
                        symptoms=symptoms,
                        diagnosis=diagnosis,
                        medical_history=medical_history,
                        medications=medications,
                        surgical_history=surgical_history,
                        pdf_content=pdf_content
                    )
                else:
                    # No variables, use prompt as-is
                    rendered_prompt = custom_prompt
            else:
                prompt_template = default_template
                prompt = PromptTemplate(
                    input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                    template=prompt_template
                )
                rendered_prompt = prompt.format(
                    symptoms=symptoms,
                    diagnosis=diagnosis,
                    medical_history=medical_history,
                    medications=medications,
                    surgical_history=surgical_history,
                    pdf_content=pdf_content
                )
            
            # Create prompt template for LangChain (always use variables even if custom prompt doesn't have them)
            if custom_prompt:
                prompt = PromptTemplate(
                    input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                    template=prompt_template
                )
            else:
                prompt = PromptTemplate(
                    input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "symptoms": symptoms,
                "diagnosis": diagnosis,
                "medical_history": medical_history,
                "medications": medications,
                "surgical_history": surgical_history,
                "pdf_content": pdf_content
            })
            
            # Extract the JSON response - LCEL returns AIMessage object
            response_text = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Parse the JSON response
            diagnoses = json.loads(response_text)
            
            # Validate the response structure
            if 'primary' in diagnoses:
                # Look up descriptions for all codes from our database
                if self.db:
                    # Look up primary diagnosis description
                    if 'code' in diagnoses['primary']:
                        primary_desc = self.lookup_icd10_description(diagnoses['primary']['code'])
                        if primary_desc:
                            diagnoses['primary']['description'] = primary_desc
                
                return diagnoses, rendered_prompt
            else:
                logger.warning(f"GPT returned invalid response structure: {diagnoses}")
                return {"primary": {}, "treatment_options": []}, rendered_prompt
                
        except Exception as e:
            logger.error(f"Error in GPT diagnosis prediction: {e}")
            return {"primary": {}, "differential": [], "treatment_options": []}, rendered_prompt if 'rendered_prompt' in locals() else ""
