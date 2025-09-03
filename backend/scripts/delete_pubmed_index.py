"""
Delete the broken pubmed index so we can recreate it properly.
"""

import os
import sys
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(backend_dir)

from app.services.pinecone_service import PineconeService


def delete_pubmed_index():
    """Delete the broken pubmed index."""
    print("🗑️  Deleting Broken PubMed Index")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    try:
        # Initialize Pinecone service
        print("1. Initializing Pinecone service...")
        pinecone_service = PineconeService()
        print("   ✅ Pinecone service initialized")
        
        # Delete the pubmed index
        index_name = "pubmed"
        print(f"   🗑️  Deleting index: {index_name}")
        
        try:
            pinecone_service.pc.delete_index(index_name)
            print(f"   ✅ Index '{index_name}' deleted successfully")
        except Exception as e:
            print(f"   ℹ️  Index '{index_name}' not found or already deleted: {e}")
        
        print("\n" + "=" * 40)
        print("🎉 PubMed index deletion completed!")
        print("You can now recreate the index with proper integrated embeddings.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check your configuration and try again")


if __name__ == "__main__":
    delete_pubmed_index()
