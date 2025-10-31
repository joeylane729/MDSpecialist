#!/usr/bin/env python3
"""
Create comprehensive PubMed table in AWS Aurora with all XML columns
"""

import os
import psycopg2
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def create_pubmed_table():
    """Create comprehensive PubMed table with all possible columns."""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Error: DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        print("🔗 Connecting to AWS Aurora database...")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Create the comprehensive table
        print("📋 Creating comprehensive PubMed table...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS pubmed_articles_1177 (
            -- Primary identification
            id SERIAL PRIMARY KEY,
            pmid VARCHAR(20) UNIQUE NOT NULL,
            
            -- Core article content
            title TEXT NOT NULL,
            abstract TEXT,
            abstract_purpose TEXT,
            abstract_methods TEXT,
            abstract_results TEXT,
            abstract_conclusion TEXT,
            abstract_background TEXT,
            abstract_objective TEXT,
            abstract_design TEXT,
            abstract_setting TEXT,
            abstract_participants TEXT,
            abstract_interventions TEXT,
            abstract_outcome_measures TEXT,
            abstract_results_detailed TEXT,
            abstract_conclusions TEXT,
            abstract_trial_registration TEXT,
            
            -- Journal information
            journal_title VARCHAR(500),
            journal_iso_abbreviation VARCHAR(100),
            issn VARCHAR(20),
            issn_linking VARCHAR(20),
            volume VARCHAR(20),
            issue VARCHAR(20),
            medline_pgn VARCHAR(100),
            
            -- Publication dates
            pub_year INTEGER,
            pub_month INTEGER,
            pub_day INTEGER,
            pub_season VARCHAR(20),
            medline_date VARCHAR(100),
            date_completed_year INTEGER,
            date_completed_month INTEGER,
            date_completed_day INTEGER,
            date_revised_year INTEGER,
            date_revised_month INTEGER,
            date_revised_day INTEGER,
            
            -- Publication metadata
            pub_model VARCHAR(50),
            publication_status VARCHAR(50),
            language VARCHAR(10),
            country VARCHAR(100),
            medline_ta VARCHAR(100),
            nlm_unique_id VARCHAR(20),
            citation_subset VARCHAR(100),
            
            -- Author information
            authors TEXT,
            author_affiliations TEXT,
            author_orcids TEXT,
            first_author_lastname VARCHAR(200),
            first_author_forename VARCHAR(200),
            first_author_initials VARCHAR(20),
            last_author_lastname VARCHAR(200),
            last_author_forename VARCHAR(200),
            last_author_initials VARCHAR(20),
            collective_name VARCHAR(500),
            
            -- Medical classification
            mesh_terms TEXT,
            mesh_qualifiers TEXT,
            major_mesh_terms TEXT,
            chemicals TEXT,
            chemical_registry_numbers TEXT,
            publication_types TEXT,
            publication_type_uis TEXT,
            
            -- Identifiers and references
            doi VARCHAR(200),
            pii VARCHAR(200),
            pmc VARCHAR(50),
            other_ids TEXT,
            grant_numbers TEXT,
            grant_agencies TEXT,
            
            -- Comments and corrections
            comments_corrections TEXT,
            ref_sources TEXT,
            
            -- Additional metadata
            vernacular_title TEXT,
            copyright_information TEXT,
            coi_statement TEXT,
            investigator_list TEXT,
            databank_list TEXT,
            accession_numbers TEXT,
            
            -- Processing metadata
            medline_citation_status VARCHAR(50),
            indexing_method VARCHAR(50),
            owner VARCHAR(50),
            article_id_list TEXT,
            history_entrez_year INTEGER,
            history_entrez_month INTEGER,
            history_entrez_day INTEGER,
            history_entrez_hour INTEGER,
            history_entrez_minute INTEGER,
            
            -- Search and embedding
            embedding_text TEXT NOT NULL,
            search_keywords TEXT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create comprehensive indexes
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_pmid ON pubmed_articles_1177(pmid);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_pub_year ON pubmed_articles_1177(pub_year);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_journal ON pubmed_articles_1177(journal_title);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_language ON pubmed_articles_1177(language);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_country ON pubmed_articles_1177(country);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_first_author ON pubmed_articles_1177(first_author_lastname);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_doi ON pubmed_articles_1177(doi);
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_issn ON pubmed_articles_1177(issn);
        
        -- Full-text search indexes
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_title_search ON pubmed_articles_1177 USING GIN(to_tsvector('english', title));
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_abstract_search ON pubmed_articles_1177 USING GIN(to_tsvector('english', abstract));
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_embedding_search ON pubmed_articles_1177 USING GIN(to_tsvector('english', embedding_text));
        CREATE INDEX IF NOT EXISTS idx_pubmed_1177_mesh_search ON pubmed_articles_1177 USING GIN(to_tsvector('english', mesh_terms));
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        
        print("✅ Comprehensive PubMed table 'pubmed_articles_1177' created successfully!")
        
        # Verify table structure
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'pubmed_articles_1177'
                ORDER BY ordinal_position
            """))
            
            print(f"\n📊 Table structure ({result.rowcount} columns):")
            print("Column Name                    | Data Type | Nullable | Default")
            print("-" * 80)
            for row in result:
                col_name = row[0][:30].ljust(30)
                data_type = row[1][:10].ljust(10)
                nullable = row[2][:8].ljust(8)
                default = (row[3] or 'None')[:20]
                print(f"{col_name} | {data_type} | {nullable} | {default}")
        
        return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Creating Comprehensive PubMed Table")
    print("=" * 60)
    
    success = create_pubmed_table()
    
    if success:
        print("\n🎉 Table creation completed successfully!")
        print("📋 Ready to upload PubMed data from pubmed25n1177.xml")
    else:
        print("\n💥 Table creation failed!")
        exit(1)

