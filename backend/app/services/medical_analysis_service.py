import os
import json
import logging
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
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
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
            
            # Predict relevant CPT codes using the search query terms
            cpt_codes = []
            if search_query:
                # Parse search query to extract individual terms (split by " OR ")
                search_terms = [term.strip() for term in search_query.split(" OR ") if term.strip()]
                logger.info(f"🔍 Predicting CPT codes for {len(search_terms)} diagnosis terms: {', '.join(search_terms[:3])}{'...' if len(search_terms) > 3 else ''}")
                cpt_codes = await self.predict_cpt_codes(search_terms)
                if cpt_codes:
                    logger.info(f"✅ Predicted {len(cpt_codes)} CPT codes")
                else:
                    logger.warning(f"⚠️  No CPT codes predicted")
            else:
                logger.warning("⚠️  Cannot predict CPT codes - no search query generated")
            
            # Extract treatment options from diagnoses if available
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
        search_query_terms: List[str]
    ) -> List[Dict[str, str]]:
        """
        Use GPT to predict relevant CPT codes that a neurosurgeon would use to treat the given diagnosis terms.
        
        Args:
            search_query_terms: List of diagnosis terms/descriptions from the search query (e.g., ["acoustic neuroma", "vestibular schwannoma", ...])
            
        Returns:
            List of dictionaries containing CPT code and description
        """
        try:
            # Format the terms as a readable list
            terms_text = "\n".join([f"- {term.strip()}" for term in search_query_terms if term.strip()])
            
            prompt = PromptTemplate(
                input_variables=["diagnosis_terms"],
                template="""Give an exhaustive list of CPT codes that could possibly be used by a neurosurgeon to treat patients with any of these diagnoses:

{diagnosis_terms}

Make sure you do not miss any possible CPT codes, even rare ones. 
Super super exhaustive, do not miss any codes that any neurosurgeon could possibly choose as the CPT code if someone has any of these diagnoses. 
It's ok if it's really rare, as long as it's possible. 
If any neurosurgeon could possibly choose a CPT code for any of these conditions, include it.

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
            )
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "diagnosis_terms": terms_text
            })
            
            # Extract the JSON response
            response_text = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean up the response (remove markdown formatting if present)
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Parse the JSON response
            cpt_codes = json.loads(response_text)
            
            logger.info(f"✅ Predicted {len(cpt_codes)} CPT codes for {len(search_query_terms)} diagnosis terms")
            return cpt_codes
            
        except Exception as e:
            logger.error(f"Error predicting CPT codes: {e}")
            return []

    async def query_cms_api(
        self,
        cpt_codes: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Query the CMS public API using CPT codes from the medical analysis.
        If more than 100 CPT codes, splits into multiple API calls.
        Groups results by provider (Rndrng_NPI) and sums Total Services.
        Returns top 25 providers by total services.
        
        Args:
            cpt_codes: List of dictionaries containing CPT codes and descriptions
            
        Returns:
            Dictionary with 'url', 'results' (grouped by provider), and metadata
        """
        if not cpt_codes or len(cpt_codes) == 0:
            logger.warning("⚠️  No CPT codes provided for CMS API query")
            return {
                "url": None,
                "results": [],
                "total_results": 0,
                "cpt_codes_searched": [],
                "error": "No CPT codes provided"
            }
        
        try:
            # Extract just the CPT code values
            cpt_code_values = [cpt['code'] for cpt in cpt_codes if 'code' in cpt]
            
            logger.info(f"🔍 Querying CMS API with {len(cpt_code_values)} CPT codes")
            
            # Build CMS API base URL
            base_url = "https://data.cms.gov/data-api/v1/dataset/92396110-2aed-4d63-a6a2-5d6207d46a29/data"
            
            # Split CPT codes into chunks of 100 if needed
            chunk_size = 100
            cpt_chunks = [
                cpt_code_values[i:i + chunk_size] 
                for i in range(0, len(cpt_code_values), chunk_size)
            ]
            
            logger.info(f"📦 Split into {len(cpt_chunks)} API call(s) (max 100 CPT codes per call)")
            
            # Make multiple API calls if needed
            all_results = []
            urls_used = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    logger.info(f"🌐 CMS API call {chunk_idx + 1}/{len(cpt_chunks)}: {len(cpt_chunk)} CPT codes")
                    
                    try:
                        response = await client.get(full_url)
                        response.raise_for_status()
                        
                        cms_data = response.json()
                        chunk_results = cms_data if isinstance(cms_data, list) else [cms_data]
                        all_results.extend(chunk_results)
                        
                        logger.info(f"✅ Call {chunk_idx + 1} returned {len(chunk_results)} results")
                    except Exception as e:
                        logger.error(f"❌ Error in API call {chunk_idx + 1}: {e}")
                        # Continue with other calls even if one fails
                        continue
            
            logger.info(f"📊 Total raw results collected: {len(all_results)}")
            
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
                        'HCPCS_Descriptions': []  # Track descriptions
                    }
                
                provider_totals[npi]['Tot_Srvcs'] += tot_srvcs_int
                
                # Track CPT codes and descriptions
                hcpcs_cd = result.get('HCPCS_Cd', '')
                hcpcs_desc = result.get('HCPCS_Desc', '')
                if hcpcs_cd:
                    provider_totals[npi]['HCPCS_Codes'].add(hcpcs_cd)
                    if hcpcs_desc and hcpcs_desc not in provider_totals[npi]['HCPCS_Descriptions']:
                        provider_totals[npi]['HCPCS_Descriptions'].append(hcpcs_desc)
            
            # Convert to list and sort by Tot_Srvcs descending, take top 25
            grouped_results = list(provider_totals.values())
            grouped_results.sort(key=lambda x: x['Tot_Srvcs'], reverse=True)
            top_25_providers = grouped_results[:25]
            
            # Convert sets to lists for JSON serialization
            for provider in top_25_providers:
                provider['HCPCS_Codes'] = sorted(list(provider['HCPCS_Codes']))
            
            logger.info(f"✅ Grouped into {len(provider_totals)} providers, returning top 25")
            
            result = {
                "url": urls_used[0] if urls_used else None,  # Primary URL for display
                "urls": urls_used,  # All URLs used
                "results": top_25_providers,
                "total_results": len(all_results),  # Total raw results
                "total_providers": len(provider_totals),  # Total unique providers
                "cpt_codes_searched": cpt_code_values,
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
        pdf_content: str = ""
    ) -> Dict[str, Any]:
        """
        Use GPT to predict primary diagnosis and treatment options based on patient information.
        
        Args:
            symptoms: Patient symptoms
            diagnosis: Patient diagnosis
            medical_history: Medical history (optional)
            medications: Current medications (optional)
            surgical_history: Surgical history (optional)
            pdf_content: Extracted content from uploaded PDF files (optional)
            
        Returns:
            Dictionary containing primary diagnosis and exactly 3 treatment options
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
                
                Analyze the information above and provide:
                1. Primary diagnosis (most likely ICD-10 code and description based on symptoms and diagnosis)
                2. Treatment options
                
                Consider the symptoms carefully when determining the most likely diagnosis and alternatives.
                For treatment options, provide evidence-based treatment approaches with realistic outcomes and complications.
                
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
                
                return diagnoses
            else:
                logger.warning(f"GPT returned invalid response structure: {diagnoses}")
                return {"primary": {}, "treatment_options": []}
                
        except Exception as e:
            logger.error(f"Error in GPT diagnosis prediction: {e}")
            return {"primary": {}, "differential": [], "treatment_options": []}
