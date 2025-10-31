#!/usr/bin/env python3
"""
Upload PubMed data from pubmed25n1177.xml to AWS Aurora
"""

import os
import sys
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PubMedUploader:
    def __init__(self):
        """Initialize the PubMed uploader."""
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        
        # Define allowed publication types (only these will be processed)
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
        
        # Month mapping
        self.month_mapping = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

    def _parse_month(self, month_text: str) -> Optional[int]:
        """Parse month text to integer."""
        if not month_text:
            return None
        return self.month_mapping.get(month_text.lower())

    def _safe_text(self, element) -> str:
        """Safely extract text from XML element."""
        if element is not None and element.text:
            return element.text.strip()
        return ""

    def _safe_join(self, elements, delimiter="; ") -> str:
        """Safely join multiple elements with delimiter."""
        texts = []
        for elem in elements:
            if elem is not None and elem.text:
                texts.append(elem.text.strip())
        return delimiter.join(texts)

    def _extract_abstract_sections(self, abstract_element) -> Dict[str, str]:
        """Extract different sections of abstract."""
        sections = {}
        if abstract_element is not None:
            for abstract_text in abstract_element.findall('.//AbstractText'):
                label = abstract_text.get('Label', '').lower()
                text = self._safe_text(abstract_text)
                if text:
                    sections[f"abstract_{label}"] = text
        return sections

    def _extract_authors(self, author_list_element) -> Dict[str, Any]:
        """Extract author information."""
        authors_data = {
            'authors': [],
            'author_affiliations': [],
            'author_orcids': [],
            'first_author_lastname': '',
            'first_author_forename': '',
            'first_author_initials': '',
            'last_author_lastname': '',
            'last_author_forename': '',
            'last_author_initials': '',
            'collective_name': ''
        }
        
        if author_list_element is None:
            return authors_data
        
        authors = author_list_element.findall('.//Author')
        if not authors:
            return authors_data
        
        for i, author in enumerate(authors):
            lastname = self._safe_text(author.find('LastName'))
            forename = self._safe_text(author.find('ForeName'))
            initials = self._safe_text(author.find('Initials'))
            collective = self._safe_text(author.find('CollectiveName'))
            
            if collective:
                authors_data['collective_name'] = collective
            elif lastname and forename:
                author_name = f"{forename} {lastname}"
                authors_data['authors'].append(author_name)
                
                # First author
                if i == 0:
                    authors_data['first_author_lastname'] = lastname
                    authors_data['first_author_forename'] = forename
                    authors_data['first_author_initials'] = initials
                
                # Last author
                if i == len(authors) - 1:
                    authors_data['last_author_lastname'] = lastname
                    authors_data['last_author_forename'] = forename
                    authors_data['last_author_initials'] = initials
            
            # Extract affiliations
            affiliation_info = author.find('AffiliationInfo')
            if affiliation_info is not None:
                affiliation = self._safe_text(affiliation_info.find('Affiliation'))
                if affiliation:
                    authors_data['author_affiliations'].append(affiliation)
            
            # Extract ORCIDs
            identifier = author.find('Identifier[@Source="ORCID"]')
            if identifier is not None:
                orcid = self._safe_text(identifier)
                if orcid:
                    authors_data['author_orcids'].append(orcid)
        
        # Convert lists to semicolon-delimited strings
        authors_data['authors'] = "; ".join(authors_data['authors'])
        authors_data['author_affiliations'] = "; ".join(authors_data['author_affiliations'])
        authors_data['author_orcids'] = "; ".join(authors_data['author_orcids'])
        
        return authors_data

    def _extract_mesh_terms(self, mesh_heading_list) -> Dict[str, str]:
        """Extract MeSH terms and qualifiers."""
        mesh_data = {
            'mesh_terms': [],
            'mesh_qualifiers': [],
            'major_mesh_terms': []
        }
        
        if mesh_heading_list is None:
            return mesh_data
        
        for mesh_heading in mesh_heading_list.findall('.//MeshHeading'):
            descriptor = mesh_heading.find('DescriptorName')
            if descriptor is not None:
                term = self._safe_text(descriptor)
                is_major = descriptor.get('MajorTopicYN', 'N') == 'Y'
                
                if term:
                    mesh_data['mesh_terms'].append(term)
                    if is_major:
                        mesh_data['major_mesh_terms'].append(term)
            
            # Extract qualifiers
            for qualifier in mesh_heading.findall('.//QualifierName'):
                qual_text = self._safe_text(qualifier)
                if qual_text:
                    mesh_data['mesh_qualifiers'].append(qual_text)
        
        # Convert to semicolon-delimited strings
        mesh_data['mesh_terms'] = "; ".join(mesh_data['mesh_terms'])
        mesh_data['mesh_qualifiers'] = "; ".join(mesh_data['mesh_qualifiers'])
        mesh_data['major_mesh_terms'] = "; ".join(mesh_data['major_mesh_terms'])
        
        return mesh_data

    def _extract_chemicals(self, chemical_list) -> Dict[str, str]:
        """Extract chemical information."""
        chemicals_data = {
            'chemicals': [],
            'chemical_registry_numbers': []
        }
        
        if chemical_list is None:
            return chemicals_data
        
        for chemical in chemical_list.findall('.//Chemical'):
            name = self._safe_text(chemical.find('NameOfSubstance'))
            registry = self._safe_text(chemical.find('RegistryNumber'))
            
            if name:
                chemicals_data['chemicals'].append(name)
            if registry:
                chemicals_data['chemical_registry_numbers'].append(registry)
        
        # Convert to semicolon-delimited strings
        chemicals_data['chemicals'] = "; ".join(chemicals_data['chemicals'])
        chemicals_data['chemical_registry_numbers'] = "; ".join(chemicals_data['chemical_registry_numbers'])
        
        return chemicals_data

    def extract_article_data(self, article_element) -> Optional[Dict[str, Any]]:
        """Extract comprehensive data from a PubMed article XML element."""
        try:
            # Extract PMID
            pmid_element = article_element.find('.//PMID')
            pmid = pmid_element.text if pmid_element is not None else f"no_pmid_{hash(str(article_element))}"
            
            # Extract article title
            title_element = article_element.find('.//ArticleTitle')
            title = self._safe_text(title_element)
            
            # Extract abstract
            abstract_element = article_element.find('.//Abstract')
            abstract = ""
            abstract_sections = {}
            if abstract_element is not None:
                abstract_texts = abstract_element.findall('.//AbstractText')
                abstract_parts = []
                for abstract_text in abstract_texts:
                    if abstract_text.text:
                        label = abstract_text.get('Label', '')
                        if label:
                            abstract_parts.append(f"{label}: {abstract_text.text}")
                            abstract_sections[f"abstract_{label.lower()}"] = abstract_text.text
                        else:
                            abstract_parts.append(abstract_text.text)
                abstract = " ".join(abstract_parts)
            
            # Extract journal information
            journal_element = article_element.find('.//Journal')
            journal_title = ""
            journal_iso_abbreviation = ""
            issn = ""
            issn_linking = ""
            volume = ""
            issue = ""
            medline_pgn = ""
            
            if journal_element is not None:
                journal_title = self._safe_text(journal_element.find('.//Title'))
                journal_iso_abbreviation = self._safe_text(journal_element.find('.//ISOAbbreviation'))
                
                issn_elem = journal_element.find('.//ISSN')
                if issn_elem is not None:
                    issn = self._safe_text(issn_elem)
                
                journal_issue = journal_element.find('.//JournalIssue')
                if journal_issue is not None:
                    volume = self._safe_text(journal_issue.find('Volume'))
                    issue = self._safe_text(journal_issue.find('Issue'))
                
                pagination = article_element.find('.//Pagination')
                if pagination is not None:
                    medline_pgn = self._safe_text(pagination.find('MedlinePgn'))
            
            # Extract publication date
            pub_date_element = article_element.find('.//PubDate')
            pub_year = None
            pub_month = None
            pub_day = None
            pub_season = ""
            
            if pub_date_element is not None:
                year_elem = pub_date_element.find('Year')
                if year_elem is not None:
                    try:
                        pub_year = int(year_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                month_elem = pub_date_element.find('Month')
                if month_elem is not None:
                    month_text = month_elem.text
                    if month_text.isdigit():
                        pub_month = int(month_text)
                    else:
                        pub_month = self._parse_month(month_text)
                
                day_elem = pub_date_element.find('Day')
                if day_elem is not None:
                    try:
                        pub_day = int(day_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                season_elem = pub_date_element.find('Season')
                if season_elem is not None:
                    pub_season = self._safe_text(season_elem)
            
            # Extract processing dates
            date_completed = article_element.find('.//DateCompleted')
            date_completed_year = None
            date_completed_month = None
            date_completed_day = None
            
            if date_completed is not None:
                year_elem = date_completed.find('Year')
                if year_elem is not None:
                    try:
                        date_completed_year = int(year_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                month_elem = date_completed.find('Month')
                if month_elem is not None:
                    try:
                        date_completed_month = int(month_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                day_elem = date_completed.find('Day')
                if day_elem is not None:
                    try:
                        date_completed_day = int(day_elem.text)
                    except (ValueError, TypeError):
                        pass
            
            date_revised = article_element.find('.//DateRevised')
            date_revised_year = None
            date_revised_month = None
            date_revised_day = None
            
            if date_revised is not None:
                year_elem = date_revised.find('Year')
                if year_elem is not None:
                    try:
                        date_revised_year = int(year_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                month_elem = date_revised.find('Month')
                if month_elem is not None:
                    try:
                        date_revised_month = int(month_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                day_elem = date_revised.find('Day')
                if day_elem is not None:
                    try:
                        date_revised_day = int(day_elem.text)
                    except (ValueError, TypeError):
                        pass
            
            # Extract publication metadata
            article = article_element.find('.//Article')
            pub_model = ""
            if article is not None:
                pub_model = article.get('PubModel', '')
            
            language_element = article_element.find('.//Language')
            language = self._safe_text(language_element)
            
            medline_journal_info = article_element.find('.//MedlineJournalInfo')
            country = ""
            medline_ta = ""
            nlm_unique_id = ""
            issn_linking = ""
            
            if medline_journal_info is not None:
                country = self._safe_text(medline_journal_info.find('Country'))
                medline_ta = self._safe_text(medline_journal_info.find('MedlineTA'))
                nlm_unique_id = self._safe_text(medline_journal_info.find('NlmUniqueID'))
                issn_linking = self._safe_text(medline_journal_info.find('ISSNLinking'))
            
            citation_subset = self._safe_text(article_element.find('.//CitationSubset'))
            
            # Extract author information
            author_list_element = article_element.find('.//AuthorList')
            authors_data = self._extract_authors(author_list_element)
            
            # Extract MeSH terms
            mesh_heading_list = article_element.find('.//MeshHeadingList')
            mesh_data = self._extract_mesh_terms(mesh_heading_list)
            
            # Extract chemicals
            chemical_list = article_element.find('.//ChemicalList')
            chemicals_data = self._extract_chemicals(chemical_list)
            
            # Extract publication types
            pub_type_list = article_element.find('.//PublicationTypeList')
            publication_types = []
            publication_type_uis = []
            
            if pub_type_list is not None:
                for pub_type in pub_type_list.findall('.//PublicationType'):
                    pub_type_text = self._safe_text(pub_type)
                    pub_type_ui = pub_type.get('UI', '')
                    
                    if pub_type_text:
                        publication_types.append(pub_type_text)
                    if pub_type_ui:
                        publication_type_uis.append(pub_type_ui)
            
            # Extract identifiers
            doi = ""
            pii = ""
            pmc = ""
            other_ids = []
            
            e_location_ids = article_element.findall('.//ELocationID')
            for e_location in e_location_ids:
                eid_type = e_location.get('EIdType', '')
                eid_text = self._safe_text(e_location)
                
                if eid_type == 'doi':
                    doi = eid_text
                elif eid_type == 'pii':
                    pii = eid_text
                elif eid_type == 'pmc':
                    pmc = eid_text
                else:
                    other_ids.append(f"{eid_type}:{eid_text}")
            
            # Extract grants
            grant_numbers = []
            grant_agencies = []
            
            grant_list = article_element.find('.//GrantList')
            if grant_list is not None:
                for grant in grant_list.findall('.//Grant'):
                    grant_id = self._safe_text(grant.find('GrantID'))
                    agency = self._safe_text(grant.find('Agency'))
                    
                    if grant_id:
                        grant_numbers.append(grant_id)
                    if agency:
                        grant_agencies.append(agency)
            
            # Extract comments and corrections
            comments_corrections = []
            ref_sources = []
            
            comments_list = article_element.find('.//CommentsCorrectionsList')
            if comments_list is not None:
                for comment in comments_list.findall('.//CommentsCorrections'):
                    ref_source = self._safe_text(comment.find('RefSource'))
                    ref_pmid = self._safe_text(comment.find('PMID'))
                    ref_type = comment.get('RefType', '')
                    
                    comment_text = f"{ref_type}: {ref_source}"
                    if ref_pmid:
                        comment_text += f" (PMID: {ref_pmid})"
                    
                    comments_corrections.append(comment_text)
                    if ref_source:
                        ref_sources.append(ref_source)
            
            # Extract additional metadata
            vernacular_title = self._safe_text(article_element.find('.//VernacularTitle'))
            copyright_info = self._safe_text(article_element.find('.//CopyrightInformation'))
            coi_statement = self._safe_text(article_element.find('.//CoiStatement'))
            
            # Extract processing metadata
            medline_citation = article_element.find('.//MedlineCitation')
            medline_citation_status = ""
            indexing_method = ""
            owner = ""
            
            if medline_citation is not None:
                medline_citation_status = medline_citation.get('Status', '')
                indexing_method = medline_citation.get('IndexingMethod', '')
                owner = medline_citation.get('Owner', '')
            
            # Extract PubMed data history
            pubmed_data = article_element.find('.//PubmedData')
            history_entrez_year = None
            history_entrez_month = None
            history_entrez_day = None
            history_entrez_hour = None
            history_entrez_minute = None
            
            if pubmed_data is not None:
                history = pubmed_data.find('.//History')
                if history is not None:
                    pub_date = history.find('.//PubMedPubDate[@PubStatus="entrez"]')
                    if pub_date is not None:
                        year_elem = pub_date.find('Year')
                        if year_elem is not None:
                            try:
                                history_entrez_year = int(year_elem.text)
                            except (ValueError, TypeError):
                                pass
                        
                        month_elem = pub_date.find('Month')
                        if month_elem is not None:
                            try:
                                history_entrez_month = int(month_elem.text)
                            except (ValueError, TypeError):
                                pass
                        
                        day_elem = pub_date.find('Day')
                        if day_elem is not None:
                            try:
                                history_entrez_day = int(day_elem.text)
                            except (ValueError, TypeError):
                                pass
                        
                        hour_elem = pub_date.find('Hour')
                        if hour_elem is not None:
                            try:
                                history_entrez_hour = int(hour_elem.text)
                            except (ValueError, TypeError):
                                pass
                        
                        minute_elem = pub_date.find('Minute')
                        if minute_elem is not None:
                            try:
                                history_entrez_minute = int(minute_elem.text)
                            except (ValueError, TypeError):
                                pass
            
            # Filter: Only process articles that have at least one allowed publication type
            if not any(pub_type in self.allowed_pub_types for pub_type in publication_types):
                return None
            
            # Filter: Only process English articles
            if language and language.lower() not in ['eng', 'english']:
                return None
            
            # Filter: Only process articles from 2005 onwards (but allow missing years)
            if pub_year:
                if pub_year < 2005:
                    return None
            
            # Create embedding text (combine title, abstract, authors, and MeSH terms)
            embedding_parts = [title]
            if abstract:
                embedding_parts.append(abstract)
            if authors_data['authors']:
                embedding_parts.append(f"Authors: {authors_data['authors']}")
            if mesh_data['mesh_terms']:
                embedding_parts.append(f"MeSH Terms: {mesh_data['mesh_terms']}")
            if chemicals_data['chemicals']:
                embedding_parts.append(f"Chemicals: {chemicals_data['chemicals']}")
            
            embedding_text = " ".join(embedding_parts)
            
            # Create search keywords
            search_keywords = []
            if mesh_data['major_mesh_terms']:
                search_keywords.extend(mesh_data['major_mesh_terms'].split("; "))
            if chemicals_data['chemicals']:
                search_keywords.extend(chemicals_data['chemicals'].split("; "))
            search_keywords_text = "; ".join(search_keywords)
            
            # Build the complete article data
            article_data = {
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'journal_title': journal_title,
                'journal_iso_abbreviation': journal_iso_abbreviation,
                'issn': issn,
                'issn_linking': issn_linking,
                'volume': volume,
                'issue': issue,
                'medline_pgn': medline_pgn,
                'pub_year': pub_year,
                'pub_month': pub_month,
                'pub_day': pub_day,
                'pub_season': pub_season,
                'date_completed_year': date_completed_year,
                'date_completed_month': date_completed_month,
                'date_completed_day': date_completed_day,
                'date_revised_year': date_revised_year,
                'date_revised_month': date_revised_month,
                'date_revised_day': date_revised_day,
                'pub_model': pub_model,
                'language': language,
                'country': country,
                'medline_ta': medline_ta,
                'nlm_unique_id': nlm_unique_id,
                'citation_subset': citation_subset,
                'doi': doi,
                'pii': pii,
                'pmc': pmc,
                'other_ids': "; ".join(other_ids),
                'grant_numbers': "; ".join(grant_numbers),
                'grant_agencies': "; ".join(grant_agencies),
                'comments_corrections': "; ".join(comments_corrections),
                'ref_sources': "; ".join(ref_sources),
                'vernacular_title': vernacular_title,
                'copyright_information': copyright_info,
                'coi_statement': coi_statement,
                'medline_citation_status': medline_citation_status,
                'indexing_method': indexing_method,
                'owner': owner,
                'history_entrez_year': history_entrez_year,
                'history_entrez_month': history_entrez_month,
                'history_entrez_day': history_entrez_day,
                'history_entrez_hour': history_entrez_hour,
                'history_entrez_minute': history_entrez_minute,
                'embedding_text': embedding_text,
                'search_keywords': search_keywords_text,
                **authors_data,
                **mesh_data,
                **chemicals_data,
                'publication_types': "; ".join(publication_types),
                'publication_type_uis': "; ".join(publication_type_uis),
                # Abstract sections with defaults
                'abstract_purpose': abstract_sections.get('abstract_purpose', ''),
                'abstract_methods': abstract_sections.get('abstract_methods', ''),
                'abstract_results': abstract_sections.get('abstract_results', ''),
                'abstract_conclusion': abstract_sections.get('abstract_conclusion', ''),
                'abstract_background': abstract_sections.get('abstract_background', ''),
                'abstract_objective': abstract_sections.get('abstract_objective', ''),
                'abstract_design': abstract_sections.get('abstract_design', ''),
                'abstract_setting': abstract_sections.get('abstract_setting', ''),
                'abstract_participants': abstract_sections.get('abstract_participants', ''),
                'abstract_interventions': abstract_sections.get('abstract_interventions', ''),
                'abstract_outcome_measures': abstract_sections.get('abstract_outcome_measures', ''),
                'abstract_results_detailed': abstract_sections.get('abstract_results_detailed', ''),
                'abstract_conclusions': abstract_sections.get('abstract_conclusions', ''),
                'abstract_trial_registration': abstract_sections.get('abstract_trial_registration', '')
            }
            
            return article_data
            
        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None

    def upload_articles_to_database(self, articles: List[Dict[str, Any]], batch_size: int = 1000):
        """Upload articles to database in batches."""
        logger.info(f"Uploading {len(articles)} articles to database...")
        
        total_batches = (len(articles) + batch_size - 1) // batch_size
        successful_uploads = 0
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            try:
                with self.engine.connect() as conn:
                    # Prepare insert statement
                    insert_sql = """
                    INSERT INTO pubmed_articles_1177 (
                        pmid, title, abstract, journal_title, journal_iso_abbreviation,
                        issn, issn_linking, volume, issue, medline_pgn,
                        pub_year, pub_month, pub_day, pub_season,
                        date_completed_year, date_completed_month, date_completed_day,
                        date_revised_year, date_revised_month, date_revised_day,
                        pub_model, language, country, medline_ta, nlm_unique_id, citation_subset,
                        authors, author_affiliations, author_orcids,
                        first_author_lastname, first_author_forename, first_author_initials,
                        last_author_lastname, last_author_forename, last_author_initials,
                        collective_name, mesh_terms, mesh_qualifiers, major_mesh_terms,
                        chemicals, chemical_registry_numbers, publication_types, publication_type_uis,
                        doi, pii, pmc, other_ids, grant_numbers, grant_agencies,
                        comments_corrections, ref_sources, vernacular_title, copyright_information,
                        coi_statement, medline_citation_status, indexing_method, owner,
                        history_entrez_year, history_entrez_month, history_entrez_day,
                        history_entrez_hour, history_entrez_minute, embedding_text, search_keywords,
                        abstract_purpose, abstract_methods, abstract_results, abstract_conclusion,
                        abstract_background, abstract_objective, abstract_design, abstract_setting,
                        abstract_participants, abstract_interventions, abstract_outcome_measures,
                        abstract_results_detailed, abstract_conclusions, abstract_trial_registration
                    ) VALUES (
                        :pmid, :title, :abstract, :journal_title, :journal_iso_abbreviation,
                        :issn, :issn_linking, :volume, :issue, :medline_pgn,
                        :pub_year, :pub_month, :pub_day, :pub_season,
                        :date_completed_year, :date_completed_month, :date_completed_day,
                        :date_revised_year, :date_revised_month, :date_revised_day,
                        :pub_model, :language, :country, :medline_ta, :nlm_unique_id, :citation_subset,
                        :authors, :author_affiliations, :author_orcids,
                        :first_author_lastname, :first_author_forename, :first_author_initials,
                        :last_author_lastname, :last_author_forename, :last_author_initials,
                        :collective_name, :mesh_terms, :mesh_qualifiers, :major_mesh_terms,
                        :chemicals, :chemical_registry_numbers, :publication_types, :publication_type_uis,
                        :doi, :pii, :pmc, :other_ids, :grant_numbers, :grant_agencies,
                        :comments_corrections, :ref_sources, :vernacular_title, :copyright_information,
                        :coi_statement, :medline_citation_status, :indexing_method, :owner,
                        :history_entrez_year, :history_entrez_month, :history_entrez_day,
                        :history_entrez_hour, :history_entrez_minute, :embedding_text, :search_keywords,
                        :abstract_purpose, :abstract_methods, :abstract_results, :abstract_conclusion,
                        :abstract_background, :abstract_objective, :abstract_design, :abstract_setting,
                        :abstract_participants, :abstract_interventions, :abstract_outcome_measures,
                        :abstract_results_detailed, :abstract_conclusions, :abstract_trial_registration
                    )
                    ON CONFLICT (pmid) DO UPDATE SET
                        title = EXCLUDED.title,
                        abstract = EXCLUDED.abstract,
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    conn.execute(text(insert_sql), batch)
                    conn.commit()
                    
                    successful_uploads += len(batch)
                    logger.info(f"✅ Batch {batch_num}/{total_batches}: Uploaded {len(batch)} articles (Total: {successful_uploads})")
                    
            except SQLAlchemyError as e:
                logger.error(f"❌ Database error in batch {batch_num}: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Unexpected error in batch {batch_num}: {e}")
                continue
        
        logger.info(f"🎉 Upload completed! Successfully uploaded {successful_uploads} articles")
        return successful_uploads

    def process_xml_file(self, xml_file_path: str) -> List[Dict[str, Any]]:
        """Process the entire XML file and extract all articles."""
        logger.info(f"Processing XML file: {xml_file_path}")
        
        articles = []
        processed_count = 0
        skipped_count = 0
        
        try:
            # Parse XML file
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            # Find all PubmedArticle elements
            pubmed_articles = root.findall('.//PubmedArticle')
            total_articles = len(pubmed_articles)
            
            logger.info(f"Found {total_articles} articles in XML file")
            
            for i, article_element in enumerate(pubmed_articles):
                try:
                    article_data = self.extract_article_data(article_element)
                    
                    if article_data:
                        articles.append(article_data)
                        processed_count += 1
                    else:
                        skipped_count += 1
                    
                    # Progress indicator
                    if (i + 1) % 1000 == 0:
                        logger.info(f"Processed {i + 1}/{total_articles} articles ({processed_count} valid, {skipped_count} skipped)")
                
                except Exception as e:
                    logger.error(f"Error processing article {i + 1}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info(f"✅ Processing completed: {processed_count} valid articles, {skipped_count} skipped")
            return articles
            
        except Exception as e:
            logger.error(f"Error processing XML file: {e}")
            return []

def main():
    """Main function to upload PubMed data."""
    print("🏥 Uploading PubMed Data from pubmed25n1177.xml")
    print("=" * 60)
    
    # Define file path
    xml_file_path = "pubmed25n1177.xml"
    
    if not os.path.exists(xml_file_path):
        print(f"❌ Error: XML file not found at {xml_file_path}")
        return
    
    try:
        # Initialize uploader
        print("1. Initializing PubMed uploader...")
        uploader = PubMedUploader()
        print("   ✅ Uploader initialized")
        
        # Process XML file
        print("\n2. Processing XML file...")
        articles = uploader.process_xml_file(xml_file_path)
        
        if not articles:
            print("   ❌ No valid articles to upload")
            return
        
        print(f"   ✅ Processed {len(articles)} valid articles")
        
        # Upload to database
        print(f"\n3. Uploading {len(articles)} articles to AWS Aurora...")
        successful_uploads = uploader.upload_articles_to_database(articles)
        
        # Verify upload
        print("\n4. Verifying upload...")
        with uploader.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pubmed_articles_1177"))
            total_count = result.scalar()
            print(f"   ✅ Database now contains {total_count} articles")
        
        print("\n" + "=" * 60)
        print("🎉 PubMed data upload completed successfully!")
        print(f"📊 Uploaded {successful_uploads} articles to AWS Aurora")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()
