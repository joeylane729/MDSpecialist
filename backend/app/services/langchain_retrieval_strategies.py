"""
LangChain Retrieval Strategies
"""

import logging
from typing import List, Dict, Any
from langchain_openai import OpenAI
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
        
        self.llm = OpenAI(temperature=0.1)
        
        self.query_prompt = PromptTemplate(
            input_variables=["patient_profile"],
            template="""
            Generate 3 optimal search queries for finding medical specialists.
            
            Patient Profile:
            - Symptoms: {symptoms}
            - Specialties needed: {specialties}
            - Urgency: {urgency}
            
            Create search queries that will find relevant medical specialists.
            Return 3 queries, one per line.
            """
        )
        
        self.query_chain = LLMChain(llm=self.llm, prompt=self.query_prompt)
        logger.info("LangChainRetrievalStrategies initialized successfully")
    
    async def retrieve_specialists(
        self,
        patient_profile: PatientProfile,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve specialists using LangChain-generated queries."""
        try:
            # Generate intelligent search queries
            query_input = {
                "symptoms": ", ".join(patient_profile.symptoms),
                "specialties": ", ".join(patient_profile.specialties_needed),
                "urgency": patient_profile.urgency_level
            }
            
            queries_response = await self.query_chain.arun(**query_input)
            queries = [q.strip() for q in queries_response.split('\n') if q.strip()]
            
            # If LLM fails, use fallback
            if not queries:
                queries = [f"{' '.join(patient_profile.symptoms)} {' '.join(patient_profile.specialties_needed)}"]
            
            # Search with each query and combine results
            all_candidates = []
            seen_ids = set()
            
            for query in queries[:3]:  # Use up to 3 queries
                try:
                    results = self.index.search(
                        namespace="__default__",
                        query={
                            "inputs": {"text": query},
                            "top_k": top_k // 3  # Divide top_k among queries
                        },
                        fields=["*"]
                    )
                    
                    # Parse results
                    if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                        for hit in results.result.hits:
                            candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                            if candidate_id and candidate_id not in seen_ids:
                                all_candidates.append(hit.fields)
                                seen_ids.add(candidate_id)
                                
                except Exception as e:
                    logger.warning(f"Query failed: {query}, error: {str(e)}")
                    continue
            
            logger.info(f"LangChain retrieval found {len(all_candidates)} candidates using {len(queries)} queries")
            return all_candidates
            
        except Exception as e:
            logger.error(f"Error in LangChain retrieval: {str(e)}")
            return self._fallback_retrieval(patient_profile, top_k)
    
    def _fallback_retrieval(
        self,
        patient_profile: PatientProfile,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Fallback simple retrieval if LangChain fails."""
        try:
            # Simple search query
            search_query = " ".join(patient_profile.symptoms + patient_profile.specialties_needed)
            
            results = self.index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": search_query},
                    "top_k": top_k
                },
                fields=["*"]
            )
            
            candidates = []
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                for hit in results.result.hits:
                    candidates.append(hit.fields)
            
            logger.info(f"Fallback retrieval found {len(candidates)} candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Fallback retrieval failed: {str(e)}")
            return []
