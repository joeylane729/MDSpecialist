#!/usr/bin/env python3
"""
Load PubMed XML files into PostgreSQL database.

This script processes multiple PubMed XML files and loads the article data
into a PostgreSQL table for querying.
"""

import os
import sys
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _parse_month(month_text: str) -> Optional[int]:
    """
    Parse month text to integer, handling both numeric and text formats.
    
    Args:
        month_text: Month as string (e.g., "01", "1", "Jan", "January", "Oct")
        
    Returns:
        Integer month (1-12) or None if invalid
    """
    if not month_text:
        return None
    
    month_text = month_text.strip()
    
    # Try to parse as integer first
    try:
        month_num = int(month_text)
        if 1 <= month_num <= 12:
            return month_num
    except ValueError:
        pass
    
    # Handle text month names
    month_mapping = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }
    
    return month_mapping.get(month_text.lower())

def create_pubmed_table():
    """Create the pubmed_articles table if it doesn't exist."""
    try:
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Create engine and session
        engine = create_engine(database_url)
        
        # Create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS pubmed_articles (
            id SERIAL PRIMARY KEY,
            pmid VARCHAR(20) UNIQUE NOT NULL,
            title TEXT,
            abstract TEXT,
            journal_title VARCHAR(500),
            journal_abbreviation VARCHAR(100),
            authors JSONB,
            keywords JSONB,
            mesh_terms JSONB,
            publication_year INTEGER,
            publication_month INTEGER,
            publication_day INTEGER,
            doi VARCHAR(200),
            language VARCHAR(10),
            source VARCHAR(50) DEFAULT 'pubmed',
            content_type VARCHAR(50) DEFAULT 'medical_research',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_pmid ON pubmed_articles(pmid);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_journal ON pubmed_articles(journal_title);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_year ON pubmed_articles(publication_year);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_language ON pubmed_articles(language);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_authors ON pubmed_articles USING GIN(authors);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_keywords ON pubmed_articles USING GIN(keywords);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_mesh ON pubmed_articles USING GIN(mesh_terms);
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_title_search ON pubmed_articles USING GIN(to_tsvector('english', title));
        CREATE INDEX IF NOT EXISTS idx_pubmed_articles_abstract_search ON pubmed_articles USING GIN(to_tsvector('english', abstract));
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        
        logger.info("✅ Created pubmed_articles table with indexes")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating table: {e}")
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
        
        # Extract publication date with fallback hierarchy
        year = month = day = None
        
        # 1. Try JournalIssue/PubDate (primary - actual publication date)
        journal_pub_date = article.find('.//JournalIssue/PubDate')
        if journal_pub_date is not None:
            year_elem = journal_pub_date.find('Year')
            month_elem = journal_pub_date.find('Month')
            day_elem = journal_pub_date.find('Day')
            year = int(year_elem.text) if year_elem is not None and year_elem.text else None
            month = _parse_month(month_elem.text) if month_elem is not None and month_elem.text else None
            day = int(day_elem.text) if day_elem is not None and day_elem.text else None
        
        # 2. Fallback to PubMedPubDate with PubStatus="pubmed" (when added to PubMed)
        if year is None or month is None:
            pubmed_date = article.find('.//PubMedPubDate[@PubStatus="pubmed"]')
            if pubmed_date is not None:
                year_elem = pubmed_date.find('Year')
                month_elem = pubmed_date.find('Month')
                day_elem = pubmed_date.find('Day')
                if year is None:
                    year = int(year_elem.text) if year_elem is not None and year_elem.text else None
                if month is None:
                    month = _parse_month(month_elem.text) if month_elem is not None and month_elem.text else None
                if day is None:
                    day = int(day_elem.text) if day_elem is not None and day_elem.text else None
        
        # 3. Last resort: DateCompleted (administrative date)
        if year is None or month is None:
            date_completed = article.find('.//DateCompleted')
            if date_completed is not None:
                year_elem = date_completed.find('Year')
                month_elem = date_completed.find('Month')
                day_elem = date_completed.find('Day')
                if year is None:
                    year = int(year_elem.text) if year_elem is not None and year_elem.text else None
                if month is None:
                    month = _parse_month(month_elem.text) if month_elem is not None and month_elem.text else None
                if day is None:
                    day = int(day_elem.text) if day_elem is not None and day_elem.text else None
        
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
        
        # Extract language
        language = ""
        language_elem = article.find('.//Language')
        if language_elem is not None:
            language = language_elem.text
        
        # Skip if no meaningful content
        if not title.strip() or len(title.strip()) < 10:
            return None
        
        return {
            "pmid": pmid,
            "title": title.strip(),
            "abstract": abstract.strip(),
            "journal_title": journal_title.strip(),
            "journal_abbreviation": journal_abbrev.strip(),
            "authors": authors,
            "keywords": keywords,
            "mesh_terms": mesh_terms,
            "publication_year": year,
            "publication_month": month,
            "publication_day": day,
            "doi": doi.strip(),
            "language": language.strip()
        }
        
    except Exception as e:
        logger.warning(f"⚠️  Error extracting article data: {e}")
        return None

def process_pubmed_file(xml_file_path: str) -> List[Dict[str, Any]]:
    """
    Process a single PubMed XML file and extract article data.
    
    Args:
        xml_file_path: Path to the PubMed XML file
        
    Returns:
        List of article dictionaries
    """
    articles = []
    
    try:
        logger.info(f"📖 Processing {xml_file_path}...")
        
        # Parse XML incrementally
        context = ET.iterparse(xml_file_path, events=('start', 'end'))
        
        for event, elem in context:
            if event == 'end' and elem.tag == 'PubmedArticle':
                # Extract article data
                article_data = extract_article_data(elem)
                if article_data:
                    articles.append(article_data)
                
                # Clear element to free memory
                elem.clear()
        
        logger.info(f"✅ Extracted {len(articles)} articles from {xml_file_path}")
        return articles
        
    except Exception as e:
        logger.error(f"❌ Error processing {xml_file_path}: {e}")
        return []

def load_articles_to_database(articles: List[Dict[str, Any]], batch_size: int = 1000):
    """
    Load articles into the PostgreSQL database.
    
    Args:
        articles: List of article dictionaries
        batch_size: Number of articles to insert in each batch
    """
    try:
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Create engine and session
        engine = create_engine(database_url)
        
        # Insert articles in batches
        total_articles = len(articles)
        inserted_count = 0
        skipped_count = 0
        
        logger.info(f"📊 Loading {total_articles} articles into database...")
        
        for i in range(0, total_articles, batch_size):
            batch = articles[i:i + batch_size]
            batch_inserted = 0
            batch_skipped = 0
            
            with engine.connect() as conn:
                for article in batch:
                    try:
                        # Prepare the insert statement
                        insert_sql = """
                        INSERT INTO pubmed_articles (
                            pmid, title, abstract, journal_title, journal_abbreviation,
                            authors, keywords, mesh_terms, publication_year, publication_month,
                            publication_day, doi, language
                        ) VALUES (
                            :pmid, :title, :abstract, :journal_title, :journal_abbreviation,
                            :authors, :keywords, :mesh_terms, :publication_year, :publication_month,
                            :publication_day, :doi, :language
                        )
                        ON CONFLICT (pmid) DO UPDATE SET
                            title = EXCLUDED.title,
                            abstract = EXCLUDED.abstract,
                            journal_title = EXCLUDED.journal_title,
                            journal_abbreviation = EXCLUDED.journal_abbreviation,
                            authors = EXCLUDED.authors,
                            keywords = EXCLUDED.keywords,
                            mesh_terms = EXCLUDED.mesh_terms,
                            publication_year = EXCLUDED.publication_year,
                            publication_month = EXCLUDED.publication_month,
                            publication_day = EXCLUDED.publication_day,
                            doi = EXCLUDED.doi,
                            language = EXCLUDED.language,
                            updated_at = CURRENT_TIMESTAMP
                        """
                        
                        conn.execute(text(insert_sql), {
                            'pmid': article['pmid'],
                            'title': article['title'],
                            'abstract': article['abstract'],
                            'journal_title': article['journal_title'],
                            'journal_abbreviation': article['journal_abbreviation'],
                            'authors': json.dumps(article['authors']),
                            'keywords': json.dumps(article['keywords']),
                            'mesh_terms': json.dumps(article['mesh_terms']),
                            'publication_year': article['publication_year'],
                            'publication_month': article['publication_month'],
                            'publication_day': article['publication_day'],
                            'doi': article['doi'],
                            'language': article['language']
                        })
                        
                        batch_inserted += 1
                        
                    except Exception as e:
                        logger.warning(f"⚠️  Error inserting article {article.get('pmid', 'unknown')}: {e}")
                        batch_skipped += 1
                        continue
                
                conn.commit()
            
            inserted_count += batch_inserted
            skipped_count += batch_skipped
            
            logger.info(f"📊 Batch {i//batch_size + 1}: Inserted {batch_inserted}, Skipped {batch_skipped}")
        
        logger.info(f"✅ Database loading completed:")
        logger.info(f"   📊 Total articles processed: {total_articles}")
        logger.info(f"   ✅ Successfully inserted: {inserted_count}")
        logger.info(f"   ⚠️  Skipped (duplicates/errors): {skipped_count}")
        
    except Exception as e:
        logger.error(f"❌ Error loading articles to database: {e}")
        raise

def main():
    """Main function to process all PubMed XML files and load them into PostgreSQL."""
    try:
        # Get the data directory path
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        data_dir = project_root / "data" / "pubmed"
        
        if not data_dir.exists():
            logger.error(f"❌ Data directory not found: {data_dir}")
            return
        
        # Create the database table
        logger.info("🏗️  Creating database table...")
        if not create_pubmed_table():
            logger.error("❌ Failed to create database table")
            return
        
        # Find all XML files
        xml_files = list(data_dir.glob("*.xml"))
        if not xml_files:
            logger.error(f"❌ No XML files found in {data_dir}")
            return
        
        logger.info(f"📁 Found {len(xml_files)} XML files to process")
        
        # Process all files
        all_articles = []
        for xml_file in sorted(xml_files):
            articles = process_pubmed_file(str(xml_file))
            all_articles.extend(articles)
        
        logger.info(f"📊 Total articles extracted: {len(all_articles)}")
        
        if all_articles:
            # Load into database
            load_articles_to_database(all_articles)
        else:
            logger.warning("⚠️  No articles to load")
        
        logger.info("🎉 PubMed data loading completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
