"""
LangChain Retrieval Strategies
"""

import logging
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.chains import LLMChain

from ..models.specialist_recommendation import PatientProfile
from .pinecone_service import PineconeService

logger = logging.getLogger(__name__)

class LangChainRetrievalStrategies:
    """LangChain-powered retrieval strategies."""
    
    def __init__(self, pinecone_service: PineconeService):
        self.pinecone_service = pinecone_service
        self.vumedi_index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
        self.pubmed_index = self.pinecone_service.pc.Index(self.pinecone_service.pubmed_index_name)
        
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        self.query_prompt = PromptTemplate(
            input_variables=["icd10_description", "user_diagnosis"],
            template="""Generate a search query to find PubMed articles and medical lectures from our vector database using both the user-entered diagnosis and the medical analysis diagnosis:

Medical Analysis Diagnosis: {icd10_description}
User-Entered Diagnosis: {user_diagnosis}

The query should include the diagnosis info above as well as all other possible ways to phrase the diagnosis (separated by the OR operator).

Example: variation 1 OR variation 2 OR variation 3 OR ...

IMPORTANT: Return ONLY the search query string itself with NO explanations, NO markdown, NO code blocks, NO additional text. Just the query."""
        )
        
        self.query_chain = LLMChain(llm=self.llm, prompt=self.query_prompt)
        logger.info("LangChainRetrievalStrategies initialized successfully")
    
    def _verify_result(self, result: dict, query_variations: list, source: str) -> bool:
        """
        Verify if a result contains any of the query variations.
        
        Args:
            result: Pinecone result with fields
            query_variations: List of query variations to match against
            source: Explicit source type ("vumedi" or "pubmed")
            
        Returns:
            True if result contains any variation, False otherwise
        """
        # Get content based on explicit source type
        content_parts = []
        
        # Always include title if available
        if result.get('title'):
            content_parts.append(result['title'])
        
        # Add source-specific content based on explicit source
        if source == 'vumedi':
            # For Vumedi: use title only (as requested)
            pass
        elif source == 'pubmed':
            # For PubMed: use title + abstract (as requested)
            if result.get('abstract'):
                content_parts.append(result['abstract'])
        
        # Combine all content
        full_content = " ".join(content_parts).lower()
        
        # Check for exact matches (case-insensitive)
        for variation in query_variations:
            if variation.lower() in full_content:
                logger.debug(f"✅ Match found: '{variation}' in {source} result")
                return True
        
        logger.debug(f"❌ No match found in {source} result: {result.get('title', 'No title')[:50]}...")
        return False
    
    def _parse_patient_input(self, patient_input: str) -> tuple:
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
    
    async def retrieve_specialist_information(
        self,
        medical_analysis_results: Dict[str, Any],
        top_k: int = 200  # Not used for distribution, kept for backward compatibility
    ) -> Dict[str, Any]:
        """Retrieve specialist information from Pinecone using LangChain-generated queries based on medical analysis results.
        
        Uses fixed limits: 100 for Vumedi, 1000 for PubMed per query.
        """
        try:
            # Extract only the two required inputs:
            # 1. Medical analysis diagnosis description (not the ICD code)
            icd10_description = medical_analysis_results.get("icd10_description", "")
            
            # 2. User-entered diagnosis from the first screen
            user_diagnosis = medical_analysis_results.get("user_diagnosis", "")
            
            query_input = {
                "icd10_description": icd10_description,
                "user_diagnosis": user_diagnosis,
            }
            
            logger.info(f"🔍 Query inputs:")
            logger.info(f"   Medical Analysis Diagnosis: {icd10_description}")
            logger.info(f"   User-Entered Diagnosis: {user_diagnosis}")
            
            query_response = await self.query_chain.arun(**query_input)
            query = query_response.strip()
            
            # Log the generated query
            logger.info(f"🔍 Generated single diagnosis-based search query:")
            logger.info(f"📊 Query limits: 50 Vumedi + 200 PubMed = 250 max results total")
            logger.info(f"   Query: {query}")
            
            # Ensure we have a query
            if not query:
                logger.error("❌ Failed to generate search query from LLM")
                raise ValueError("Failed to generate search query from LLM")
            
            # Parse query variations for verification
            query_variations = [variation.strip() for variation in query.split(" OR ")]
            logger.info(f"🔍 Parsed {len(query_variations)} query variations for verification:")
            for i, variation in enumerate(query_variations, 1):
                logger.info(f"   {i}. {variation}")
            
            # Execute single search and group results
            treatment_results = {}
            seen_ids = set()
            
            # Use primary diagnosis as the single treatment group
            treatment_id = "primary_diagnosis"
            treatment_name = icd10_description or "Primary Diagnosis"
            
            try:
                logger.info(f"🔍 Executing Pinecone search for '{treatment_name}': '{query[:80]}{'...' if len(query) > 80 else ''}'")
                
                # Use separate limits for Vumedi and PubMed
                vumedi_top_k = 100  # Max 100 total for Vumedi
                pubmed_top_k = 100000  # Max 100000 total for PubMed
                logger.debug(f"   📊 Using top_k={vumedi_top_k} for Vumedi, {pubmed_top_k} for PubMed")
                
                # Query Vumedi index
                vumedi_results = self.vumedi_index.search(
                    namespace="__default__",
                    query={
                        "inputs": {"text": query},
                        "top_k": vumedi_top_k
                    },
                    fields=["*"]
                )
                
                # Query PubMed index
                pubmed_results = self.pubmed_index.search(
                    namespace="__default__",
                    query={
                        "inputs": {"text": query},
                        "top_k": pubmed_top_k
                    },
                    fields=["*"]
                )
                
                # Initialize treatment results
                treatment_results[treatment_id] = {
                    "name": treatment_name,
                    "results": [],
                    "query": query
                }
                
                # Parse Vumedi results
                vumedi_count = 0
                vumedi_filtered = 0
                if hasattr(vumedi_results, 'result') and hasattr(vumedi_results.result, 'hits'):
                    for hit in vumedi_results.result.hits:
                        candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                        if candidate_id and candidate_id not in seen_ids:
                            # Add source information and treatment metadata
                            hit.fields["_source"] = "vumedi"
                            hit.fields["_treatment_id"] = treatment_id
                            hit.fields["_treatment_name"] = treatment_name
                            hit.fields["_score"] = getattr(hit, '_score', None)
                            
                            # Verify the result contains query variations
                            is_verified = self._verify_result(hit.fields, query_variations, source="vumedi")
                            hit.fields["_verified"] = is_verified
                            
                            # Store all results (both verified and unverified)
                            treatment_results[treatment_id]["results"].append(hit.fields)
                            seen_ids.add(candidate_id)
                            
                            if is_verified:
                                vumedi_count += 1
                            else:
                                vumedi_filtered += 1
                                logger.debug(f"❌ Filtered Vumedi result: {hit.fields.get('title', 'No title')[:50]}...")
                
                # Parse PubMed results
                pubmed_count = 0
                pubmed_filtered = 0
                if hasattr(pubmed_results, 'result') and hasattr(pubmed_results.result, 'hits'):
                    for hit in pubmed_results.result.hits:
                        # Get PMID from hit._id (newer API) or hit.id (older API)
                        pmid = getattr(hit, '_id', None) or getattr(hit, 'id', None)
                        candidate_id = pmid or f"{hit.fields.get('title', '')}_{hit.fields.get('authors', '')}"
                        if candidate_id and candidate_id not in seen_ids:
                            # Add source information and treatment metadata
                            hit.fields["_source"] = "pubmed"
                            hit.fields["_treatment_id"] = treatment_id
                            hit.fields["_treatment_name"] = treatment_name
                            hit.fields["_id"] = pmid  # Store the PMID for later use
                            hit.fields["_score"] = getattr(hit, '_score', None)
                            
                            # Verify the result contains query variations
                            is_verified = self._verify_result(hit.fields, query_variations, source="pubmed")
                            hit.fields["_verified"] = is_verified
                            
                            # Store all results (both verified and unverified)
                            treatment_results[treatment_id]["results"].append(hit.fields)
                            seen_ids.add(candidate_id)
                            
                            if is_verified:
                                pubmed_count += 1
                            else:
                                pubmed_filtered += 1
                                logger.debug(f"❌ Filtered PubMed result: {hit.fields.get('title', 'No title')[:50]}...")
                
                total_stored = vumedi_count + vumedi_filtered + pubmed_count + pubmed_filtered
                logger.info(f"✅ Search returned {vumedi_count} verified Vumedi + {pubmed_count} verified PubMed = {vumedi_count + pubmed_count} verified results")
                logger.info(f"📊 Stored total: {total_stored} results ({vumedi_count + vumedi_filtered} Vumedi, {pubmed_count + pubmed_filtered} PubMed)")
                if vumedi_filtered > 0 or pubmed_filtered > 0:
                    logger.info(f"🔍 Including {vumedi_filtered} Vumedi + {pubmed_filtered} PubMed unverified results for debug display")
                            
            except Exception as e:
                logger.error(f"❌ Search failed for '{treatment_name}': {str(e)}")
                raise
            
            # Count total results by source and verification status
            total_results = len(treatment_results[treatment_id]["results"])
            vumedi_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "vumedi")
            pubmed_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "pubmed")
            verified_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_verified") == True)
            
            logger.info(f"📊 Results summary:")
            logger.info(f"   📋 Total stored: {total_results} results ({vumedi_total} Vumedi, {pubmed_total} PubMed)")
            logger.info(f"   ✅ Verified: {verified_total} results")
            logger.info(f"   ❌ Unverified: {total_results - verified_total} results")
            logger.info(f"✅ LangChain retrieval completed using single diagnosis-based query")
            logger.info(f"🔍 All results stored with verification status for debug display")
            logger.debug(f"🔍 Returning results grouped under treatment_id: {treatment_id}")
            
            # Return both the treatment results and the search query
            return {
                "treatment_results": treatment_results,
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"❌ Error in LangChain retrieval: {str(e)}")
            raise
    

