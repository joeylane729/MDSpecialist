import os
import sys
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging
import time
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pinecone_service import PineconeService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PubMedLoader:
    def __init__(self):
        """Initialize the PubMed loader with Pinecone service."""
        self.pinecone_service = PineconeService()
        
        # Get the pubmed-publications index
        self.index = self.pinecone_service.pc.Index("pubmed-publications")
        
        # Data directory
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "pubmed"
        
        # Define allowed publication types (only these will be processed)
        self.allowed_pub_types = {
            'Journal Article', 'Review', 'Case Reports', 'Clinical Trial', 
            'Randomized Controlled Trial', 'Meta-Analysis', 'Systematic Review',
            'Comparative Study', 'Evaluation Study', 'Validation Study',
            'Multicenter Study', 'Observational Study', 'Cohort Study',
            'Case-Control Study', 'Cross-Sectional Study', 'Longitudinal Study',
            'Prospective Study', 'Retrospective Study', 'Pilot Study',
            'Feasibility Study', 'Proof of Concept Study', 'Phase I Clinical Trial',
            'Phase II Clinical Trial', 'Phase III Clinical Trial', 'Phase IV Clinical Trial'
        }

    def extract_article_data(self, article_element) -> Optional[Dict[str, Any]]:
        """Extract relevant data from a PubMed article XML element."""
        try:
            # Extract PMID
            pmid_element = article_element.find('.//PMID')
            pmid = pmid_element.text if pmid_element is not None else f"no_pmid_{hash(str(article_element))}"
            
            # Extract article title
            title_element = article_element.find('.//ArticleTitle')
            title = title_element.text if title_element is not None else ""
            
            # Extract abstract
            abstract_parts = []
            abstract_elements = article_element.findall('.//AbstractText')
            for abstract_elem in abstract_elements:
                if abstract_elem.text:
                    label = abstract_elem.get('Label', '')
                    if label:
                        abstract_parts.append(f"{label}: {abstract_elem.text}")
                    else:
                        abstract_parts.append(abstract_elem.text)
            abstract = " ".join(abstract_parts)
            
            # Extract journal title
            journal_element = article_element.find('.//Journal/Title')
            journal_title = journal_element.text if journal_element is not None else ""
            
            # Extract publication year
            pub_year = None
            pub_date_element = article_element.find('.//PubDate')
            if pub_date_element is not None:
                year_element = pub_date_element.find('Year')
                if year_element is not None:
                    pub_year = year_element.text
            
            # Extract authors
            authors = []
            author_elements = article_element.findall('.//Author')
            for author_elem in author_elements:
                last_name = author_elem.find('LastName')
                first_name = author_elem.find('ForeName')
                if last_name is not None and first_name is not None:
                    authors.append(f"{first_name.text} {last_name.text}")
            
            # Extract MeSH terms
            mesh_terms = []
            mesh_elements = article_element.findall('.//MeshHeading/DescriptorName')
            for mesh_elem in mesh_elements:
                if mesh_elem.text:
                    mesh_terms.append(mesh_elem.text)
            
            # Extract publication types
            pub_types = []
            pub_type_elements = article_element.findall('.//PublicationType')
            for pub_type_elem in pub_type_elements:
                if pub_type_elem.text:
                    pub_types.append(pub_type_elem.text)
            
            # Extract language
            language_element = article_element.find('.//Language')
            language = language_element.text if language_element is not None else None
            
            # Extract ISSN
            issn_elem = article_element.find('.//Journal/ISSN')
            issn = issn_elem.text if issn_elem is not None else None
            
            # Extract author affiliations (set to empty to reduce metadata size)
            author_affiliations = []
            
            # Extract author ORCIDs
            author_orcids = []
            orcid_elements = article_element.findall('.//Author/Identifier[@Source="ORCID"]')
            for orcid_elem in orcid_elements:
                if orcid_elem.text:
                    author_orcids.append(orcid_elem.text)
            
            # Filter: Only process articles that have at least one allowed publication type
            if not any(pub_type in self.allowed_pub_types for pub_type in pub_types):
                return None
            
            # Filter: Only process English articles
            if language and language.lower() not in ['eng', 'english']:
                return None
            
            # Filter: Only process articles from 2005 onwards (but allow missing years)
            if pub_year:
                try:
                    pub_year_int = int(pub_year)
                    if pub_year_int < 2005:
                        return None
                except (ValueError, TypeError):
                    # If we can't parse the year, skip this article
                    return None
            
            # Create text for embedding (combine title, abstract, authors, and MeSH terms)
            embedding_text = f"{title}"
            if abstract:
                embedding_text += f" {abstract}"
            if authors:
                embedding_text += f" {' '.join(authors)}"
            if mesh_terms:
                embedding_text += f" {' '.join(mesh_terms)}"
            
            return {
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'journal_title': journal_title,
                'issn': issn,
                'pub_year': pub_year,
                'authors': authors,
                'author_affiliations': author_affiliations,
                'author_orcids': author_orcids,
                'mesh_terms': mesh_terms,
                'pub_types': pub_types,
                'language': language,
                'embedding_text': embedding_text
            }
            
        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None
    
    def process_xml_file(self, xml_file_path: Path) -> List[Dict[str, Any]]:
        """Process a single XML file and extract all articles."""
        logger.info(f"Processing file: {xml_file_path.name}")
        
        try:
            # Parse the XML file
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            articles = []
            total_articles = 0
            filtered_articles = 0
            
            # Find all PubmedArticle elements
            for article_element in root.findall('.//PubmedArticle'):
                total_articles += 1
                article_data = self.extract_article_data(article_element)
                if article_data:
                    articles.append(article_data)
                else:
                    filtered_articles += 1
            
            logger.info(f"Extracted {len(articles)} articles from {xml_file_path.name} "
                       f"(filtered out {filtered_articles} articles with disallowed publication types, non-English language, or pre-2005 publication year)")
            return articles
            
        except Exception as e:
            logger.error(f"Error processing file {xml_file_path.name}: {e}")
            return []
    
    def prepare_articles_for_pinecone(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare articles for Pinecone upload with integrated embeddings."""
        logger.info(f"Preparing {len(articles)} articles for Pinecone upload with integrated embeddings...")
        
        prepared_articles = []
        
        for i, article in enumerate(articles):
            try:
                # For integrated embeddings, we just need to format the data
                # The embedding will be generated automatically by Pinecone
                prepared_articles.append(article)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Prepared {i + 1}/{len(articles)} articles")
                    
            except Exception as e:
                logger.error(f"Error preparing article {article['pmid']}: {e}")
                continue
        
        logger.info(f"Successfully prepared {len(prepared_articles)} articles for upload")
        return prepared_articles
    
    def upload_to_pinecone(self, articles: List[Dict[str, Any]], batch_size: int = 96):
        """Upload articles to Pinecone using integrated embeddings with retry logic."""
        logger.info(f"Uploading {len(articles)} articles to Pinecone using integrated embeddings...")
        
        removed_articles = []  # Track articles that were removed due to metadata size limits
        total_batches = (len(articles) + batch_size - 1) // batch_size
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            # Prepare records for integrated embeddings
            records = []
            for article in batch:
                # Convert None values to empty strings for Pinecone compatibility
                record = {
                    '_id': article['pmid'],  # Use _id as specified in documentation
                    'text': article['embedding_text'],  # This will be used for embedding generation
                    'title': article['title'] or '',
                    'abstract': article['abstract'] or '',
                    'journal_title': article['journal_title'] or '',
                    'issn': article['issn'] or '',
                    'pub_year': article['pub_year'] or '',
                    'authors': '; '.join(article['authors']) if article['authors'] else '',
                    'author_affiliations': '; '.join(article['author_affiliations']) if article['author_affiliations'] else '',
                    'author_orcids': '; '.join(article['author_orcids']) if article['author_orcids'] else '',
                    'mesh_terms': '; '.join(article['mesh_terms']) if article['mesh_terms'] else '',
                    'pub_types': '; '.join(article['pub_types']) if article['pub_types'] else '',
                    'language': article['language'] or ''
                }
                records.append(record)
            
            # Try to upload with retry logic
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # Upload batch to Pinecone using integrated embeddings
                    self.index.upsert_records(
                        "__default__",
                        records
                    )
                    
                    logger.info(f"Uploaded batch {batch_num}/{total_batches} ({len(batch)} articles)")
                    success = True
                    
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's a rate limit error (429)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"Rate limit hit for batch {batch_num}, waiting 60 seconds before retry {retry_count}/{max_retries}")
                            time.sleep(60)  # Wait 60 seconds
                            continue
                        else:
                            logger.error(f"Rate limit error for batch {batch_num} after {max_retries} retries: {e}")
                            break
                    
                    # Check if it's a metadata size error (400)
                    elif "400" in error_str and "Metadata size" in error_str:
                        # Extract the index of the problematic record
                        match = re.search(r'found at index (\d+)', error_str)
                        if match:
                            problematic_index = int(match.group(1))
                            problematic_pmid = records[problematic_index]['_id']
                            
                            # Remove the problematic record
                            removed_articles.append({
                                'pmid': problematic_pmid,
                                'reason': 'Metadata size exceeds 40KB limit',
                                'batch': batch_num
                            })
                            
                            # Remove the problematic record and retry
                            records.pop(problematic_index)
                            logger.warning(f"Removed article {problematic_pmid} from batch {batch_num} due to metadata size limit")
                            
                            # If we still have records, retry
                            if records:
                                continue
                            else:
                                logger.error(f"All records in batch {batch_num} were too large, skipping batch")
                                break
                        else:
                            logger.error(f"Metadata size error for batch {batch_num} but couldn't parse index: {e}")
                            break
                    
                    # Other errors
                    else:
                        logger.error(f"Error uploading batch {batch_num}: {e}")
                        break
        
        # Log summary of removed articles
        if removed_articles:
            logger.info(f"\n=== REMOVED ARTICLES SUMMARY ===")
            logger.info(f"Total articles removed: {len(removed_articles)}")
            logger.info(f"Reason: Metadata size exceeds 40KB limit")
            logger.info(f"\nRemoved articles:")
            for article in removed_articles:
                logger.info(f"  - PMID: {article['pmid']} (Batch {article['batch']})")
        else:
            logger.info("No articles were removed due to metadata size limits")
        
        logger.info("Upload to Pinecone completed!")
    
    def run(self):
        """Main execution method."""
        logger.info("Starting PubMed data loading to Pinecone...")
        
        # Find XML files
        xml_files = list(self.data_dir.glob("*.xml"))
        logger.info(f"Found {len(xml_files)} XML files to process")
        
        # Process XML files one at a time to avoid memory accumulation
        total_files = len(xml_files)
        total_articles_processed = 0
        
        for i, xml_file in enumerate(xml_files, 1):
            logger.info(f"Processing file {i}/{total_files}: {xml_file.name}")
            articles = self.process_xml_file(xml_file)
            
            if articles:
                logger.info(f"Extracted {len(articles)} articles from {xml_file.name}")
                
                # Prepare articles for Pinecone
                articles_with_embeddings = self.prepare_articles_for_pinecone(articles)
                
                if articles_with_embeddings:
                    # Upload to Pinecone immediately
                    self.upload_to_pinecone(articles_with_embeddings)
                    total_articles_processed += len(articles_with_embeddings)
                    logger.info(f"Successfully uploaded {len(articles_with_embeddings)} articles from {xml_file.name}")
                else:
                    logger.error(f"No articles with embeddings generated from {xml_file.name}")
                
                # Clear memory
                del articles
                del articles_with_embeddings
            else:
                logger.warning(f"No articles extracted from {xml_file.name}")
        
        logger.info(f"PubMed data loading completed successfully! Total articles processed: {total_articles_processed}")

if __name__ == "__main__":
    loader = PubMedLoader()
    loader.run()
