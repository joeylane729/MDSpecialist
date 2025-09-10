import os
import sys
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_original_filtering():
    """Test the original script's filtering logic on first 100 articles."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "pubmed"
    target_file = data_dir / "pubmed25n1200.xml"
    
    # Allowed publication types (same as in the main script)
    allowed_pub_types = {
        'Journal Article', 'Review', 'Case Reports', 'Clinical Trial', 
        'Randomized Controlled Trial', 'Meta-Analysis', 'Systematic Review',
        'Comparative Study', 'Evaluation Study', 'Validation Study',
        'Multicenter Study', 'Observational Study', 'Cohort Study',
        'Case-Control Study', 'Cross-Sectional Study', 'Longitudinal Study',
        'Prospective Study', 'Retrospective Study', 'Pilot Study',
        'Feasibility Study', 'Proof of Concept Study', 'Phase I Clinical Trial',
        'Phase II Clinical Trial', 'Phase III Clinical Trial', 'Phase IV Clinical Trial'
    }
    
    try:
        tree = ET.parse(target_file)
        root = tree.getroot()
        
        articles = []
        total_articles = 0
        filtered_articles = 0
        
        # Find first 100 PubmedArticle elements
        for i, article_element in enumerate(root.findall('.//PubmedArticle')):
            if i >= 100:  # Only process first 100
                break
                
            total_articles += 1
            
            try:
                # Extract PMID
                pmid_elem = article_element.find('.//PMID')
                pmid = pmid_elem.text if pmid_elem is not None else None
                
                if not pmid:
                    filtered_articles += 1
                    continue

                # Extract title
                title_elem = article_element.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else None
                
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
                
                # Extract publication year
                pub_year_elem = article_element.find('.//PubDate/Year')
                pub_year = pub_year_elem.text if pub_year_elem is not None else None
                
                # Extract publication types
                pub_types = []
                pub_type_list = article_element.find('.//PublicationTypeList')
                if pub_type_list is not None:
                    for pub_type in pub_type_list.findall('PublicationType'):
                        pub_types.append(pub_type.text)
                
                # Extract language
                language_element = article_element.find('.//Language')
                language = language_element.text if language_element is not None else "eng"
                
                # Apply filters (same as original script)
                if not any(pub_type in allowed_pub_types for pub_type in pub_types):
                    filtered_articles += 1
                    continue
                
                if language.lower() not in ['eng', 'english']:
                    filtered_articles += 1
                    continue
                
                try:
                    pub_year_int = int(pub_year) if pub_year else 0
                    if pub_year_int < 2005:
                        filtered_articles += 1
                        continue
                except (ValueError, TypeError):
                    filtered_articles += 1
                    continue
                
                # If we get here, article passed all filters
                articles.append({
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract,
                    'pub_types': pub_types,
                    'language': language,
                    'pub_year': pub_year
                })
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                filtered_articles += 1
                continue
        
        logger.info(f"Processed {total_articles} articles")
        logger.info(f"Filtered out {filtered_articles} articles")
        logger.info(f"Passed filters: {len(articles)} articles")
        
        # Show some examples
        for i, article in enumerate(articles[:5]):
            logger.info(f"Article {i+1}: PMID {article['pmid']}, Title: {article['title'][:50]}...")
        
        return len(articles)
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return 0

if __name__ == "__main__":
    passed_count = test_original_filtering()
    logger.info(f"Final result: {passed_count} articles passed filters out of 100 tested")
