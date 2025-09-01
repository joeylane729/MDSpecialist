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
        self.index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
        
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        self.query_prompt = PromptTemplate(
            input_variables=["symptoms"],
            template="""
            Generate 5 diverse and comprehensive search queries for finding medical specialists.
            
            Patient Information:
            {symptoms}
            
            Create diverse search queries that will find relevant medical specialists based on ALL the patient information provided (symptoms, diagnosis, medical history, medications, surgical history, etc.):
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
            
            query_input = {
                "symptoms": patient_input,
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
            
            # Search with each query and combine results
            all_candidates = []
            seen_ids = set()
            
            for i, query in enumerate(queries[:5], 1):  # Use up to 5 queries
                try:
                    logger.info(f"🔍 Executing Pinecone query {i}: '{query}'")
                    results = self.index.search(
                        namespace="__default__",
                        query={
                            "inputs": {"text": query},
                            "top_k": top_k // 3  # Distribute top_k across queries
                        },
                        fields=["*"]
                    )
                    
                    # Parse results
                    query_results_count = 0
                    if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                        for hit in results.result.hits:
                            candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                            if candidate_id and candidate_id not in seen_ids:
                                all_candidates.append(hit.fields)
                                seen_ids.add(candidate_id)
                                query_results_count += 1
                    
                    logger.info(f"✅ Query {i} returned {query_results_count} new results (total unique: {len(all_candidates)})")
                                
                except Exception as e:
                    logger.error(f"Query failed: {query}, error: {str(e)}")
                    raise
            
            # Add additional broad searches if we don't have enough results
            if len(all_candidates) < 50:
                logger.info(f"Only found {len(all_candidates)} results, adding broader searches...")
                
                # Specialty-based searches removed - using only LLM-generated queries
            
            logger.info(f"LangChain retrieval found {len(all_candidates)} specialist information records using {len(queries)} queries")
            return all_candidates
            
        except Exception as e:
            logger.error(f"Error in LangChain retrieval: {str(e)}")
            raise
    

