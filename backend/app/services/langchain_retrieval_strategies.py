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
            logger.info(f"🔍 Starting Postgres PubMed query for: '{query[:100]}{'...' if len(query) > 100 else ''}'")
            
            # Split query variations if " OR " is present
            query_variations = [v.strip() for v in query.split(" OR ")]
            logger.info(f"📋 Parsed {len(query_variations)} query variations")
            
            # Build simple WHERE clause that checks if search terms appear in title or abstract
            valid_variations = [v.strip() for v in query_variations if v.strip()]
            
            if not valid_variations:
                logger.warning("⚠️ No valid query variations after processing")
                return []
            
            logger.info(f"✅ Using {len(valid_variations)} valid variations for search")
            
            # Escape single quotes and build simple ILIKE conditions
            where_conditions = []
            for v in valid_variations:
                escaped = v.replace("'", "''")
                # Check if term appears in title or abstract (case-insensitive)
                # Qualify column names with table name to avoid ambiguity with JOIN
                where_conditions.append(
                    f"(pubmed_articles.title ILIKE '%{escaped}%' OR pubmed_articles.abstract ILIKE '%{escaped}%')"
                )
            
            # Combine WHERE conditions with OR
            where_clause = " OR ".join(where_conditions)
            
            # Build SQL query - simple text matching
            logger.info(f"🔧 Building SQL query with {len(where_conditions)} WHERE conditions")
            
            sql_query = text(f"""
                SELECT 
                    pubmed_articles.pmid::text as _id,
                    pubmed_articles.pmid,
                    pubmed_articles.title,
                    COALESCE(pubmed_articles.abstract, '') as abstract,
                    COALESCE(pubmed_articles.journal_title, '') as journal_title,
                    COALESCE(pubmed_articles.journal_abbrev, '') as journal_abbrev,
                    COALESCE(pubmed_articles.issn, '') as issn,
                    COALESCE(pubmed_articles.doi, '') as doi,
                    COALESCE(pubmed_articles.language, '') as language,
                    COALESCE(pubmed_articles.journal_country, '') as journal_country,
                    -- Return authors JSONB directly for matching (keep string version for display)
                    pubmed_articles.authors as authors_jsonb,
                    -- Also keep string format for backward compatibility
                    CASE 
                        WHEN pubmed_articles.authors::text = '[]' OR pubmed_articles.authors IS NULL THEN ''
                        ELSE (
                            SELECT string_agg(
                                TRIM(
                                    COALESCE(a->>'forename', '') || ' ' ||
                                    COALESCE(a->>'lastname', '')
                                ),
                                '; '
                            )
                            FROM jsonb_array_elements(pubmed_articles.authors) a
                        )
                    END as authors,
                    -- Convert other JSONB fields to strings for compatibility
                    COALESCE(pubmed_articles.mesh_terms::text, '[]') as mesh_terms,
                    COALESCE(pubmed_articles.chemicals::text, '[]') as chemicals,
                    COALESCE(pubmed_articles.grants::text, '[]') as grants,
                    COALESCE(pubmed_articles.citations::text, '[]') as citations,
                    COALESCE(pubmed_articles.publication_types::text, '[]') as publication_types,
                    -- Get journal quartile for scoring (NULL if not found)
                    journals.sjr_quartile as sjr_quartile,
                    -- Simple relevance score: 1.0 for all matches (we'll sort by pmid DESC)
                    1.0 as relevance_score
                FROM pubmed_articles
                LEFT JOIN journals ON 
                    -- Normalize ISSNs by removing dashes and spaces, then compare
                    -- Handles format differences: 
                    --   - pubmed "1933-0693" vs journals "19330693" (exact match)
                    --   - pubmed "1933-0693" vs journals "19330693,00223085" (contained in comma-separated list)
                    -- Normalize both sides: remove dashes and spaces
                    (
                        -- Exact match after normalization
                        REPLACE(REPLACE(COALESCE(pubmed_articles.issn, ''), '-', ''), ' ', '') = 
                        REPLACE(REPLACE(COALESCE(journals.issn, ''), '-', ''), ' ', '')
                        OR
                        -- Pattern match for comma-separated ISSNs in journals table
                        -- After normalization, check if normalized pubmed ISSN appears as a whole value
                        -- Regex ensures it's at word boundaries (start/end or surrounded by commas)
                        REPLACE(REPLACE(COALESCE(journals.issn, ''), '-', ''), ' ', '') ~ 
                        ('(^|,)' || REPLACE(REPLACE(COALESCE(pubmed_articles.issn, ''), '-', ''), ' ', '') || '(,|$)')
                    )
                    -- Only match if both have non-empty ISSNs after normalization
                    AND REPLACE(REPLACE(COALESCE(pubmed_articles.issn, ''), '-', ''), ' ', '') != ''
                    AND REPLACE(REPLACE(COALESCE(journals.issn, ''), '-', ''), ' ', '') != ''
                WHERE {where_clause}
                ORDER BY pubmed_articles.pmid DESC
                LIMIT :limit
            """)
            
            logger.info(f"🚀 Executing Postgres query with limit={top_k}")
            
            # Log the exact SQL query being executed
            query_params = {"limit": top_k}
            query_sql = str(sql_query.compile(compile_kwargs={"literal_binds": False}))
            logger.info(f"📋 SQL Query:\n{query_sql}")
            logger.info(f"📋 Query Parameters: {query_params}")
            
            # Also log the full rendered query for debugging
            try:
                # Try to render the query with parameters
                rendered_query = query_sql
                for param, value in query_params.items():
                    rendered_query = rendered_query.replace(f":{param}", str(value))
                logger.info(f"📋 Rendered Query (approximate):\n{rendered_query}")
            except Exception as render_error:
                logger.debug(f"Could not render query: {render_error}")
            
            # Execute query with limit parameter
            if self.db:
                logger.info("📊 Using database session from context")
                result = self.db.execute(sql_query, query_params)
            else:
                logger.info("📊 Using new database connection")
                with self.engine.connect() as conn:
                    result = conn.execute(sql_query, query_params)
            
            logger.info("✅ Query executed, fetching results...")
            
            # Fetch all results - result.execute() returns a cursor-like object
            # For SQLAlchemy, we need to iterate or use fetchall()
            try:
                if hasattr(result, 'fetchall'):
                    rows = result.fetchall()
                    logger.info(f"📊 Fetched {len(rows)} rows from query")
                else:
                    rows = list(result)
                    logger.info(f"📊 Converted result to list: {len(rows)} rows")
            except Exception as fetch_error:
                logger.error(f"❌ Error fetching results: {str(fetch_error)}")
                # Try iterating directly
                rows = []
                try:
                    for row in result:
                        rows.append(row)
                    logger.info(f"📊 Iterated to get {len(rows)} rows")
                except Exception as iter_error:
                    logger.error(f"❌ Error iterating results: {str(iter_error)}")
                    return []
            
            # Convert results to format matching Pinecone hits
            hits = []
            for row in rows:
                # Get authors_jsonb (may not exist if query is old)
                authors_jsonb = None
                if hasattr(row, 'authors_jsonb'):
                    import json
                    try:
                        authors_jsonb = row.authors_jsonb if isinstance(row.authors_jsonb, list) else json.loads(row.authors_jsonb) if row.authors_jsonb else []
                    except:
                        authors_jsonb = []
                
                hit_fields = {
                    "_id": str(row.pmid),  # Store as string for consistency
                    "pmid": str(row.pmid),
                    "title": row.title or "",
                    "abstract": row.abstract or "",
                    "authors": row.authors or "",  # String format for display
                    "authors_jsonb": authors_jsonb or [],  # JSONB format for matching
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
                    "sjr_quartile": row.sjr_quartile if hasattr(row, 'sjr_quartile') else None,  # Journal quartile for scoring
                    "_score": float(row.relevance_score) if row.relevance_score else 0.0
                }
                hits.append(hit_fields)
            
            # Log quartile statistics
            quartile_stats = {'Q1': 0, 'Q2': 0, 'Q3': 0, 'Q4': 0, 'None': 0}
            for hit in hits:
                quartile = hit.get('sjr_quartile')
                if quartile in quartile_stats:
                    quartile_stats[quartile] += 1
                else:
                    quartile_stats['None'] += 1
            
            logger.info(f"✅ Postgres query returned {len(hits)} PubMed articles for query: '{query[:80]}{'...' if len(query) > 80 else ''}'")
            logger.info(f"📊 Quartile breakdown: Q1={quartile_stats['Q1']}, Q2={quartile_stats['Q2']}, Q3={quartile_stats['Q3']}, Q4={quartile_stats['Q4']}, None={quartile_stats['None']}")
            
            # Log sample quartile values for debugging
            if hits:
                sample_with_quartile = [h for h in hits[:10] if h.get('sjr_quartile')]
                if sample_with_quartile:
                    logger.info(f"📋 Sample articles with quartile data: {[(h.get('pmid'), h.get('issn'), h.get('sjr_quartile')) for h in sample_with_quartile[:5]]}")
                else:
                    logger.warning(f"⚠️  No quartile data found in first 10 articles. Sample ISSNs: {[h.get('issn') for h in hits[:5] if h.get('issn')]}")
            
            return hits
            
        except Exception as e:
            logger.error(f"❌ Error querying PubMed from Postgres: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
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
    

