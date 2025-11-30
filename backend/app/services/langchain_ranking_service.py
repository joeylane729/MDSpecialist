"""
LangChain-powered ranking service for combining NPI providers with Pinecone data.

This service takes a list of NPI providers and Pinecone specialist information,
then uses LangChain to rank the NPI providers based on relevance to the Pinecone data.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from ..models.specialist_recommendation import SpecialistRecommendation
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class LangChainRankingService:
    """Service for ranking NPI providers based on Pinecone specialist information."""
    
    def __init__(self, db: Session = None):
        self.llm = ChatOpenAI(model="gpt-5-mini", temperature=0.1, request_timeout=300)
        self.db = db
        
        # Prompt for ranking NPI providers based on Pinecone data
        self.ranking_prompt = PromptTemplate(
            input_variables=["npi_providers", "pinecone_data", "patient_profile"],
            template="""
            You are a medical specialist ranking expert. Your task is to return doctor names with their corresponding Vumedi links/titles and PubMed articles based on the information from Pinecone.
            The Pinecone data contains two types of content:
            1. VUMEDI: Medical education videos with doctor names in "featuring" field, links, and titles
            2. PUBMED: Research articles with author names, PMIDs, and titles
            
            STRICT RULES:
            1. The list you return must only include names from the npi_providers list.
            2. Do not add any names that do not appear in the Pinecone data.
            3. For each doctor, include:
               - Vumedi content: link and title from Vumedi records where they appear
               - PubMed content: PMID and title from PubMed records where they appear as authors
            4. Match names with slight variations (middle initial, capitalization, nicknames, etc.)
            
            NPI Providers (NPI: Name):
            {npi_providers}
            
            Specialist Information from Pinecone:
            {pinecone_data}
            
            Return a JSON object with the fields below and do not include any other text in your response:
            1. "providers": An array of objects, each containing:
               - "name" (doctor name in "FIRST LAST" format, all caps)
               - "vumedi_content": Array of objects with "link" and "title" from Vumedi records
               - "pubmed_articles": Array of objects with "pmid" and "title" from PubMed records
               - Ranked in order of relevance (most relevant first)
            2. "explanation": A 2-sentence explanation of your results.
            
            Example:
            {{
                "providers": [
                    {{
                        "name": "ALBERT SMITH", 
                        "vumedi_content": [
                            {{"link": "https://example.com/video1", "title": "Advanced Treatment for Cluster Headaches"}}
                        ],
                        "pubmed_articles": [
                            {{"pmid": "12345678", "title": "Novel Approaches to Cluster Headache Management"}}
                        ]
                    }},
                    {{
                        "name": "JANE DOE", 
                        "vumedi_content": [
                            {{"link": "https://example.com/video2", "title": "Migraine Management Strategies"}}
                        ],
                        "pubmed_articles": []
                    }}
                ],
                "explanation": "I found Albert Smith in both Vumedi videos and PubMed articles about cluster headaches, so I ranked him first."
            }}
            
           
            """
        )
        
        self.ranking_chain = self.ranking_prompt | self.llm
    
    def _batch_get_medical_school_scores(self, npi_list: List[str]) -> Dict[str, int]:
        """Batch get medical school ranking scores for multiple NPI providers."""
        if not self.db or not npi_list:
            return {}
            
        try:
            # Use DISTINCT ON to get the best (lowest rank) medical school for each NPI
            # Ensure all NPIs are strings for the query
            npi_list_str = [str(npi) for npi in npi_list]
            
            # Use DISTINCT ON to get the best (lowest rank) medical school for each NPI
            # Cast npi_list to text[] to match the text type of the "NPI" column
            # Use bindparam to explicitly specify array type for SQLAlchemy
            from sqlalchemy import bindparam, ARRAY, String
            query = text("""
                SELECT DISTINCT ON (nmr."NPI") nmr."NPI", msr.rank 
                FROM npi_medical_school_mapping_results nmr
                JOIN medical_school_rankings msr ON nmr."Medical_School_ID" = msr.id
                WHERE nmr."NPI"::text = ANY(:npi_list)
                ORDER BY nmr."NPI", msr.rank ASC
            """).bindparams(bindparam("npi_list", type_=ARRAY(String)))
            
            query_params = {"npi_list": npi_list_str}
            
            # Log the exact SQL query being executed
            query_sql = str(query.compile(compile_kwargs={"literal_binds": False}))
            logger.info(f"📋 Batch Medical School Query SQL:\n{query_sql}")
            logger.info(f"📋 Query Parameters: {len(npi_list_str)} NPIs")
            logger.info(f"📋 Sample NPIs being queried: {npi_list_str[:5]}")
            
            # Test query: Check if a specific NPI exists (for debugging)
            # Wrap in try-except so it doesn't break the main query if it fails
            if '1649209008' in npi_list_str:
                try:
                    test_query = text("""
                        SELECT nmr."NPI", msr.rank, msr.school_listed
                        FROM npi_medical_school_mapping_results nmr
                        JOIN medical_school_rankings msr ON nmr."Medical_School_ID" = msr.id
                        WHERE nmr."NPI"::text = '1649209008'
                ORDER BY msr.rank ASC
                LIMIT 1
            """)
                    test_result = self.db.execute(test_query)
                    test_row = test_result.fetchone()
                    if test_row:
                        logger.info(f"🔍 TEST: NPI 1649209008 found in mapping - School: {test_row[2]}, Rank: {test_row[1]}")
                    else:
                        logger.warning(f"⚠️  TEST: NPI 1649209008 NOT found in npi_medical_school_mapping_results table")
                except Exception as test_error:
                    logger.warning(f"⚠️  TEST query failed (non-fatal): {test_error}")
            
            result = self.db.execute(query, query_params)
            rows = result.fetchall()
            
            logger.info(f"📊 Query returned {len(rows)} rows from database")
            
            scores = {}
            for row in rows:
                npi = str(row[0])  # Ensure NPI is a string
                rank = row[1]
                
                # Convert rank to points: 1-25 = 3 points, 26-50 = 2 points, 51-75 = 1 point
                if rank <= 25:
                    points = 3
                elif rank <= 50:
                    points = 2
                elif rank <= 75:
                    points = 1
                else:
                    points = 0
                
                scores[npi] = points
                logger.debug(f"📋 NPI {npi}: rank {rank} = {points} points")
            
            # Log which NPIs were found vs not found
            found_npis = set(scores.keys())
            queried_npis = set(npi_list_str)
            missing_npis = queried_npis - found_npis
            if missing_npis:
                logger.warning(f"⚠️  {len(missing_npis)} NPIs not found in medical school mapping: {list(missing_npis)[:10]}")
            
            logger.info(f"✅ Fetched medical school scores for {len(scores)} NPIs (queried {len(npi_list_str)})")
            return scores
                
        except Exception as e:
            logger.error(f"Error batch looking up medical schools: {e}")
            return {}
    
    def _batch_get_residency_scores(self, npi_list: List[str]) -> Dict[str, int]:
        """Batch get residency ranking scores for multiple NPI providers."""
        if not self.db or not npi_list:
            return {}

        try:
            npi_list_str = [str(npi) for npi in npi_list]
            from sqlalchemy import bindparam, ARRAY, String
            query = text("""
                SELECT DISTINCT ON (nrr.npi) nrr.npi, rr.id
                FROM npi_residency_mapping_results nrr
                JOIN residency_rankings rr ON nrr.residency_program_id = rr.id
                WHERE nrr.npi = ANY(:npi_list)
                ORDER BY nrr.npi, rr.id ASC
            """).bindparams(bindparam("npi_list", type_=ARRAY(String)))

            logger.info("📋 Fetching residency ranking scores for NPIs")
            logger.info(f"📋 Query Parameters: {len(npi_list_str)} NPIs")
            logger.info(f"📋 Sample NPIs for residency lookup: {npi_list_str[:5]}")

            result = self.db.execute(query, {"npi_list": npi_list_str})
            rows = result.fetchall()

            logger.info(f"📊 Residency query returned {len(rows)} rows from database")

            scores: Dict[str, int] = {}
            for row in rows:
                npi = str(row[0])
                rank = row[1]
                if rank is None:
                    continue

                if rank <= 25:
                    points = 3
                elif rank <= 50:
                    points = 2
                elif rank <= 75:
                    points = 1
                else:
                    points = 0

                scores[npi] = points
                logger.debug(f"📋 Residency NPI {npi}: rank {rank} = {points} points")

            found_npis = set(scores.keys())
            queried_npis = set(npi_list_str)
            missing_npis = queried_npis - found_npis
            if missing_npis:
                logger.warning(f"⚠️  {len(missing_npis)} NPIs not found in residency mapping: {list(missing_npis)[:10]}")

            logger.info(f"✅ Fetched residency scores for {len(scores)} NPIs (queried {len(npi_list_str)})")
            return scores

        except Exception as e:
            logger.error(f"Error batch looking up residencies: {e}")
            return {}

    def _batch_get_certification_scores(self, npi_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch get board certification scores for multiple NPI providers.
        Returns dict with keys: 'certification_points', 'is_certified', 'has_abns', 'has_aoa'
        Scoring: ABNS (has_abns=TRUE OR results_count>0) = 5 points, AOA (has_aoa=TRUE) = 2 points
        """
        if not self.db or not npi_list:
            return {}
            
        try:
            npi_list_str = [str(npi) for npi in npi_list]
            from sqlalchemy import bindparam, ARRAY, String
            query = text("""
                SELECT npi, has_abns, has_aoa, results_count
                FROM npi_certification_mapping_results
                WHERE npi = ANY(:npi_list)
            """).bindparams(bindparam("npi_list", type_=ARRAY(String)))
            
            result = self.db.execute(query, {"npi_list": npi_list_str})
            rows = result.fetchall()
            
            scores: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                npi = str(row[0])
                has_abns = row[1]
                has_aoa = row[2]
                results_count = row[3]
                
                # Determine ABNS: has_abns = 'TRUE' OR results_count > 0
                # Handle results_count which might be string, int, or empty
                results_count_int = 0
                if results_count:
                    try:
                        if isinstance(results_count, str):
                            results_count_int = int(results_count.strip()) if results_count.strip() else 0
                        else:
                            results_count_int = int(results_count)
                    except (ValueError, TypeError):
                        results_count_int = 0
                is_abns = (has_abns == 'TRUE' or has_abns is True) or results_count_int > 0
                # Determine AOA: has_aoa = 'TRUE'
                is_aoa = (has_aoa == 'TRUE' or has_aoa is True)
                
                # Calculate points: ABNS = 5 points, AOA = 2 points
                abns_points = 5 if is_abns else 0
                aoa_points = 2 if is_aoa else 0
                total_points = abns_points + aoa_points
                
                # is_certified is True if either ABNS or AOA is true
                is_certified = is_abns or is_aoa
                
                scores[npi] = {
                    'certification_points': total_points,
                    'is_certified': is_certified,
                    'has_abns': is_abns,
                    'has_aoa': is_aoa,
                    'abns_points': abns_points,
                    'aoa_points': aoa_points
                }
            
            logger.info(f"✅ Fetched certification scores for {len(scores)} NPIs (queried {len(npi_list_str)})")
            return scores
                
        except Exception as e:
            logger.error(f"Error batch looking up certifications: {e}")
            return {}
    
    def _get_medical_school_score(self, npi: str) -> int:
        """Get medical school ranking score for a single NPI provider (deprecated, use batch version)."""
        scores = self._batch_get_medical_school_scores([npi])
        return scores.get(npi, 0)
    
    def _calculate_weighted_score(
        self,
        raw_scores: Dict[str, Dict[str, float]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate weighted scores from raw component scores.
        
        Weights:
        - Clinical Volume: 40%
        - PubMed: 40%
        - Training: 10% (Med school + Residency + Certification)
        - Experience: 6%
        - Vumedi: 4%
        
        Args:
            raw_scores: Dict mapping NPI to dict of raw component scores
            
        Returns:
            Dict mapping NPI to weighted score components and final score
        """
        if not raw_scores:
            return {}
        
        # Find max values for normalization (except clinical volume which is binary)
        max_pubmed = max((scores.get('pubmed_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_vumedi = max((scores.get('vumedi_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_training = max((scores.get('training_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_experience = max((scores.get('experience_raw', 0) for scores in raw_scores.values()), default=1.0)
        
        # Avoid division by zero
        max_pubmed = max(max_pubmed, 1.0)
        max_vumedi = max(max_vumedi, 1.0)
        max_training = max(max_training, 1.0)
        max_experience = max(max_experience, 1.0)
        
        weighted_scores = {}
        
        for npi, scores in raw_scores.items():
            # Normalize components to 0-1 (0-100%)
            clinical_volume_pct = scores.get('clinical_volume_raw', 0.0)  # Already 0.0 or 1.0
            pubmed_pct = min(scores.get('pubmed_raw', 0) / max_pubmed, 1.0)
            vumedi_pct = min(scores.get('vumedi_raw', 0) / max_vumedi, 1.0)
            training_pct = min(scores.get('training_raw', 0) / max_training, 1.0)
            experience_pct = min(scores.get('experience_raw', 0) / max_experience, 1.0)
            
            # Apply weights and calculate final score (0-100)
            clinical_volume_weighted = clinical_volume_pct * 40.0  # 40%
            pubmed_weighted = pubmed_pct * 40.0  # 40%
            training_weighted = training_pct * 10.0  # 10%
            experience_weighted = experience_pct * 6.0  # 6%
            vumedi_weighted = vumedi_pct * 4.0  # 4%
            
            final_score = clinical_volume_weighted + pubmed_weighted + training_weighted + experience_weighted + vumedi_weighted
            
            weighted_scores[npi] = {
                'clinical_volume_pct': clinical_volume_pct * 100,
                'pubmed_pct': pubmed_pct * 100,
                'vumedi_pct': vumedi_pct * 100,
                'training_pct': training_pct * 100,
                'experience_pct': experience_pct * 100,
                'clinical_volume_weighted': clinical_volume_weighted,
                'pubmed_weighted': pubmed_weighted,
                'vumedi_weighted': vumedi_weighted,
                'training_weighted': training_weighted,
                'experience_weighted': experience_weighted,
                'final_score': final_score
            }
        
        return weighted_scores
    
    def _calculate_experience_points(self, years_experience_raw: Optional[Any]) -> Tuple[Optional[int], int]:
        """Normalize years of experience and return the bonus points."""
        if years_experience_raw in (None, "", "--"):
            return None, 0
        try:
            years = int(float(years_experience_raw))
        except (TypeError, ValueError):
            return None, 0
        if years < 0:
            return None, 0
        if 10 <= years <= 45:
            return years, 5
        return years, 0
    
    async def rank_npi_providers(
        self, 
        npi_providers: List[Dict[str, Any]], 
        pinecone_data: List[Dict[str, Any]], 
        patient_profile: Dict[str, Any],
        max_providers: int = 10000,
        top_cms_npis: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Rank NPI providers based on simple exact name matching with Pinecone data.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            pinecone_data: List of specialist information from Pinecone (Vumedi/PubMed)
            patient_profile: Patient profile with symptoms, diagnosis, etc. (not used, kept for compatibility)
            max_providers: Maximum number of providers to rank (default: 10000)
            top_cms_npis: Optional set of NPI strings for top 25 CMS providers (for clinical volume bonus)
            
        Returns:
            Dictionary with 'ranking' (list of NPI numbers), 'provider_links', 'provider_scores', and 'explanation'
        """
        try:
            logger.info(f"🎯 === SIMPLE NAME MATCHING RANKING STARTED ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📊 Max providers to rank: {max_providers}")
            logger.info(f"📊 Pinecone records: {len(pinecone_data)}")
            
            # Take only the first max_providers for ranking
            providers_to_rank = npi_providers[:max_providers]
            
            # Build lookup maps for NPI providers
            # Map: (first_name.lower, last_name.lower) -> provider_dict
            npi_by_name = {}
            # Map: full_name.lower -> provider_dict (for Vumedi matching)
            npi_by_full_name = {}
            
            for provider in providers_to_rank:
                npi = provider.get('npi', '')
                if not npi:
                    continue
                
                # Try multiple field name variations
                first_name = (provider.get('first_name') or provider.get('provider_first_name') or '').strip()
                last_name = (provider.get('last_name') or provider.get('provider_last_name') or '').strip()
                full_name = (provider.get('name') or provider.get('full_name') or '').strip()
                
                # If we have a full name but not first/last, parse it
                if full_name and not (first_name and last_name):
                    name_parts = full_name.strip().split()
                    if len(name_parts) >= 2:
                        # Assume first part(s) are first name, last part is last name
                        first_name = ' '.join(name_parts[:-1])
                        last_name = name_parts[-1]
                
                # Log provider data for first few to debug
                if len(npi_by_name) < 3:
                    logger.info(f"📋 Provider sample: npi={npi}, first_name={first_name}, last_name={last_name}, full_name={full_name}")
                
                # Build name-based lookup
                # Normalize: use only the first word of first_name to handle middle initials
                # e.g., "Theodore" matches "Theodore H" from PubMed
                if first_name and last_name:
                    first_name_normalized = first_name.split()[0].lower() if first_name else ''
                    last_name_normalized = last_name.lower()
                    name_key = (first_name_normalized, last_name_normalized)
                    if name_key not in npi_by_name:
                        npi_by_name[name_key] = []
                    npi_by_name[name_key].append(provider)
                
                # Build full name lookup for Vumedi
                if full_name:
                    npi_by_full_name[full_name.lower()] = provider
            
            logger.info(f"📊 Built lookup maps: {len(npi_by_name)} first+last name combinations, {len(npi_by_full_name)} full names")
            
            # Log sample keys for debugging
            if npi_by_name:
                sample_keys = list(npi_by_name.keys())[:3]
                logger.info(f"📋 Sample name keys: {sample_keys}")
            
            # Track matches: npi -> {vumedi_content: [], pubmed_articles: []}
            provider_matches = {}
            
            # Process Pinecone data for matches
            for record in pinecone_data:
                source = record.get('_source', 'unknown')
                
                if source == 'vumedi':
                    # Vumedi: Match by full name from "featuring" OR "author" field
                    featuring = (record.get('featuring') or '').strip()
                    author = (record.get('author') or '').strip()
                    
                    # Check both fields (case-insensitive)
                    matched_provider = None
                    
                    # Try featuring field first
                    if featuring:
                        featuring_lower = featuring.lower()
                        if featuring_lower in npi_by_full_name:
                            matched_provider = npi_by_full_name[featuring_lower]
                    
                    # If no match in featuring, try author field
                    if not matched_provider and author:
                        author_lower = author.lower()
                        if author_lower in npi_by_full_name:
                            matched_provider = npi_by_full_name[author_lower]
                    
                    # If we found a match in either field, add to results
                    if matched_provider:
                        npi = matched_provider.get('npi', '')
                        if npi:
                            if npi not in provider_matches:
                                provider_matches[npi] = {
                                    'vumedi_content': [],
                                    'pubmed_articles': []
                                }
                            provider_matches[npi]['vumedi_content'].append({
                                'link': record.get('link', ''),
                                'title': record.get('title', '')
                            })
                
                elif source == 'pubmed':
                    # PubMed: Match by exact first name + last name from authors JSONB
                    authors_jsonb = record.get('authors_jsonb', [])
                    
                    if authors_jsonb and isinstance(authors_jsonb, list):
                        # Log first PubMed article authors for debugging
                        if len(provider_matches) == 0:
                            logger.info(f"📋 First PubMed article authors: {authors_jsonb[:3] if authors_jsonb else 'No authors'}")
                        
                        # Use JSONB format with separate forename/lastname fields
                        # Track author position for weighted scoring
                        total_authors = len(authors_jsonb)
                        for author_idx, author_obj in enumerate(authors_jsonb):
                            if isinstance(author_obj, dict):
                                forename = (author_obj.get('forename') or '').strip()
                                lastname = (author_obj.get('lastname') or '').strip()
                                
                                # Normalize: use only the first word of forename to handle middle initials
                                # e.g., "Theodore H" -> "theodore" to match "Theodore" from NPI
                                if forename and lastname:
                                    forename_normalized = forename.split()[0].lower() if forename else ''
                                    lastname_normalized = lastname.lower()
                                    name_key = (forename_normalized, lastname_normalized)
            
                                    # Determine author position for weighted scoring
                                    # Last author: 3 points, First author: 2 points, Middle: 1 point
                                    if total_authors == 1:
                                        author_position = 'last'  # Only one author gets last author weight (3 points)
                                    elif author_idx == 0:
                                        author_position = 'first'
                                    elif author_idx == total_authors - 1:
                                        author_position = 'last'
                                    else:
                                        author_position = 'middle'
                                    
                                    # Log first few attempts for debugging
                                    if len(provider_matches) == 0:
                                        logger.info(f"📋 Attempting match: ('{forename_normalized}', '{lastname_normalized}') -> in map? {name_key in npi_by_name}")
                                    
                                    if name_key in npi_by_name:
                                        # Match found - add to all providers with this name
                                        for provider in npi_by_name[name_key]:
                                            npi = provider.get('npi', '')
                                            if npi:
                                                if npi not in provider_matches:
                                                    provider_matches[npi] = {
                                                        'vumedi_content': [],
                                                        'pubmed_articles': []
                                                    }
                                                provider_matches[npi]['pubmed_articles'].append({
                                                    'pmid': record.get('_id', record.get('pmid', '')),
                                                    'title': record.get('title', ''),
                                                    'author_position': author_position,  # Track position for weighted scoring
                                                    'sjr_quartile': record.get('sjr_quartile')  # Journal quartile for scoring
                                                })
            
            logger.info(f"✅ Found {len(provider_matches)} providers with matches")
            
            # Batch fetch all medical school scores for all NPIs at once
            # Normalize all NPIs to strings for consistent lookup
            all_npis = set()
            for npi in provider_matches.keys():
                all_npis.add(str(npi))  # Ensure string format
            for provider in providers_to_rank:
                npi = provider.get('npi', '')
                if npi:
                    all_npis.add(str(npi))  # Ensure string format
            
            med_school_scores = self._batch_get_medical_school_scores(list(all_npis))
            logger.info(f"📊 Fetched medical school scores for {len(med_school_scores)} NPIs in batch")
            residency_scores = self._batch_get_residency_scores(list(all_npis))
            logger.info(f"📊 Fetched residency scores for {len(residency_scores)} NPIs in batch")
            certification_scores = self._batch_get_certification_scores(list(all_npis))
            logger.info(f"📊 Fetched certification scores for {len(certification_scores)} NPIs in batch")
            
            # Build provider links and scores
            provider_links = {}
            provider_scores = {}
            raw_component_scores = {}  # Store raw scores for weighted calculation
            
            # First pass: Calculate raw scores for all providers
            raw_scores = {}  # Store raw component scores before normalization
            
            logger.info(f"🔍 DEBUG: Processing {len(provider_matches)} providers with matches")
            logger.info(f"🔍 DEBUG: Building provider_links and scores...")
            
            for idx, (npi, matches) in enumerate(provider_matches.items()):
                try:
                    logger.debug(f"🔍 DEBUG: Processing provider {idx+1}/{len(provider_matches)}: NPI={npi}")
                    
                    vumedi_count = len(matches.get('vumedi_content', []))
                    pubmed_articles = matches.get('pubmed_articles', [])
                    pubmed_count = len(pubmed_articles)
            
                    # Calculate weighted PubMed score based on author position and journal quartile
                    # Last author: 3 points, First author: 2 points, Middle: 1 point
                    # Quartile multipliers: Q1=1.0, Q2=0.75, Q3=0.5, Q4=0.25, NULL/missing=1.0
                    pubmed_weighted_points = 0
                    pubmed_base_points = 0  # Points before quartile multiplier
                    first_author_count = 0
                    middle_author_count = 0
                    last_author_count = 0
                    
                    # Track quartile counts
                    quartile_counts = {
                        'Q1': 0,
                        'Q2': 0,
                        'Q3': 0,
                        'Q4': 0,
                        'no_quartile': 0  # Articles without quartile data
                    }
                    
                    # Quartile multiplier mapping
                    quartile_multipliers = {
                        'Q1': 1.0,
                        'Q2': 0.75,
                        'Q3': 0.5,
                        'Q4': 0.25
                    }
                    
                    for article in pubmed_articles:
                        position = article.get('author_position', 'middle')  # Default to middle if not specified
                        sjr_quartile = article.get('sjr_quartile')  # Get quartile from article data
                        
                        # Get base points based on author position
                        if position == 'last':
                            base_points = 3
                            last_author_count += 1
                        elif position == 'first':
                            base_points = 2
                            first_author_count += 1
                        else:  # middle
                            base_points = 1
                            middle_author_count += 1
                        
                        # Track base points (before quartile multiplier)
                        pubmed_base_points += base_points
                        
                        # Track quartile count
                        if sjr_quartile in quartile_counts:
                            quartile_counts[sjr_quartile] += 1
                        else:
                            quartile_counts['no_quartile'] += 1
                        
                        # Apply quartile multiplier (default to 1.0 if quartile is missing/null)
                        quartile_multiplier = quartile_multipliers.get(sjr_quartile, 1.0) if sjr_quartile else 1.0
                        weighted_points = base_points * quartile_multiplier
                        pubmed_weighted_points += weighted_points
                    
                    logger.debug(f"🔍 DEBUG: NPI {npi} - Vumedi: {vumedi_count}, PubMed: {pubmed_count} (First: {first_author_count}, Middle: {middle_author_count}, Last: {last_author_count}, Weighted: {pubmed_weighted_points} points)")
            
                    # Get provider info for experience calculation
                    provider = None
                    try:
                        for p in providers_to_rank:
                            if str(p.get('npi')) == str(npi):
                                provider = p
                                break
                    except Exception as e:
                        logger.error(f"❌ DEBUG: Error finding provider info for NPI {npi}: {e}")
                        provider = None
                    
                    years_experience_raw = None
                    if provider:
                        years_experience_raw = provider.get('yearsExperience', provider.get('years_experience'))
                    years_experience, experience_points = self._calculate_experience_points(years_experience_raw)
                    
                    # Log matched PubMed articles for top providers
                    if pubmed_count > 0 and len(provider_links) < 20:
                        provider_name = provider.get('name', '') if provider else npi
                        try:
                            pubmed_titles = [art.get('title', 'No title')[:80] for art in matches['pubmed_articles'][:3]]
                            pmids = [art.get('pmid', '') for art in matches['pubmed_articles']]
                            logger.info(f"📋 Provider {provider_name} (NPI {npi}) matched {pubmed_count} PubMed articles: PMIDs={pmids[:5]}")
                        except Exception as e:
                            logger.error(f"❌ DEBUG: Error extracting PMIDs for NPI {npi}: {e}")
                            logger.error(f"❌ DEBUG: matches['pubmed_articles'] type: {type(matches.get('pubmed_articles'))}")
                    
                    try:
                        provider_links[npi] = {
                            'vumedi_content': matches.get('vumedi_content', []),
                            'pubmed_articles': matches.get('pubmed_articles', [])
                        }
                        logger.debug(f"🔍 DEBUG: Successfully added provider_links for NPI {npi}")
                    except Exception as e:
                        logger.error(f"❌ DEBUG: Error building provider_links for NPI {npi}: {e}")
                        logger.error(f"❌ DEBUG: matches structure: {list(matches.keys())}")
                        raise
                        
                    # Normalize NPI to string for consistent lookup
                    npi_str = str(npi)
                    med_school_score = med_school_scores.get(npi_str, 0)
                    residency_score = residency_scores.get(npi_str, 0)
                    cert_info = certification_scores.get(npi_str, {})
                    certification_points = cert_info.get('certification_points', 0) if isinstance(cert_info, dict) else 0
                    
                    # Check if provider is in top 25 CMS results (clinical volume bonus)
                    clinical_volume_points = 0
                    if top_cms_npis:
                        logger.debug(f"🔍 DEBUG: Checking NPI {npi_str} against {len(top_cms_npis)} top CMS NPIs")
                        if npi_str in top_cms_npis:
                            clinical_volume_points = 20
                            logger.info(f"✅ [Ranking] NPI {npi_str} ({provider.get('first_name', '') if provider else ''} {provider.get('last_name', '') if provider else ''}) is in top 25 CMS results - adding 20 clinical volume points")
                        # Check for Theodore Schwartz specifically
                        if provider:
                            first_name = provider.get('first_name', '').upper()
                            last_name = provider.get('last_name', '').upper()
                            if 'THEODORE' in first_name and 'SCHWARTZ' in last_name:
                                logger.info(f"🔍 [Ranking] Checking Theodore Schwartz NPI {npi_str} - in top_cms_npis? {npi_str in top_cms_npis}")
                                logger.info(f"🔍 [Ranking] Sample top_cms_npis: {list(list(top_cms_npis)[:5])}")
                    else:
                        logger.debug(f"🔍 DEBUG: No top_cms_npis provided for NPI {npi_str}")
                    
                    # Calculate raw component scores for weighted system
                    # Store raw scores for normalization pass
                    raw_component_scores[npi] = {
                        'vumedi_raw': vumedi_count * 4,  # Vumedi raw score
                        'pubmed_raw': pubmed_weighted_points,  # PubMed raw score (already weighted by quartiles)
                        'training_raw': med_school_score + residency_score + certification_points,  # Training raw score
                        'experience_raw': experience_points,  # Experience raw score
                        'clinical_volume_raw': 1.0 if clinical_volume_points > 0 else 0.0  # Binary: 1.0 if in top 25, 0.0 otherwise
                    }
                    
                    # Calculate legacy scores for backward compatibility (will be replaced with weighted)
                    content_score = (vumedi_count * 4) + pubmed_weighted_points
                    total_score = content_score + med_school_score + residency_score + experience_points + certification_points + clinical_volume_points
                    
                    # Extract certification details
                    is_certified = cert_info.get('is_certified', False) if isinstance(cert_info, dict) else False
                    has_abns = cert_info.get('has_abns', False) if isinstance(cert_info, dict) else False
                    has_aoa = cert_info.get('has_aoa', False) if isinstance(cert_info, dict) else False
                    abns_points = cert_info.get('abns_points', 0) if isinstance(cert_info, dict) else 0
                    aoa_points = cert_info.get('aoa_points', 0) if isinstance(cert_info, dict) else 0
                    
                    # Log if medical school score is missing
                    if med_school_score == 0 and npi_str in med_school_scores:
                        logger.debug(f"🔍 DEBUG: NPI {npi_str} found in med_school_scores but score is 0")
                    elif med_school_score == 0:
                        logger.debug(f"🔍 DEBUG: NPI {npi_str} not found in med_school_scores (available keys: {list(med_school_scores.keys())[:5]})")
                    
                    if residency_score == 0 and npi_str in residency_scores:
                        logger.debug(f"🔍 DEBUG: NPI {npi_str} found in residency_scores but score is 0")
                    elif residency_score == 0:
                        logger.debug(f"🔍 DEBUG: NPI {npi_str} not found in residency_scores (available keys: {list(residency_scores.keys())[:5]})")
                    
                    logger.debug(
                        f"🔍 DEBUG: NPI {npi} - Content score: {content_score}, Med school: {med_school_score}, "
                        f"Residency: {residency_score}, Experience: {experience_points} (from {years_experience} years), "
                        f"Certification: {certification_points} (ABNS: {abns_points}, AOA: {aoa_points}), "
                        f"Clinical Volume: {clinical_volume_points}, Total: {total_score}"
                    )
                    
                    provider_scores[npi] = {
                        'score': total_score,  # Will be replaced with weighted score
                        'content_score': content_score,
                        'med_school_score': med_school_score,
                        'residency_score': residency_score,
                        'experience_points': experience_points,
                        'certification_points': certification_points,
                        'clinical_volume_points': clinical_volume_points,
                        'is_certified': is_certified,
                        'has_abns': has_abns,
                        'has_aoa': has_aoa,
                        'abns_points': abns_points,
                        'aoa_points': aoa_points,
                        'years_experience': years_experience,
                        'vumedi_count': vumedi_count,
                        'pubmed_count': pubmed_count,
                        'pubmed_first_author_count': first_author_count,
                        'pubmed_middle_author_count': middle_author_count,
                        'pubmed_last_author_count': last_author_count,
                        'pubmed_base_points': pubmed_base_points,  # Points before quartile multiplier
                        'pubmed_weighted_points': pubmed_weighted_points,  # Points after quartile multiplier
                        'pubmed_quartile_q1_count': quartile_counts['Q1'],
                        'pubmed_quartile_q2_count': quartile_counts['Q2'],
                        'pubmed_quartile_q3_count': quartile_counts['Q3'],
                        'pubmed_quartile_q4_count': quartile_counts['Q4'],
                        'pubmed_quartile_no_data_count': quartile_counts['no_quartile'],
                        'npi': npi
                    }
                    
                    logger.debug(f"🔍 DEBUG: Successfully built scores for NPI {npi}")
                        
                except Exception as e:
                    logger.error(f"❌ DEBUG: Error processing provider NPI {npi}: {e}")
                    import traceback
                    logger.error(f"❌ DEBUG: Traceback:\n{traceback.format_exc()}")
                    # Continue with next provider instead of crashing
                    continue
            
            # Calculate weighted scores from raw component scores
            if raw_component_scores:
                weighted_scores = self._calculate_weighted_score(raw_component_scores)
                # Update provider_scores with weighted values
                for npi, weighted_data in weighted_scores.items():
                    if npi in provider_scores:
                        provider_scores[npi]['score'] = weighted_data['final_score']
                        # Store weighted breakdown for frontend display
                        provider_scores[npi]['weighted_breakdown'] = {
                            'clinical_volume': {
                                'percentage': weighted_data['clinical_volume_pct'],
                                'weighted_points': weighted_data['clinical_volume_weighted'],
                                'weight': 40.0
                            },
                            'pubmed': {
                                'percentage': weighted_data['pubmed_pct'],
                                'weighted_points': weighted_data['pubmed_weighted'],
                                'weight': 40.0
                            },
                            'training': {
                                'percentage': weighted_data['training_pct'],
                                'weighted_points': weighted_data['training_weighted'],
                                'weight': 10.0
                            },
                            'experience': {
                                'percentage': weighted_data['experience_pct'],
                                'weighted_points': weighted_data['experience_weighted'],
                                'weight': 6.0
                            },
                            'vumedi': {
                                'percentage': weighted_data['vumedi_pct'],
                                'weighted_points': weighted_data['vumedi_weighted'],
                                'weight': 4.0
                            }
                        }
            
            # Sort providers by score (descending), then by name
            providers_with_scores = []
            for provider in providers_to_rank:
                npi = provider.get('npi', '')
                if npi in provider_scores:
                    providers_with_scores.append((
                        provider.get('name', ''),
                        provider_scores[npi]
                    ))
            
            # Sort by score descending, then name ascending
            providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
            
            # Extract ranked NPI list
            ranked_npis = [score['npi'] for _, score in providers_with_scores]
            
            # Add unmatched providers with scores (will be updated with weighted scores)
            unmatched_raw_scores = {}  # Store raw scores for unmatched providers
            # Normalize matched_npis to strings for consistent comparison
            matched_npis = set(str(npi) for npi in ranked_npis)
            for provider in providers_to_rank:
                npi = provider.get('npi', '')
                if npi:
                    npi_str = str(npi)  # Normalize to string
                    if npi_str not in matched_npis:
                        med_school_score = med_school_scores.get(npi_str, 0)
                        residency_score = residency_scores.get(npi_str, 0)
                        cert_info = certification_scores.get(npi_str, {})
                        certification_points = cert_info.get('certification_points', 0) if isinstance(cert_info, dict) else 0
                        is_certified = cert_info.get('is_certified', False) if isinstance(cert_info, dict) else False
                        has_abns = cert_info.get('has_abns', False) if isinstance(cert_info, dict) else False
                        has_aoa = cert_info.get('has_aoa', False) if isinstance(cert_info, dict) else False
                        abns_points = cert_info.get('abns_points', 0) if isinstance(cert_info, dict) else 0
                        aoa_points = cert_info.get('aoa_points', 0) if isinstance(cert_info, dict) else 0
                        years_experience_raw = provider.get('yearsExperience', provider.get('years_experience'))
                        years_experience, experience_points = self._calculate_experience_points(years_experience_raw)
                        total_score = med_school_score + residency_score + experience_points + certification_points
                        provider_scores[npi] = {  # Keep original npi format for key consistency
                            'score': total_score,
                            'content_score': 0,
                            'med_school_score': med_school_score,
                            'residency_score': residency_score,
                            'experience_points': experience_points,
                            'certification_points': certification_points,
                            'is_certified': is_certified,
                            'has_abns': has_abns,
                            'has_aoa': has_aoa,
                            'abns_points': abns_points,
                            'aoa_points': aoa_points,
                            'years_experience': years_experience,
                            'vumedi_count': 0,
                            'pubmed_count': 0,
                            'pubmed_first_author_count': 0,
                            'pubmed_middle_author_count': 0,
                            'pubmed_last_author_count': 0,
                            'pubmed_base_points': 0,
                            'pubmed_weighted_points': 0,
                            'pubmed_quartile_q1_count': 0,
                            'pubmed_quartile_q2_count': 0,
                            'pubmed_quartile_q3_count': 0,
                            'pubmed_quartile_q4_count': 0,
                            'pubmed_quartile_no_data_count': 0,
                            'npi': npi
                        }
                        provider_links[npi] = {
                            'vumedi_content': [],
                            'pubmed_articles': []
                        }
                        ranked_npis.append(npi)
            
            logger.info(f"✅ === SIMPLE NAME MATCHING COMPLETED ===")
            logger.info(f"✅ Matched {len(matched_npis)} providers, {len(ranked_npis) - len(matched_npis)} unmatched")
            logger.info(f"🏆 Top 10 ranked NPIs: {ranked_npis[:10]}")
            
            explanation = f"Matched {len(matched_npis)} providers using exact name matching. " \
                         f"Found {sum(score['vumedi_count'] for score in provider_scores.values())} Vumedi matches " \
                         f"and {sum(score['pubmed_count'] for score in provider_scores.values())} PubMed matches."
            
            # Ensure ALL providers have weighted_breakdown (even if all zeros)
            # This is needed for providers without matches or with zero scores
            for npi in provider_scores:
                if 'weighted_breakdown' not in provider_scores[npi]:
                    # Create a zero-weighted breakdown for providers without one
                    provider_scores[npi]['weighted_breakdown'] = {
                        'clinical_volume': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': 40.0
                        },
                        'pubmed': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': 40.0
                        },
                        'training': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': 10.0
                        },
                        'experience': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': 6.0
                        },
                        'vumedi': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': 4.0
                        }
                    }
                    # Also ensure score is set (might be 0 for unmatched providers)
                    if 'score' not in provider_scores[npi]:
                        provider_scores[npi]['score'] = 0.0
            
            return {
                'ranking': ranked_npis,
                'provider_links': provider_links,  # NPI-keyed
                'provider_scores': {npi: score for npi, score in provider_scores.items()},  # NPI-keyed
                'explanation': explanation
            }
            
        except Exception as e:
            logger.error(f"❌ Error in simple name matching: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            # Fallback: return original order (first max_providers)
            fallback_ranking = [provider.get('npi', '') for provider in npi_providers[:max_providers] if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Ranking failed - showing providers in original order.',
                'provider_links': {},
                'provider_scores': {}
            }
    
    def _format_npi_providers(self, providers: List[Dict[str, Any]]) -> str:
        """Format NPI providers for LLM input."""
        formatted = []
        for provider in providers:
            npi = provider.get('npi', '')
            name = provider.get('name', '')  # Use the 'name' field from NPI endpoint
            formatted.append(f"{npi}: {name}")
        return "\n".join(formatted)
    
    def _format_pinecone_data(self, pinecone_data: List[Dict[str, Any]]) -> str:
        """Format Pinecone data for LLM input - handles both Vumedi and PubMed data."""
        formatted = []
        vumedi_count = 0
        pubmed_count = 0
        
        for i, record in enumerate(pinecone_data, 1):
            source = record.get('_source', 'unknown')
            
            if source == 'vumedi':
                vumedi_count += 1
                author = record.get('author', 'Unknown author')
                featuring = record.get('featuring', 'Unknown specialist')
                link = record.get('link', 'No link available')
                title = record.get('title', 'No title available')
                formatted.append(f"{i}. [VUMEDI] Author: {author}, Featuring: {featuring}, Link: {link}, Title: {title}")
                
            elif source == 'pubmed':
                pubmed_count += 1
                authors = record.get('authors', 'Unknown authors')
                # Get PMID from _id field (stored by retrieval service)
                pmid = record.get('_id', 'No PMID available')
                title = record.get('title', 'No title available')
                
                # Debug: Log available fields for first few PubMed records
                if pubmed_count <= 3:
                    logger.info(f"🔍 PubMed record fields: {list(record.keys())}")
                    logger.info(f"🔍 PMID value (from '_id' field): {pmid}")
                
                formatted.append(f"{i}. [PUBMED] Authors: {authors}, PMID: {pmid}, Title: {title}")
                
            else:
                # Fallback for records without source tag (assume Vumedi for backward compatibility)
                author = record.get('author', 'Unknown author')
                featuring = record.get('featuring', 'Unknown specialist')
                link = record.get('link', 'No link available')
                title = record.get('title', 'No title available')
                formatted.append(f"{i}. [VUMEDI] Author: {author}, Featuring: {featuring}, Link: {link}, Title: {title}")
        
        logger.info(f"📊 Formatted Pinecone data: {vumedi_count} Vumedi records, {pubmed_count} PubMed records")
        return "\n".join(formatted)
    
    def _format_patient_profile(self, patient_profile: Dict[str, Any]) -> str:
        """Format patient profile for LLM input."""
        symptoms = patient_profile.get('symptoms', [])
        
        return f"""
        Symptoms: {', '.join(symptoms) if symptoms else 'Not specified'}

        """
    
    def _parse_ranking_response(self, response: str, providers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse LLM response to extract ranked NPI numbers and explanation."""
        try:
            import json
            import re
            
            # Clean the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            logger.info(f"DEBUG: Original response: {response[:200]}...")
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove ```
            cleaned_response = cleaned_response.strip()
            logger.info(f"Processing cleaned LLM response")
            
            # Try to parse as JSON first
            try:
                result = json.loads(cleaned_response)
                logger.info(f"Successfully parsed JSON response")
                if isinstance(result, dict) and 'providers' in result and 'explanation' in result:
                    # New format with 'providers' field - now contains doctor names with links
                    providers_data = result['providers']
                    logger.info(f"Parsed {len(providers_data)} provider entries from LLM response")
                    
                    # Extract doctor names, Vumedi content, and PubMed articles
                    doctor_names = []
                    doctor_links = {}
                    logger.info(f"Processing {len(providers_data)} provider entries from LLM response")
                    for i, provider_entry in enumerate(providers_data):
                        if isinstance(provider_entry, dict) and 'name' in provider_entry:
                            name = provider_entry['name']
                            
                            # Extract Vumedi content
                            vumedi_content = provider_entry.get('vumedi_content', [])
                            vumedi_links = []
                            for vumedi_item in vumedi_content:
                                if isinstance(vumedi_item, dict):
                                    vumedi_links.append({
                                        'link': vumedi_item.get('link', ''),
                                        'title': vumedi_item.get('title', 'Medical Content')
                                    })
                            
                            # Extract PubMed articles
                            pubmed_articles = provider_entry.get('pubmed_articles', [])
                            pubmed_links = []
                            for pubmed_item in pubmed_articles:
                                if isinstance(pubmed_item, dict):
                                    pubmed_links.append({
                                        'pmid': pubmed_item.get('pmid', pubmed_item.get('_id', '')),
                                        'title': pubmed_item.get('title', 'Research Article')
                                    })
                            
                            doctor_names.append(name)
                            doctor_links[name] = {
                                'vumedi_content': vumedi_links,
                                'pubmed_articles': pubmed_links
                            }
                            
                            logger.info(f"Doctor {name}: {len(vumedi_links)} Vumedi links, {len(pubmed_links)} PubMed articles")
                            
                        elif isinstance(provider_entry, str):
                            # Fallback for old format (just names)
                            doctor_names.append(provider_entry)
                            doctor_links[provider_entry] = {
                                'vumedi_content': [],
                                'pubmed_articles': []
                            }
                    
                    logger.info(f"Extracted {len(doctor_names)} doctor names with {len(doctor_links)} content entries")
                    
                    # Convert doctor names back to NPI numbers
                    npi_ranking = self._convert_names_to_npis(doctor_names, providers)
                    logger.info(f"Converted to {len(npi_ranking)} NPI numbers")
                    
                    # Count total content for logging
                    total_vumedi = sum(len(links['vumedi_content']) for links in doctor_links.values())
                    total_pubmed = sum(len(links['pubmed_articles']) for links in doctor_links.values())
                    logger.info(f"Returning {len(doctor_links)} doctor content entries: {total_vumedi} Vumedi links, {total_pubmed} PubMed articles")
                    
                    # Calculate scores and re-sort doctors by content count + medical school
                    logger.info("🎯 Calculating content scores and medical school scores...")
                    doctor_scores = {}
                    
                    for doctor_name, content in doctor_links.items():
                        vumedi_count = len(content['vumedi_content'])
                        pubmed_count = len(content['pubmed_articles'])
                        content_score = (vumedi_count + pubmed_count) * 4  # Each result counts as 4 points
                        
                        # Get medical school score for this doctor
                        # Find the NPI for this doctor name
                        doctor_npi = None
                        for provider in providers:
                            if provider.get('name', '').upper() == doctor_name:
                                doctor_npi = provider.get('npi', '')
                                break
                        
                        med_school_score = 0
                        if doctor_npi:
                            med_school_score = self._get_medical_school_score(doctor_npi)
                        
                        total_score = content_score + med_school_score
                        doctor_scores[doctor_name] = {
                            'npi': doctor_npi,
                            'score': total_score,
                            'content_score': content_score,
                            'vumedi_count': vumedi_count,
                            'pubmed_count': pubmed_count,
                            'med_school_score': med_school_score
                        }
                        logger.info(f"📊 {doctor_name}: {vumedi_count} Vumedi + {pubmed_count} PubMed (×4) + {med_school_score} Med School = {total_score} total")
                    
                    # Re-sort the NPI ranking based on content scores
                    if doctor_scores:
                        # Create a mapping from doctor names back to NPIs
                        name_to_npi = {}
                        for provider in providers:
                            provider_name = provider.get('name', '').upper()
                            if provider_name in doctor_scores:
                                name_to_npi[provider_name] = provider.get('npi', '')
                        
                        # Sort doctors by score (highest first)
                        sorted_doctors = sorted(doctor_scores.items(), key=lambda x: x[1]['score'], reverse=True)
                        logger.info(f"🏆 Top 5 doctors by total score (content + medical school):")
                        for i, (name, score_data) in enumerate(sorted_doctors[:5]):
                            logger.info(f"   {i+1}. {name}: {score_data['score']} total ({score_data['content_score']} content + {score_data['med_school_score']} med school)")
                        
                        # Rebuild NPI ranking in score order
                        re_sorted_npis = []
                        for doctor_name, score_data in sorted_doctors:
                            if doctor_name in name_to_npi and name_to_npi[doctor_name]:
                                re_sorted_npis.append(name_to_npi[doctor_name])
                        
                        # Update the ranking with the re-sorted NPIs
                        npi_ranking = re_sorted_npis
                        logger.info(f"✅ Re-sorted {len(npi_ranking)} NPIs by total score (content + medical school)")
                    else:
                        logger.warning("⚠️ No doctor scores calculated, keeping original GPT ranking")
                    
                    return {
                        'ranking': npi_ranking,
                        'explanation': result['explanation'],
                        'provider_links': doctor_links,  # Include both Vumedi and PubMed content for UI display
                        'provider_scores': doctor_scores  # Include scores for UI display
                    }
                else:
                    logger.warning("JSON response missing 'providers' or 'explanation' fields")
            except json.JSONDecodeError:
                pass
            
            # If JSON parsing fails, try to extract NPI numbers using regex
            npi_pattern = r'\b\d{10}\b'  # 10-digit NPI numbers
            found_npis = re.findall(npi_pattern, cleaned_response)
            
            if found_npis:
                return {
                    'ranking': found_npis,
                    'explanation': 'Ranking completed successfully.',
                    'provider_links': {},
                    'provider_scores': {}
                }
            
            # If no NPIs found, return original order
            logger.warning("Could not parse ranking response, returning original order")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Could not parse ranking response - showing providers in original order.',
                'provider_links': {},
                'provider_scores': {}
            }
            
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Error parsing ranking response - showing providers in original order.',
                'provider_links': {},
                'provider_scores': {}
            }
    
    def _convert_names_to_npis(self, doctor_names: List[str], providers: List[Dict[str, Any]]) -> List[str]:
        """Convert doctor names back to NPI numbers."""
        npi_ranking = []
        
        # Create a mapping from names to NPIs
        name_to_npi = {}
        for provider in providers:
            name = provider.get('name', '').strip().upper()
            npi = provider.get('npi', '')
            if name and npi:
                name_to_npi[name] = npi
        
        # Convert each doctor name to NPI
        for doctor_name in doctor_names:
            doctor_name_clean = doctor_name.strip().upper()
            if doctor_name_clean in name_to_npi:
                npi_ranking.append(name_to_npi[doctor_name_clean])
                logger.debug(f"✅ Matched '{doctor_name_clean}' to NPI {name_to_npi[doctor_name_clean]}")
            else:
                logger.warning(f"⚠️  Could not find NPI for doctor name: '{doctor_name_clean}'")
        
        return npi_ranking
    

    async def rank_npi_providers_by_treatment(
        self,
        npi_providers: List[Dict[str, Any]],
        treatment_pinecone_data: Dict[str, Any],
        patient_profile: Dict[str, Any],
        max_providers: int = 10000,
        top_cms_npis: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Rank ALL NPI providers by score (publications + videos), then by GPT relevance within score groups.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            treatment_pinecone_data: Dictionary with treatment-specific Pinecone data
            patient_profile: Patient profile with symptoms, diagnosis, etc.
            max_providers: Maximum number of providers to rank per treatment (default: 10000)
            top_cms_npis: Optional set of NPI strings for top 25 CMS providers (for clinical volume bonus)
            
        Returns:
            Dictionary with treatment-specific rankings showing ALL providers with scores
        """
        try:
            logger.info(f"🎯 === TREATMENT-SPECIFIC RANKING STARTED (SCORE-BASED) ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📋 Treatments to rank: {len(treatment_pinecone_data)}")
            
            treatment_rankings = {}
            
            # Rank providers for each treatment option
            for treatment_id, treatment_data in treatment_pinecone_data.items():
                treatment_name = treatment_data.get("name", f"Treatment {treatment_id}")
                all_pinecone_data = treatment_data.get("results", [])
                
                # Filter to only verified results for ranking
                pinecone_data = [result for result in all_pinecone_data if result.get("_verified") == True]
                
                logger.info(f"🔍 Ranking providers for treatment: {treatment_name}")
                logger.info(f"📊 Total Pinecone data for {treatment_name}: {len(all_pinecone_data)} records")
                logger.info(f"✅ Using verified results for ranking: {len(pinecone_data)} records")
                
                if not pinecone_data:
                    # No Pinecone data - return all providers with zero scores
                    logger.warning(f"⚠️  No Pinecone data for treatment {treatment_name}, returning all providers with zero scores")
                    ranked_npis = [p.get('npi', '') for p in npi_providers if p.get('npi')]
                    treatment_rankings[treatment_id] = {
                        "name": treatment_name,
                        "ranked_providers": ranked_npis,
                        "explanation": f"No specialist information found for {treatment_name}. Showing all {len(ranked_npis)} providers with zero scores.",
                        "provider_links": {},
                        "provider_scores": {}
                    }
                    continue
                
                # Use GPT to rank providers with Pinecone matches
                ranking_result = await self.rank_npi_providers(
                    npi_providers=npi_providers,
                    pinecone_data=pinecone_data,
                    patient_profile=patient_profile,
                    max_providers=max_providers,
                    top_cms_npis=top_cms_npis
                )
                
                # Get the ranked NPIs and scores from GPT (already calculated with new scoring system)
                matched_npis = ranking_result.get("ranking", [])
                provider_links = ranking_result.get("provider_links", {})
                provider_scores = ranking_result.get("provider_scores", {})  # Keyed by NPI from rank_npi_providers
                gpt_explanation = ranking_result.get("explanation", "")
                
                # Note: provider_scores is keyed by NPI (string), not by name
                # Sort matched providers by score (descending), then by NPI
                matched_providers_with_scores = [
                    (npi, scores) for npi, scores in provider_scores.items() if npi in matched_npis
                ]
                matched_providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
                
                # Reorder matched NPIs by score
                matched_npis_by_score = [npi for npi, _ in matched_providers_with_scores]
                
                # Find providers that were NOT matched
                matched_npi_set = set(matched_npis_by_score)
                unmatched_npis = [
                    p.get('npi', '') 
                    for p in npi_providers 
                    if p.get('npi') and p.get('npi') not in matched_npi_set
                ]
                
                # Add scores for unmatched doctors (only medical school score since no content)
                # Key by NPI to keep consistency
                # Get certification scores for unmatched providers
                all_unmatched_npis = [str(npi) for npi in unmatched_npis if npi]
                certification_scores_unmatched = self._batch_get_certification_scores(all_unmatched_npis) if all_unmatched_npis else {}
                
                # Initialize raw scores dictionary for unmatched providers (for weighted scoring)
                unmatched_raw_scores = {}
                
                for npi in unmatched_npis:
                    if npi and npi not in provider_scores:
                        # Get medical school score even for unmatched doctors
                        med_school_score = self._get_medical_school_score(npi)
                        cert_info = certification_scores_unmatched.get(str(npi), {})
                        certification_points = cert_info.get('certification_points', 0) if isinstance(cert_info, dict) else 0
                        is_certified = cert_info.get('is_certified', False) if isinstance(cert_info, dict) else False
                        has_abns = cert_info.get('has_abns', False) if isinstance(cert_info, dict) else False
                        has_aoa = cert_info.get('has_aoa', False) if isinstance(cert_info, dict) else False
                        abns_points = cert_info.get('abns_points', 0) if isinstance(cert_info, dict) else 0
                        aoa_points = cert_info.get('aoa_points', 0) if isinstance(cert_info, dict) else 0
                        provider_info = next((p for p in npi_providers if p.get('npi') == npi), None)
                        years_experience_raw = None
                        if provider_info:
                            years_experience_raw = provider_info.get('yearsExperience', provider_info.get('years_experience'))
                        years_experience, experience_points = self._calculate_experience_points(years_experience_raw)
                        
                        # Check if unmatched provider is in top 25 CMS results (clinical volume bonus)
                        clinical_volume_points = 0
                        npi_str = str(npi)
                        residency_score = 0  # Unmatched providers don't have residency score calculated
                        if top_cms_npis:
                            if npi_str in top_cms_npis:
                                clinical_volume_points = 20
                                logger.info(f"✅ [Ranking] Unmatched NPI {npi_str} ({provider_info.get('first_name', '') if provider_info else ''} {provider_info.get('last_name', '') if provider_info else ''}) is in top 25 CMS results - adding 20 clinical volume points")
                            # Check for Theodore Schwartz specifically
                            if provider_info:
                                first_name = provider_info.get('first_name', '').upper()
                                last_name = provider_info.get('last_name', '').upper()
                                if 'THEODORE' in first_name and 'SCHWARTZ' in last_name:
                                    logger.info(f"🔍 [Ranking] Unmatched Theodore Schwartz NPI {npi_str} - in top_cms_npis? {npi_str in top_cms_npis}")
                        else:
                            logger.debug(f"🔍 DEBUG: No top_cms_npis provided for unmatched NPI {npi_str}")
                        
                        # Store raw scores for weighted calculation
                        unmatched_raw_scores[npi] = {
                            'vumedi_raw': 0,  # Unmatched providers have no content
                            'pubmed_raw': 0,
                            'training_raw': med_school_score + residency_score + certification_points,
                            'experience_raw': experience_points,
                            'clinical_volume_raw': 1.0 if clinical_volume_points > 0 else 0.0
                        }
                        
                        total_score = med_school_score + experience_points + certification_points + clinical_volume_points
                        provider_scores[npi] = {
                            'npi': npi,
                            'score': total_score,
                            'content_score': 0,
                            'vumedi_count': 0,
                            'pubmed_count': 0,
                            'pubmed_first_author_count': 0,
                            'pubmed_middle_author_count': 0,
                            'pubmed_last_author_count': 0,
                            'pubmed_base_points': 0,
                            'pubmed_weighted_points': 0,
                            'clinical_volume_points': clinical_volume_points,
                            'pubmed_quartile_q1_count': 0,
                            'pubmed_quartile_q2_count': 0,
                            'pubmed_quartile_q3_count': 0,
                            'pubmed_quartile_q4_count': 0,
                            'pubmed_quartile_no_data_count': 0,
                            'experience_points': experience_points,
                            'years_experience': years_experience,
                            'med_school_score': med_school_score,
                            'certification_points': certification_points,
                            'is_certified': is_certified,
                            'has_abns': has_abns,
                            'has_aoa': has_aoa,
                            'abns_points': abns_points,
                            'aoa_points': aoa_points
                        }
                
                # Calculate weighted scores for unmatched providers
                if unmatched_raw_scores:
                    # Combine matched and unmatched raw scores for normalization
                    all_raw_scores = {**raw_component_scores, **unmatched_raw_scores}
                    weighted_scores = self._calculate_weighted_score(all_raw_scores)
                    
                    # Update unmatched provider scores with weighted values
                    for npi, weighted_data in weighted_scores.items():
                        if npi in provider_scores and npi in unmatched_raw_scores:
                            provider_scores[npi]['score'] = weighted_data['final_score']
                            # Store weighted breakdown for frontend display
                            provider_scores[npi]['weighted_breakdown'] = {
                                'clinical_volume': {
                                    'percentage': weighted_data['clinical_volume_pct'],
                                    'weighted_points': weighted_data['clinical_volume_weighted'],
                                    'weight': 40.0
                                },
                                'pubmed': {
                                    'percentage': weighted_data['pubmed_pct'],
                                    'weighted_points': weighted_data['pubmed_weighted'],
                                    'weight': 40.0
                                },
                                'training': {
                                    'percentage': weighted_data['training_pct'],
                                    'weighted_points': weighted_data['training_weighted'],
                                    'weight': 10.0
                                },
                                'experience': {
                                    'percentage': weighted_data['experience_pct'],
                                    'weighted_points': weighted_data['experience_weighted'],
                                    'weight': 6.0
                                },
                                'vumedi': {
                                    'percentage': weighted_data['vumedi_pct'],
                                    'weighted_points': weighted_data['vumedi_weighted'],
                                    'weight': 4.0
                                }
                            }
                    # Also update matched providers if not already updated
                    for npi, weighted_data in weighted_scores.items():
                        if npi in provider_scores and npi not in unmatched_raw_scores and 'weighted_breakdown' not in provider_scores[npi]:
                            provider_scores[npi]['score'] = weighted_data['final_score']
                            provider_scores[npi]['weighted_breakdown'] = {
                                'clinical_volume': {
                                    'percentage': weighted_data['clinical_volume_pct'],
                                    'weighted_points': weighted_data['clinical_volume_weighted'],
                                    'weight': 40.0
                                },
                                'pubmed': {
                                    'percentage': weighted_data['pubmed_pct'],
                                    'weighted_points': weighted_data['pubmed_weighted'],
                                    'weight': 40.0
                                },
                                'training': {
                                    'percentage': weighted_data['training_pct'],
                                    'weighted_points': weighted_data['training_weighted'],
                                    'weight': 10.0
                                },
                                'experience': {
                                    'percentage': weighted_data['experience_pct'],
                                    'weighted_points': weighted_data['experience_weighted'],
                                    'weight': 6.0
                                },
                                'vumedi': {
                                    'percentage': weighted_data['vumedi_pct'],
                                    'weighted_points': weighted_data['vumedi_weighted'],
                                    'weight': 4.0
                                }
                            
                            # Ensure ALL providers have weighted_breakdown (even if all zeros)
                            # This is needed for providers without matches or with zero scores
                            for npi in provider_scores:
                                if 'weighted_breakdown' not in provider_scores[npi]:
                                    # Create a zero-weighted breakdown for providers without one
                                    provider_scores[npi]['weighted_breakdown'] = {
                                        'clinical_volume': {
                                            'raw': 0.0,
                                            'percentage': 0.0,
                                            'weighted_points': 0.0,
                                            'weight': 40.0
                                        },
                                        'pubmed': {
                                            'raw': 0.0,
                                            'percentage': 0.0,
                                            'weighted_points': 0.0,
                                            'weight': 40.0
                                        },
                                        'training': {
                                            'raw': 0.0,
                                            'percentage': 0.0,
                                            'weighted_points': 0.0,
                                            'weight': 10.0
                                        },
                                        'experience': {
                                            'raw': 0.0,
                                            'percentage': 0.0,
                                            'weighted_points': 0.0,
                                            'weight': 6.0
                                        },
                                        'vumedi': {
                                            'raw': 0.0,
                                            'percentage': 0.0,
                                            'weighted_points': 0.0,
                                            'weight': 4.0
                                        }
                                    }
                                    # Also ensure score is set (might be 0 for unmatched providers)
                                    if 'score' not in provider_scores[npi]:
                                        provider_scores[npi]['score'] = 0.0
                
                # Sort ALL providers (matched + unmatched) by their total scores
                # provider_scores is keyed by NPI, so iterate correctly
                all_providers_with_scores = [
                    (npi, scores) for npi, scores in provider_scores.items()
                ]
                all_providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
                all_ranked_npis = [npi for npi, _ in all_providers_with_scores]
                
                # Update explanation
                doctors_with_content = len(matched_providers_with_scores)
                total_vumedi = sum(scores['vumedi_count'] for _, scores in matched_providers_with_scores)
                total_pubmed = sum(scores['pubmed_count'] for _, scores in matched_providers_with_scores)
                total_content_score = sum(scores['content_score'] for _, scores in matched_providers_with_scores)
                total_med_school_score = sum(scores['med_school_score'] for _, scores in matched_providers_with_scores)
                total_experience_points = sum(scores.get('experience_points', 0) for _, scores in matched_providers_with_scores)
                
                explanation = (
                    f"Ranked {len(all_ranked_npis)} providers by content score (×4), medical school ranking, and experience bonus. "
                    f"{doctors_with_content} providers found with {total_vumedi} Vumedi videos and {total_pubmed} PubMed articles (×4 = {total_content_score} points) plus {total_med_school_score} medical school points and {total_experience_points} experience points related to {treatment_name}. "
                    f"Providers with higher total scores (content + medical school + experience) are ranked higher."
                )
                
                # Store the results for this treatment
                treatment_rankings[treatment_id] = {
                    "name": treatment_name,
                    "ranked_providers": all_ranked_npis,
                    "explanation": explanation,
                    "provider_links": provider_links,
                    "provider_scores": provider_scores
                }
                
                logger.info(f"✅ Completed ranking for {treatment_name}: {doctors_with_content} with content, {len(unmatched_npis)} with zero scores")
            
            logger.info(f"✅ === TREATMENT-SPECIFIC RANKING COMPLETED ===")
            logger.info(f"📊 Total treatments ranked: {len(treatment_rankings)}")
            
            return {
                "treatment_rankings": treatment_rankings,
                "total_treatments": len(treatment_rankings)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in treatment-specific ranking: {str(e)}")
            raise