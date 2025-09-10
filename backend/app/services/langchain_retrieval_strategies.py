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
            input_variables=["symptoms", "diagnosis", "medical_history", "medications", "surgical_history", "pdf_content"],
            template="""
            Generate 5 diverse and comprehensive search queries for finding medical specialists.
            
            Patient Information:
            Symptoms: {symptoms}
            Diagnosis: {diagnosis}
            Medical History: {medical_history}
            Current Medications: {medications}
            Surgical History: {surgical_history}
            
            Additional Information from Medical Records/PDFs:
            {pdf_content}
            
            Create diverse search queries that will find relevant medical specialists based on all the patient information provided (symptoms, diagnosis, medical history, medications, surgical history, PDF content, etc.):
            1. One focused on the specific condition/symptoms
            2. One focused on treatment approaches
            3. One focused on related conditions
            4. One focused on diagnostic approaches
            5. One broad query for general relevance
            
            Return 5 queries, one per line.
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
        patient_profile: Dict[str, Any],
        top_k: int = 200
    ) -> List[Dict[str, Any]]:
        """Retrieve specialist information from Pinecone using LangChain-generated queries."""
        try:
            # Generate intelligent search queries
            # Use the full patient information instead of just extracted symptoms
            patient_input = patient_profile.get("additional_notes", "")
            if not patient_input:
                # Fallback to symptoms if additional_notes not available
                patient_input = ", ".join(patient_profile.get("symptoms", []))
            
            # Parse patient input to extract individual fields including PDF content
            symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content = self._parse_patient_input(patient_input)
            
            query_input = {
                "symptoms": symptoms,
                "diagnosis": diagnosis,
                "medical_history": medical_history,
                "medications": medications,
                "surgical_history": surgical_history,
                "pdf_content": pdf_content,
            }
            
            queries_response = await self.query_chain.arun(**query_input)
            queries = [q.strip() for q in queries_response.split('\n') if q.strip()]
            
            # Log the generated queries
            logger.info(f"🔍 Generated {len(queries)} Pinecone search queries:")
            for i, query in enumerate(queries, 1):
                logger.info(f"  {i}. {query}")
            
            # Ensure we have queries
            if not queries:
                raise ValueError("Failed to generate search queries from LLM")
            
            # Search with each query and combine results from both indexes
            all_candidates = []
            seen_ids = set()
            
            for i, query in enumerate(queries[:5], 1):  # Use up to 5 queries
                try:
                    logger.info(f"🔍 Executing Pinecone query {i}: '{query}'")
                    
                    # Query Vumedi index
                    vumedi_results = self.vumedi_index.search(
                        namespace="__default__",
                        query={
                            "inputs": {"text": query},
                            "top_k": top_k // 6  # Distribute top_k across queries and indexes
                        },
                        fields=["*"]
                    )
                    
                    # Query PubMed index
                    pubmed_results = self.pubmed_index.search(
                        namespace="__default__",
                        query={
                            "inputs": {"text": query},
                            "top_k": top_k // 6  # Distribute top_k across queries and indexes
                        },
                        fields=["*"]
                    )
                    
                    # Parse Vumedi results
                    vumedi_count = 0
                    if hasattr(vumedi_results, 'result') and hasattr(vumedi_results.result, 'hits'):
                        for hit in vumedi_results.result.hits:
                            candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                            if candidate_id and candidate_id not in seen_ids:
                                # Add source information
                                hit.fields["_source"] = "vumedi"
                                all_candidates.append(hit.fields)
                                seen_ids.add(candidate_id)
                                vumedi_count += 1
                    
                    # Parse PubMed results
                    pubmed_count = 0
                    if hasattr(pubmed_results, 'result') and hasattr(pubmed_results.result, 'hits'):
                        for hit in pubmed_results.result.hits:
                            candidate_id = hit.fields.get("pmid", f"{hit.fields.get('title', '')}_{hit.fields.get('authors', '')}")
                            if candidate_id and candidate_id not in seen_ids:
                                # Add source information
                                hit.fields["_source"] = "pubmed"
                                all_candidates.append(hit.fields)
                                seen_ids.add(candidate_id)
                                pubmed_count += 1
                    
                    logger.info(f"✅ Query {i} returned {vumedi_count} Vumedi + {pubmed_count} PubMed = {vumedi_count + pubmed_count} new results (total unique: {len(all_candidates)})")
                                
                except Exception as e:
                    logger.error(f"Query failed: {query}, error: {str(e)}")
                    raise
            
            # Add additional broad searches if we don't have enough results
            if len(all_candidates) < 50:
                logger.info(f"Only found {len(all_candidates)} results, adding broader searches...")
                
                # Specialty-based searches removed - using only LLM-generated queries
            
            # Count results by source
            vumedi_count = sum(1 for candidate in all_candidates if candidate.get("_source") == "vumedi")
            pubmed_count = sum(1 for candidate in all_candidates if candidate.get("_source") == "pubmed")
            
            logger.info(f"LangChain retrieval found {len(all_candidates)} specialist information records using {len(queries)} queries")
            logger.info(f"📊 Results breakdown: {vumedi_count} from Vumedi, {pubmed_count} from PubMed")
            logger.info(f"🔍 DEBUG: Returning type: {type(all_candidates)}, length: {len(all_candidates)}")
            return all_candidates
            
        except Exception as e:
            logger.error(f"Error in LangChain retrieval: {str(e)}")
            raise
    

