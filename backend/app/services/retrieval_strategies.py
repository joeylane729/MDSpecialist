"""
Simple Retrieval Strategies
"""

import logging
from typing import List, Dict, Any
from ..models.specialist_recommendation import PatientProfile
from .pinecone_service import PineconeService

logger = logging.getLogger(__name__)

class RetrievalStrategies:
    """Simple retrieval strategies."""
    
    def __init__(self, pinecone_service: PineconeService):
        self.pinecone_service = pinecone_service
        self.index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
        logger.info("RetrievalStrategies initialized successfully")
    
    async def retrieve_specialists(
        self,
        patient_profile: PatientProfile,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """Simple specialist retrieval using vector search."""
        try:
            # Create simple search query from patient input
            search_query = " ".join(patient_profile.symptoms + patient_profile.specialties_needed)
            
            # Simple vector search
            results = self.index.search(
                namespace="__default__",
                query={
                    "inputs": {"text": search_query},
                    "top_k": top_k
                },
                fields=["*"]
            )
            
            # Parse results
            candidates = []
            if hasattr(results, 'result') and hasattr(results.result, 'hits'):
                for hit in results.result.hits:
                    candidates.append(hit.fields)
            
            logger.info(f"Vector similarity search found {len(candidates)} candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Error in retrieval: {str(e)}")
            return []