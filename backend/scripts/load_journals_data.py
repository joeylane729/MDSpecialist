#!/usr/bin/env python3
"""
Script to load journal rankings CSV data into PostgreSQL database.
This script reads the journal-rankings.csv file and inserts the data into the journals table.
"""

import os
import sys
import pandas as pd
import logging
from sqlalchemy.exc import IntegrityError

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models.journals import Journal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('journals_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_numeric(value):
    """Parse numeric values, handling commas and empty strings."""
    if pd.isna(value) or value == '':
        return None
    try:
        # Remove commas and convert to float
        if isinstance(value, str):
            value = value.replace(',', '')
        return float(value)
    except (ValueError, TypeError):
        return None

def parse_boolean(value):
    """Parse boolean values from Yes/No strings."""
    if pd.isna(value) or value == '':
        return False
    return str(value).lower() == 'yes'

def parse_quartile(value):
    """Parse quartile values (Q1, Q2, Q3, Q4)."""
    if pd.isna(value) or value == '':
        return None
    value_str = str(value).strip()
    if value_str in ['Q1', 'Q2', 'Q3', 'Q4']:
        return value_str
    return None

def load_journals_data(csv_path, batch_size=1000):
    """
    Load journals data from CSV into PostgreSQL database.
    
    Args:
        csv_path (str): Path to the CSV file
        batch_size (int): Number of records to insert in each batch
    """
    logger.info(f"Starting journals data import from: {csv_path}")
    
    try:
        # Read CSV file with semicolon separator
        logger.info("Reading CSV file...")
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        logger.info(f"Loaded {len(df)} records from CSV")
        
        # Clean and prepare data
        logger.info("Cleaning and preparing data...")
        
        # Handle missing values
        df = df.fillna('')
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Process data in batches
            total_records = len(df)
            inserted_count = 0
            skipped_count = 0
            error_count = 0
            
            for i in range(0, total_records, batch_size):
                batch = df.iloc[i:i + batch_size]
                batch_records = []
                
                for _, row in batch.iterrows():
                    try:
                        # Create Journal object
                        journal_record = Journal(
                            source_id=str(row['Sourceid']),
                            title=row['Title'],
                            journal_type=row['Type'],
                            issn=row['Issn'],
                            publisher=row['Publisher'],
                            open_access=parse_boolean(row['Open Access']),
                            open_access_diamond=parse_boolean(row['Open Access Diamond']),
                            rank=parse_numeric(row['Rank']),
                            sjr_score=parse_numeric(row['SJR']),
                            sjr_quartile=parse_quartile(row['SJR Best Quartile']),
                            h_index=parse_numeric(row['H index']),
                            total_docs_2024=parse_numeric(row['Total Docs. (2024)']),
                            total_docs_3years=parse_numeric(row['Total Docs. (3years)']),
                            total_references=parse_numeric(row['Total Refs.']),
                            total_citations_3years=parse_numeric(row['Total Citations (3years)']),
                            citable_docs_3years=parse_numeric(row['Citable Docs. (3years)']),
                            citations_per_doc_2years=parse_numeric(row['Citations / Doc. (2years)']),
                            refs_per_doc=parse_numeric(row['Ref. / Doc.']),
                            female_percentage=parse_numeric(row['%Female']),
                            overton_score=parse_numeric(row['Overton']),
                            sdg_count=parse_numeric(row['SDG']),
                            country=row['Country'],
                            region=row['Region'],
                            coverage_period=row['Coverage'],
                            categories=row['Categories'],
                            areas=row['Areas']
                        )
                        
                        batch_records.append(journal_record)
                        
                    except Exception as e:
                        logger.error(f"Error processing row {i}: {e}")
                        error_count += 1
                        continue
                
                # Insert batch
                if batch_records:
                    try:
                        db.add_all(batch_records)
                        db.commit()
                        inserted_count += len(batch_records)
                        logger.info(f"Inserted batch {i//batch_size + 1}: {len(batch_records)} records")
                    except IntegrityError as e:
                        db.rollback()
                        logger.warning(f"Batch {i//batch_size + 1} had integrity errors, rolling back: {e}")
                        # Try inserting records one by one to identify problematic ones
                        for record in batch_records:
                            try:
                                db.add(record)
                                db.commit()
                                inserted_count += 1
                            except IntegrityError:
                                db.rollback()
                                skipped_count += 1
                                logger.warning(f"Skipped record due to integrity error: {record.title}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
                        error_count += len(batch_records)
            
            logger.info(f"Import completed!")
            logger.info(f"Total records processed: {total_records}")
            logger.info(f"Successfully inserted: {inserted_count}")
            logger.info(f"Skipped: {skipped_count}")
            logger.info(f"Errors: {error_count}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise

if __name__ == "__main__":
    # Path to the CSV file
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'journal-rankings.csv')
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found at: {csv_path}")
        sys.exit(1)
    
    # Load the data
    load_journals_data(csv_path)
