"""
Specialist Information Retrieval Service
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ..models.specialist_recommendation import PatientProfile
from .medical_analysis_service import parse_search_query

logger = logging.getLogger(__name__)

class SpecialistInformationRetrievalService:
    """Service for retrieving specialist information from medical content databases."""
    
    def __init__(self, db: Optional[Session] = None):
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
        logger.info("SpecialistInformationRetrievalService initialized successfully")
    
    def _query_vumedi_from_postgres(self, diagnostic_terms: List[str], anatomic_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Query Vumedi videos: must match at least one diagnostic term AND at least one anatomic term.
        If anatomic_terms is empty, only diagnostic match is required.
        """
        try:
            diagnostic_terms = [t.strip().lower() for t in diagnostic_terms if t and t.strip()]
            anatomic_terms = [t.strip().lower() for t in anatomic_terms if t and t.strip()]
            if not diagnostic_terms and not anatomic_terms:
                return []
            logger.info(f"🔍 Querying Vumedi: {len(diagnostic_terms)} diagnostic, {len(anatomic_terms)} anatomic terms")

            def build_or_conditions(terms: List[str], prefix: str) -> tuple:
                conditions = []
                params = {}
                for i, term in enumerate(terms):
                    key = f"{prefix}_{i}"
                    params[key] = f"%{term}%"
                    conditions.append(f"(LOWER(title) LIKE :{key} OR LOWER(featuring) LIKE :{key} OR LOWER(specialty) LIKE :{key})")
                return (" OR ".join(conditions), params) if conditions else ("1=0", {})

            diag_clause, diag_params = build_or_conditions(diagnostic_terms, "term_d")
            anat_clause, anat_params = build_or_conditions(anatomic_terms, "term_a")
            query_params = {**diag_params, **anat_params}

            if diagnostic_terms and anatomic_terms:
                where_clause = f"({diag_clause}) AND ({anat_clause})"
            elif diagnostic_terms:
                where_clause = diag_clause
            else:
                where_clause = anat_clause

            sql_query = text(f"""
                SELECT 
                    title,
                    author,
                    date,
                    views,
                    duration,
                    link,
                    thumbnail,
                    featuring,
                    specialty,
                    scraped_at
                FROM vumedi_content_consolidated
                WHERE {where_clause}
                ORDER BY title
            """)
            
            logger.info(f"🚀 Executing Postgres Vumedi query (no limit)")
            
            # Execute query
            if self.db:
                logger.info("📊 Using database session from context")
                result = self.db.execute(sql_query, query_params)
            else:
                logger.info("📊 Using new database connection")
                database_url = os.getenv('DATABASE_URL')
                if not database_url:
                    logger.error("❌ DATABASE_URL not found")
                    return []
                engine = create_engine(database_url)
                with engine.connect() as conn:
                    result = conn.execute(sql_query, query_params)
            
            # Convert results to list
            rows = []
            try:
                for row in result:
                    rows.append(row)
                logger.info(f"📊 Retrieved {len(rows)} Vumedi videos")
            except Exception as iter_error:
                logger.error(f"❌ Error iterating Vumedi results: {str(iter_error)}")
                return []
            
            # Convert to expected format
            hits = []
            for row in rows:
                hit_fields = {
                    "title": row.title or "",
                    "author": row.author or "",
                    "date": row.date or "",
                    "views": row.views or "",
                    "duration": row.duration or "",
                    "link": row.link or "",
                    "thumbnail": row.thumbnail or "",
                    "featuring": row.featuring or "",
                    "specialty": row.specialty or "",
                    "scraped_at": str(row.scraped_at) if row.scraped_at else "",
                    "_score": 1.0  # Default relevance score
                }
                hits.append(hit_fields)
            
            logger.info(f"✅ Postgres query returned {len(hits)} Vumedi videos")
            
            return hits
            
        except Exception as e:
            logger.error(f"❌ Error querying Vumedi from Postgres: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
            return []
    
    def _query_pubmed_from_postgres(self, diagnostic_terms: List[str], anatomic_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Query PubMed articles: must match at least one diagnostic term AND at least one anatomic term.
        If anatomic_terms is empty, only diagnostic match is required.
        """
        if not self.engine and not self.db:
            logger.error("❌ No database connection available for PubMed query")
            return []

        diagnostic_terms = [v.strip() for v in diagnostic_terms if v and v.strip()]
        anatomic_terms = [v.strip() for v in anatomic_terms if v and v.strip()]
        if not diagnostic_terms and not anatomic_terms:
            return []

        try:
            logger.info(f"🔍 PubMed query: {len(diagnostic_terms)} diagnostic, {len(anatomic_terms)} anatomic terms")

            def build_or_conditions(terms: List[str]) -> str:
                conds = []
                for v in terms:
                    escaped = v.replace("'", "''")
                    conds.append(f"(pubmed_articles.title ILIKE '%{escaped}%' OR pubmed_articles.abstract ILIKE '%{escaped}%')")
                return " OR ".join(conds) if conds else "1=0"

            diag_clause = build_or_conditions(diagnostic_terms)
            anat_clause = build_or_conditions(anatomic_terms)
            if diagnostic_terms and anatomic_terms:
                where_clause = f"({diag_clause}) AND ({anat_clause})"
            elif diagnostic_terms:
                where_clause = diag_clause
            else:
                where_clause = anat_clause
            
            sql_query = text(f"""
                WITH filtered_articles AS (
                    -- First, filter pubmed_articles to reduce JOIN size
                    SELECT 
                        pmid,
                        title,
                        abstract,
                        journal_title,
                        journal_abbrev,
                        issn,
                        doi,
                        language,
                        journal_country,
                        authors,
                        mesh_terms,
                        chemicals,
                        grants,
                        citations,
                        publication_types,
                        -- Pre-normalize ISSN once for JOIN
                        replace(replace(lower(issn), '-'::text, ''::text), ' '::text, ''::text) AS normalized_issn
                    FROM pubmed_articles
                    WHERE {where_clause}
                    ORDER BY pmid DESC
                ), filtered as materialized (
                    SELECT * FROM filtered_articles
                )
                SELECT 
                    f.pmid::text as _id,
                    f.pmid,
                    f.title,
                    COALESCE(f.abstract, '') as abstract,
                    COALESCE(f.journal_title, '') as journal_title,
                    COALESCE(f.journal_abbrev, '') as journal_abbrev,
                    COALESCE(f.issn, '') as issn,
                    COALESCE(f.doi, '') as doi,
                    COALESCE(f.language, '') as language,
                    COALESCE(f.journal_country, '') as journal_country,
                    -- Return authors JSONB directly for matching (keep string version for display)
                    f.authors as authors_jsonb,
                    -- Also keep string format for backward compatibility
                    CASE 
                        WHEN f.authors::text = '[]' OR f.authors IS NULL THEN ''
                        ELSE (
                            SELECT string_agg(
                                TRIM(
                                    COALESCE(a->>'forename', '') || ' ' ||
                                    COALESCE(a->>'lastname', '')
                                ),
                                '; '
                            )
                            FROM jsonb_array_elements(f.authors) a
                        )
                    END as authors,
                    -- Convert other JSONB fields to strings for compatibility
                    COALESCE(f.mesh_terms::text, '[]') as mesh_terms,
                    COALESCE(f.chemicals::text, '[]') as chemicals,
                    COALESCE(f.grants::text, '[]') as grants,
                    COALESCE(f.citations::text, '[]') as citations,
                    COALESCE(f.publication_types::text, '[]') as publication_types,
                    -- Get journal quartile for scoring (NULL if not found)
                    j.sjr_quartile as sjr_quartile,
                    -- Simple relevance score: 1.0 for all matches (we'll sort by pmid DESC)
                    1.0 as relevance_score
                FROM filtered f
                LEFT JOIN journals j ON 
                    f.normalized_issn = j.normalized_issn
            """)
            
            logger.info(f"🚀 Executing Postgres query (no limit)")
            
            # Log the exact SQL query being executed
            query_params = {}
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
            
            # Execute query
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
            
            # Convert results to expected format
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
    
    def _verify_result(self, result: dict, diagnostic_terms: List[str], anatomic_terms: List[str], source: str) -> bool:
        """
        Verify if a result contains at least one diagnostic term AND at least one anatomic term.
        If anatomic_terms is empty, only requires at least one diagnostic term.
        """
        content_parts = []
        if result.get('title'):
            content_parts.append(result['title'])
        if source == 'pubmed' and result.get('abstract'):
            content_parts.append(result['abstract'])
        if source == 'vumedi' and result.get('featuring'):
            content_parts.append(result['featuring'])
        if source == 'vumedi' and result.get('specialty'):
            content_parts.append(result['specialty'])
        full_content = " ".join(content_parts).lower()

        has_diagnostic = False
        if diagnostic_terms:
            for t in diagnostic_terms:
                if t.lower() in full_content:
                    has_diagnostic = True
                    break
        else:
            has_diagnostic = True
        has_anatomic = False
        if anatomic_terms:
            for t in anatomic_terms:
                if t.lower() in full_content:
                    has_anatomic = True
                    break
        else:
            has_anatomic = True

        if has_diagnostic and has_anatomic:
            logger.debug(f"✅ Verified {source} result: at least one diagnostic + one anatomic")
            return True
        logger.debug(f"❌ Unverified {source} result: diagnostic={has_diagnostic}, anatomic={has_anatomic}")
        return False
    
    def _parse_patient_input(self, patient_input: str) -> tuple:
        """
        Parse the combined patient input string to extract individual fields.
        
        Args:
            patient_input: Combined patient input string
            
        Returns:
            Tuple of (diagnosis, medical_history, medications, surgical_history, pdf_content)
        """
        # Initialize with empty strings
        diagnosis = ""
        medical_history = ""
        medications = ""
        surgical_history = ""
        pdf_content = ""
        
        # Split by sections
        sections = patient_input.split('\n\n')
        
        for section in sections:
            section = section.strip()
            if section.startswith('Diagnosis:'):
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
        
        return diagnosis, medical_history, medications, surgical_history, pdf_content
    
    async def retrieve_specialist_information(
        self,
        medical_analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve specialist information using pre-generated queries based on medical analysis results.
        
        Queries are executed against Postgres database with no limits on result count.
        """
        try:
            # Use pre-generated search query and parsed terms from medical analysis
            query = medical_analysis_results.get("search_query", "")
            diagnostic_terms = medical_analysis_results.get("search_query_diagnostic_terms")
            anatomic_terms = medical_analysis_results.get("search_query_anatomic_terms")
            if diagnostic_terms is None or anatomic_terms is None:
                if query:
                    diagnostic_terms, anatomic_terms = parse_search_query(query)
                else:
                    diagnostic_terms, anatomic_terms = [], []

            if not query and not diagnostic_terms and not anatomic_terms:
                logger.error("❌ No pre-generated search query found in medical analysis results")
                raise ValueError("No pre-generated search query available - search query must be generated during medical analysis")

            logger.info(f"🔍 Using search terms: {len(diagnostic_terms)} diagnostic, {len(anatomic_terms)} anatomic")
            if query:
                logger.info(f"   Query string: {query[:80]}{'...' if len(query) > 80 else ''}")
            
            # Execute single search and group results
            treatment_results = {}
            seen_ids = set()
            
            # Use primary diagnosis as the single treatment group
            treatment_id = "primary_diagnosis"
            treatment_name = medical_analysis_results.get("icd10_description", "Primary Diagnosis")
            
            try:
                logger.info(f"🔍 Executing search for '{treatment_name}' (at least one diagnostic + one anatomic)")
                # Query Vumedi and PubMed with diagnostic + anatomic terms (articles must match at least one of each)
                vumedi_hits = self._query_vumedi_from_postgres(diagnostic_terms, anatomic_terms)
                pubmed_hits = self._query_pubmed_from_postgres(diagnostic_terms, anatomic_terms)
                
                # Initialize treatment results
                treatment_results[treatment_id] = {
                    "name": treatment_name,
                    "results": [],
                    "query": query
                }
                
                # Parse Vumedi results from Postgres
                vumedi_count = 0
                vumedi_filtered = 0
                for hit_fields in vumedi_hits:
                    # Get link as unique identifier
                    candidate_id = hit_fields.get("link", f"{hit_fields.get('title', '')}_{hit_fields.get('author', '')}")
                    if candidate_id and candidate_id not in seen_ids:
                        # Add source information and treatment metadata
                        hit_fields["_source"] = "vumedi"
                        hit_fields["_treatment_id"] = treatment_id
                        hit_fields["_treatment_name"] = treatment_name
                        # _score already set by Postgres query
                        
                        # Verify the result contains at least one diagnostic and one anatomic term
                        is_verified = self._verify_result(hit_fields, diagnostic_terms, anatomic_terms, source="vumedi")
                        hit_fields["_verified"] = is_verified
                        
                        # Store all results (both verified and unverified)
                        treatment_results[treatment_id]["results"].append(hit_fields)
                        seen_ids.add(candidate_id)
                        
                        if is_verified:
                            vumedi_count += 1
                        else:
                            vumedi_filtered += 1
                            logger.debug(f"❌ Filtered Vumedi result: {hit_fields.get('title', 'No title')[:50]}...")
                
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
                        
                        # Verify the result contains at least one diagnostic and one anatomic term
                        is_verified = self._verify_result(hit_fields, diagnostic_terms, anatomic_terms, source="pubmed")
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
            logger.info(f"✅ Retrieval completed using single diagnosis-based query")
            logger.info(f"🔍 All results stored with verification status for debug display")
            logger.debug(f"🔍 Returning results grouped under treatment_id: {treatment_id}")
            
            # Return both the treatment results and the search query
            return {
                "treatment_results": treatment_results,
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"❌ Error in retrieval: {str(e)}")
            raise
    

