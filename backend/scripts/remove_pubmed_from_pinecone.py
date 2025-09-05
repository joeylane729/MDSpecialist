"""
Remove PubMed articles from Pinecone index.

This script deletes all PubMed articles that were added to the index.
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(backend_dir)

from app.services.pinecone_service import PineconeService


def remove_pubmed_articles():
    """Remove all PubMed articles from the Pinecone index."""
    print("🗑️  Removing PubMed Articles from Pinecone")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    try:
        # Initialize Pinecone service
        print("1. Initializing Pinecone service...")
        pinecone_service = PineconeService()
        print("   ✅ Pinecone service initialized")
        
        # Get the index
        index_name = pinecone_service.default_index_name
        print(f"   📁 Using index: {index_name}")
        
        # Check index exists
        index_info = pinecone_service.get_index_info()
        if index_info["status"] != "found":
            print(f"   ❌ Index not found: {index_info['message']}")
            return
        
        # Get initial stats
        initial_vectors = index_info["stats"].get("total_vector_count", 0)
        print(f"   📊 Current vectors in index: {initial_vectors:,}")
        
        # Get the index
        index = pinecone_service.pc.Index(index_name)
        
        # Delete PubMed articles by metadata filter
        print("\n2. Removing PubMed articles...")
        print("   🔍 Looking for articles with source='pubmed'...")
        
        # Delete all vectors with source='pubmed'
        delete_response = index.delete(
            filter={"source": "pubmed"}
        )
        
        print("   ✅ Delete request sent to Pinecone")
        
        # Wait a moment for deletion to process
        import time
        print("   ⏳ Waiting for deletion to complete...")
        time.sleep(5)
        
        # Get final stats
        print("\n3. Verifying deletion...")
        final_stats = pinecone_service.get_index_info()
        if final_stats["status"] == "found":
            final_vectors = final_stats["stats"].get("total_vector_count", 0)
            vectors_removed = initial_vectors - final_vectors
            print(f"   📊 Final vector count: {final_vectors:,}")
            print(f"   📊 Vectors removed: {vectors_removed:,}")
            
            if vectors_removed > 0:
                print(f"   ✅ Successfully removed {vectors_removed:,} PubMed articles")
            else:
                print(f"   ℹ️  No PubMed articles were found to remove")
        
        print("\n" + "=" * 50)
        print("🎉 PubMed article removal completed!")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check your configuration and try again")


if __name__ == "__main__":
    remove_pubmed_articles()
