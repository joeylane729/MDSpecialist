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
            input_variables=["primary_diagnosis", "differential_diagnoses", "treatment_options", "icd10_code", "icd10_description", "num_treatments"],
            template="""
            Generate {num_treatments} targeted search queries for finding medical specialists - one query for each treatment option.
            
            Medical Analysis Results:
            Primary Diagnosis: {primary_diagnosis}
            ICD-10 Code: {icd10_code}
            ICD-10 Description: {icd10_description}
            
            Differential Diagnoses:
            {differential_diagnoses}
            
            Treatment Options:
            {treatment_options}
            
            Create {num_treatments} search queries that will find medical specialists who specialize in each specific treatment approach. Each query should:
            1. Focus on the specific treatment option and its implementation
            2. Include relevant diagnostic information and medical context
            3. Target specialists who perform or specialize in that particular treatment
            4. Be specific enough to find highly relevant specialist information
            
            Return {num_treatments} queries, one per line.
            """
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
            # Extract structured medical analysis data
            primary_diagnosis = medical_analysis_results.get("predicted_icd10", "")
            icd10_description = medical_analysis_results.get("icd10_description", "")
            
            # Format differential diagnoses
            differential_diagnoses = medical_analysis_results.get("differential_diagnoses", [])
            differential_text = ""
            if differential_diagnoses:
                differential_text = "\n".join([
                    f"- {dx.get('code', '')}: {dx.get('description', '')}" 
                    for dx in differential_diagnoses
                ])
            
            # Format treatment options
            treatment_options = medical_analysis_results.get("treatment_options", [])
            treatment_text = ""
            num_treatments = len(treatment_options)
            if treatment_options:
                treatment_text = "\n".join([
                    f"- {tx.get('name', '')}: {tx.get('outcomes', '')}" 
                    for tx in treatment_options
                ])
            
            # If no treatment options, fall back to generating 3 queries based on diagnosis
            if num_treatments == 0:
                num_treatments = 3
                logger.warning("⚠️  No treatment options found, generating 3 diagnosis-based queries")
            
            query_input = {
                "primary_diagnosis": f"{primary_diagnosis} - {icd10_description}",
                "differential_diagnoses": differential_text,
                "treatment_options": treatment_text,
                "icd10_code": primary_diagnosis,
                "icd10_description": icd10_description,
                "num_treatments": num_treatments,
            }
            
            queries_response = await self.query_chain.arun(**query_input)
            queries = [q.strip() for q in queries_response.split('\n') if q.strip()]
            
            # Log the generated queries
            logger.info(f"🔍 Generated {len(queries)} Pinecone search queries (one per treatment option):")
            logger.info(f"📊 Query limits: 50 Vumedi + 200 PubMed = 250 max results per treatment")
            for i, query in enumerate(queries, 1):
                logger.info(f"   {i}. {query}")
            
            # Ensure we have queries
            if not queries:
                logger.error("❌ Failed to generate search queries from LLM")
                raise ValueError("Failed to generate search queries from LLM")
            
            # Search with each query and group results by treatment option
            treatment_results = {}
            seen_ids = set()
            
            for i, query in enumerate(queries[:num_treatments], 1):  # Use up to num_treatments queries
                # Get the treatment option for this query
                treatment_option = treatment_options[i-1] if i-1 < len(treatment_options) else None
                treatment_name = treatment_option.get('name', f'Treatment {i}') if treatment_option else f'Treatment {i}'
                treatment_id = f'treatment_{i}'
                try:
                    logger.info(f"🔍 Executing Pinecone query {i} for '{treatment_name}': '{query[:80]}{'...' if len(query) > 80 else ''}'")
                    
                    # Use separate limits for Vumedi and PubMed
                    vumedi_top_k = 50  # Max 50 per Vumedi query
                    pubmed_top_k = 200  # Max 200 per PubMed query
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
                    
                    # Initialize treatment results if not exists
                    if treatment_id not in treatment_results:
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
                            # Debug: Log available fields for first few hits
                            if pubmed_count < 3:
                                logger.info(f"🔍 PubMed hit fields: {list(hit.fields.keys())}")
                                logger.info(f"🔍 Hit object attributes: {[attr for attr in dir(hit) if not attr.startswith('_')]}")
                                logger.info(f"🔍 Hit _id: {getattr(hit, '_id', 'NO_ID_ATTR')}")
                                logger.info(f"🔍 Hit id: {getattr(hit, 'id', 'NO_ID_ATTR')}")
                            
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
                    
                    logger.info(f"✅ Query {i} ({treatment_name}) returned {vumedi_count} Vumedi + {pubmed_count} PubMed = {vumedi_count + pubmed_count} new results")
                                
                except Exception as e:
                    logger.error(f"❌ Query {i} failed for '{treatment_name}': {str(e)}")
                    raise
            
            # Count results by treatment and source
            total_results = 0
            logger.info("📊 Treatment-specific results summary:")
            for treatment_id, treatment_data in treatment_results.items():
                treatment_count = len(treatment_data["results"])
                total_results += treatment_count
                vumedi_count = sum(1 for result in treatment_data["results"] if result.get("_source") == "vumedi")
                pubmed_count = sum(1 for result in treatment_data["results"] if result.get("_source") == "pubmed")
                logger.info(f"   📋 {treatment_data['name']}: {treatment_count} results ({vumedi_count} Vumedi, {pubmed_count} PubMed)")
            
            logger.info(f"✅ LangChain retrieval completed: {total_results} specialist records using {len(queries)} treatment-focused queries")
            logger.debug(f"🔍 Returning {len(treatment_results)} treatment groups")
            return treatment_results
            
        except Exception as e:
            logger.error(f"❌ Error in LangChain retrieval: {str(e)}")
            raise
    

