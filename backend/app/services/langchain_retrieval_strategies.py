"""
LangChain Retrieval Strategies
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ..models.specialist_recommendation import PatientProfile
from .pinecone_service import PineconeService

logger = logging.getLogger(__name__)

class LangChainRetrievalStrategies:
    """LangChain-powered retrieval strategies."""
    
    def __init__(self, pinecone_service: PineconeService, db: Optional[Session] = None):
        self.pinecone_service = pinecone_service
        self.vumedi_index = self.pinecone_service.pc.Index(self.pinecone_service.default_index_name)
        # No longer using self.pubmed_index - replaced with Postgres queries
        self.db = db
        if not db:
            # Create database connection if not provided
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                self.engine = create_engine(database_url)
            else:
                self.engine = None
                logger.warning("⚠️ DATABASE_URL not set - PubMed queries will use Postgres connection")
        else:
            self.engine = None
        
        # Note: Query generation is now handled by MedicalAnalysisService
        # This service only uses pre-generated search queries
        logger.info("LangChainRetrievalStrategies initialized successfully")
    
    def _query_pubmed_from_postgres(self, query: str, top_k: int = 10000) -> List[Dict[str, Any]]:
        """
        Query PubMed articles from Postgres using full-text search.
        
        Args:
            query: Search query string (can contain " OR " separated variations)
            top_k: Maximum number of results to return
            
        Returns:
            List of dictionaries matching the format expected from Pinecone hits
        """
        if not self.engine and not self.db:
            logger.error("❌ No database connection available for PubMed query")
            return []
        
        try:
            # Split query variations if " OR " is present
            query_variations = [v.strip() for v in query.split(" OR ")]
            
            # Build Postgres full-text search query
            # Use tsvector for title + abstract search
            # Convert query terms to tsquery format (handle OR terms)
            search_terms = []
            for variation in query_variations:
                # Escape special characters and convert to tsquery format
                # Split by spaces and join with & for AND logic
                terms = variation.split()
                # For each variation, use OR logic
                if terms:
                    # Convert each term to proper tsquery format
                    escaped_terms = [term.replace(':', '').replace('!', '').replace('&', '').replace('|', '') for term in terms if term]
                    if escaped_terms:
                        # Join terms with & for AND within variation, we'll use OR between variations
                        search_terms.extend(escaped_terms)
            
            if not search_terms:
                logger.warning("⚠️ No valid search terms extracted from query")
                return []
            
            # Build Postgres full-text search query that handles OR variations
            # Use parameterized queries for safety
            # For simplicity, use the first variation or combine all with OR in tsquery
            valid_variations = [v.strip() for v in query_variations if v.strip()]
            
            if not valid_variations:
                logger.warning("⚠️ No valid query variations after processing")
                return []
            
            # For OR logic in Postgres tsquery, we'll build the query string
            # Escape single quotes in query variations for SQL safety
            escaped_variations = [v.replace("'", "''") for v in valid_variations]
            
            # Build tsquery: combine all variations with OR operator (|)
            if len(escaped_variations) == 1:
                tsquery_expr = f"plainto_tsquery('english', '{escaped_variations[0]}')"
            else:
                # Combine multiple variations with OR (|)
                tsqueries = [f"plainto_tsquery('english', '{v}')" for v in escaped_variations]
                tsquery_expr = " | ".join(tsqueries)
            
            # Build SQL query with full-text search
            # Search both title and abstract, rank by relevance
            sql_query = text(f"""
                SELECT 
                    pmid::text as _id,
                    pmid,
                    title,
                    COALESCE(abstract, '') as abstract,
                    COALESCE(journal_title, '') as journal_title,
                    COALESCE(journal_abbrev, '') as journal_abbrev,
                    COALESCE(issn, '') as issn,
                    COALESCE(doi, '') as doi,
                    COALESCE(language, '') as language,
                    COALESCE(journal_country, '') as journal_country,
                    -- Convert authors JSONB to string format
                    CASE 
                        WHEN authors::text = '[]' OR authors IS NULL THEN ''
                        ELSE (
                            SELECT string_agg(
                                COALESCE(a->>'name', ''),
                                '; '
                            )
                            FROM jsonb_array_elements(authors) a
                        )
                    END as authors,
                    -- Convert other JSONB fields to strings for compatibility
                    COALESCE(mesh_terms::text, '[]') as mesh_terms,
                    COALESCE(chemicals::text, '[]') as chemicals,
                    COALESCE(grants::text, '[]') as grants,
                    COALESCE(citations::text, '[]') as citations,
                    COALESCE(publication_types::text, '[]') as publication_types,
                    -- Calculate relevance score based on full-text search
                    ts_rank_cd(
                        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                        setweight(to_tsvector('english', COALESCE(abstract, '')), 'B'),
                        ({tsquery_expr})
                    ) as relevance_score
                FROM pubmed_articles
                WHERE 
                    -- Full-text search on title and abstract with OR logic
                    (
                        to_tsvector('english', COALESCE(title, '')) ||
                        to_tsvector('english', COALESCE(abstract, ''))
                    ) @@ ({tsquery_expr})
                ORDER BY relevance_score DESC, pmid DESC
                LIMIT :limit
            """)
            
            # Execute query with limit parameter
            if self.db:
                result = self.db.execute(sql_query, {"limit": top_k})
            else:
                with self.engine.connect() as conn:
                    result = conn.execute(sql_query, {"limit": top_k})
            
            # Convert results to format matching Pinecone hits
            hits = []
            for row in result:
                hit_fields = {
                    "_id": str(row.pmid),  # Store as string for consistency
                    "pmid": str(row.pmid),
                    "title": row.title or "",
                    "abstract": row.abstract or "",
                    "authors": row.authors or "",
                    "journal_title": row.journal_title or "",
                    "journal_abbrev": row.journal_abbrev or "",
                    "issn": row.issn or "",
                    "doi": row.doi or "",
                    "language": row.language or "",
                    "journal_country": row.journal_country or "",
                    "mesh_terms": row.mesh_terms or "[]",
                    "chemicals": row.chemicals or "[]",
                    "grants": row.grants or "[]",
                    "citations": row.citations or "[]",
                    "publication_types": row.publication_types or "[]",
                    "_score": float(row.relevance_score) if row.relevance_score else 0.0
                }
                hits.append(hit_fields)
            
            logger.info(f"✅ Postgres query returned {len(hits)} PubMed articles for query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
            return hits
            
        except Exception as e:
            logger.error(f"❌ Error querying PubMed from Postgres: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _verify_result(self, result: dict, query_variations: list, source: str) -> bool:
        """
        Verify if a result contains any of the query variations.
        
        Args:
            result: Pinecone result with fields
            query_variations: List of query variations to match against
            source: Explicit source type ("vumedi" or "pubmed")
            
        Returns:
            True if result contains any variation, False otherwise
        """
        # Get content based on explicit source type
        content_parts = []
        
        # Always include title if available
        if result.get('title'):
            content_parts.append(result['title'])
        
        # Add source-specific content based on explicit source
        if source == 'vumedi':
            # For Vumedi: use title only (as requested)
            pass
        elif source == 'pubmed':
            # For PubMed: use title + abstract (as requested)
            if result.get('abstract'):
                content_parts.append(result['abstract'])
        
        # Combine all content
        full_content = " ".join(content_parts).lower()
        
        # Check for exact matches (case-insensitive)
        for variation in query_variations:
            if variation.lower() in full_content:
                logger.debug(f"✅ Match found: '{variation}' in {source} result")
                return True
        
        logger.debug(f"❌ No match found in {source} result: {result.get('title', 'No title')[:50]}...")
        return False
    
    def _parse_patient_input(self, patient_input: str) -> tuple:
        """
        Parse the combined patient input string to extract individual fields.
        
        Args:
            patient_input: Combined patient input string
            
        Returns:
            Tuple of (symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content)
        """
        # Initialize with empty strings
        symptoms = ""
        diagnosis = ""
        medical_history = ""
        medications = ""
        surgical_history = ""
        pdf_content = ""
        
        # Split by sections
        sections = patient_input.split('\n\n')
        
        for section in sections:
            section = section.strip()
            if section.startswith('Symptoms:'):
                symptoms = section.replace('Symptoms:', '').strip()
            elif section.startswith('Diagnosis:'):
                diagnosis = section.replace('Diagnosis:', '').strip()
            elif section.startswith('Medical History:'):
                medical_history = section.replace('Medical History:', '').strip()
            elif section.startswith('Current Medications:'):
                medications = section.replace('Current Medications:', '').strip()
            elif section.startswith('Surgical History:'):
                surgical_history = section.replace('Surgical History:', '').strip()
            elif section.startswith('Additional Information from Files:'):
                # Extract PDF content from the files section
                pdf_content = section.replace('Additional Information from Files:', '').strip()
                # Remove the "(PDF uploaded)" notes and keep only actual content
                pdf_content = pdf_content.replace('(PDF uploaded)', '').strip()
        
        return symptoms, diagnosis, medical_history, medications, surgical_history, pdf_content
    
    async def retrieve_specialist_information(
        self,
        medical_analysis_results: Dict[str, Any],
        top_k: int = 200  # Not used for distribution, kept for backward compatibility
    ) -> Dict[str, Any]:
        """Retrieve specialist information from Pinecone using LangChain-generated queries based on medical analysis results.
        
        Uses fixed limits: 100 for Vumedi, 1000 for PubMed per query.
        """
        try:
            # Use pre-generated search query from medical analysis
            query = medical_analysis_results.get("search_query", "")
            
            if not query:
                logger.error("❌ No pre-generated search query found in medical analysis results")
                raise ValueError("No pre-generated search query available - search query must be generated during medical analysis")
            
            logger.info(f"🔍 Using pre-generated search query from medical analysis:")
            logger.info(f"📊 Query limits: 50 Vumedi + 200 PubMed = 250 max results total")
            logger.info(f"   Query: {query}")
            
            # Parse query variations for verification
            query_variations = [variation.strip() for variation in query.split(" OR ")]
            logger.info(f"🔍 Parsed {len(query_variations)} query variations for verification:")
            for i, variation in enumerate(query_variations, 1):
                logger.info(f"   {i}. {variation}")
            
            # Execute single search and group results
            treatment_results = {}
            seen_ids = set()
            
            # Use primary diagnosis as the single treatment group
            treatment_id = "primary_diagnosis"
            treatment_name = medical_analysis_results.get("icd10_description", "Primary Diagnosis")
            
            try:
                logger.info(f"🔍 Executing Pinecone search for '{treatment_name}': '{query[:80]}{'...' if len(query) > 80 else ''}'")
                
                # Use separate limits for Vumedi and PubMed
                vumedi_top_k = 100  # Max 100 total for Vumedi
                pubmed_top_k = 10000  # Max 10000 total for PubMed
                logger.debug(f"   📊 Using top_k={vumedi_top_k} for Vumedi, {pubmed_top_k} for PubMed")
                
                # Query Vumedi index (still using Pinecone)
                vumedi_results = self.vumedi_index.search(
                    namespace="__default__",
                    query={
                        "inputs": {"text": query},
                        "top_k": vumedi_top_k
                    },
                    fields=["*"]
                )
                
                # Query PubMed from Postgres database (replacing Pinecone)
                pubmed_hits = self._query_pubmed_from_postgres(query, pubmed_top_k)
                
                # Initialize treatment results
                treatment_results[treatment_id] = {
                    "name": treatment_name,
                    "results": [],
                    "query": query
                }
                
                # Parse Vumedi results
                vumedi_count = 0
                vumedi_filtered = 0
                if hasattr(vumedi_results, 'result') and hasattr(vumedi_results.result, 'hits'):
                    for hit in vumedi_results.result.hits:
                        candidate_id = hit.fields.get("link", f"{hit.fields.get('title', '')}_{hit.fields.get('author', '')}")
                        if candidate_id and candidate_id not in seen_ids:
                            # Add source information and treatment metadata
                            hit.fields["_source"] = "vumedi"
                            hit.fields["_treatment_id"] = treatment_id
                            hit.fields["_treatment_name"] = treatment_name
                            hit.fields["_score"] = getattr(hit, '_score', None)
                            
                            # Verify the result contains query variations
                            is_verified = self._verify_result(hit.fields, query_variations, source="vumedi")
                            hit.fields["_verified"] = is_verified
                            
                            # Store all results (both verified and unverified)
                            treatment_results[treatment_id]["results"].append(hit.fields)
                            seen_ids.add(candidate_id)
                            
                            if is_verified:
                                vumedi_count += 1
                            else:
                                vumedi_filtered += 1
                                logger.debug(f"❌ Filtered Vumedi result: {hit.fields.get('title', 'No title')[:50]}...")
                
                # Parse PubMed results from Postgres
                pubmed_count = 0
                pubmed_filtered = 0
                for hit_fields in pubmed_hits:
                    # Get PMID from _id field (already in hit_fields dict from Postgres)
                    pmid = hit_fields.get('_id') or hit_fields.get('pmid')
                    candidate_id = pmid or f"{hit_fields.get('title', '')}_{hit_fields.get('authors', '')}"
                    if candidate_id and candidate_id not in seen_ids:
                        # Add source information and treatment metadata
                        hit_fields["_source"] = "pubmed"
                        hit_fields["_treatment_id"] = treatment_id
                        hit_fields["_treatment_name"] = treatment_name
                        hit_fields["_id"] = str(pmid) if pmid else None  # Store the PMID for later use
                        # _score already set by Postgres query
                        
                        # Verify the result contains query variations
                        is_verified = self._verify_result(hit_fields, query_variations, source="pubmed")
                        hit_fields["_verified"] = is_verified
                        
                        # Store all results (both verified and unverified)
                        treatment_results[treatment_id]["results"].append(hit_fields)
                        seen_ids.add(candidate_id)
                        
                        if is_verified:
                            pubmed_count += 1
                        else:
                            pubmed_filtered += 1
                            logger.debug(f"❌ Filtered PubMed result: {hit_fields.get('title', 'No title')[:50]}...")
                
                total_stored = vumedi_count + vumedi_filtered + pubmed_count + pubmed_filtered
                logger.info(f"✅ Search returned {vumedi_count} verified Vumedi + {pubmed_count} verified PubMed = {vumedi_count + pubmed_count} verified results")
                logger.info(f"📊 Stored total: {total_stored} results ({vumedi_count + vumedi_filtered} Vumedi, {pubmed_count + pubmed_filtered} PubMed)")
                if vumedi_filtered > 0 or pubmed_filtered > 0:
                    logger.info(f"🔍 Including {vumedi_filtered} Vumedi + {pubmed_filtered} PubMed unverified results for debug display")
                            
            except Exception as e:
                logger.error(f"❌ Search failed for '{treatment_name}': {str(e)}")
                raise
            
            # Count total results by source and verification status
            total_results = len(treatment_results[treatment_id]["results"])
            vumedi_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "vumedi")
            pubmed_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_source") == "pubmed")
            verified_total = sum(1 for result in treatment_results[treatment_id]["results"] if result.get("_verified") == True)
            
            logger.info(f"📊 Results summary:")
            logger.info(f"   📋 Total stored: {total_results} results ({vumedi_total} Vumedi, {pubmed_total} PubMed)")
            logger.info(f"   ✅ Verified: {verified_total} results")
            logger.info(f"   ❌ Unverified: {total_results - verified_total} results")
            logger.info(f"✅ LangChain retrieval completed using single diagnosis-based query")
            logger.info(f"🔍 All results stored with verification status for debug display")
            logger.debug(f"🔍 Returning results grouped under treatment_id: {treatment_id}")
            
            # Return both the treatment results and the search query
            return {
                "treatment_results": treatment_results,
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"❌ Error in LangChain retrieval: {str(e)}")
            raise
    

