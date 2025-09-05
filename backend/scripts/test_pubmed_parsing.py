"""
Test script to verify PubMed XML parsing works correctly.

This script tests the parsing logic without uploading to Pinecone.
"""

import os
import sys
import xml.etree.ElementTree as ET

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(backend_dir)

from load_pubmed_to_pinecone import is_medical_article, extract_article_data


def test_pubmed_parsing():
    """Test PubMed XML parsing with a small sample."""
    print("🧪 Testing PubMed XML Parsing")
    print("=" * 40)
    
    # Define file path
    xml_file_path = os.path.join(
        os.path.dirname(__file__), 
        "..", "..", 
        "data", "pubmed-sample-1256.xml"
    )
    
    if not os.path.exists(xml_file_path):
        print(f"❌ Error: XML file not found at {xml_file_path}")
        return
    
    try:
        # Parse first few articles
        context = ET.iterparse(xml_file_path, events=('start', 'end'))
        
        article_count = 0
        medical_articles = 0
        test_records = []
        
        print("📖 Parsing first 10 articles for testing...")
        
        for event, elem in context:
            if event == 'end' and elem.tag == 'PubmedArticle':
                article_count += 1
                
                # Check if it's a medical article (now always True)
                is_medical = is_medical_article(elem)
                if is_medical:
                    medical_articles += 1
                
                # Extract article data for first few articles
                if article_count <= 5:
                    article_data = extract_article_data(elem)
                    if article_data:
                        test_records.append(article_data)
                        print(f"\n📄 Article {article_count}:")
                        print(f"   PMID: {article_data['metadata']['pmid']}")
                        print(f"   Title: {article_data['metadata']['title'][:100]}...")
                        print(f"   Journal: {article_data['metadata']['journal_title']}")
                        print(f"   Medical: {'✅' if is_medical else '❌'}")
                        print(f"   Text length: {len(article_data['text'])} chars")
                
                # Stop after 10 articles
                if article_count >= 10:
                    break
                
                # Clear element to free memory
                elem.clear()
        
        print(f"\n📊 Test Results:")
        print(f"   Total articles processed: {article_count}")
        print(f"   Articles to be loaded: {medical_articles}")
        print(f"   Successfully parsed: {len(test_records)}")
        
        if test_records:
            print(f"\n✅ Parsing test successful! Ready to load to Pinecone.")
        else:
            print(f"\n❌ Parsing test failed. Check the XML structure.")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pubmed_parsing()
