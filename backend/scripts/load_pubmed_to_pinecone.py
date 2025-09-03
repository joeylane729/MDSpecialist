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
        True for all articles (no filtering)
    """
    # Load all articles - no filtering
    return True


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
        
        # Prepare metadata (handle None values safely)
        metadata = {
            "pmid": pmid,
            "title": title.strip() if title else "",
            "journal_title": journal_title.strip() if journal_title else "",
            "journal_abbreviation": journal_abbrev.strip() if journal_abbrev else "",
            "abstract": abstract.strip() if abstract else "",
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
        # Only log errors for debugging, not every single one
        if "NoneType" not in str(e):  # Skip common NoneType errors
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
        
        print(f"✅ Processed {len(records)} valid articles from {article_count} total articles")
        print(f"   📊 Articles to be loaded: {medical_articles}")
        print(f"   📊 Articles with missing data: {article_count - len(records)}")
        print(f"   📊 Success rate: {(len(records)/article_count)*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Error processing XML file: {e}")
        return []
    
    return records


def upload_to_pinecone(pinecone_service: PineconeService, records: List[Dict[str, Any]], batch_size: int = 96, index_name: str = "pubmed"):
    """
    Upload PubMed records to Pinecone in batches with real-time monitoring.
    
    Args:
        pinecone_service: Initialized PineconeService
        records: List of prepared records
        batch_size: Number of records to upload per batch
        index_name: Name of the index to upload to
    """
    print(f"🚀 Starting upload to Pinecone index: {index_name}")
    
    # Get the index
    index = pinecone_service.pc.Index(index_name)
    
    total_records = len(records)
    successful_uploads = 0
    failed_uploads = 0
    
    # Get initial stats
    print("\n📊 Initial Index Stats:")
    initial_stats = pinecone_service.get_index_info()
    if initial_stats["status"] == "found":
        initial_vectors = initial_stats["stats"].get("total_vector_count", 0)
        print(f"   📈 Starting vector count: {initial_vectors:,}")
    
    # Process in batches
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_records + batch_size - 1) // batch_size
        
        print(f"\n📦 Uploading batch {batch_num}/{total_batches} ({len(batch)} records)...")
        
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
            
            # Show progress and current stats every few batches
            if batch_num % 5 == 0 or batch_num == total_batches:
                try:
                    current_stats = pinecone_service.get_index_info()
                    if current_stats["status"] == "found":
                        current_vectors = current_stats["stats"].get("total_vector_count", 0)
                        vectors_added = current_vectors - initial_vectors
                        print(f"   📊 Progress: {vectors_added:,} vectors added so far")
                        print(f"   📊 Current total: {current_vectors:,} vectors")
                        
                        # Show storage info if available
                        if "dimension" in current_stats["stats"]:
                            dimension = current_stats["stats"]["dimension"]
                            print(f"   📏 Vector dimension: {dimension}")
                        
                        # Show index size if available
                        if "index_size" in current_stats["stats"]:
                            index_size = current_stats["stats"]["index_size"]
                            print(f"   💾 Index size: {index_size}")
                        
                except Exception as e:
                    print(f"   ⚠️  Could not fetch current stats: {e}")
            
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
    
    # Show final stats
    print(f"\n📊 Final Index Stats:")
    try:
        final_stats = pinecone_service.get_index_info()
        if final_stats["status"] == "found":
            final_vectors = final_stats["stats"].get("total_vector_count", 0)
            total_added = final_vectors - initial_vectors
            print(f"   📈 Final vector count: {final_vectors:,}")
            print(f"   📈 Vectors added this session: {total_added:,}")
            
            # Show additional stats if available
            if "dimension" in final_stats["stats"]:
                dimension = final_stats["stats"]["dimension"]
                print(f"   📏 Vector dimension: {dimension}")
            
            if "index_size" in final_stats["stats"]:
                index_size = final_stats["stats"]["index_size"]
                print(f"   💾 Final index size: {index_size}")
                
    except Exception as e:
        print(f"   ⚠️  Could not fetch final stats: {e}")


def main():
    """Main function to load PubMed data into Pinecone."""
    print("🏥 Loading PubMed Research Articles to Pinecone")
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
        
        # Create or use pubmed index
        pubmed_index_name = "pubmed"
        print(f"   📁 Using index: {pubmed_index_name}")
        
        # Check if pubmed index exists, create if it doesn't
        index_info = pinecone_service.get_index_info(pubmed_index_name)
        if index_info["status"] != "found":
            print(f"   🔨 Creating new index: {pubmed_index_name}")
            create_result = pinecone_service.create_index(pubmed_index_name)
            if create_result["status"] not in ["created", "exists"]:
                print(f"   ❌ Failed to create index: {create_result['message']}")
                return
            print(f"   ✅ Index ready: {pubmed_index_name}")
        else:
            print(f"   ✅ Using existing index: {pubmed_index_name}")
        
        # Show initial index details
        print(f"   📊 Initial index stats:")
        if "stats" in index_info:
            stats = index_info["stats"]
            if "total_vector_count" in stats:
                print(f"      📈 Current vectors: {stats['total_vector_count']:,}")
            if "dimension" in stats:
                print(f"      📏 Vector dimension: {stats['dimension']}")
            if "index_size" in stats:
                print(f"      💾 Current size: {stats['index_size']}")
        else:
            print(f"      📈 New index - no vectors yet")
        
        # Process the XML data
        print("\n2. Processing PubMed data...")
        # You can limit the number of articles for testing by setting max_articles
        records = process_pubmed_data(xml_file_path, max_articles=None)
        
        if not records:
            print("   ❌ No valid records to upload")
            return
        
        # Upload to Pinecone
        print(f"\n3. Uploading {len(records)} records to Pinecone...")
        upload_to_pinecone(pinecone_service, records, index_name=pubmed_index_name)
        
        # Verify upload
        print("\n4. Verifying upload...")
        final_stats = pinecone_service.get_index_info(pubmed_index_name)
        if final_stats["status"] == "found":
            vector_count = final_stats["stats"].get("total_vector_count", 0)
            print(f"   ✅ Index now contains {vector_count} vectors")
        
        print("\n" + "=" * 50)
        print("🎉 PubMed data loading completed successfully!")
        print("Your Pinecone index now contains research articles for semantic search.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check your configuration and try again")


if __name__ == "__main__":
    main()
