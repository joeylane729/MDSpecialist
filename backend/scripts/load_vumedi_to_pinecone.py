"""
Load Vumedi content data into Pinecone vector database.

This script reads the vumedi_content_consolidated.csv file and uploads
the content to Pinecone for semantic search capabilities.
"""

import os
import sys
import csv
import uuid
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(backend_dir)

from app.services.pinecone_service import PineconeService


def process_vumedi_data(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Process the Vumedi CSV data and prepare it for Pinecone upload.
    
    Args:
        csv_file_path: Path to the vumedi_content_consolidated.csv file
        
    Returns:
        List of dictionaries ready for Pinecone upsert
    """
    records = []
    
    print(f"📖 Reading data from {csv_file_path}...")
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row_num, row in enumerate(reader, 1):
            # Create the text content for embedding
            # Combine title, author, featuring, and specialty for rich search
            text_parts = []
            
            # Add title (main content)
            if row.get('title'):
                text_parts.append(f"Title: {row['title']}")
            
            # Add author information
            if row.get('author'):
                text_parts.append(f"Author: {row['author']}")
            
            # Add featuring doctor
            if row.get('featuring'):
                text_parts.append(f"Featuring: {row['featuring']}")
            
            # Add specialty
            if row.get('specialty'):
                text_parts.append(f"Specialty: {row['specialty']}")
            
            # Combine all text for embedding
            chunk_text = " | ".join(text_parts)
            
            # Skip if no meaningful content
            if not chunk_text.strip() or chunk_text.strip() == "Title: ":
                print(f"⚠️  Skipping row {row_num}: No meaningful content")
                continue
            
            # Create unique ID for this record
            record_id = str(uuid.uuid4())
            
            # Prepare metadata (everything except the text that gets embedded)
            metadata = {
                "title": row.get('title', '').strip(),
                "author": row.get('author', '').strip(),
                "date": row.get('date', '').strip(),
                "views": row.get('views', '').strip(),
                "duration": row.get('duration', '').strip(),
                "link": row.get('link', '').strip(),
                "thumbnail": row.get('thumbnail', '').strip(),
                "featuring": row.get('featuring', '').strip(),
                "specialty": row.get('specialty', '').strip(),
                "scraped_at": row.get('scraped_at', '').strip(),
                "source": "vumedi",
                "content_type": "medical_video"
            }
            
            # Create the record for Pinecone
            record = {
                "id": record_id,
                "text": chunk_text,
                "metadata": metadata
            }
            
            records.append(record)
            
            # Progress indicator
            if row_num % 1000 == 0:
                print(f"   Processed {row_num} rows...")
    
    print(f"✅ Processed {len(records)} valid records from {row_num} total rows")
    return records


def upload_to_pinecone(pinecone_service: PineconeService, records: List[Dict[str, Any]], batch_size: int = 96, retry_failed: bool = False):
    """
    Upload records to Pinecone in batches with retry capability.
    
    Args:
        pinecone_service: Initialized PineconeService
        records: List of prepared records
        batch_size: Number of records to upload per batch
        retry_failed: Whether to retry failed batches from previous runs
    """
    print(f"🚀 Starting upload to Pinecone...")
    
    # Get the index
    index = pinecone_service.pc.Index(pinecone_service.default_index_name)
    
    total_records = len(records)
    successful_uploads = 0
    failed_uploads = 0
    failed_batches = []  # Track failed batches for retry
    
    # Process in batches
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_records + batch_size - 1) // batch_size
        
        print(f"📦 Uploading batch {batch_num}/{total_batches} ({len(batch)} records)...")
        
        try:
            # Prepare batch for Pinecone with integrated embeddings using upsert_records
            # Format according to the documentation: _id, chunk_text, and other metadata
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
            
            # Store failed batch info for retry
            failed_batches.append({
                "batch_num": batch_num,
                "start_idx": i,
                "end_idx": i + len(batch),
                "records": batch,
                "error": error_message
            })
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
    
    return failed_batches


def main():
    """Main function to load Vumedi data into Pinecone."""
    print("🏥 Loading Vumedi Content to Pinecone")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Define file path
    csv_file_path = os.path.join(
        os.path.dirname(__file__), 
        "..", "..", 
        "data", "vumedi-scraping", "vumedi_content_consolidated.csv"
    )
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Error: CSV file not found at {csv_file_path}")
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
        
        # Process the CSV data
        print("\n2. Processing Vumedi data...")
        records = process_vumedi_data(csv_file_path)
        
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
        print("🎉 Vumedi data loading completed successfully!")
        print("Your Pinecone index now contains medical video content for semantic search.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Check your configuration and try again")


if __name__ == "__main__":
    main()
