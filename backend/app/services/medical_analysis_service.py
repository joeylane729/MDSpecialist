import json
import logging
import asyncio
import httpx
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.prompts import PromptTemplate
from ..config.llm_config import get_llm
from ..models.icd_cpt_mapping import IcdCptMapping
from ..models.cpt_consolidated import CptConsolidated

logger = logging.getLogger(__name__)


def extract_llm_response_content(response: Any) -> str:
    """
    Extract text content from LLM response, handling both OpenAI (string) and Gemini (list) formats.
    
    Args:
        response: LLM response object (AIMessage from LangChain)
    
    Returns:
        Extracted text content as a string
    """
    if hasattr(response, 'content'):
        content = response.content
        if isinstance(content, list):
            # Gemini returns content as a list of dictionaries with 'type' and 'text' keys
            # Example: [{'type': 'text', 'text': '...'}]
            text_parts = []
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                else:
                    text_parts.append(str(item))
            return ' '.join(text_parts).strip()
        else:
            return str(content).strip()
    else:
        return str(response).strip()


class MedicalAnalysisService:
    """Service for comprehensive medical analysis including specialty determination, ICD-10 coding, and diagnosis prediction."""
    
    def __init__(self, db: Session = None, llm_provider: Optional[str] = None):
        logger.info(f"🏥 [MedicalAnalysisService] Initializing service...")
        self.llm = get_llm(use_case="medical_analysis", temperature=0.1, provider=llm_provider)
        logger.info(f"✅ [MedicalAnalysisService] Service initialized with LLM configured")
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
            logger.info(f"🏥 [Medical Analysis] Starting comprehensive analysis")
            logger.info(f"   - Diagnosis: {diagnosis[:100] if diagnosis else 'None'}...")
            logger.info(f"   - Anatomical location: {anatomical_location or 'Not specified'}")
            logger.info(f"   - Treatment options generation: REMOVED (no longer generated)")
            
            # Generate ICD-10 codes (treatment options generation removed)
            logger.info(f"   🔄 Generating ICD-10 codes...")
            predicted_icd10_codes, icd10_relevancy_scores, icd10_llm_descriptions, icd10_prompt_text = await self.predict_icd10_code(
                diagnosis, anatomical_location, pdf_content, custom_prompt=custom_icd10_prompt
            )
            logger.info(f"   ✅ Generated {len(predicted_icd10_codes)} ICD-10 codes")
            
            # Use first code as primary for backward compatibility, but store all codes
            primary_icd10 = predicted_icd10_codes[0] if predicted_icd10_codes else None
            
            medical_analysis = {
                "predicted_icd10": primary_icd10,  # Primary code for backward compatibility
                "predicted_icd10_codes": predicted_icd10_codes,  # All codes
                "icd10_relevancy_scores": icd10_relevancy_scores,  # Code -> relevancy score mapping
                "icd10_llm_descriptions": icd10_llm_descriptions,  # Code -> LLM description mapping
                "diagnoses": {}  # Empty dict for backward compatibility
            }
            
            # Add ICD-10 descriptions for all codes
            if predicted_icd10_codes and self.db:
                logger.info(f"Fetching descriptions for {len(predicted_icd10_codes)} ICD-10 codes")
                icd10_descriptions = self.lookup_icd10_descriptions(predicted_icd10_codes)
                logger.info(f"Retrieved {len([d for d in icd10_descriptions.values() if d])} descriptions out of {len(icd10_descriptions)} codes")
                logger.debug(f"ICD-10 descriptions mapping: {dict(list(icd10_descriptions.items())[:5])}...")  # Log first 5
                medical_analysis["icd10_descriptions"] = icd10_descriptions  # All code -> description mappings
                
                # Also set primary description for backward compatibility
                if primary_icd10:
                    primary_description = icd10_descriptions.get(primary_icd10)
                    if primary_description:
                        medical_analysis["icd10_description"] = primary_description
                    else:
                        logger.warning(f"Could not find ICD-10 description for: {primary_icd10}")
            else:
                logger.warning(f"Not fetching ICD-10 descriptions: codes={len(predicted_icd10_codes) if predicted_icd10_codes else 0}, db={self.db is not None}")
            
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
            icd10_descriptions = medical_analysis.get("icd10_descriptions", {})
            logger.info(f"Returning comprehensive result with {len(icd10_descriptions)} ICD-10 descriptions")
            if icd10_descriptions:
                found_descriptions = len([d for d in icd10_descriptions.values() if d])
                logger.info(f"  - {found_descriptions} descriptions found, {len(icd10_descriptions) - found_descriptions} missing")
            
            comprehensive_result = {
                # User input fields
                "user_diagnosis": diagnosis,  # User-entered diagnosis text
                
                # Medical analysis data (flattened for frontend compatibility)
                "predicted_icd10": medical_analysis["predicted_icd10"],  # Primary code for backward compatibility
                "predicted_icd10_codes": medical_analysis.get("predicted_icd10_codes", []),  # All ICD-10 codes
                "icd10_relevancy_scores": medical_analysis.get("icd10_relevancy_scores", {}),  # Code -> relevancy score mapping (0-100)
                "icd10_llm_descriptions": medical_analysis.get("icd10_llm_descriptions", {}),  # Code -> LLM description mappings
                "icd10_description": medical_analysis.get("icd10_description"),  # Primary description for backward compatibility
                "icd10_descriptions": icd10_descriptions,  # All code -> database description mappings
                "icd10_prompt_text": icd10_prompt_text,  # Actual GPT prompt used to generate ICD-10 code
                "determined_specialty": determined_specialty,  # Specialty determined for provider search
                "search_query": search_query,  # Pre-generated search query
                "search_query_prompt_text": search_query_prompt_text,  # Actual GPT prompt used to generate search query
                
                # Keep original nested structure for backward compatibility
                "diagnoses": medical_analysis["diagnoses"]
            }
            
            logger.info(f"✅ [Medical Analysis] Comprehensive analysis completed successfully")
            logger.info(f"   - ICD-10 codes: {len(comprehensive_result.get('predicted_icd10_codes', []))} codes")
            logger.info(f"   - Search query: {'Generated' if comprehensive_result.get('search_query') else 'Not generated'}")
            logger.info(f"   - Treatment options: REMOVED (no longer part of flow)")
            logger.info(f"   - Next step: User will click 'Generate CPT Codes' button to get categorized CPT codes")
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
    
    def lookup_icd10_descriptions(self, codes: List[str]) -> Dict[str, Optional[str]]:
        """
        Look up descriptions for multiple ICD-10 codes from the database.
        
        Args:
            codes: List of ICD-10 codes to look up
            
        Returns:
            Dictionary mapping code to description (or None if not found)
        """
        if not self.db or not codes:
            logger.warning(f"lookup_icd10_descriptions called but db={self.db is not None}, codes={len(codes) if codes else 0}")
            return {}
        
        logger.info(f"Looking up descriptions for {len(codes)} ICD-10 codes: {codes[:5]}{'...' if len(codes) > 5 else ''}")
        result = {}
        found_count = 0
        for code in codes:
            description = self.lookup_icd10_description(code)
            result[code] = description
            if description:
                found_count += 1
        
        logger.info(f"Found descriptions for {found_count}/{len(codes)} ICD-10 codes")
        return result

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
    ) -> Tuple[List[str], Dict[str, int], Dict[str, str], str]:
        """
        Use GPT to predict 5-10 ICD-10 codes based on patient information.
        Includes codes for similar/related pathology from nearby anatomic locations.
        May include codes with "uncertain" or "unspecified" in descriptions.
        Each code includes a relevancy score (0-100%) and a description.
        
        Args:
            diagnosis: Patient diagnosis
            anatomical_location: Anatomical location of the condition (e.g., "brain", "spine", "arm")
            pdf_content: Extracted content from uploaded PDF files (optional)
            custom_prompt: Optional custom prompt to override default
            
        Returns:
            Tuple of (List of ICD-10 codes, Dict mapping code -> relevancy_score, Dict mapping code -> LLM description, rendered prompt text)
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
                prompt_template = """Patient Information:
Diagnosis: {diagnosis}
Anatomical Location: {anatomical_location}

Additional Information from Medical Records/PDFs:
{pdf_content}

Provide between 5 and 10 of the most likely ICD-10 codes for this diagnosis, including:
- Codes for similar pathology in a similar anatomic location
- If codes use terms like "uncertain behavior" or "unspecified behavior" in their descriptions then the anatomic location and/or the pathologic diagnosis must be the same as the original diagnosis
- DO NOT include codes that contain descriptions of anatomy that is not immediately adjacent to the anatomical location
- Please make sure to preserve the pathologic category of the original diagnosis. For example, if the original diagnosis is a neoplasm, then all the ICD-10 codes should designate neoplasms. If the original diagnosis is a vascular lesion, then all the ICD- 10 codes should be vascular lesions. If the original diagnosis is a medical condition, then all the ICD-10 codes should be medical conditions. If the original diagnosis is a degenerative disease, then all the ICD-10 codes should be degenerative diseases.

For each code, assign a relevancy score from 0-100% indicating how relevant the code is to the diagnosis, and provide a description of what the code represents.

Return the response in this exact JSON format:
[
    {{
        "code": "ICD10_CODE",
        "description": "Brief description of what this code represents",
        "relevancy_score": 95
    }},
    {{
        "code": "ICD10_CODE",
        "description": "Brief description of what this code represents",
        "relevancy_score": 85
    }}
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text."""
                
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
            
            # Log which LLM provider is being used for ICD-10 generation
            llm_provider = getattr(self.llm, '_provider', 'unknown').upper()
            logger.info(f"🔍 [ICD-10 Generation] Using {llm_provider} LLM to generate ICD-10 codes")
            
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
            
            logger.info(f"✅ [ICD-10 Generation] {llm_provider} LLM response received")
            
            # Extract the ICD-10 codes from the response - LCEL returns AIMessage object
            response_text = extract_llm_response_content(response)
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Extract JSON array
            first_bracket = response_text.find('[')
            last_bracket = response_text.rfind(']')
            if first_bracket != -1 and last_bracket != -1:
                response_text = response_text[first_bracket:last_bracket + 1]
            
            # Parse JSON array
            try:
                icd_data = json.loads(response_text)
                if not isinstance(icd_data, list):
                    # If single item returned, wrap in list
                    icd_data = [icd_data] if icd_data else []
                
                # Validate and extract codes, scores, and descriptions
                valid_codes = []
                relevancy_scores = {}
                llm_descriptions = {}
                
                for item in icd_data:
                    # Handle both old format (string) and new format (dict with code, description, and relevancy_score)
                    if isinstance(item, dict):
                        code_str = str(item.get('code', '')).strip()
                        score = item.get('relevancy_score', 0)
                        description = str(item.get('description', '')).strip()
                        # Validate score is 0-100
                        if not isinstance(score, (int, float)) or score < 0 or score > 100:
                            score = 0
                        relevancy_scores[code_str] = int(score)
                        if description:
                            llm_descriptions[code_str] = description
                    else:
                        # Old format: just a string code
                        code_str = str(item).strip().replace('"', '').replace("'", "")
                        relevancy_scores[code_str] = 0  # Default score if not provided
                    
                    # Basic validation that it looks like an ICD-10 code (letter followed by numbers)
                    if len(code_str) >= 3 and code_str[0].isalpha() and any(c.isdigit() for c in code_str):
                        valid_codes.append(code_str)
                    else:
                        logger.warning(f"GPT returned invalid ICD-10 code: {code_str}")
                
                if valid_codes:
                    logger.info(f"GPT returned {len(valid_codes)} ICD-10 codes: {valid_codes}")
                    logger.info(f"Relevancy scores: {relevancy_scores}")
                    logger.info(f"LLM descriptions: {len(llm_descriptions)} codes with descriptions")
                    return valid_codes, relevancy_scores, llm_descriptions, rendered_prompt
                else:
                    logger.warning("No valid ICD-10 codes found in GPT response")
                    return [], {}, {}, rendered_prompt
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse ICD-10 codes JSON: {e}")
                logger.debug(f"Response text: {response_text[:500]}")
                return [], {}, {}, rendered_prompt
                
        except Exception as e:
            logger.error(f"Error in GPT ICD-10 prediction: {e}", exc_info=True)
            return [], {}, {}, rendered_prompt if 'rendered_prompt' in locals() else ""

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
                prompt_template = """Generate a concise search query to find PubMed articles and medical lectures from our database using the user-entered diagnosis, the anatomical location, and the medical analysis diagnosis:

Medical Analysis Diagnosis: {icd10_description}
User-Entered Diagnosis: {user_diagnosis}
Anatomical Location: {anatomical_location}

RULES:
- The query should include all variations of this diagnosis separated by the OR operator
- The terms should be specific to the diagnosis and not general terms like "brain tumor" or "brain surgery" or “back pain” or “back surgery” or “neck surgery” or “spine problem”.

Example: term1 OR term2 OR term3 OR term4 OR term5

IMPORTANT: Do not include quotations around each term in the search query, just the terms themselves separated by the OR operator.
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
            
            # Log which LLM provider is being used for search query generation
            llm_provider = getattr(self.llm, '_provider', 'unknown').upper()
            logger.info(f"🔍 [Search Query Generation] Using {llm_provider} LLM to generate search query")
            
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
            query = extract_llm_response_content(response)
            
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

    async def generate_cpt_codes_only(
        self,
        search_query_terms: List[str],
        anatomical_location: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Use GPT to generate CPT codes and descriptions only (no category or relevancy score).
        Used as the first step before DB lookup and categorization.

        Args:
            search_query_terms: List of diagnosis terms from the search query
            anatomical_location: Anatomical location of the condition
            custom_prompt: Optional custom prompt (may use {diagnosis_terms}, {anatomical_location}; no {categories})

        Returns:
            Tuple of (List of dicts with code and description, rendered prompt text)
        """
        try:
            logger.info(f"🚀 [GPT CPT Generation] Starting code+description-only generation")
            terms_text = "\n".join([f"- {term.strip()}" for term in search_query_terms if term.strip()])

            if custom_prompt:
                escaped_prompt = custom_prompt.replace("{diagnosis_terms}", "__DIAGNOSIS_TERMS__").replace(
                    "{anatomical_location}", "__ANATOMICAL_LOCATION__"
                )
                escaped_prompt = escaped_prompt.replace("{", "{{").replace("}", "}}")
                escaped_prompt = escaped_prompt.replace("{{__DIAGNOSIS_TERMS__}}", "{diagnosis_terms}").replace(
                    "{{__ANATOMICAL_LOCATION__}}", "{anatomical_location}"
                )
                prompt_template = escaped_prompt
                invoke_dict = {}
                if "{diagnosis_terms}" in custom_prompt:
                    invoke_dict["diagnosis_terms"] = terms_text
                if "{anatomical_location}" in custom_prompt:
                    invoke_dict["anatomical_location"] = anatomical_location or ""
                try:
                    rendered_prompt = custom_prompt.format(**invoke_dict) if invoke_dict else custom_prompt
                except KeyError:
                    rendered_prompt = custom_prompt
            else:
                prompt_template = """Give an exhaustive list of primary CPT codes that could possibly be used to treat patients with any of these diagnoses or a similar diagnosis in an adjacent location in a simple or complex treatment:

Diagnosis Terms:
{diagnosis_terms}

Anatomical Location: {anatomical_location}
Specialty: Neurosurgery

IMPORTANT:
- Include all CPT codes for treatment of related diagnoses in an adjacent location in a simple or complex treatment
- Do not include any add-on CPT codes (these generally start with a + sign)
- Do not include codes that start with 99XXX, 98XXX, or 6178X
- Do not include codes ending in 99 or 89 (XXX99, XXX89 format)
- Escape all quotes in descriptions (use \\" for quotes inside strings)
- Keep descriptions concise (under 100 characters)
- Do NOT include newlines in description strings
- Ensure all strings are properly closed

Return the response in this exact JSON format (code and description only):
[
    {{"code": "CPT_CODE", "description": "Procedure description"}},
    {{"code": "CPT_CODE", "description": "Procedure description"}}
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text."""
                rendered_prompt = prompt_template.format(
                    diagnosis_terms=terms_text,
                    anatomical_location=anatomical_location or ""
                )

            input_vars = []
            if custom_prompt:
                if "{diagnosis_terms}" in custom_prompt:
                    input_vars.append("diagnosis_terms")
                if "{anatomical_location}" in custom_prompt:
                    input_vars.append("anatomical_location")
            else:
                input_vars = ["diagnosis_terms", "anatomical_location"]
            prompt = PromptTemplate(
                input_variables=input_vars if input_vars else ["diagnosis_terms", "anatomical_location"],
                template=prompt_template
            )
            chain = prompt | self.llm
            invoke_dict = {}
            if "{diagnosis_terms}" in prompt_template:
                invoke_dict["diagnosis_terms"] = terms_text
            if "{anatomical_location}" in prompt_template:
                invoke_dict["anatomical_location"] = anatomical_location or ""
            response = await chain.ainvoke(invoke_dict)
            response_text = extract_llm_response_content(response)
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            first_bracket = response_text.find("[")
            last_bracket = response_text.rfind("]")
            if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
                response_text = response_text[first_bracket : last_bracket + 1]

            try:
                raw_codes = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed in generate_cpt_codes_only: {e}")
                return [], rendered_prompt

            # Normalize to list of {code, description} (drop category/relevancy if present)
            cpt_codes = []
            for item in raw_codes:
                if isinstance(item, dict) and item.get("code"):
                    code = str(item["code"]).strip()
                    if code.endswith("99") or code.endswith("89"):
                        continue
                    cpt_codes.append({
                        "code": code,
                        "description": str(item.get("description", "")).strip()
                    })
            logger.info(f"✅ [GPT CPT Generation] Generated {len(cpt_codes)} codes (description only)")
            return cpt_codes, rendered_prompt
        except Exception as e:
            logger.error(f"Error in generate_cpt_codes_only: {e}", exc_info=True)
            return [], ""
    
    def get_cpt_codes_from_icd10(self, icd10_codes: List[str]) -> List[Dict[str, str]]:
        """
        Query database to get CPT codes mapped to one or more ICD-10 codes.
        
        Args:
            icd10_codes: List of ICD-10 codes (e.g., ["D35.2", "D35.1"])
            
        Returns:
            List of dictionaries containing CPT code and description
        """
        if not self.db:
            logger.warning("Cannot query CPT codes - no database session")
            return []
        
        if not icd10_codes or len(icd10_codes) == 0:
            return []
        
        try:
            # Normalize all ICD-10 codes (keep dots, uppercase)
            cleaned_icds = [code.strip().upper() for code in icd10_codes if code and code.strip()]
            
            if not cleaned_icds:
                return []
            
            # Query database for CPT codes matching any of the ICD-10 codes
            mappings = self.db.query(IcdCptMapping).filter(
                IcdCptMapping.icd10_code.in_(cleaned_icds)
            ).all()
            
            # Convert to list of dicts with unique CPT codes (deduplicate)
            # Filter out codes starting with "98", "99", "7", "8", "0" and codes ending with "F" or "U"
            cpt_codes_dict = {}
            for mapping in mappings:
                cpt_code = mapping.cpt_code.strip()
                # Skip codes based on exclusion rules
                if not cpt_code:
                    continue
                # Skip codes starting with "98", "99", "7", "8", or "0"
                if cpt_code.startswith('98') or cpt_code.startswith('99') or \
                   cpt_code.startswith('7') or cpt_code.startswith('8') or \
                   cpt_code.startswith('0'):
                    continue
                # Skip codes ending with "F" or "U"
                if cpt_code.endswith('F') or cpt_code.endswith('U'):
                    continue
                # Skip XXX99 and XXX89 format
                if cpt_code.endswith('99') or cpt_code.endswith('89'):
                    continue
                # Add to dict if not already present; store mapping description as fallback
                if cpt_code not in cpt_codes_dict:
                    mapping_desc = (mapping.description or mapping.additional_field or "").strip()
                    cpt_codes_dict[cpt_code] = {
                        "code": cpt_code,
                        "description": mapping_desc  # fallback; overwritten by consolidated if present
                    }
            
            # Prefer long descriptions from cpt_consolidated; fallback to ICD-CPT mapping description only
            code_list = list(cpt_codes_dict.keys())
            consolidated = self.lookup_cpt_long_descriptions(code_list) if code_list else {}
            for cpt_code, entry in cpt_codes_dict.items():
                entry["description"] = consolidated.get(cpt_code) or entry["description"]
            
            cpt_codes = list(cpt_codes_dict.values())
            logger.info(f"Found {len(cpt_codes)} CPT codes for {len(cleaned_icds)} ICD-10 code(s): {cleaned_icds}")
            return cpt_codes
            
        except Exception as e:
            logger.error(f"Error querying CPT codes from ICD-10 codes {icd10_codes}: {e}", exc_info=True)
            return []

    def lookup_cpt_long_descriptions(self, cpt_codes: List[str]) -> Dict[str, str]:
        """
        Look up long descriptions from cpt_consolidated for the given CPT codes.

        Args:
            cpt_codes: List of CPT codes (e.g., ["99202", "61510"])

        Returns:
            Dict mapping cpt_code -> long_desc from cpt_consolidated (only codes found)
        """
        if not self.db or not cpt_codes:
            return {}
        try:
            cleaned = [c.strip() for c in cpt_codes if c and str(c).strip()]
            if not cleaned:
                return {}
            rows = self.db.query(CptConsolidated.cpt_code, CptConsolidated.long_desc).filter(
                CptConsolidated.cpt_code.in_(cleaned)
            ).all()
            result = {row.cpt_code: (row.long_desc or "").strip() for row in rows if row.long_desc}
            logger.info(f"Looked up {len(result)} CPT long descriptions from cpt_consolidated for {len(cleaned)} codes")
            return result
        except Exception as e:
            logger.error(f"Error looking up CPT descriptions from cpt_consolidated: {e}", exc_info=True)
            return {}

    async def categorize_cpt_codes(
        self,
        cpt_codes: List[Dict[str, str]],
        treatment_options: List[Dict[str, str]],
        custom_prompt: Optional[str] = None,
        diagnosis_terms: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Use GPT to assign categories to CPT codes from database.
        Categorizes codes in batches of 10 using hardcoded categories that match
        the GPT treatment options generation.
        
        Args:
            cpt_codes: List of CPT codes with code and description
            treatment_options: List of treatment options with categories (for context)
            custom_prompt: Optional custom prompt to override default
            diagnosis_terms: Optional list of diagnosis terms for relevancy scoring
            
        Returns:
            Tuple of (List of CPT codes with category field added, rendered prompt text)
        """
        if not cpt_codes or len(cpt_codes) == 0:
            return [], ""
        
        try:
            # Use hardcoded categories matching GPT treatment options generation
            categories = ["Surgery", "Radiation", "Endovascular", "Medical", "Diagnostic Testing"]
            categories_text = ", ".join(categories)
            
            # Format diagnosis terms for prompt (similar to GPT CPT code generation)
            diagnosis_terms_text = ""
            if diagnosis_terms and len(diagnosis_terms) > 0:
                diagnosis_terms_text = "\n".join([f"- {term.strip()}" for term in diagnosis_terms if term.strip()])
            else:
                diagnosis_terms_text = "Not specified"
            
            # Categorize codes in batches of 10
            logger.info(f"Categorizing {len(cpt_codes)} codes in batches of 10 using categories: {categories_text}")
            
            # Create a map of code -> description from original CPT codes
            description_map = {cpt['code']: cpt.get('description', '') for cpt in cpt_codes}
            
            # Process in batches of 10
            batch_size = 10
            all_categorized = []
            first_batch_prompt = ""  # Save the first batch's prompt to show in UI
            
            for i in range(0, len(cpt_codes), batch_size):
                batch = cpt_codes[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(cpt_codes) + batch_size - 1) // batch_size
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} codes)...")
                
                # Format batch for prompt
                batch_codes_text = "\n".join([f"- {cpt['code']}: {cpt.get('description', '')}" for cpt in batch])
                
                # Use custom prompt if provided, otherwise use default with predefined categories
                if custom_prompt:
                    # For custom prompts, we'll still use the categories we determined
                    prompt_template = custom_prompt.replace("{categories}", categories_text).replace("{cpt_codes}", batch_codes_text)
                    rendered_prompt = prompt_template
                    prompt = PromptTemplate(
                        input_variables=[],
                        template=prompt_template
                    )
                else:
                    prompt_template = """Categorize the following CPT codes into ONE of these 5 categories:

Categories (you MUST use only these):
{categories}

CPT Codes:
{cpt_codes}

Then, for each CPT code, assign a relevancy score from 0-100% indicating how likely the code is to be used to treat the diagnosis terms below.

Diagnosis Terms:
{diagnosis_terms}

Return the response in this exact JSON format:
[
    {{
        "code": "CPT_CODE",
        "category": "Category name",
        "relevancy_score": 95
    }}
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text. Use ONLY the categories provided above."""
                    
                    prompt = PromptTemplate(
                        input_variables=["categories", "diagnosis_terms", "cpt_codes"],
                        template=prompt_template
                    )
                    
                    rendered_prompt = prompt_template.format(
                        categories=categories_text,
                        diagnosis_terms=diagnosis_terms_text,
                        cpt_codes=batch_codes_text
                    )
                
                # Save the first batch's prompt to display in UI
                if batch_num == 1:
                    first_batch_prompt = rendered_prompt
                
                # Create chain and invoke
                chain = prompt | self.llm
                
                # Log which LLM provider is being used for AAPC categorization
                llm_provider = getattr(self.llm, '_provider', 'unknown').upper()
                if batch_num == 1:
                    logger.info(f"🔍 [AAPC CPT Categorization] Using {llm_provider} LLM to categorize database CPT codes (batch {batch_num}/{total_batches})")
                
                if custom_prompt:
                    response = await chain.ainvoke({})
                else:
                    response = await chain.ainvoke({
                        "categories": categories_text,
                        "diagnosis_terms": diagnosis_terms_text,
                        "cpt_codes": batch_codes_text
                    })
                
                # Extract JSON response
                response_text = extract_llm_response_content(response)
                
                # Clean up response
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                
                # Extract JSON array
                first_bracket = response_text.find('[')
                last_bracket = response_text.rfind(']')
                if first_bracket != -1 and last_bracket != -1:
                    response_text = response_text[first_bracket:last_bracket + 1]
                
                # Parse JSON
                try:
                    batch_categorized = json.loads(response_text)
                    all_categorized.extend(batch_categorized)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON for batch {batch_num}: {e}")
                    # Add batch codes with default category and score
                    for cpt in batch:
                        all_categorized.append({
                            "code": cpt['code'],
                            "category": categories[0],  # Use first category as default
                            "relevancy_score": 50  # Default score
                        })
            
            # Create a map of code -> category from all categorized results
            category_map = {item['code']: item.get('category') for item in all_categorized if 'code' in item and item.get('category')}
            
            # Create a map of code -> relevancy_score from all categorized results
            relevancy_score_map = {}
            for item in all_categorized:
                if 'code' in item and 'relevancy_score' in item:
                    score = item.get('relevancy_score', 0)
                    # Validate score is 0-100
                    if not isinstance(score, (int, float)) or score < 0 or score > 100:
                        score = 0
                    relevancy_score_map[item['code']] = int(score)
            
            # Determine default category: use most common category from results
            default_category = categories[0]
            if category_map:
                category_usage = {}
                for cat in category_map.values():
                    if cat:
                        category_usage[cat] = category_usage.get(cat, 0) + 1
                if category_usage:
                    default_category = max(category_usage.items(), key=lambda x: x[1])[0]
            
            # Determine default relevancy score: use average of all scores, or 50 if none
            default_relevancy_score = 50
            if relevancy_score_map:
                scores = list(relevancy_score_map.values())
                if scores:
                    default_relevancy_score = int(sum(scores) / len(scores))
            
            # Apply categories and relevancy scores to all CPT codes (including those not in GPT response)
            # Attach descriptions from original data
            result = []
            category_counts = {}
            for cpt in cpt_codes:
                category = category_map.get(cpt['code'], default_category)  # Default to most common category if not categorized
                relevancy_score = relevancy_score_map.get(cpt['code'], default_relevancy_score)  # Default to average score if not provided
                result.append({
                    "code": cpt['code'],
                    "description": description_map.get(cpt['code'], ''),  # Use description from original data
                    "category": category,
                    "relevancy_score": relevancy_score,
                    "relevant": relevancy_score >= 40,
                })
                category_counts[category] = category_counts.get(category, 0) + 1
            
            logger.info(f"Categorized {len(result)} CPT codes using GPT")
            logger.info(f"Category distribution: {dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True))}")
            
            # Build final rendered prompt (show the first batch's actual prompt)
            if not custom_prompt:
                final_rendered_prompt = first_batch_prompt
            else:
                final_rendered_prompt = first_batch_prompt if first_batch_prompt else rendered_prompt
            
            return result, final_rendered_prompt
            
        except Exception as e:
            logger.error(f"Error categorizing CPT codes: {e}", exc_info=True)
            # Return codes with default category and score if categorization fails
            default_prompt = f"Categorize the following CPT codes into one of these categories: Surgery, Radiation, Endovascular, Medical, Diagnostic Testing"
            return [{"code": cpt['code'], "description": cpt.get('description', ''), "category": "Medical", "relevancy_score": 50, "relevant": True} for cpt in cpt_codes], default_prompt
    
    async def generate_cpt_codes_from_analysis(
        self,
        search_query: str,
        anatomical_location: str = "",
        custom_prompt: Optional[str] = None,
        icd10_code: Optional[List[str]] = None  # List of ICD-10 codes
    ) -> Tuple[List[Dict[str, str]], str, str, List[Dict[str, str]], Dict[str, str]]:
        """
        Generate CPT codes in two LLM steps: (1) codes + descriptions only, (2) categorize + relevancy using DB descriptions.
        Also queries database for CPT codes mapped to ICD-10 code if provided.
        
        Args:
            search_query: Search query string (typically from generate_search_query)
            anatomical_location: Anatomical location of the condition
            custom_prompt: Optional custom prompt for the generation step (categorization uses its own default)
            icd10_code: Optional ICD-10 code(s) to query database for mapped CPT codes
            
        Returns:
            Tuple of (merged GPT CPT codes with category/relevancy from step 2, generation prompt text, categorization prompt text, database-mapped CPT codes, GPT CPT db descriptions map)
        """
        if not search_query:
            logger.warning("Cannot generate CPT codes - no search query provided")
            return [], "", "", [], {}

        search_terms = [term.strip() for term in search_query.split(" OR ") if term.strip()]
        logger.info(f"📋 [CPT Code Generation] Two-step: generate codes -> DB lookup -> categorize")
        logger.info(f"   - Search terms: {len(search_terms)} terms")
        logger.info(f"   - ICD-10 codes for DB query: {len(icd10_code) if icd10_code else 0} codes")
        logger.info(f"   - Anatomical location: {anatomical_location or 'Not specified'}")

        # Step 1: Generate codes and descriptions only (no category/relevancy)
        async def get_gpt_codes_only():
            logger.info(f"   🔄 [GPT Step 1] Generating CPT codes and descriptions only...")
            start_time = asyncio.get_event_loop().time()
            result = await self.generate_cpt_codes_only(search_terms, anatomical_location, custom_prompt=custom_prompt)
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"   ✅ [GPT Step 1] Completed in {elapsed:.2f}s")
            return result

        async def get_db_codes():
            if icd10_code:
                logger.info(f"   🔄 [Database] Starting database CPT code query...")
                start_time = asyncio.get_event_loop().time()
                codes_list = icd10_code if isinstance(icd10_code, list) else [icd10_code]
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.get_cpt_codes_from_icd10, codes_list)
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"   ✅ [Database] Found {len(result)} CPT codes in {elapsed:.2f}s")
                return result
            return []

        overall_start = asyncio.get_event_loop().time()
        gpt_result, db_codes = await asyncio.gather(get_gpt_codes_only(), get_db_codes())
        overall_elapsed = asyncio.get_event_loop().time() - overall_start

        gpt_codes_raw, generation_prompt_text = gpt_result
        if not gpt_codes_raw:
            logger.warning("No GPT CPT codes from step 1; skipping categorization")
            return [], generation_prompt_text, "", db_codes, {}

        # Step 1.5: Look up long descriptions from cpt_consolidated
        gpt_code_list = [c.get("code") for c in gpt_codes_raw if c.get("code")]
        gpt_cpt_db_descriptions = self.lookup_cpt_long_descriptions(gpt_code_list) if self.db else {}

        # Step 2: Build list with DATABASE descriptions for categorization (fallback to LLM description if no DB hit)
        cpt_for_categorization = []
        for c in gpt_codes_raw:
            code = c.get("code", "")
            db_desc = gpt_cpt_db_descriptions.get(code, "")
            desc = db_desc if db_desc else c.get("description", "")
            cpt_for_categorization.append({"code": code, "description": desc})

        logger.info(f"   🔄 [GPT Step 2] Categorizing {len(cpt_for_categorization)} codes with DB descriptions...")
        categorized_codes, categorization_prompt_text = await self.categorize_cpt_codes(
            cpt_codes=cpt_for_categorization,
            treatment_options=[],
            custom_prompt=None,
            diagnosis_terms=search_terms
        )

        # Merge: keep LLM description from step 1 for display; use category and relevancy from step 2
        llm_desc_by_code = {c["code"]: c.get("description", "") for c in gpt_codes_raw}
        merged_gpt_codes = []
        for cat in categorized_codes:
            code = cat.get("code", "")
            if code.endswith("99") or code.endswith("89"):
                continue
            score = cat.get("relevancy_score", 50)
            merged_gpt_codes.append({
                "code": code,
                "description": llm_desc_by_code.get(code, cat.get("description", "")),
                "category": cat.get("category", "Medical"),
                "relevancy_score": score,
                "relevant": score >= 40,
            })

        logger.info(f"✅ [CPT Code Generation] Two-step completed in {overall_elapsed:.2f}s")
        logger.info(f"   - GPT codes: {len(merged_gpt_codes)} (merged)")
        logger.info(f"   - Database codes: {len(db_codes)}")
        logger.info(f"   - CPT consolidated: {len(gpt_cpt_db_descriptions)} long descriptions")

        return merged_gpt_codes, generation_prompt_text, categorization_prompt_text, db_codes, gpt_cpt_db_descriptions

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
        # TEMPORARILY DISABLED: CMS API calls take too long and are being skipped for testing other features.
        # The search functionality will still work without CMS data - it just won't include clinical volume metrics.
        # To re-enable, remove this early return block.
        return {
            "url": None,
            "urls": [],
            "results": [],
            "total_results": 0,
            "total_providers": 0,
            "cpt_codes_searched": [cpt.get("code", "") for cpt in cpt_codes] if cpt_codes else [],
            "years_queried": [],
            "error": None
        }
        
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
            
            # Split CPT codes into chunks of 50 if needed
            chunk_size = 50
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
            
            async with httpx.AsyncClient(
                timeout=300.0,
                limits=httpx.Limits(max_keepalive_connections=200, max_connections=500)
            ) as client:
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
                                all_chunk_results = []
                                page_size = 5000
                                max_parallel_pages = 10  # Fetch up to 10 pages in parallel
                                
                                # First, fetch page 0 to see if there's data
                                first_url = url + f"&size={page_size}&offset=0"
                                response = await client.get(first_url)
                                response.raise_for_status()
                                cms_data = response.json()
                                first_page = cms_data if isinstance(cms_data, list) else [cms_data]
                                
                                if len(first_page) == 0:
                                    logger.info(f"CMS API call for {year} chunk {chunk_idx + 1}: no results found")
                                    return []
                                
                                # Add year metadata to first page
                                for result in first_page:
                                    result['_year'] = year
                                all_chunk_results.extend(first_page)
                                page_count = 1
                                
                                # If first page is full, there are likely more pages - fetch in parallel batches
                                if len(first_page) >= page_size:
                                    offset = page_size
                                    
                                    while True:
                                        # Create batch of parallel page requests
                                        page_tasks = []
                                        for i in range(max_parallel_pages):
                                            page_url = url + f"&size={page_size}&offset={offset + (i * page_size)}"
                                            page_tasks.append(client.get(page_url))
                                        
                                        # Execute batch in parallel
                                        responses = await asyncio.gather(*page_tasks, return_exceptions=True)
                                        
                                        # Process responses
                                        found_data = False
                                        should_continue = True
                                        
                                        for i, resp in enumerate(responses):
                                            if isinstance(resp, Exception):
                                                # First page in batch failed - stop pagination
                                                if i == 0:
                                                    should_continue = False
                                                    break
                                                # Later pages failed - stop at this batch but keep previous results
                                                logger.warning(f"Error fetching page {offset // page_size + i + 1} for {year} chunk {chunk_idx + 1}: {resp}")
                                                break
                                            
                                            try:
                                                resp.raise_for_status()
                                                page_data = resp.json()
                                                page_results = page_data if isinstance(page_data, list) else [page_data]
                                                
                                                if len(page_results) == 0:
                                                    should_continue = False
                                                    break
                                                
                                                # Add year metadata
                                                for result in page_results:
                                                    result['_year'] = year
                                                all_chunk_results.extend(page_results)
                                                page_count += 1
                                                found_data = True
                                                
                                                # If this page has fewer than page_size, we've reached the end
                                                if len(page_results) < page_size:
                                                    should_continue = False
                                                    break
                                            except httpx.HTTPStatusError as e:
                                                if e.response.status_code == 404:
                                                    # 404 means no more pages
                                                    should_continue = False
                                                    break
                                                else:
                                                    logger.warning(f"HTTP {e.response.status_code} on page {offset // page_size + i + 1} for {year} chunk {chunk_idx + 1}")
                                                    if i == 0:
                                                        should_continue = False
                                                    break
                                        
                                        if not should_continue or not found_data:
                                            break
                                        
                                        # Move offset forward for next batch
                                        offset += max_parallel_pages * page_size
                                
                                logger.info(f"CMS API call for {year} chunk {chunk_idx + 1}: fetched {len(all_chunk_results)} rows across {page_count} page(s)")
                                
                                return all_chunk_results
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
                Specialty: Neurosurgery
                
                Additional Information from Medical Records/PDFs:
                {pdf_content}
                
                Analyze the information above and provide the most common treatment options based on the diagnosis, specialty, and anatomical location. 
                For each treatment option, include the general category of the treatment option. You MUST use one of these categories:
                - Surgery
                - Radiation
                - Endovascular
                - Medical
                - Diagnostic Testing
                                
                Return the response in this exact JSON format:
                {{
                    "treatment_options": [
                        {{
                            "name": "Treatment name",
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
            response_text = extract_llm_response_content(response)
            
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
