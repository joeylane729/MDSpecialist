"""
LangChain Retrieval Strategies
"""

import logging
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

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
            template="""Generate a search query to find PubMed articles and medical lectures from our vector database about this diagnosis:

Medical Analysis Diagnosis: {icd10_description}
User-Entered Diagnosis: {user_diagnosis}

IMPORTANT: Return ONLY the search query string itself with NO explanations, NO markdown, NO code blocks, NO additional text. Just the query."""
        )
        
        self.query_chain = LLMChain(llm=self.llm, prompt=self.query_prompt)
        logger.info("LangChainRetrievalStrategies initialized successfully")
    
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
        
        Uses fixed limits: 50 for Vumedi, 200 for PubMed per query.
        """
        try:
            # Extract only the two required inputs:
            # 1. Medical analysis diagnosis description (not the ICD code)
            icd10_description = medical_analysis_results.get("icd10_description", "")
            
            # 2. User-entered diagnosis from the first screen
            user_diagnosis = medical_analysis_results.get("conditions", "")
            
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
            
            # Execute single search and group results
            treatment_results = {}
            seen_ids = set()
            
            # Use primary diagnosis as the single treatment group
            treatment_id = "primary_diagnosis"
            treatment_name = icd10_description or "Primary Diagnosis"
            
            try:
                logger.info(f"🔍 Executing Pinecone search for '{treatment_name}': '{query[:80]}{'...' if len(query) > 80 else ''}'")
                
                # Use separate limits for Vumedi and PubMed
                vumedi_top_k = 50  # Max 50 total for Vumedi
                pubmed_top_k = 200  # Max 200 total for PubMed
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
                if hasattr(vumedi_results, 'result') and hasattr(vumedi_results.result, 'hits'):
                    for hit in vumedi_results.result.hits:
                        candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                        if candidate_id and candidate_id not in seen_ids:
                            # Add source information and treatment metadata
                            hit.fields["_source"] = "vumedi"
                            hit.fields["_treatment_id"] = treatment_id
                            hit.fields["_treatment_name"] = treatment_name
                            treatment_results[treatment_id]["results"].append(hit.fields)
                            seen_ids.add(candidate_id)
                            vumedi_count += 1
                
                # Parse PubMed results
                pubmed_count = 0
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
                            treatment_results[treatment_id]["results"].append(hit.fields)
                            seen_ids.add(candidate_id)
                            pubmed_count += 1
                
                logger.info(f"✅ Search returned {vumedi_count} Vumedi + {pubmed_count} PubMed = {vumedi_count + pubmed_count} total results")
                            
            except Exception as e:
                logger.error(f"❌ Search failed for '{treatment_name}': {str(e)}")
                raise
            
            # Count total results by source
            total_results = len(treatment_results[treatment_id]["results"])
            vumedi_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "vumedi")
            pubmed_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "pubmed")
            
            logger.info(f"📊 Results summary:")
            logger.info(f"   📋 Total: {total_results} results ({vumedi_total} Vumedi, {pubmed_total} PubMed)")
            logger.info(f"✅ LangChain retrieval completed using single diagnosis-based query")
            logger.debug(f"🔍 Returning results grouped under treatment_id: {treatment_id}")
            
            # Return both the treatment results and the search query
            return {
                "treatment_results": treatment_results,
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"❌ Error in LangChain retrieval: {str(e)}")
            raise
    

