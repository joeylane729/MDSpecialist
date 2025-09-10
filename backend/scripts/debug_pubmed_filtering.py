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

class PubMedFilterDebugger:
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "pubmed"
        
        # Allowed publication types (same as in the main script)
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
        
        # Statistics
        self.stats = {
            'total_articles': 0,
            'filtered_by_pub_type': 0,
            'filtered_by_language': 0,
            'filtered_by_year': 0,
            'filtered_by_abstract': 0,
            'filtered_by_title': 0,
            'passed_all_filters': 0
        }
        
        # Sample filtered articles for inspection
        self.filtered_samples = {
            'pub_type': [],
            'language': [],
            'year': [],
            'abstract': [],
            'title': []
        }
        
        # Count publication types for analysis
        self.pub_type_counts = {}

    def extract_article_data(self, article_element) -> Optional[Dict[str, Any]]:
        """Extract data from a single article element."""
        try:
            # Extract PMID
            pmid_elem = article_element.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            if not pmid:
                return None

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
            
            # Extract journal title
            journal_elem = article_element.find('.//Journal/Title')
            journal_title = journal_elem.text if journal_elem is not None else None
            
            # Extract publication year
            pub_year_elem = article_element.find('.//PubDate/Year')
            pub_year = pub_year_elem.text if pub_year_elem is not None else None
            
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
            language_elem = article_element.find('.//Language')
            language = language_elem.text if language_elem is not None else None
            
            # Extract ISSN
            issn_elem = article_element.find('.//Journal/ISSN')
            issn = issn_elem.text if issn_elem is not None else None
            
            # Extract author affiliations
            author_affiliations = []
            affiliation_elements = article_element.findall('.//Author/AffiliationInfo/Affiliation')
            for affil_elem in affiliation_elements:
                if affil_elem.text:
                    author_affiliations.append(affil_elem.text)
            
            # Extract author ORCIDs
            author_orcids = []
            orcid_elements = article_element.findall('.//Author/Identifier[@Source="ORCID"]')
            for orcid_elem in orcid_elements:
                if orcid_elem.text:
                    author_orcids.append(orcid_elem.text)

            return {
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'journal_title': journal_title,
                'pub_year': pub_year,
                'authors': authors,
                'mesh_terms': mesh_terms,
                'pub_types': pub_types,
                'language': language,
                'issn': issn,
                'author_affiliations': author_affiliations,
                'author_orcids': author_orcids
            }
            
        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None

    def analyze_article(self, article_data: Dict[str, Any]) -> str:
        """Analyze why an article was filtered out."""
        reasons = []
        
        # Check publication types
        if not any(pub_type in self.allowed_pub_types for pub_type in article_data['pub_types']):
            reasons.append('pub_type')
            if len(self.filtered_samples['pub_type']) < 10:
                self.filtered_samples['pub_type'].append({
                    'pmid': article_data['pmid'],
                    'pub_types': article_data['pub_types'],
                    'title': article_data['title'][:100] + '...' if article_data['title'] and len(article_data['title']) > 100 else article_data['title']
                })
            
            # Count publication types
            for pub_type in article_data['pub_types']:
                self.pub_type_counts[pub_type] = self.pub_type_counts.get(pub_type, 0) + 1
        
        # Check language
        if article_data['language'] and article_data['language'].lower() not in ['eng', 'english']:
            reasons.append('language')
            if len(self.filtered_samples['language']) < 5:
                self.filtered_samples['language'].append({
                    'pmid': article_data['pmid'],
                    'language': article_data['language'],
                    'title': article_data['title'][:100] + '...' if article_data['title'] and len(article_data['title']) > 100 else article_data['title']
                })
        
        # Check publication year
        try:
            pub_year_int = int(article_data['pub_year']) if article_data['pub_year'] else 0
            if pub_year_int < 2005:
                reasons.append('year')
                if len(self.filtered_samples['year']) < 5:
                    self.filtered_samples['year'].append({
                        'pmid': article_data['pmid'],
                        'pub_year': article_data['pub_year'],
                        'title': article_data['title'][:100] + '...' if article_data['title'] and len(article_data['title']) > 100 else article_data['title']
                    })
        except (ValueError, TypeError):
            reasons.append('year')
            if len(self.filtered_samples['year']) < 5:
                self.filtered_samples['year'].append({
                    'pmid': article_data['pmid'],
                    'pub_year': article_data['pub_year'],
                    'title': article_data['title'][:100] + '...' if article_data['title'] and len(article_data['title']) > 100 else article_data['title']
                })
        
        # Check abstract
        if not article_data['abstract'] or len(article_data['abstract'].strip()) < 50:
            reasons.append('abstract')
            if len(self.filtered_samples['abstract']) < 5:
                self.filtered_samples['abstract'].append({
                    'pmid': article_data['pmid'],
                    'abstract_length': len(article_data['abstract']) if article_data['abstract'] else 0,
                    'title': article_data['title'][:100] + '...' if article_data['title'] and len(article_data['title']) > 100 else article_data['title']
                })
        
        # Check title
        if not article_data['title'] or len(article_data['title'].strip()) < 10:
            reasons.append('title')
            if len(self.filtered_samples['title']) < 5:
                self.filtered_samples['title'].append({
                    'pmid': article_data['pmid'],
                    'title': article_data['title'],
                    'title_length': len(article_data['title']) if article_data['title'] else 0
                })
        
        return reasons

    def process_xml_file(self, xml_file: Path) -> List[Dict[str, Any]]:
        """Process a single XML file and analyze filtering."""
        logger.info(f"Processing {xml_file.name}...")
        
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            articles = []
            article_elements = root.findall('.//PubmedArticle')
            
            logger.info(f"Found {len(article_elements)} articles in {xml_file.name}")
            
            for article_element in article_elements:
                self.stats['total_articles'] += 1
                
                article_data = self.extract_article_data(article_element)
                if not article_data:
                    continue
                
                # Analyze why this article might be filtered
                filter_reasons = self.analyze_article(article_data)
                
                if not filter_reasons:
                    self.stats['passed_all_filters'] += 1
                    articles.append(article_data)
                else:
                    # Count each filter reason
                    for reason in filter_reasons:
                        self.stats[f'filtered_by_{reason}'] += 1
                
                # Log progress
                if self.stats['total_articles'] % 1000 == 0:
                    logger.info(f"Processed {self.stats['total_articles']} articles...")
            
            return articles
            
        except Exception as e:
            logger.error(f"Error processing {xml_file.name}: {e}")
            return []

    def run(self):
        """Run the debug analysis."""
        logger.info("Starting PubMed filtering debug analysis...")
        
        # Process the first file
        target_file = self.data_dir / "pubmed25n1200.xml"
        if target_file.exists():
            logger.info(f"Processing {target_file.name}")
            articles = self.process_xml_file(target_file)
            
            logger.info(f"Total articles processed: {self.stats['total_articles']}")
            logger.info(f"Articles that passed all filters: {self.stats['passed_all_filters']}")
            logger.info(f"Articles filtered by publication type: {self.stats['filtered_by_pub_type']}")
            logger.info(f"Articles filtered by language: {self.stats['filtered_by_language']}")
            logger.info(f"Articles filtered by year: {self.stats['filtered_by_year']}")
            logger.info(f"Articles filtered by abstract: {self.stats['filtered_by_abstract']}")
            logger.info(f"Articles filtered by title: {self.stats['filtered_by_title']}")
            
            # Show publication type counts
            print("\n" + "="*80)
            print("PUBLICATION TYPE COUNTS (FILTERED OUT)")
            print("="*80)
            sorted_pub_types = sorted(self.pub_type_counts.items(), key=lambda x: x[1], reverse=True)
            for pub_type, count in sorted_pub_types[:20]:  # Show top 20
                print(f"{pub_type}: {count}")
            
            # Show samples of filtered articles
            print("\n" + "="*80)
            print("SAMPLES OF FILTERED ARTICLES")
            print("="*80)
            
            for filter_type, samples in self.filtered_samples.items():
                if samples:
                    print(f"\n{filter_type.upper()} FILTER SAMPLES:")
                    print("-" * 40)
                    for sample in samples:
                        print(f"PMID: {sample['pmid']}")
                        if 'title' in sample:
                            print(f"Title: {sample['title']}")
                        if 'pub_types' in sample:
                            print(f"Pub Types: {sample['pub_types']}")
                        if 'language' in sample:
                            print(f"Language: {sample['language']}")
                        if 'pub_year' in sample:
                            print(f"Year: {sample['pub_year']}")
                        if 'abstract_length' in sample:
                            print(f"Abstract Length: {sample['abstract_length']}")
                        if 'title_length' in sample:
                            print(f"Title Length: {sample['title_length']}")
                        print()
        else:
            logger.error(f"Target file {target_file.name} not found!")

if __name__ == "__main__":
    debugger = PubMedFilterDebugger()
    debugger.run()
