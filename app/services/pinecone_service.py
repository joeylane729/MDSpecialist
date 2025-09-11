"""
Pinecone Service

Service for managing Pinecone vector database operations.
"""

import os
from typing import Optional, Dict, Any, List
from pinecone import Pinecone, ServerlessSpec


class PineconeService:
    """Service for Pinecone vector database operations."""
    
    def __init__(self):
        """Initialize Pinecone client."""
        self.api_key = os.getenv('PINECONE_API_KEY')
        if not self.api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        
        # Initialize Pinecone client
        self.pc = Pinecone(api_key=self.api_key)
        
        # Default index configuration
        self.default_index_name = "concierge-md-dev"
        self.pubmed_index_name = "pubmed-publications"
        self.default_cloud = "aws"
        self.default_region = "us-east-1"
        self.default_model = "llama-text-embed-v2"
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Pinecone connection and return status information.
        
        Returns:
            Dictionary with connection status and available indexes
        """
        try:
            # List existing indexes to test connection
            indexes = self.pc.list_indexes()
            
            return {
                "status": "success",
                "message": "Successfully connected to Pinecone",
                "indexes": [index.name for index in indexes],
                "total_indexes": len(indexes)
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to connect to Pinecone: {str(e)}",
                "indexes": [],
                "total_indexes": 0
            }
    
    def create_index(
        self, 
        index_name: Optional[str] = None,
        model: Optional[str] = None,
        cloud: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new Pinecone index with integrated embedding model.
        
        Args:
            index_name: Name of the index (defaults to default_index_name)
            model: Embedding model to use (defaults to default_model)
            cloud: Cloud provider (defaults to default_cloud)
            region: Cloud region (defaults to default_region)
            
        Returns:
            Dictionary with creation status
        """
        index_name = index_name or self.default_index_name
        model = model or self.default_model
        cloud = cloud or self.default_cloud
        region = region or self.default_region
        
        try:
            # Check if index already exists
            if self.pc.has_index(index_name):
                return {
                    "status": "exists",
                    "message": f"Index '{index_name}' already exists",
                    "index_name": index_name
                }
            
            # Create the index
            self.pc.create_index_for_model(
                name=index_name,
                cloud=cloud,
                region=region,
                embed={
                    "model": model,
                    "field_map": {"text": "chunk_text"}
                }
            )
            
            return {
                "status": "created",
                "message": f"Successfully created index '{index_name}'",
                "index_name": index_name,
                "model": model,
                "cloud": cloud,
                "region": region
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create index '{index_name}': {str(e)}",
                "index_name": index_name
            }
    
    def get_index_info(self, index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a specific index.
        
        Args:
            index_name: Name of the index (defaults to default_index_name)
            
        Returns:
            Dictionary with index information
        """
        index_name = index_name or self.default_index_name
        
        try:
            if not self.pc.has_index(index_name):
                return {
                    "status": "not_found",
                    "message": f"Index '{index_name}' not found",
                    "index_name": index_name
                }
            
            index = self.pc.Index(index_name)
            stats = index.describe_index_stats()
            
            return {
                "status": "found",
                "message": f"Index '{index_name}' found",
                "index_name": index_name,
                "stats": stats
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get info for index '{index_name}': {str(e)}",
                "index_name": index_name
            }
    
    def delete_index(self, index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a Pinecone index.
        
        Args:
            index_name: Name of the index to delete (defaults to default_index_name)
            
        Returns:
            Dictionary with deletion status
        """
        index_name = index_name or self.default_index_name
        
        try:
            if not self.pc.has_index(index_name):
                return {
                    "status": "not_found",
                    "message": f"Index '{index_name}' not found",
                    "index_name": index_name
                }
            
            self.pc.delete_index(index_name)
            
            return {
                "status": "deleted",
                "message": f"Successfully deleted index '{index_name}'",
                "index_name": index_name
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to delete index '{index_name}': {str(e)}",
                "index_name": index_name
            }
    
    def upsert_with_integrated_embeddings(
        self, 
        records: list, 
        index_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upsert records using integrated embeddings.
        
        Args:
            records: List of records with 'id', 'text', and 'metadata'
            index_name: Name of the index (defaults to default_index_name)
            
        Returns:
            Dictionary with upsert status
        """
        index_name = index_name or self.default_index_name
        
        try:
            if not self.pc.has_index(index_name):
                return {
                    "status": "error",
                    "message": f"Index '{index_name}' not found",
                    "index_name": index_name
                }
            
            index = self.pc.Index(index_name)
            
            # Format records for integrated embeddings
            vectors = []
            for record in records:
                # For integrated embeddings, the text goes in metadata["chunk_text"]
                vector = {
                    "id": record["id"],
                    "metadata": {
                        **record.get("metadata", {}),
                        "chunk_text": record["text"]
                    }
                }
                vectors.append(vector)
            
            # Upsert the vectors
            result = index.upsert(vectors=vectors)
            
            return {
                "status": "success",
                "message": f"Successfully upserted {len(vectors)} records",
                "index_name": index_name,
                "upserted_count": result.upserted_count if hasattr(result, 'upserted_count') else len(vectors)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to upsert to index '{index_name}': {str(e)}",
                "index_name": index_name
            }
