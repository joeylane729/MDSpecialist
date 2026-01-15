import json
import logging
import asyncio
import httpx
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class MedicalAnalysisService:
    """Service for comprehensive medical analysis including specialty determination, ICD-10 coding, and diagnosis prediction."""
    
    def __init__(self, db: Session = None):
        self.llm = ChatOpenAI(model="gpt-5.1", temperature=0.1)
        self.db = db
    
    def set_db(self, db: Session):
        """Set the database session for ICD-10 lookups."""
        self.db = db
    
    async def comprehensive_analysis(
        self,
        diagnosis: str,
        anatomical_location: str = "",
        medical_history: str = "",
        medications: str = "",
        surgical_history: str = "",
        pdf_content: str = "",
        custom_diagnoses_prompt: Optional[str] = None,
        custom_search_query_prompt: Optional[str] = None,
        custom_icd10_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform comprehensive medical analysis including patient processing and medical analysis.
        CPT codes are NOT generated in this step - they must be generated separately via generate_cpt_codes_from_analysis().
        
        Args:
            diagnosis: Patient diagnosis
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            medical_history: Medical history (deprecated - always empty)
            medications: Current medications (deprecated - always empty)
            surgical_history: Surgical history (deprecated - always empty)
            pdf_content: Extracted content from uploaded PDF files (optional)
            custom_diagnoses_prompt: Optional custom prompt to override default for diagnosis/treatment generation
            custom_search_query_prompt: Optional custom prompt to override default for search query generation
            custom_icd10_prompt: Optional custom prompt to override default for ICD-10 code generation
        """
        try:
            # Perform medical analysis with diagnosis, anatomical location, and PDF content
            diagnoses_result, diagnoses_prompt_text = await self.predict_diagnoses(
                diagnosis, anatomical_location, pdf_content,
                custom_prompt=custom_diagnoses_prompt
            )
            
            predicted_icd10, icd10_prompt_text = await self.predict_icd10_code(
                diagnosis, anatomical_location, pdf_content, custom_prompt=custom_icd10_prompt
            )
            
            medical_analysis = {
                "predicted_icd10": predicted_icd10,
                "diagnoses": diagnoses_result
            }
            
            # Ensure diagnoses is not None
            if medical_analysis["diagnoses"] is None:
                logger.warning("predict_diagnoses returned None, setting to empty dict")
                medical_analysis["diagnoses"] = {}
            
            # Add ICD-10 description if we have the code
            if medical_analysis["predicted_icd10"] and self.db:
                icd10_description = self.lookup_icd10_description(medical_analysis["predicted_icd10"])
                if icd10_description:
                    medical_analysis["icd10_description"] = icd10_description
                else:
                    logger.warning(f"Could not find ICD-10 description for: {medical_analysis['predicted_icd10']}")
            
            # Extract treatment options from diagnoses if available (needed for CPT code prediction)
            treatment_options = []
            if medical_analysis["diagnoses"] and "treatment_options" in medical_analysis["diagnoses"]:
                treatment_options = medical_analysis["diagnoses"]["treatment_options"]
                # Log treatment options with categories
                logger.info(f"📋 Extracted {len(treatment_options)} treatment options from medical analysis:")
                for i, option in enumerate(treatment_options, 1):
                    category = option.get('category', 'Not specified')
                    name = option.get('name', 'Unnamed')
                    logger.info(f"   {i}. {name} (Category: {category})")
            else:
                logger.warning("No treatment options found in medical analysis")
            
            # Generate search query using the same prompt as SpecialistInformationRetrievalService
            search_query = ""
            search_query_prompt_text = ""
            if medical_analysis.get("icd10_description") and diagnosis:
                search_query, search_query_prompt_text = await self.generate_search_query(
                    icd10_description=medical_analysis.get("icd10_description", ""),
                    user_diagnosis=diagnosis,
                    anatomical_location=anatomical_location,
                    custom_prompt=custom_search_query_prompt
                )
            else:
                logger.warning("Cannot generate search query - missing ICD-10 description or user diagnosis")
            
            # Determine specialty for provider filtering (used by NPI search step)
            # Note: determine_specialty currently returns a constant, but we keep the call for future use
            determined_specialty = await self.determine_specialty("")  # Parameter not currently used
            if not determined_specialty:
                logger.warning("Failed to determine specialty, will use fallback in provider search")
            
            # Extract diagnosis data for frontend compatibility
            
            # Combine patient profile and medical analysis into unified result
            # Note: CPT codes are NOT generated in this step - they must be generated separately via /medical-analysis/cpt-codes
            comprehensive_result = {
                # User input fields
                "user_diagnosis": diagnosis,  # User-entered diagnosis text
                
                # Medical analysis data (flattened for frontend compatibility)
                "predicted_icd10": medical_analysis["predicted_icd10"],
                "icd10_description": medical_analysis.get("icd10_description"),
                "icd10_prompt_text": icd10_prompt_text,  # Actual GPT prompt used to generate ICD-10 code
                "determined_specialty": determined_specialty,  # Specialty determined for provider search
                "treatment_options": treatment_options,
                "diagnoses_prompt_text": diagnoses_prompt_text,  # Actual GPT prompt used to generate diagnoses/treatment options
                "search_query": search_query,  # Pre-generated search query
                "search_query_prompt_text": search_query_prompt_text,  # Actual GPT prompt used to generate search query
                
                # Keep original nested structure for backward compatibility
                "diagnoses": medical_analysis["diagnoses"]
            }
            
            logger.info(f"Comprehensive analysis completed: ICD-10={comprehensive_result['predicted_icd10']}, {len(treatment_options)} treatment options")
            return comprehensive_result
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}", exc_info=True)
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
            return None
            
        try:
            # Try the original code first
            query = text("SELECT description FROM icd10_codes WHERE code = :code")
            result = self.db.execute(query, {"code": code})
            row = result.fetchone()
            if row:
                return row[0]
            
            # If not found, try without the dot (GPT often returns codes with dots like "C71.9")
            code_without_dot = code.replace('.', '')
            if code_without_dot != code:
                query = text("SELECT description FROM icd10_codes WHERE code = :code")
                result = self.db.execute(query, {"code": code_without_dot})
                row = result.fetchone()
                if row:
                    return row[0]
            
            logger.warning(f"No description found for ICD-10 code: {code}")
            return None
        except Exception as e:
            logger.error(f"Error looking up ICD-10 description for {code}: {e}", exc_info=True)
            return None

    async def determine_specialty(self, diagnosis_text: str) -> Optional[str]:
        """
        Determine specialty for provider search.
        
        PROOF OF CONCEPT: Hard-coded to return "Neurological Surgery" for all cases
        to confine the proof of concept to only consider neurosurgeons.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant medical specialty as a string
        """
        return "Neurological Surgery"

    async def predict_icd10_code(
        self, 
        diagnosis: str, 
        anatomical_location: str = "",
        pdf_content: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        Use GPT to predict the most accurate ICD-10 code based on patient information.
        
        Args:
            diagnosis: Patient diagnosis
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            pdf_content: Extracted content from uploaded PDF files (optional)
            custom_prompt: Optional custom prompt to override default
            
        Returns:
            Tuple of (ICD-10 code as string or None if failed, rendered prompt text)
        """
        try:
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                # Escape all curly braces except for our template variables to prevent LangChain from parsing them
                escaped_prompt = custom_prompt
                # Temporarily replace our template variables with placeholders
                escaped_prompt = escaped_prompt.replace("{diagnosis}", "__DIAGNOSIS__")
                escaped_prompt = escaped_prompt.replace("{anatomical_location}", "__ANATOMICAL_LOCATION__")
                escaped_prompt = escaped_prompt.replace("{pdf_content}", "__PDF_CONTENT__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS__}}", "{diagnosis}")
                escaped_prompt = escaped_prompt.replace("{{__ANATOMICAL_LOCATION__}}", "{anatomical_location}")
                escaped_prompt = escaped_prompt.replace("{{__PDF_CONTENT__}}", "{pdf_content}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if any(var in custom_prompt for var in ["{diagnosis}", "{anatomical_location}", "{pdf_content}"]):
                    try:
                        rendered_prompt = custom_prompt.format(
                            diagnosis=diagnosis,
                            anatomical_location=anatomical_location or "",
                            pdf_content=pdf_content
                        )
                    except KeyError as e:
                        logger.warning(f"Could not format custom prompt with variables: {e}")
                        rendered_prompt = custom_prompt
                else:
                    rendered_prompt = custom_prompt
            else:
                prompt_template = """
                Patient Information:
                Diagnosis: {diagnosis}
                Anatomical Location: {anatomical_location}
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Return ONLY the ICD-10 code.
                Example: I21.9
                
                No other text.
                """
                
                # Render the prompt with actual values to capture what was sent to GPT
                rendered_prompt = prompt_template.format(
                    diagnosis=diagnosis,
                    anatomical_location=anatomical_location or "",
                    pdf_content=pdf_content
                )
            
            # Create prompt template with variables only if custom prompt uses them
            if custom_prompt:
                input_vars = []
                if "{diagnosis}" in prompt_template:
                    input_vars.append("diagnosis")
                if "{anatomical_location}" in prompt_template:
                    input_vars.append("anatomical_location")
                if "{pdf_content}" in prompt_template:
                    input_vars.append("pdf_content")
                prompt = PromptTemplate(
                    input_variables=input_vars if input_vars else ["diagnosis", "anatomical_location", "pdf_content"],
                    template=prompt_template
                )
            else:
                prompt = PromptTemplate(
                    input_variables=["diagnosis", "anatomical_location", "pdf_content"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            invoke_dict = {}
            if "{diagnosis}" in prompt_template:
                invoke_dict["diagnosis"] = diagnosis
            if "{anatomical_location}" in prompt_template:
                invoke_dict["anatomical_location"] = anatomical_location or ""
            if "{pdf_content}" in prompt_template:
                invoke_dict["pdf_content"] = pdf_content
            
            response = await chain.ainvoke(invoke_dict if invoke_dict else {
                "diagnosis": diagnosis,
                "anatomical_location": anatomical_location or "",
                "pdf_content": pdf_content
            })
            
            # Extract the ICD-10 code from the response - LCEL returns AIMessage object
            icd_code = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            icd_code = icd_code.replace('"', '').replace("'", "").strip()
            
            # Basic validation that it looks like an ICD-10 code (letter followed by numbers)
            if len(icd_code) >= 3 and icd_code[0].isalpha() and any(c.isdigit() for c in icd_code):
                return icd_code, rendered_prompt
            else:
                logger.warning(f"GPT returned invalid ICD-10 code: {icd_code}")
                return None, rendered_prompt
                
        except Exception as e:
            logger.error(f"Error in GPT ICD-10 prediction: {e}")
            return None, rendered_prompt if 'rendered_prompt' in locals() else ""

    async def generate_search_query(
        self,
        icd10_description: str,
        user_diagnosis: str,
        anatomical_location: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate a search query using the exact same prompt as SpecialistInformationRetrievalService.
        
        Args:
            icd10_description: Medical analysis diagnosis description
            user_diagnosis: User-entered diagnosis
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            custom_prompt: Optional custom prompt to override default
            
        Returns:
            Tuple of (search query string with OR-separated variations, rendered prompt text)
        """
        try:
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                # Escape all curly braces except for our template variables to prevent LangChain from parsing them
                escaped_prompt = custom_prompt
                # Temporarily replace our template variables with placeholders
                escaped_prompt = escaped_prompt.replace("{icd10_description}", "__ICD10_DESCRIPTION__")
                escaped_prompt = escaped_prompt.replace("{user_diagnosis}", "__USER_DIAGNOSIS__")
                escaped_prompt = escaped_prompt.replace("{anatomical_location}", "__ANATOMICAL_LOCATION__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__ICD10_DESCRIPTION__}}", "{icd10_description}")
                escaped_prompt = escaped_prompt.replace("{{__USER_DIAGNOSIS__}}", "{user_diagnosis}")
                escaped_prompt = escaped_prompt.replace("{{__ANATOMICAL_LOCATION__}}", "{anatomical_location}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if "{icd10_description}" in custom_prompt or "{user_diagnosis}" in custom_prompt or "{anatomical_location}" in custom_prompt:
                    try:
                        rendered_prompt = custom_prompt.format(
                            icd10_description=icd10_description,
                            user_diagnosis=user_diagnosis,
                            anatomical_location=anatomical_location or ""
                        )
                    except KeyError as e:
                        # If formatting fails, log and use as-is
                        logger.warning(f"Could not format custom prompt with variables: {e}")
                        rendered_prompt = custom_prompt
                else:
                    # If custom prompt doesn't have these variables, use it as-is
                    rendered_prompt = custom_prompt
            else:
                prompt_template = """Generate a concise search query to find PubMed articles and medical lectures from our database using both the user-entered diagnosis and the medical analysis diagnosis:

Medical Analysis Diagnosis: {icd10_description}
User-Entered Diagnosis: {user_diagnosis}
Anatomical Location: {anatomical_location}

RULES:
- The query should include all variations of this diagnosis separated by the OR operator
- The terms should be specific to the diagnosis and not general terms like "brain tumor" or "brain surgery"
- If anatomical location is provided, ensure the search query includes location-specific terms

Example: term1 OR term2 OR term3 OR term4 OR term5

IMPORTANT: Return ONLY the search query string itself with NO explanations, NO markdown, NO code blocks, NO additional text. Just the query."""
                
                # Render the prompt with actual values to capture what was sent to GPT
                rendered_prompt = prompt_template.format(
                    icd10_description=icd10_description,
                    user_diagnosis=user_diagnosis,
                    anatomical_location=anatomical_location or ""
                )
            
            # Create prompt template with variables only if custom prompt uses them
            if custom_prompt:
                # Try to detect if the custom prompt uses the variables
                if "{icd10_description}" in custom_prompt or "{user_diagnosis}" in custom_prompt or "{anatomical_location}" in custom_prompt:
                    input_vars = []
                    if "{icd10_description}" in custom_prompt:
                        input_vars.append("icd10_description")
                    if "{user_diagnosis}" in custom_prompt:
                        input_vars.append("user_diagnosis")
                    if "{anatomical_location}" in custom_prompt:
                        input_vars.append("anatomical_location")
                    prompt = PromptTemplate(
                        input_variables=input_vars,
                        template=prompt_template
                    )
                else:
                    # If no variables, use the prompt as-is without template
                    prompt = PromptTemplate(
                        input_variables=[],
                        template=prompt_template
                    )
            else:
                prompt = PromptTemplate(
                    input_variables=["icd10_description", "user_diagnosis", "anatomical_location"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            # Invoke with variables if they exist in the template
            if "{icd10_description}" in prompt_template or "{user_diagnosis}" in prompt_template or "{anatomical_location}" in prompt_template:
                invoke_dict = {}
                if "{icd10_description}" in prompt_template:
                    invoke_dict["icd10_description"] = icd10_description
                if "{user_diagnosis}" in prompt_template:
                    invoke_dict["user_diagnosis"] = user_diagnosis
                if "{anatomical_location}" in prompt_template:
                    invoke_dict["anatomical_location"] = anatomical_location or ""
                response = await chain.ainvoke(invoke_dict)
            else:
                response = await chain.ainvoke({})
            
            # Extract the query response
            query = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if query.startswith('```json'):
                query = query.replace('```json', '').replace('```', '').strip()
            elif query.startswith('```'):
                query = query.replace('```', '').strip()
            
            logger.info(f"Generated search query: {query[:100]}...")
            return query, rendered_prompt
            
        except Exception as e:
            logger.error(f"Error generating search query: {e}", exc_info=True)
            return "", ""

    async def predict_cpt_codes(
        self,
        search_query_terms: List[str],
        treatment_options: Optional[List[Dict[str, str]]] = None,
        anatomical_location: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Use GPT to predict relevant CPT codes that a neurosurgeon would use to treat the given diagnosis terms and treatment options.
        
        Args:
            search_query_terms: List of diagnosis terms/descriptions from the search query (e.g., ["acoustic neuroma", "vestibular schwannoma", ...])
            treatment_options: Optional list of treatment options with name, outcomes, and complications
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            custom_prompt: Optional custom prompt to override default
            
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
                escaped_prompt = escaped_prompt.replace("{anatomical_location}", "__ANATOMICAL_LOCATION__")
                escaped_prompt = escaped_prompt.replace("{treatment_options}", "__TREATMENT_OPTIONS__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS_TERMS__}}", "{diagnosis_terms}")
                escaped_prompt = escaped_prompt.replace("{{__ANATOMICAL_LOCATION__}}", "{anatomical_location}")
                escaped_prompt = escaped_prompt.replace("{{__TREATMENT_OPTIONS__}}", "{treatment_options}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if "{diagnosis_terms}" in custom_prompt or "{anatomical_location}" in custom_prompt or "{treatment_options}" in custom_prompt:
                    try:
                        invoke_dict = {}
                        if "{diagnosis_terms}" in custom_prompt:
                            invoke_dict["diagnosis_terms"] = terms_text
                        if "{anatomical_location}" in custom_prompt:
                            invoke_dict["anatomical_location"] = anatomical_location or ""
                        if "{treatment_options}" in custom_prompt:
                            invoke_dict["treatment_options"] = treatment_options_text
                        rendered_prompt = custom_prompt.format(**invoke_dict)
                    except KeyError as e:
                        # If formatting fails, log and use as-is
                        logger.warning(f"Could not format custom prompt with variables: {e}")
                        rendered_prompt = custom_prompt
                else:
                    # If custom prompt doesn't have these variables, use it as-is
                    rendered_prompt = custom_prompt
            else:
                prompt_template = """Give an exhaustive list of primary CPT codes that could possibly be used by a neurosurgeon to treat patients with any of these diagnoses or a similar diagnosis in an adjacent location in a simple or complex treatment:
{diagnosis_terms}

Anatomical Location: {anatomical_location}

Only consider CPT codes that could be used for the following treatment options and this anatomical location: 
{treatment_options}

IMPORTANT: 
- Focus on CPT codes specific to the anatomical location provided (e.g., brain, spine, peripheral nerve)
- Include all CPT codes for treatment of related diagnoses in an adjacent location in a simple or complex treatment
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
                    anatomical_location=anatomical_location or "",
                    treatment_options=treatment_options_text
                )
            
            # Create prompt template with variables only if custom prompt uses them
            if custom_prompt:
                # Try to detect if the custom prompt uses the variables
                input_vars = []
                if "{diagnosis_terms}" in custom_prompt:
                    input_vars.append("diagnosis_terms")
                if "{anatomical_location}" in custom_prompt:
                    input_vars.append("anatomical_location")
                if "{treatment_options}" in custom_prompt:
                    input_vars.append("treatment_options")
                prompt = PromptTemplate(
                    input_variables=input_vars if input_vars else ["diagnosis_terms", "anatomical_location", "treatment_options"],
                    template=prompt_template
                )
            else:
                prompt = PromptTemplate(
                    input_variables=["diagnosis_terms", "anatomical_location", "treatment_options"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            # Invoke with variables only if they're expected
            invoke_dict = {}
            if "{diagnosis_terms}" in prompt_template:
                invoke_dict["diagnosis_terms"] = terms_text
            if "{anatomical_location}" in prompt_template:
                invoke_dict["anatomical_location"] = anatomical_location or ""
            if "{treatment_options}" in prompt_template:
                invoke_dict["treatment_options"] = treatment_options_text
            
            if invoke_dict:
                response = await chain.ainvoke(invoke_dict)
            else:
                response = await chain.ainvoke({})
                # For custom prompts without variables, the rendered prompt is the prompt itself
                if not rendered_prompt:
                    rendered_prompt = prompt_template
            
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
                logger.warning(f"Initial JSON parse failed, attempting to fix: {json_error}")
                
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
                    logger.info(f"Extracted {len(cpt_codes)} valid CPT codes from partial JSON")
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
                            logger.info(f"Extracted {len(cpt_codes)} valid CPT codes using regex pattern matching")
                        else:
                            logger.error(f"Could not extract any valid CPT codes. JSON error: {json_error}")
                            logger.debug(f"Problematic JSON (first 1000 chars): {response_text[:1000]}")
                            return []
                    else:
                        logger.error(f"Could not extract valid CPT codes. JSON error: {json_error}")
                        logger.debug(f"Problematic JSON (first 1000 chars): {response_text[:1000]}")
                        return []
            
            logger.info(f"Predicted {len(cpt_codes)} CPT codes for {len(search_query_terms)} diagnosis terms")
            return cpt_codes, rendered_prompt
        except Exception as e:
            logger.error(f"Error predicting CPT codes: {e}", exc_info=True)
            return [], ""
    
    async def generate_cpt_codes_from_analysis(
        self,
        search_query: str,
        treatment_options: List[Dict[str, str]],
        anatomical_location: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Generate CPT codes from search query and treatment options.
        This is a convenience method for the separate CPT code generation endpoint.
        
        Args:
            search_query: Search query string (typically from generate_search_query)
            treatment_options: List of treatment options with name, outcomes, and complications
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            
        Returns:
            Tuple of (List of dictionaries containing CPT code and description, rendered prompt text)
        """
        if not search_query:
            logger.warning("Cannot generate CPT codes - no search query provided")
            return [], ""
        
        # Parse search query to extract individual terms (split by " OR ")
        search_terms = [term.strip() for term in search_query.split(" OR ") if term.strip()]
        
        return await self.predict_cpt_codes(search_terms, treatment_options, anatomical_location, custom_prompt=custom_prompt)

    async def query_cms_api(
        self,
        cpt_codes: List[Dict[str, str]],
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query the CMS public API using CPT codes from the medical analysis.
        Aggregates data across the most recent 5 years (2023-2019).
        If more than 100 CPT codes, splits into multiple API calls per year.
        If state is provided, filters results by state (but returns all, not just top 25).
        Groups results by provider (Rndrng_NPI) and sums Total Services across all years.
        Returns all providers (still sorted by total services descending), or all providers in the specified state.
        
        Args:
            cpt_codes: List of dictionaries containing CPT codes and descriptions
            state: Optional state filter (2-letter abbreviation or full name)
            
        Returns:
            Dictionary with 'url', 'urls', 'results' (grouped by provider), and metadata
        """
        if not cpt_codes or len(cpt_codes) == 0:
            logger.warning("No CPT codes provided for CMS API query")
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
            
            logger.info(f"Querying CMS API with {len(cpt_code_values)} CPT codes across 5 years")
            
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
            
            # Convert state to 2-letter abbreviation early (for use in URL)
            state_abbrev_for_url = None
            if state:
                state_abbrev_for_url = state.upper().strip()
                if len(state_abbrev_for_url) > 2:
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
                    state_abbrev_for_url = state_map.get(state_abbrev_for_url, state_abbrev_for_url)
            
            # Calculate total API calls: 5 years × number of chunks
            total_calls = len(year_uuids) * len(cpt_chunks)
            
            # Make API calls for all years and chunks
            all_results = []
            urls_used = []
            
            async with httpx.AsyncClient(timeout=90.0) as client:
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
                        
                        # Build URL components
                        hcpcs_filter = (
                            f"filter[hcpcs][condition][path]=HCPCS_Cd&"
                            f"filter[hcpcs][condition][operator]=IN&"
                            f"{filter_params}"
                        )
                        
                        # Add state filter at the beginning if provided
                        if state_abbrev_for_url:
                            state_filter = (
                                f"filter[state][condition][path]=Rndrng_Prvdr_State_Abrvtn&"
                                f"filter[state][condition][operator]==&"
                                f"filter[state][condition][value]={state_abbrev_for_url}&"
                            )
                            full_url = f"{base_url}?{state_filter}{hcpcs_filter}"
                        else:
                            full_url = f"{base_url}?{hcpcs_filter}"
                        
                        urls_used.append(full_url)
                        
                        # Create async task for this API call
                        async def make_api_call(url: str, year: int, chunk_idx: int, total_chunks: int, chunk_size: int):
                            try:
                                response = await client.get(url)
                                response.raise_for_status()
                                
                                cms_data = response.json()
                                chunk_results = cms_data if isinstance(cms_data, list) else [cms_data]
                                
                                # Add year metadata to each result for tracking
                                for result in chunk_results:
                                    result['_year'] = year
                                
                                return chunk_results
                            except Exception as e:
                                logger.error(f"Error in CMS API call for {year} chunk {chunk_idx + 1}: {e}", exc_info=True)
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
            
            logger.info(f"Total raw CMS results collected: {len(all_results)}")
            
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
            
            # Filter by state if provided (API already filters, but keep as safety check)
            # Since we filter at the API level, this should be redundant but kept for safety
            filtered_count = None
            if state:
                # Use the state abbreviation we already computed
                state_abbrev = state_abbrev_for_url
                
                # Filter by state (return all, not just top 25)
                # Note: This should be redundant since API already filters, but kept as safety check
                filtered_by_state = [
                    p for p in grouped_results 
                    if (p.get('Rndrng_Prvdr_State_Abrvtn') or '').upper().strip() == state_abbrev
                ]
                final_providers = filtered_by_state
                filtered_count = len(filtered_by_state)
            else:
                # No state filter, return all providers
                final_providers = grouped_results
            
            # Convert sets to lists and build descriptions list matching CPT codes
            for provider in final_providers:
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
            
            logger.info(f"CMS API query complete: {len(provider_totals)} providers, {len(final_providers)} returned")
            
            result = {
                "url": urls_used[0] if urls_used else None,  # Primary URL for display (first one)
                "urls": urls_used,  # All URLs used (all years and chunks)
                "results": final_providers,  # All providers (no top 25 limit), still sorted by Tot_Srvcs descending
                "total_results": len(all_results),  # Total raw results across all years
                "total_providers": len(provider_totals),  # Total unique providers
                "cpt_codes_searched": cpt_code_values,
                "years_queried": sorted(year_uuids.keys(), reverse=True),  # Years included in aggregation
                "error": None
            }
            
            return result
                
        except httpx.TimeoutException as e:
            logger.error(f"CMS API request timed out: {e}", exc_info=True)
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
            logger.error(f"CMS API HTTP error: {e.response.status_code} - {e}", exc_info=True)
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
            logger.error(f"Error querying CMS API: {e}", exc_info=True)
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
        diagnosis: str, 
        anatomical_location: str = "",
        pdf_content: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], str]:
        """
        Use GPT to predict primary diagnosis and treatment options based on patient information.
        
        Args:
            diagnosis: Patient diagnosis
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            pdf_content: Extracted content from uploaded PDF files (optional)
            custom_prompt: Optional custom prompt to override default
            
        Returns:
            Tuple of (Dictionary containing primary diagnosis and treatment options, rendered prompt text)
        """
        try:
            default_template = """
                Patient Information:
                Diagnosis: {diagnosis}
                Anatomical Location: {anatomical_location}
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Analyze the information above and provide treatment options performed specifically by a neurosurgeon for this anatomical location.

                Provide the most common treatment options based on the diagnosis and anatomical location. 
                For each treatment option, include the general category of the treatment option. For example:
                - Surgery
                - Radiosurgery
                - Endovascular
                - Medical
                                
                Return the response in this exact JSON format:
                {{
                    "treatment_options": [
                        {{
                            "name": "Treatment name",
                            "outcomes": "Expected outcomes and success rates",
                            "complications": "Potential complications and risks",
                            "category": "Category of the treatment option"
                        }}
                    ]
                }}
                                
                """
            
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                # Escape all curly braces except for our template variables to prevent LangChain from parsing them
                escaped_prompt = custom_prompt
                # Temporarily replace our template variables with placeholders
                escaped_prompt = escaped_prompt.replace("{diagnosis}", "__DIAGNOSIS__")
                escaped_prompt = escaped_prompt.replace("{anatomical_location}", "__ANATOMICAL_LOCATION__")
                escaped_prompt = escaped_prompt.replace("{pdf_content}", "__PDF_CONTENT__")
                # Escape all remaining curly braces
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                # Restore our template variables
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS__}}", "{diagnosis}")
                escaped_prompt = escaped_prompt.replace("{{__ANATOMICAL_LOCATION__}}", "{anatomical_location}")
                escaped_prompt = escaped_prompt.replace("{{__PDF_CONTENT__}}", "{pdf_content}")
                
                prompt_template = escaped_prompt
                # For custom prompts, format with the variables if they're present
                if any(var in custom_prompt for var in ["{diagnosis}", "{anatomical_location}", "{pdf_content}"]):
                    # Variables are present, use LangChain PromptTemplate
                    input_vars = []
                    if "{diagnosis}" in custom_prompt:
                        input_vars.append("diagnosis")
                    if "{anatomical_location}" in custom_prompt:
                        input_vars.append("anatomical_location")
                    if "{pdf_content}" in custom_prompt:
                        input_vars.append("pdf_content")
                    prompt = PromptTemplate(
                        input_variables=input_vars,
                        template=prompt_template
                    )
                    invoke_dict = {}
                    if "{diagnosis}" in custom_prompt:
                        invoke_dict["diagnosis"] = diagnosis
                    if "{anatomical_location}" in custom_prompt:
                        invoke_dict["anatomical_location"] = anatomical_location or ""
                    if "{pdf_content}" in custom_prompt:
                        invoke_dict["pdf_content"] = pdf_content
                    rendered_prompt = prompt.format(**invoke_dict)
                else:
                    # No variables, use prompt as-is
                    rendered_prompt = custom_prompt
            else:
                prompt_template = default_template
                prompt = PromptTemplate(
                    input_variables=["diagnosis", "anatomical_location", "pdf_content"],
                    template=prompt_template
                )
                rendered_prompt = prompt.format(
                    diagnosis=diagnosis,
                    anatomical_location=anatomical_location or "",
                    pdf_content=pdf_content
                )
            
            # Create prompt template for LangChain (always use variables even if custom prompt doesn't have them)
            if custom_prompt:
                input_vars = []
                if "{diagnosis}" in prompt_template:
                    input_vars.append("diagnosis")
                if "{anatomical_location}" in prompt_template:
                    input_vars.append("anatomical_location")
                if "{pdf_content}" in prompt_template:
                    input_vars.append("pdf_content")
                prompt = PromptTemplate(
                    input_variables=input_vars if input_vars else ["diagnosis", "anatomical_location", "pdf_content"],
                    template=prompt_template
                )
            else:
                prompt = PromptTemplate(
                    input_variables=["diagnosis", "anatomical_location", "pdf_content"],
                    template=prompt_template
                )
            
            chain = prompt | self.llm
            
            invoke_dict = {}
            if "{diagnosis}" in prompt_template:
                invoke_dict["diagnosis"] = diagnosis
            if "{anatomical_location}" in prompt_template:
                invoke_dict["anatomical_location"] = anatomical_location or ""
            if "{pdf_content}" in prompt_template:
                invoke_dict["pdf_content"] = pdf_content
            
            response = await chain.ainvoke(invoke_dict if invoke_dict else {
                "diagnosis": diagnosis,
                "anatomical_location": anatomical_location or "",
                "pdf_content": pdf_content
            })
            
            # Extract the JSON response - LCEL returns AIMessage object
            response_text = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Try to extract JSON from response if it's embedded in other text
            # Look for JSON object boundaries
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            # Parse the JSON response
            try:
                diagnoses = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing error at position {json_err.pos}: {json_err.msg}")
                logger.debug(f"Response text around error: {response_text[max(0, json_err.pos-100):min(len(response_text), json_err.pos+100)]}")
                logger.debug(f"Full response text length: {len(response_text)} characters")
                raise
            
            # Validate the response structure
            if 'treatment_options' in diagnoses and isinstance(diagnoses['treatment_options'], list):
                # Log treatment options with details
                logger.info(f"📋 GPT returned {len(diagnoses['treatment_options'])} treatment options:")
                for i, option in enumerate(diagnoses['treatment_options'], 1):
                    category = option.get('category', 'Not specified')
                    name = option.get('name', 'Unnamed')
                    logger.info(f"   {i}. {name} (Category: {category})")
                
                return diagnoses, rendered_prompt
            else:
                logger.warning(f"GPT returned invalid response structure: {diagnoses}")
                return {"treatment_options": []}, rendered_prompt
                
        except Exception as e:
            logger.error(f"Error in GPT diagnosis prediction: {e}", exc_info=True)
            return {"treatment_options": []}, rendered_prompt if 'rendered_prompt' in locals() else ""
