"""
Load PubMed sample data into Pinecone vector database.

This script reads the pubmed-sample-1256.xml file and uploads
medical research articles to Pinecone for semantic search capabilities.
"""

import os
import sys
import xml.etree.ElementTree as ET
import uuid
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(backend_dir)

from app.services.pinecone_service import PineconeService


def is_medical_article(article: ET.Element) -> bool:
    """
    Check if an article is medical/scientific in nature.
    
    Args:
        article: XML element containing article data
        
    Returns:
        True if medical/scientific, False otherwise
    """
    # Check publication types
    pub_types = article.findall('.//PublicationType')
    medical_types = {
        'Journal Article', 'Research Support', 'Clinical Trial', 'Case Reports',
        'Review', 'Meta-Analysis', 'Systematic Review', 'Practice Guideline',
        'Randomized Controlled Trial', 'Observational Study', 'Cohort Study'
    }
    
    for pub_type in pub_types:
        if pub_type.text in medical_types:
            return True
    
    # Check if it's from a medical journal (basic check)
    journal_title = article.find('.//Journal/Title')
    if journal_title is not None:
        journal_text = journal_title.text.lower()
        medical_keywords = ['medical', 'health', 'clinical', 'biomedical', 'pharmacology', 
                           'surgery', 'cardiology', 'oncology', 'neurology', 'psychiatry']
        if any(keyword in journal_text for keyword in medical_keywords):
            return True
    
    return False


def extract_article_data(article: ET.Element) -> Optional[Dict[str, Any]]:
    """
    Extract relevant data from a PubMed article XML element.
    
    Args:
        article: XML element containing article data
        
    Returns:
        Dictionary with extracted article data or None if invalid
    """
    try:
        # Extract PMID
        pmid_elem = article.find('.//PMID')
        if pmid_elem is None:
            return None
        pmid = pmid_elem.text
        
        # Extract title
        title_elem = article.find('.//ArticleTitle')
        title = title_elem.text if title_elem is not None else ""
        
        # Extract abstract
        abstract_elem = article.find('.//Abstract/AbstractText')
        abstract = abstract_elem.text if abstract_elem is not None else ""
        
        # Extract journal information
        journal_title_elem = article.find('.//Journal/Title')
        journal_title = journal_title_elem.text if journal_title_elem is not None else ""
        
        journal_abbrev_elem = article.find('.//Journal/ISOAbbreviation')
        journal_abbrev = journal_abbrev_elem.text if journal_abbrev_elem is not None else ""
        
        # Extract publication date
        pub_date = article.find('.//ArticleDate')
        year = month = day = ""
        if pub_date is not None:
            year_elem = pub_date.find('Year')
            month_elem = pub_date.find('Month')
            day_elem = pub_date.find('Day')
            year = year_elem.text if year_elem is not None else ""
            month = month_elem.text if month_elem is not None else ""
            day = day_elem.text if day_elem is not None else ""
        
        # Extract authors
        authors = []
        author_list = article.find('.//AuthorList')
        if author_list is not None:
            for author in author_list.findall('Author'):
                last_name_elem = author.find('LastName')
                fore_name_elem = author.find('ForeName')
                if last_name_elem is not None and fore_name_elem is not None:
                    authors.append(f"{fore_name_elem.text} {last_name_elem.text}")
        
        # Extract keywords
        keywords = []
        keyword_list = article.find('.//KeywordList')
        if keyword_list is not None:
            for keyword in keyword_list.findall('Keyword'):
                if keyword.text:
                    keywords.append(keyword.text)
        
        # Extract MeSH terms (if available)
        mesh_terms = []
        mesh_list = article.find('.//MeshHeadingList')
        if mesh_list is not None:
            for mesh in mesh_list.findall('.//DescriptorName'):
                if mesh.text:
                    mesh_terms.append(mesh.text)
        
        # Extract DOI
        doi = ""
        doi_elem = article.find('.//ELocationID[@EIdType="doi"]')
        if doi_elem is not None:
            doi = doi_elem.text
        
        # Create the text content for embedding
        text_parts = []
        if title:
            text_parts.append(f"Title: {title}")
        if abstract:
            text_parts.append(f"Abstract: {abstract}")
        if keywords:
            text_parts.append(f"Keywords: {', '.join(keywords)}")
        if mesh_terms:
            text_parts.append(f"MeSH Terms: {', '.join(mesh_terms)}")
        
        # Combine all text for embedding
        chunk_text = " | ".join(text_parts)
        
        # Skip if no meaningful content
        if not chunk_text.strip() or len(chunk_text.strip()) < 50:
            return None
        
        # Create unique ID for this record
        record_id = f"pubmed_{pmid}"
        
        # Prepare metadata
        metadata = {
            "pmid": pmid,
            "title": title.strip(),
            "journal_title": journal_title.strip(),
            "journal_abbreviation": journal_abbrev.strip(),
            "abstract": abstract.strip(),
            "authors": authors,
            "keywords": keywords,
            "mesh_terms": mesh_terms,
            "publication_year": year,
            "publication_month": month,
            "publication_day": day,
            "doi": doi,
            "source": "pubmed",
            "content_type": "medical_research"
        }
        
        return {
            "id": record_id,
            "text": chunk_text,
            "metadata": metadata
        }
        
    except Exception as e:
        print(f"⚠️  Error extracting article data: {e}")
        return None


def process_pubmed_data(xml_file_path: str, max_articles: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Process the PubMed XML data and prepare it for Pinecone upload.
    
    Args:
        xml_file_path: Path to the pubmed-sample-1256.xml file
        max_articles: Maximum number of articles to process (None for all)
        
    Returns:
        List of dictionaries ready for Pinecone upsert
    """
    records = []
    article_count = 0
    medical_articles = 0
    
    print(f"📖 Reading PubMed data from {xml_file_path}...")
    
    try:
        # Parse XML incrementally
        context = ET.iterparse(xml_file_path, events=('start', 'end'))
        
        for event, elem in context:
            if event == 'end' and elem.tag == 'PubmedArticle':
                article_count += 1
                
                # Check if it's a medical article
                if is_medical_article(elem):
                    medical_articles += 1
                    
                    # Extract article data
                    article_data = extract_article_data(elem)
                    if article_data:
                        records.append(article_data)
                    
                    # Progress indicator
                    if medical_articles % 100 == 0:
                        print(f"   Processed {medical_articles} medical articles...")
                
                # Limit processing if max_articles is specified
                if max_articles and medical_articles >= max_articles:
                    print(f"   Reached limit of {max_articles} medical articles")
                    break
                
                # Clear element to free memory
                elem.clear()
                
                # Also clear parent elements to free more memory
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
        
        print(f"✅ Processed {len(records)} valid medical articles from {article_count} total articles")
        print(f"   📊 Medical articles: {medical_articles}")
        print(f"   📊 Non-medical articles: {article_count - medical_articles}")
        
    except Exception as e:
        print(f"❌ Error processing XML file: {e}")
        return []
    
    return records


def upload_to_pinecone(pinecone_service: PineconeService, records: List[Dict[str, Any]], batch_size: int = 96):
    """
    Upload PubMed records to Pinecone in batches.
    
    Args:
        pinecone_service: Initialized PineconeService
        records: List of prepared records
        batch_size: Number of records to upload per batch
    """
    print(f"🚀 Starting upload to Pinecone...")
    
    # Get the index
    index = pinecone_service.pc.Index(pinecone_service.default_index_name)
    
    total_records = len(records)
    successful_uploads = 0
    failed_uploads = 0
    
    # Process in batches
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_records + batch_size - 1) // batch_size
        
        print(f"📦 Uploading batch {batch_num}/{total_batches} ({len(batch)} records)...")
        
        try:
            # Prepare batch for Pinecone
            records_batch = []
            for record in batch:
                pinecone_record = {
                    "_id": record["id"],
                    "chunk_text": record["text"],  # This gets auto-embedded by Pinecone
                    **record["metadata"]  # All other metadata fields
                }
                records_batch.append(pinecone_record)
            
            # Upload batch using upsert_records for integrated embeddings
            index.upsert_records("__default__", records_batch)
            successful_uploads += len(batch)
            print(f"   ✅ Batch {batch_num} uploaded successfully")
            
        except Exception as e:
            error_message = str(e)
            print(f"   ❌ Batch {batch_num} failed: {error_message}")
            failed_uploads += len(batch)
            
            # If it's a rate limit error, add a small delay
            if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
                print(f"   ⏳ Rate limited - continuing with next batch...")
                import time
                time.sleep(1)  # Brief pause
    
    print(f"\n📊 Upload Summary:")
    print(f"   ✅ Successful: {successful_uploads} records")
    print(f"   ❌ Failed: {failed_uploads} records")
    print(f"   📈 Success Rate: {(successful_uploads/total_records)*100:.1f}%")


def main():
    """Main function to load PubMed data into Pinecone."""
    print("🏥 Loading PubMed Medical Research to Pinecone")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
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
        # Initialize Pinecone service
        print("1. Initializing Pinecone service...")
        pinecone_service = PineconeService()
        print("   ✅ Pinecone service initialized")
        
        # Check index exists
        index_info = pinecone_service.get_index_info()
        if index_info["status"] != "found":
            print(f"   ❌ Index not found: {index_info['message']}")
            return
        
        print(f"   📁 Using index: {index_info['index_name']}")
        
        # Process the XML data
        print("\n2. Processing PubMed data...")
        # You can limit the number of articles for testing by setting max_articles
        records = process_pubmed_data(xml_file_path, max_articles=None)
        
        if not records:
            print("   ❌ No valid records to upload")
            return
        
        # Upload to Pinecone
        print(f"\n3. Uploading {len(records)} records to Pinecone...")
        upload_to_pinecone(pinecone_service, records)
        
        # Verify upload
        print("\n4. Verifying upload...")
        final_stats = pinecone_service.get_index_info()
        if final_stats["status"] == "found":
            vector_count = final_stats["stats"].get("total_vector_count", 0)
            print(f"   ✅ Index now contains {vector_count} vectors")
        
        print("\n" + "=" * 50)
        print("🎉 PubMed data loading completed successfully!")
        print("Your Pinecone index now contains medical research articles for semantic search.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check your configuration and try again")


if __name__ == "__main__":
    main()
