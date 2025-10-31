#!/usr/bin/env python3
"""
Fast PubMed upload with minimal parsing - 5-10 columns approach
"""

import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

class FastPubMedUploader:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        
        # Minimal parsing - just extract essential fields
        self.allowed_pub_types = {
            'Journal Article', 'Review', 'Case Reports', 'Clinical Trial', 
            'Randomized Controlled Trial', 'Meta-Analysis', 'Systematic Review',
            'Comparative Study', 'Evaluation Study', 'Validation Study',
            'Multicenter Study', 'Observational Study', 'Cohort Study',
            'Case-Control Study', 'Cross-Sectional Study', 'Longitudinal Study',
            'Prospective Study', 'Retrospective Study', 'Pilot Study',
            'Feasibility Study', 'Proof of Concept Study', 'Phase I Clinical Trial',
            'Phase II Clinical Trial', 'Phase III Clinical Trial', 'Phase IV Clinical Trial',
            'Letter', 'Comment', 'Editorial', 'News', 'Practice Guideline'
        }

    def create_fast_table(self):
        """Create a fast table with minimal columns."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS pubmed_fast (
            -- Primary identification
            id SERIAL PRIMARY KEY,
            pmid VARCHAR(20) UNIQUE NOT NULL,
            
            -- Essential parsed fields
            title TEXT NOT NULL,
            abstract TEXT,
            journal_title VARCHAR(500),
            pub_year INTEGER,
            language VARCHAR(10),
            
            -- Important identifiers
            doi VARCHAR(200),
            pmc VARCHAR(50),
            volume VARCHAR(20),
            issue VARCHAR(20),
            
            -- Raw XML sections (minimal parsing)
            authors_raw TEXT,           -- Raw AuthorList XML
            mesh_raw TEXT,              -- Raw MeshHeadingList XML  
            chemicals_raw TEXT,         -- Raw ChemicalList XML
            grants_raw TEXT,            -- Raw GrantList XML
            abstract_sections_raw TEXT, -- Raw Abstract XML
            
            -- Search optimization
            embedding_text TEXT NOT NULL,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Minimal indexes for speed
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_pmid ON pubmed_fast(pmid);
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_pub_year ON pubmed_fast(pub_year);
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_journal ON pubmed_fast(journal_title);
        
        -- Full-text search indexes
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_title_search ON pubmed_fast USING GIN(to_tsvector('english', title));
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_abstract_search ON pubmed_fast USING GIN(to_tsvector('english', abstract));
        CREATE INDEX IF NOT EXISTS idx_pubmed_fast_embedding_search ON pubmed_fast USING GIN(to_tsvector('english', embedding_text));
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        
        print("✅ Fast PubMed table created with 10 columns")

    def extract_minimal_data(self, article_element) -> Dict[str, Any]:
        """Extract minimal data with raw XML sections."""
        try:
            # Extract PMID
            pmid_element = article_element.find('.//PMID')
            pmid = pmid_element.text if pmid_element is not None else f"no_pmid_{hash(str(article_element))}"
            
            # Extract title
            title_element = article_element.find('.//ArticleTitle')
            title = title_element.text.strip() if title_element is not None and title_element.text else ""
            
            # Extract abstract (simple concatenation)
            abstract_element = article_element.find('.//Abstract')
            abstract = ""
            if abstract_element is not None:
                abstract_texts = abstract_element.findall('.//AbstractText')
                abstract_parts = []
                for abstract_text in abstract_texts:
                    if abstract_text.text:
                        abstract_parts.append(abstract_text.text.strip())
                abstract = " ".join(abstract_parts)
            
            # Extract journal
            journal_element = article_element.find('.//Journal/Title')
            journal_title = journal_element.text.strip() if journal_element is not None and journal_element.text else ""
            
            # Extract publication year
            pub_year = None
            year_element = article_element.find('.//PubDate/Year')
            if year_element is not None and year_element.text:
                try:
                    pub_year = int(year_element.text)
                except (ValueError, TypeError):
                    pass
            
            # Extract language
            language_element = article_element.find('.//Language')
            language = language_element.text.strip() if language_element is not None and language_element.text else ""
            
            # Extract important identifiers
            doi = ""
            pmc = ""
            volume = ""
            issue = ""
            
            # Extract DOI
            doi_element = article_element.find('.//ELocationID[@EIdType="doi"]')
            if doi_element is not None and doi_element.text:
                doi = doi_element.text.strip()
            
            # Extract PMC ID
            pmc_element = article_element.find('.//ArticleId[@IdType="pmc"]')
            if pmc_element is not None and pmc_element.text:
                pmc = pmc_element.text.strip()
            
            # Extract volume and issue
            volume_element = article_element.find('.//Volume')
            if volume_element is not None and volume_element.text:
                volume = volume_element.text.strip()
            
            issue_element = article_element.find('.//Issue')
            if issue_element is not None and issue_element.text:
                issue = issue_element.text.strip()
            
            # Extract raw XML sections (minimal parsing)
            authors_raw = self._extract_raw_xml_section(article_element, './/AuthorList')
            mesh_raw = self._extract_raw_xml_section(article_element, './/MeshHeadingList')
            chemicals_raw = self._extract_raw_xml_section(article_element, './/ChemicalList')
            grants_raw = self._extract_raw_xml_section(article_element, './/GrantList')
            abstract_sections_raw = self._extract_raw_xml_section(article_element, './/Abstract')
            
            # Check publication types
            pub_type_list = article_element.find('.//PublicationTypeList')
            publication_types = []
            if pub_type_list is not None:
                for pub_type in pub_type_list.findall('.//PublicationType'):
                    if pub_type.text:
                        publication_types.append(pub_type.text)
            
            # Filter: Only process articles that have at least one allowed publication type
            if not any(pub_type in self.allowed_pub_types for pub_type in publication_types):
                return None
            
            # Filter: Only process English articles
            if language and language.lower() not in ['eng', 'english']:
                return None
            
            # Filter: Only process articles from 2005 onwards
            if pub_year and pub_year < 2005:
                return None
            
            # Create embedding text (combine title, abstract, journal)
            embedding_parts = [title]
            if abstract:
                embedding_parts.append(abstract)
            if journal_title:
                embedding_parts.append(f"Journal: {journal_title}")
            
            embedding_text = " ".join(embedding_parts)
            
            return {
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'journal_title': journal_title,
                'pub_year': pub_year,
                'language': language,
                'doi': doi,
                'pmc': pmc,
                'volume': volume,
                'issue': issue,
                'authors_raw': authors_raw,
                'mesh_raw': mesh_raw,
                'chemicals_raw': chemicals_raw,
                'grants_raw': grants_raw,
                'abstract_sections_raw': abstract_sections_raw,
                'embedding_text': embedding_text
            }
            
        except Exception as e:
            print(f"Error extracting article data: {e}")
            return None

    def _extract_raw_xml_section(self, article_element, xpath: str) -> str:
        """Extract raw XML section as string."""
        section_element = article_element.find(xpath)
        if section_element is not None:
            # Convert element to string
            return ET.tostring(section_element, encoding='unicode')
        return ""

    def upload_fast(self, xml_file_path: str, batch_size: int = 5000):
        """Upload with minimal parsing for maximum speed."""
        print(f"🚀 Fast upload starting with batch size: {batch_size}")
        
        # Parse XML file
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Find all PubmedArticle elements
        pubmed_articles = root.findall('.//PubmedArticle')
        total_articles = len(pubmed_articles)
        
        print(f"📊 Found {total_articles} articles in XML file")
        
        articles = []
        processed_count = 0
        skipped_count = 0
        
        for i, article_element in enumerate(pubmed_articles):
            try:
                article_data = self.extract_minimal_data(article_element)
                
                if article_data:
                    articles.append(article_data)
                    processed_count += 1
                else:
                    skipped_count += 1
                
                # Progress indicator
                if (i + 1) % 1000 == 0:
                    print(f"Processed {i + 1}/{total_articles} articles ({processed_count} valid, {skipped_count} skipped)")
            
            except Exception as e:
                print(f"Error processing article {i + 1}: {e}")
                skipped_count += 1
                continue
        
        print(f"✅ Processing completed: {processed_count} valid articles, {skipped_count} skipped")
        
        # Upload in batches
        print(f"📤 Uploading {len(articles)} articles to database...")
        
        total_batches = (len(articles) + batch_size - 1) // batch_size
        successful_uploads = 0
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            try:
                with self.engine.connect() as conn:
                    # Simple insert with essential columns
                    insert_sql = """
                    INSERT INTO pubmed_fast (
                        pmid, title, abstract, journal_title, pub_year, language,
                        doi, pmc, volume, issue,
                        authors_raw, mesh_raw, chemicals_raw, grants_raw, abstract_sections_raw, embedding_text
                    ) VALUES (
                        :pmid, :title, :abstract, :journal_title, :pub_year, :language,
                        :doi, :pmc, :volume, :issue,
                        :authors_raw, :mesh_raw, :chemicals_raw, :grants_raw, :abstract_sections_raw, :embedding_text
                    )
                    ON CONFLICT (pmid) DO UPDATE SET
                        title = EXCLUDED.title,
                        abstract = EXCLUDED.abstract
                    """
                    
                    conn.execute(text(insert_sql), batch)
                    conn.commit()
                    
                    successful_uploads += len(batch)
                    print(f"✅ Batch {batch_num}/{total_batches}: Uploaded {len(batch)} articles (Total: {successful_uploads})")
                    
            except Exception as e:
                print(f"❌ Database error in batch {batch_num}: {e}")
                continue
        
        print(f"🎉 Upload completed! Successfully uploaded {successful_uploads} articles")
        return successful_uploads

def main():
    """Main function for fast PubMed upload."""
    print("⚡ Fast PubMed Upload - Minimal Parsing Approach")
    print("=" * 60)
    
    xml_file_path = "pubmed25n1177.xml"
    
    if not os.path.exists(xml_file_path):
        print(f"❌ Error: XML file not found at {xml_file_path}")
        return
    
    try:
        # Initialize uploader
        print("1. Initializing fast PubMed uploader...")
        uploader = FastPubMedUploader()
        
        # Create table
        print("2. Creating fast table...")
        uploader.create_fast_table()
        
        # Upload data
        print("3. Uploading data with minimal parsing...")
        successful_uploads = uploader.upload_fast(xml_file_path, batch_size=5000)
        
        # Verify upload
        print("4. Verifying upload...")
        with uploader.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pubmed_fast"))
            total_count = result.scalar()
            print(f"   ✅ Database now contains {total_count} articles")
        
        print("\n" + "=" * 60)
        print("🎉 Fast PubMed upload completed!")
        print(f"📊 Uploaded {successful_uploads} articles in ~10 columns")
        print("⚡ Much faster than 88-column approach!")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()
