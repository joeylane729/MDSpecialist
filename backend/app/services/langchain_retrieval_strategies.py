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
            input_variables=["patient_profile"],
            template="""
            Generate 5 diverse and comprehensive search queries for finding medical specialists.
            
            Patient Profile:
            - Symptoms: {symptoms}
            - Specialties needed: {specialties}
            - Urgency: {urgency}
            
            Create diverse search queries that will find relevant medical specialists:
            1. One focused on the specific condition/symptoms
            2. One focused on the medical specialty
            3. One focused on treatment approaches
            4. One focused on related conditions
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
            query_input = {
                "symptoms": ", ".join(patient_profile.get("symptoms", [])),
                "specialties": ", ".join(patient_profile.get("specialties_needed", [])),
                "urgency": patient_profile.get("urgency_level", "medium")
            }
            
            queries_response = await self.query_chain.arun(**query_input)
            queries = [q.strip() for q in queries_response.split('\n') if q.strip()]
            
            # Ensure we have queries
            if not queries:
                raise ValueError("Failed to generate search queries from LLM")
            
            # Search with each query and combine results
            all_candidates = []
            seen_ids = set()
            
            for query in queries[:5]:  # Use up to 5 queries
                try:
                    results = self.index.search(
                        namespace="__default__",
                        query={
                            "inputs": {"text": query},
                            "top_k": top_k // 3  # Distribute top_k across queries
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
                    logger.error(f"Query failed: {query}, error: {str(e)}")
                    raise
            
            # Add additional broad searches if we don't have enough results
            if len(all_candidates) < 50:
                logger.info(f"Only found {len(all_candidates)} results, adding broader searches...")
                
                # Add broader searches based on specialty
                specialty = patient_profile.get("specialties_needed", [])
                if specialty:
                    for spec in specialty[:2]:  # Try top 2 specialties
                        try:
                            broad_results = self.index.search(
                                namespace="__default__",
                                query={
                                    "inputs": {"text": f"{spec} specialist medical education"},
                                    "top_k": 50
                                },
                                fields=["*"]
                            )
                            
                            if hasattr(broad_results, 'result') and hasattr(broad_results.result, 'hits'):
                                for hit in broad_results.result.hits:
                                    candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                                    if candidate_id and candidate_id not in seen_ids:
                                        all_candidates.append(hit.fields)
                                        seen_ids.add(candidate_id)
                                        
                        except Exception as e:
                            logger.error(f"Broad search failed for {spec}: {str(e)}")
            
            logger.info(f"LangChain retrieval found {len(all_candidates)} specialist information records using {len(queries)} queries")
            return all_candidates
            
        except Exception as e:
            logger.error(f"Error in LangChain retrieval: {str(e)}")
            raise
    

