#!/usr/bin/env python3
"""
Script to load Vumedi CSV data into PostgreSQL database.
This script reads the vumedi_content.csv file and inserts the data into the vumedi_content table.
"""

import os
import sys
import pandas as pd
from datetime import datetime
import logging

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models.vumedi_content import VumediContent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vumedi_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_views(views_str):
    """Parse views string to extract numeric value."""
    if pd.isna(views_str) or views_str == '':
        return None
    try:
        # Remove "views" text and commas, then convert to int
        views_clean = str(views_str).replace(' views', '').replace(',', '')
        return int(views_clean)
    except (ValueError, AttributeError):
        return None

def parse_date(date_str):
    """Parse date string to datetime object."""
    if pd.isna(date_str) or date_str == '':
        return None
    try:
        # Handle various date formats
        if isinstance(date_str, str):
            # Try common formats
            for fmt in ['%B %d, %Y', '%B %d %Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        return None
    except Exception:
        return None

def load_vumedi_data(csv_path, batch_size=1000):
    """
    Load Vumedi data from CSV into PostgreSQL database.
    
    Args:
        csv_path (str): Path to the CSV file
        batch_size (int): Number of records to insert in each batch
    """
    logger.info(f"Starting Vumedi data import from: {csv_path}")
    
    try:
        # Read CSV file
        logger.info("Reading CSV file...")
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} records from CSV")
        
        # Clean and prepare data
        logger.info("Cleaning and preparing data...")
        
        # Handle missing values
        df = df.fillna('')
        
        # Parse dates
        df['scraped_at'] = pd.to_datetime(df['scraped_at'], errors='coerce')
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Process data in batches
            total_records = len(df)
            inserted_count = 0
            skipped_count = 0
            
            for i in range(0, total_records, batch_size):
                batch = df.iloc[i:i + batch_size]
                batch_records = []
                
                for _, row in batch.iterrows():
                    try:
                        # Create VumediContent object
                        vumedi_record = VumediContent(
                            title=row['title'],
                            author=row['author'],
                            date=row['date'],
                            views=row['views'],
                            duration=row['duration'],
                            link=row['link'],
                            thumbnail=row['thumbnail'],
                            featuring=row['featuring'],
                            specialty=row['specialty'],
                            specialty_url=row['specialty_url'],
                            page_number=row['page_number'] if pd.notna(row['page_number']) else None,
                            source=row['source'],
                            scraped_at=row['scraped_at'] if pd.notna(row['scraped_at']) else None
                        )
                        batch_records.append(vumedi_record)
                        
                    except Exception as e:
                        logger.warning(f"Error processing row {i}: {e}")
                        skipped_count += 1
                        continue
                
                # Insert batch
                if batch_records:
                    try:
                        # Insert batch with duplicate handling
                        for record in batch_records:
                            try:
                                db.add(record)
                                db.commit()
                                inserted_count += 1
                            except Exception as e:
                                if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                                    # Skip duplicates on title+specialty
                                    skipped_count += 1
                                    db.rollback()
                                else:
                                    # Other error, log and skip
                                    logger.warning(f"Error inserting record: {e}")
                                    skipped_count += 1
                                    db.rollback()
                        logger.info(f"Processed batch {i//batch_size + 1}: {len(batch_records)} records")
                    except Exception as e:
                        logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                        skipped_count += len(batch_records)
                
                # Progress update
                progress = min((i + batch_size) / total_records * 100, 100)
                logger.info(f"Progress: {progress:.1f}% ({inserted_count}/{total_records} records inserted)")
            
            logger.info(f"Import completed successfully!")
            logger.info(f"Total records processed: {total_records}")
            logger.info(f"Records inserted: {inserted_count}")
            logger.info(f"Records skipped: {skipped_count}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise

def main():
    """Main function to run the import."""
    # Path to the CSV file
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data', 'vumedi-scraping', 'vumedi_content.csv'
    )
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    
    try:
        # Load the data
        load_vumedi_data(csv_path)
        logger.info("Vumedi data import completed successfully!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
