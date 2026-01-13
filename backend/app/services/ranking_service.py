"""
Ranking service for combining NPI providers with specialist data.

This service takes a list of NPI providers and specialist information,
then ranks the NPI providers algorithmically based on relevance to the specialist data.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from ..models.specialist_recommendation import SpecialistRecommendation
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RankingService:
    """Service for ranking NPI providers based on specialist information."""
    
    # Scoring weights (must sum to 100)
    WEIGHT_CLINICAL_VOLUME = 10.0  # Clinical Volume weight
    WEIGHT_PUBMED = 70.0  # PubMed Articles weight
    WEIGHT_TRAINING = 10.0  # Training (Med school + Residency + Certification) weight
    WEIGHT_EXPERIENCE = 5.0  # Experience weight
    WEIGHT_VUMEDI = 5.0  # Medical Lectures (Vumedi) weight
    
    # Validate weights sum to 100
    _WEIGHT_TOTAL = WEIGHT_CLINICAL_VOLUME + WEIGHT_PUBMED + WEIGHT_TRAINING + WEIGHT_EXPERIENCE + WEIGHT_VUMEDI
    assert abs(_WEIGHT_TOTAL - 100.0) < 0.01, f"Scoring weights must sum to 100, but sum to {_WEIGHT_TOTAL}"
    
    def __init__(self, db: Session = None):
        self.db = db
    
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
    
    def _calculate_percentile(
        self,
        value: float,
        all_values: List[float]
    ) -> float:
        """
        Calculate percentile for a given value against a list of all values.
        
        Percentile = (count of values below this value / total count) * 100
        
        Args:
            value: The value to calculate percentile for
            all_values: List of all values to compare against
            
        Returns:
            Percentile (0-100) where 0 = lowest, 100 = highest
        """
        if not all_values or value is None or value == 0:
            return 0.0
        
        # Count how many values are below this value
        values_below = sum(1 for v in all_values if v < value)
        total_count = len(all_values)
        
        if total_count == 0:
            return 0.0
        
        # Calculate percentile: percentage of providers with lower Tot_Srvcs
        percentile = (values_below / total_count) * 100
        
        return round(percentile, 2)
    
    def _calculate_weighted_score(
        self,
        raw_scores: Dict[str, Dict[str, float]],
        cms_tot_srvcs: Optional[Dict[str, int]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate weighted scores from raw component scores.
        
        Weights:
        - Clinical Volume: 38%
        - PubMed: 38%
        - Training: 10% (Med school + Residency + Certification)
        - Experience: 6%
        - Vumedi: 3%
        - Reviews: 5%
        
        Args:
            raw_scores: Dict mapping NPI to dict of raw component scores
            cms_tot_srvcs: Optional dict mapping NPI (string) to Tot_Srvcs (int) for percentile calculation
            
        Returns:
            Dict mapping NPI to weighted score components and final score
        """
        if not raw_scores:
            return {}
        
        # Calculate percentile distribution from ALL CMS providers (if available)
        percentile_map = {}
        if cms_tot_srvcs:
            all_tot_srvcs = list(cms_tot_srvcs.values())
            # Create percentile map for each provider in raw_scores
            for npi, scores in raw_scores.items():
                clinical_volume_raw = scores.get('clinical_volume_raw', 0)
                if clinical_volume_raw > 0:
                    percentile_map[npi] = self._calculate_percentile(
                        clinical_volume_raw,
                        all_tot_srvcs
                    )
                else:
                    percentile_map[npi] = 0.0
        
        # Calculate percentile distribution for PubMed from raw_scores
        pubmed_percentile_map = {}
        all_pubmed_raw = [scores.get('pubmed_raw', 0) for scores in raw_scores.values()]
        for npi, scores in raw_scores.items():
            pubmed_raw = scores.get('pubmed_raw', 0)
            if pubmed_raw > 0:
                pubmed_percentile_map[npi] = self._calculate_percentile(
                    pubmed_raw,
                    all_pubmed_raw
                )
            else:
                pubmed_percentile_map[npi] = 0.0
        
        # Find max values for normalization (including clinical volume which is now percentage-based)
        # Only calculate max from providers that actually have clinical volume data (non-zero)
        # This ensures entities/facilities not in cms_tot_srvcs don't affect the max
        clinical_volume_values = [scores.get('clinical_volume_raw', 0) for scores in raw_scores.values() if scores.get('clinical_volume_raw', 0) > 0]
        max_clinical_volume = max(clinical_volume_values, default=1.0) if clinical_volume_values else 1.0
        max_pubmed = max((scores.get('pubmed_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_vumedi = max((scores.get('vumedi_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_training = max((scores.get('training_raw', 0) for scores in raw_scores.values()), default=1.0)
        max_experience = max((scores.get('experience_raw', 0) for scores in raw_scores.values()), default=1.0)
        
        # Avoid division by zero
        max_clinical_volume = max(max_clinical_volume, 1.0)
        max_pubmed = max(max_pubmed, 1.0)
        max_vumedi = max(max_vumedi, 1.0)
        max_training = max(max_training, 1.0)
        max_experience = max(max_experience, 1.0)
        
        # Store max values for frontend display
        max_values = {
            'clinical_volume': max_clinical_volume,
            'pubmed': max_pubmed,
            'vumedi': max_vumedi,
            'training': max_training,
            'experience': max_experience
        }
        
        weighted_scores = {}
        
        for npi, scores in raw_scores.items():
            # Normalize components to 0-1 (0-100%)
            clinical_volume_raw_value = scores.get('clinical_volume_raw', 0)
            logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: _calculate_weighted_score for NPI {npi}: clinical_volume_raw={clinical_volume_raw_value}, max_clinical_volume={max_clinical_volume}")
            clinical_volume_pct = min(clinical_volume_raw_value / max_clinical_volume, 1.0) if max_clinical_volume > 0 else 0.0  # Percentage of max Tot_Srvcs
            pubmed_pct = min(scores.get('pubmed_raw', 0) / max_pubmed, 1.0)
            vumedi_pct = min(scores.get('vumedi_raw', 0) / max_vumedi, 1.0)
            training_pct = min(scores.get('training_raw', 0) / max_training, 1.0)
            experience_pct = min(scores.get('experience_raw', 0) / max_experience, 1.0)
            
            # Apply weights and calculate final score (0-100)
            clinical_volume_weighted = clinical_volume_pct * self.WEIGHT_CLINICAL_VOLUME
            pubmed_weighted = pubmed_pct * self.WEIGHT_PUBMED
            training_weighted = training_pct * self.WEIGHT_TRAINING
            experience_weighted = experience_pct * self.WEIGHT_EXPERIENCE
            vumedi_weighted = vumedi_pct * self.WEIGHT_VUMEDI
            
            final_score = clinical_volume_weighted + pubmed_weighted + training_weighted + experience_weighted + vumedi_weighted
            
            # Store raw value in breakdown_details
            breakdown_clinical_volume_raw = clinical_volume_raw_value
            logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: Storing breakdown_details for NPI {npi}: clinical_volume.raw={breakdown_clinical_volume_raw}")
            
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
                'final_score': final_score,
                'breakdown_details': {  # Store details for frontend display
                    'clinical_volume': {
                        'raw': breakdown_clinical_volume_raw,
                        'max': max_values['clinical_volume'],
                        'percentage': clinical_volume_pct * 100,
                        'weighted_points': clinical_volume_weighted,
                        'weight': self.WEIGHT_CLINICAL_VOLUME,
                        'percentile': percentile_map.get(npi, 0.0)
                    },
                    'pubmed': {
                        'raw': scores.get('pubmed_raw', 0),
                        'max': max_values['pubmed'],
                        'percentage': pubmed_pct * 100,
                        'weighted_points': pubmed_weighted,
                        'weight': self.WEIGHT_CLINICAL_VOLUME,
                        'percentile': pubmed_percentile_map.get(npi, 0.0)
                    },
                    'training': {'raw': scores.get('training_raw', 0), 'max': max_values['training'], 'percentage': training_pct * 100, 'weighted_points': training_weighted, 'weight': 10},
                    'experience': {'raw': scores.get('experience_raw', 0), 'max': max_values['experience'], 'percentage': experience_pct * 100, 'weighted_points': experience_weighted, 'weight': 6},
                    'vumedi': {'raw': scores.get('vumedi_raw', 0), 'max': max_values['vumedi'], 'percentage': vumedi_pct * 100, 'weighted_points': vumedi_weighted, 'weight': 3},
                }
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
        specialist_data: List[Dict[str, Any]], 
        patient_profile: Dict[str, Any],
        max_providers: int = 10000,
        cms_tot_srvcs: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Rank NPI providers based on simple exact name matching with specialist data.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            specialist_data: List of specialist information (Vumedi/PubMed)
            patient_profile: Patient profile (not used, kept for compatibility)
            max_providers: Maximum number of providers to rank (default: 10000)
            cms_tot_srvcs: Optional dict mapping NPI (string) to Tot_Srvcs (int) for clinical volume scoring
            
        Returns:
            Dictionary with 'ranking' (list of NPI numbers), 'provider_links', and 'provider_scores'
        """
        try:
            logger.info(f"🎯 === SIMPLE NAME MATCHING RANKING STARTED ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📊 Max providers to rank: {max_providers}")
            logger.info(f"📊 Specialist records: {len(specialist_data)}")
            
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
            
            # Process specialist data for matches
            for record in specialist_data:
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
            
            logger.info(f"✅ Found {len(provider_matches)} providers with PubMed/Vumedi matches")
            
            # Batch fetch all medical school scores for all NPIs at once
            # Normalize all NPIs to strings for consistent lookup
            all_npis = set()
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
            
            logger.info(f"🔍 Collecting raw data for ALL {len(providers_to_rank)} providers...")
            
            # Process ALL providers (not just those with matches)
            # Collect all raw data first, then calculate weighted scores once
            for idx, provider in enumerate(providers_to_rank):
                try:
                    npi = provider.get('npi', '')
                    if not npi:
                        continue
                    
                    npi_str = str(npi)
                    logger.debug(f"🔍 DEBUG: Processing provider {idx+1}/{len(providers_to_rank)}: NPI={npi_str}")
                    
                    # Check if this provider has PubMed/Vumedi matches
                    matches = provider_matches.get(npi, {})
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
                    years_experience_raw = provider.get('yearsExperience', provider.get('years_experience'))
                    years_experience, experience_points = self._calculate_experience_points(years_experience_raw)
                    
                    # Log matched PubMed articles for top providers
                    if pubmed_count > 0 and len(provider_links) < 20:
                        provider_name = provider.get('name', '') or npi_str
                        try:
                            pubmed_titles = [art.get('title', 'No title')[:80] for art in pubmed_articles[:3]]
                            pmids = [art.get('pmid', '') for art in pubmed_articles]
                            logger.info(f"📋 Provider {provider_name} (NPI {npi_str}) matched {pubmed_count} PubMed articles: PMIDs={pmids[:5]}")
                        except Exception as e:
                            logger.error(f"❌ DEBUG: Error extracting PMIDs for NPI {npi_str}: {e}")
                            logger.error(f"❌ DEBUG: matches['pubmed_articles'] type: {type(matches.get('pubmed_articles'))}")
                    
                    # Build provider_links for all providers (empty lists if no matches)
                    provider_links[npi_str] = {
                        'vumedi_content': matches.get('vumedi_content', []),
                        'pubmed_articles': matches.get('pubmed_articles', [])
                    }
                    
                    # Get training and certification scores
                    med_school_score = med_school_scores.get(npi_str, 0)
                    residency_score = residency_scores.get(npi_str, 0)
                    cert_info = certification_scores.get(npi_str, {})
                    certification_points = cert_info.get('certification_points', 0) if isinstance(cert_info, dict) else 0
                    
                    # Calculate clinical volume raw score (Tot_Srvcs from CMS)
                    clinical_volume_raw = 0.0
                    if cms_tot_srvcs:
                        if npi_str in cms_tot_srvcs:
                            clinical_volume_raw = float(cms_tot_srvcs[npi_str])
                            # Log for top providers or specific NPIs (like Theodore Schwartz)
                            if npi_str in ['1811916455'] or idx < 10:
                                logger.info(f"📊 CLINICAL_VOLUME: NPI {npi_str} has Tot_Srvcs: {clinical_volume_raw} from CMS")
                            else:
                                logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: NPI {npi_str} has Tot_Srvcs: {clinical_volume_raw} from CMS")
                        else:
                            # Log for top providers or specific NPIs (like Theodore Schwartz)
                            if npi_str in ['1811916455'] or idx < 10:
                                logger.warning(f"⚠️  CLINICAL_VOLUME: NPI {npi_str} NOT found in cms_tot_srvcs (has {len(cms_tot_srvcs)} entries)")
                                logger.info(f"📊 Sample NPIs in cms_tot_srvcs: {list(cms_tot_srvcs.keys())[:10]}")
                            else:
                                logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: NPI {npi_str} NOT found in cms_tot_srvcs (has {len(cms_tot_srvcs)} entries)")
                    else:
                        if npi_str in ['1811916455'] or idx < 10:
                            logger.warning(f"⚠️  CLINICAL_VOLUME: cms_tot_srvcs is None/empty for NPI {npi_str}")
                        else:
                            logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: cms_tot_srvcs is None/empty for NPI {npi_str}")
                    
                    # Calculate raw component scores for weighted system
                    # Store raw scores for normalization pass (for ALL providers)
                    raw_component_scores[npi_str] = {
                        'vumedi_raw': vumedi_count * 4,  # Vumedi raw score (0 if no matches)
                        'pubmed_raw': pubmed_weighted_points,  # PubMed raw score (0 if no matches, already weighted by quartiles)
                        'training_raw': med_school_score + residency_score + certification_points,  # Training raw score
                        'experience_raw': experience_points,  # Experience raw score
                        'clinical_volume_raw': clinical_volume_raw  # Tot_Srvcs from CMS (0 if not in CMS data, will be normalized to percentage)
                    }
                    logger.debug(f"📊 CLINICAL_VOLUME_DEBUG: Stored raw_component_scores[{npi_str}] with clinical_volume_raw={clinical_volume_raw}")
                    
                    # Extract certification details
                    is_certified = cert_info.get('is_certified', False) if isinstance(cert_info, dict) else False
                    has_abns = cert_info.get('has_abns', False) if isinstance(cert_info, dict) else False
                    has_aoa = cert_info.get('has_aoa', False) if isinstance(cert_info, dict) else False
                    abns_points = cert_info.get('abns_points', 0) if isinstance(cert_info, dict) else 0
                    aoa_points = cert_info.get('aoa_points', 0) if isinstance(cert_info, dict) else 0
                    
                    logger.debug(
                        f"🔍 DEBUG: NPI {npi_str} - Med school: {med_school_score}, "
                        f"Residency: {residency_score}, Experience: {experience_points} (from {years_experience} years), "
                        f"Certification: {certification_points} (ABNS: {abns_points}, AOA: {aoa_points}), "
                        f"Clinical Volume: {clinical_volume_raw}, "
                        f"Vumedi: {vumedi_count}, PubMed: {pubmed_count} (weighted: {pubmed_weighted_points})"
                    )
                    
                    # Build provider_scores for ALL providers (score will be calculated after collecting all raw data)
                    provider_scores[npi_str] = {
                        'score': 0,  # Will be replaced with weighted score after all data is collected
                        'med_school_score': med_school_score,
                        'residency_score': residency_score,
                        'experience_points': experience_points,
                        'certification_points': certification_points,
                        'clinical_volume_points': 0,  # Deprecated - now using percentage-based scoring via weighted_breakdown
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
                        'npi': npi_str
                    }
                        
                except Exception as e:
                    logger.error(f"❌ DEBUG: Error processing provider NPI {npi_str}: {e}")
                    import traceback
                    logger.error(f"❌ DEBUG: Traceback:\n{traceback.format_exc()}")
                    # Continue with next provider instead of crashing
                    continue
            
            logger.info(f"✅ Collected raw data for {len(raw_component_scores)} providers")
            
            # Calculate weighted scores from raw component scores for ALL providers at once
            if raw_component_scores:
                logger.info(f"📊 Calculating weighted scores for all {len(raw_component_scores)} providers...")
                weighted_scores = self._calculate_weighted_score(raw_component_scores, cms_tot_srvcs=cms_tot_srvcs)
                # Update provider_scores with weighted values for ALL providers
                for npi_str, weighted_data in weighted_scores.items():
                    if npi_str in provider_scores:
                        provider_scores[npi_str]['score'] = weighted_data['final_score']
                        # Store weighted breakdown for frontend display
                        provider_scores[npi_str]['weighted_breakdown'] = {
                            'clinical_volume': {
                                'percentage': weighted_data['clinical_volume_pct'],
                                'weighted_points': weighted_data['clinical_volume_weighted'],
                                'weight': self.WEIGHT_CLINICAL_VOLUME
                            },
                            'pubmed': {
                                'percentage': weighted_data['pubmed_pct'],
                                'weighted_points': weighted_data['pubmed_weighted'],
                                'weight': self.WEIGHT_PUBMED
                            },
                            'training': {
                                'percentage': weighted_data['training_pct'],
                                'weighted_points': weighted_data['training_weighted'],
                                'weight': self.WEIGHT_TRAINING
                            },
                            'experience': {
                                'percentage': weighted_data['experience_pct'],
                                'weighted_points': weighted_data['experience_weighted'],
                                'weight': self.WEIGHT_EXPERIENCE
                            },
                            'vumedi': {
                                'percentage': weighted_data['vumedi_pct'],
                                'weighted_points': weighted_data['vumedi_weighted'],
                                'weight': self.WEIGHT_VUMEDI
                            },
                            'breakdown_details': weighted_data.get('breakdown_details', {})
                        }
            
            # Ensure ALL providers have weighted_breakdown (even if all zeros)
            # This is needed for providers without PubMed/Vumedi matches or with zero scores
            for npi_str in provider_scores:
                if 'weighted_breakdown' not in provider_scores[npi_str]:
                    provider_scores[npi_str]['weighted_breakdown'] = {
                        'clinical_volume': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': self.WEIGHT_CLINICAL_VOLUME
                        },
                        'pubmed': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': self.WEIGHT_PUBMED
                        },
                        'training': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': self.WEIGHT_TRAINING
                        },
                        'experience': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': self.WEIGHT_EXPERIENCE
                        },
                        'vumedi': {
                            'raw': 0.0,
                            'percentage': 0.0,
                            'weighted_points': 0.0,
                            'weight': self.WEIGHT_VUMEDI
                        }
                    }
            
            # Sort providers by score (descending), then by name
            providers_with_scores = []
            for provider in providers_to_rank:
                npi = provider.get('npi', '')
                if npi:
                    npi_str = str(npi)
                    if npi_str in provider_scores:
                        providers_with_scores.append((
                            provider.get('name', ''),
                            provider_scores[npi_str]
                        ))
            
            # Sort by score descending, then name ascending
            providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
            
            # Extract ranked NPI list
            ranked_npis = [score['npi'] for _, score in providers_with_scores]
            
            providers_with_pubmed = len([npi for npi in ranked_npis if provider_scores.get(npi, {}).get('pubmed_count', 0) > 0])
            logger.info(f"✅ === RANKING COMPLETED ===")
            logger.info(f"✅ Processed {len(ranked_npis)} providers ({providers_with_pubmed} with PubMed/Vumedi matches)")
            logger.info(f"🏆 Top 10 ranked NPIs: {ranked_npis[:10]}")
            
            # Batch fetch reviews for all ranked providers (same as PubMed)
            logger.info(f"📦 Batch fetching reviews for {len(ranked_npis)} providers")
            # Debug: Check if patient_profile has search_query
            if isinstance(patient_profile, dict):
                search_query = patient_profile.get('search_query', 'NOT FOUND')
                logger.info(f"🔍 [Reviews Debug] patient_profile.search_query = {search_query[:100] if search_query != 'NOT FOUND' else 'NOT FOUND'}")
            else:
                logger.warning(f"⚠️ [Reviews Debug] patient_profile is not a dict: {type(patient_profile)}")
            reviews_data_by_npi = self._batch_fetch_reviews(ranked_npis, patient_profile)
            
            # Extract relevant review counts for scoring and add reviews to provider_links
            reviews_counts = {}  # NPI -> relevant_count
            theodore_npi = '1811916455'
            
            for npi in ranked_npis:
                npi_str = str(npi)  # Normalize to string for lookup
                review_data = reviews_data_by_npi.get(npi_str, {})
                reviews_list = review_data.get('reviews', [])
                relevant_count = review_data.get('relevant_count', 0)
                reviews_counts[npi] = relevant_count
                
                # Detailed logging for Theodore Schwartz
                if npi_str == theodore_npi or npi == theodore_npi:
                    logger.info(f"🔍 [Theodore Debug] Extracting reviews_counts:")
                    logger.info(f"🔍 [Theodore Debug]   - npi (original): {npi}, npi_str: {npi_str}")
                    logger.info(f"🔍 [Theodore Debug]   - review_data from reviews_data_by_npi: {review_data}")
                    logger.info(f"🔍 [Theodore Debug]   - relevant_count extracted: {relevant_count}")
                    logger.info(f"🔍 [Theodore Debug]   - reviews_list length: {len(reviews_list)}")
                    logger.info(f"🔍 [Theodore Debug]   - reviews_counts[{npi}] = {relevant_count}")
                    logger.info(f"🔍 [Theodore Debug]   - reviews_counts keys: {list(reviews_counts.keys())[:5]}...")
                
                if npi in provider_links:
                    provider_links[npi]['reviews'] = reviews_list
                else:
                    # Provider has no PubMed/Vumedi but might have reviews
                    provider_links[npi] = {
                        'vumedi_content': [],
                        'pubmed_articles': [],
                        'reviews': reviews_list
                    }
            
            logger.info(f"✅ Added reviews to provider_links for {len(reviews_data_by_npi)} providers")
            
            # Note: Reviews are included in provider_links for UI display but NOT used in scoring
            
            return {
                'ranking': ranked_npis,
                'provider_links': provider_links,  # NPI-keyed
                'provider_scores': {npi: score for npi, score in provider_scores.items()}  # NPI-keyed
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
                'provider_links': {},
                'provider_scores': {}
            }
    
    async def rank_npi_providers_by_treatment(
        self,
        npi_providers: List[Dict[str, Any]],
        treatment_specialist_data: Dict[str, Any],
        patient_profile: Dict[str, Any],
        max_providers: int = 10000,
        cms_tot_srvcs: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Rank ALL NPI providers by score (publications + videos), then by GPT relevance within score groups.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            treatment_specialist_data: Dictionary with treatment-specific specialist data
            patient_profile: Patient profile
            max_providers: Maximum number of providers to rank per treatment (default: 10000)
            cms_tot_srvcs: Optional dict mapping NPI (string) to Tot_Srvcs (int) for clinical volume scoring
            
        Returns:
            Dictionary with treatment-specific rankings showing ALL providers with scores
        """
        try:
            logger.info(f"🎯 === TREATMENT-SPECIFIC RANKING STARTED (SCORE-BASED) ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📋 Treatments to rank: {len(treatment_specialist_data)}")
            
            treatment_rankings = {}
            
            # Rank providers for each treatment option
            for treatment_id, treatment_data in treatment_specialist_data.items():
                treatment_name = treatment_data.get("name", f"Treatment {treatment_id}")
                all_specialist_data = treatment_data.get("results", [])
                
                # Filter to only verified results for ranking
                specialist_data = [result for result in all_specialist_data if result.get("_verified") == True]
                
                logger.info(f"🔍 Ranking providers for treatment: {treatment_name}")
                logger.info(f"📊 Total specialist data for {treatment_name}: {len(all_specialist_data)} records")
                logger.info(f"✅ Using verified results for ranking: {len(specialist_data)} records")
                
                if not specialist_data:
                    # No specialist data - return all providers with zero scores
                    logger.warning(f"⚠️  No specialist data for treatment {treatment_name}, returning all providers with zero scores")
                    ranked_npis = [p.get('npi', '') for p in npi_providers if p.get('npi')]
                    treatment_rankings[treatment_id] = {
                        "name": treatment_name,
                        "ranked_providers": ranked_npis,
                        "provider_links": {},
                        "provider_scores": {}
                    }
                    continue
                
                # Use GPT to rank providers with specialist matches
                ranking_result = await self.rank_npi_providers(
                    npi_providers=npi_providers,
                    specialist_data=specialist_data,
                    patient_profile=patient_profile,
                    max_providers=max_providers,
                    cms_tot_srvcs=cms_tot_srvcs
                )
                
                # Get the ranked NPIs and scores (all providers are now included)
                ranked_npis = ranking_result.get("ranking", [])
                provider_links = ranking_result.get("provider_links", {})
                provider_scores = ranking_result.get("provider_scores", {})  # Keyed by NPI (string) from rank_npi_providers
                
                # Sort ALL providers by their total scores
                # provider_scores is keyed by NPI (string), so iterate correctly
                all_providers_with_scores = [
                    (npi, scores) for npi, scores in provider_scores.items()
                ]
                all_providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
                all_ranked_npis = [npi for npi, _ in all_providers_with_scores]
                
                # Store the results for this treatment
                providers_with_pubmed = len([npi for npi in all_ranked_npis if provider_scores.get(npi, {}).get('pubmed_count', 0) > 0])
                treatment_rankings[treatment_id] = {
                    "name": treatment_name,
                    "ranked_providers": all_ranked_npis,
                    "provider_links": provider_links,
                    "provider_scores": provider_scores
                }
                
                logger.info(f"✅ Completed ranking for {treatment_name}: {providers_with_pubmed} with PubMed/Vumedi matches, {len(all_ranked_npis)} total providers")
            
            logger.info(f"✅ === TREATMENT-SPECIFIC RANKING COMPLETED ===")
            logger.info(f"📊 Total treatments ranked: {len(treatment_rankings)}")
            
            return {
                "treatment_rankings": treatment_rankings,
                "total_treatments": len(treatment_rankings)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in treatment-specific ranking: {str(e)}")
            raise
    
    def _batch_fetch_reviews(self, npis: List[str], patient_profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch ALL reviews for multiple NPIs and mark each as relevant/not relevant.
        Returns reviews with is_relevant boolean flag.
        
        Args:
            npis: List of NPI numbers
            patient_profile: Patient profile dict containing search_query for keyword filtering
            
        Returns:
            Dictionary mapping NPI to dict with 'reviews' (list with is_relevant flag) and 'relevant_count' (int)
        """
        from ..models.healthgrades_review import HealthgradesReview
        
        # DEBUG: Check model definition
        logger.info(f"🔍 [Reviews Debug] HealthgradesReview class attributes: {[attr for attr in dir(HealthgradesReview) if not attr.startswith('_') and not callable(getattr(HealthgradesReview, attr, None))]}")
        if hasattr(HealthgradesReview, '__table__'):
            logger.info(f"🔍 [Reviews Debug] HealthgradesReview table columns: {list(HealthgradesReview.__table__.columns.keys())}")
            if 'review_rating' in HealthgradesReview.__table__.columns:
                logger.info(f"🔍 [Reviews Debug] review_rating column exists in table: {HealthgradesReview.__table__.columns['review_rating']}")
            else:
                logger.error(f"❌ [Reviews Debug] review_rating column MISSING from table definition!")
        else:
            logger.error(f"❌ [Reviews Debug] HealthgradesReview has no __table__ attribute!")
        
        if not npis or not self.db:
            return {}
        
        try:
            start_time = time.time()
            logger.info(f"📦 [Reviews] Batch fetching ALL reviews for {len(npis)} NPIs")
            
            # Extract search_query from patient_profile (must be set from first medical analysis, same as PubMed)
            search_query = patient_profile.get('search_query', '') if isinstance(patient_profile, dict) else ''
            
            if not search_query:
                logger.error(f"❌ [Reviews] CRITICAL: search_query is missing from patient_profile! This should be set from the first medical analysis (same as used for PubMed).")
                logger.error(f"❌ [Reviews] patient_profile keys: {list(patient_profile.keys()) if isinstance(patient_profile, dict) else 'NOT A DICT'}")
            
            # Extract keywords for relevance checking
            keyword_list = []
            if search_query:
                keyword_list = [k.strip().lower() for k in search_query.split(' OR ') if k.strip()]
                logger.info(f"🔍 [Reviews] Using {len(keyword_list)} keywords for relevance checking: {', '.join(keyword_list[:3])}{'...' if len(keyword_list) > 3 else ''}")
            else:
                logger.warning(f"⚠️ [Reviews] No search_query available - all reviews will be marked as not relevant")
            
            # Fetch ALL reviews (no SQL filtering)
            query_start = time.time()
            all_reviews = self.db.query(HealthgradesReview).filter(
                HealthgradesReview.npi.in_(npis)
            ).order_by(
                HealthgradesReview.npi,
                HealthgradesReview.review_index
            ).limit(100 * len(npis)).all()
            query_duration = time.time() - query_start
            
            logger.info(f"📦 [Reviews] Found {len(all_reviews)} total reviews across {len(npis)} NPIs")
            logger.info(f"⏱️  [Reviews] Database query took {query_duration:.3f} seconds ({query_duration*1000:.1f}ms)")
            
            # Debug: Check a few reviews to verify review_rating is loaded
            if all_reviews:
                sample_review = all_reviews[0]
                logger.info(f"🔍 [Reviews Debug] Sample review object type: {type(sample_review)}")
                logger.info(f"🔍 [Reviews Debug] Sample review ID {sample_review.id}: available attributes: {[attr for attr in dir(sample_review) if not attr.startswith('_') and not callable(getattr(sample_review, attr, None))]}")
                logger.info(f"🔍 [Reviews Debug] Sample review has review_rating attr: {hasattr(sample_review, 'review_rating')}")
                logger.info(f"🔍 [Reviews Debug] Sample review __dict__ keys: {list(sample_review.__dict__.keys())}")
                
                # Check SQLAlchemy mapper
                from sqlalchemy.inspection import inspect as sql_inspect
                mapper = sql_inspect(type(sample_review))
                logger.info(f"🔍 [Reviews Debug] SQLAlchemy mapper columns: {list(mapper.columns.keys())}")
                if 'review_rating' in mapper.columns:
                    logger.info(f"🔍 [Reviews Debug] review_rating found in mapper.columns")
                else:
                    logger.error(f"❌ [Reviews Debug] review_rating NOT in mapper.columns!")
                
                # Now try to access review_rating
                try:
                    rating_value = sample_review.review_rating
                    logger.info(f"🔍 [Reviews Debug] Sample review ID {sample_review.id}: review_rating={rating_value}, type={type(rating_value).__name__}")
                except AttributeError as e:
                    logger.error(f"❌ [Reviews Debug] AttributeError accessing review_rating: {e}")
                
                # Check for Theodore's review_index 111 specifically
                theodore_review_111 = next((r for r in all_reviews if str(r.npi) == '1811916455' and r.review_index == 111), None)
                if theodore_review_111:
                    logger.info(f"🔍 [Reviews Debug] Theodore review_index 111 found")
                    try:
                        logger.info(f"🔍 [Reviews Debug] Theodore review_index 111: review_rating={theodore_review_111.review_rating}, type={type(theodore_review_111.review_rating).__name__}")
                    except AttributeError as e:
                        logger.error(f"❌ [Reviews Debug] AttributeError accessing Theodore review_rating: {e}")
                else:
                    logger.warning(f"⚠️  [Reviews Debug] Theodore review_index 111 not found in query results")
            
            # Group by NPI and mark each review as relevant/not relevant
            reviews_by_npi = {}
            theodore_npi = '1811916455'
            theodore_relevant_count = 0
            theodore_total_count = 0
            
            for review in all_reviews:
                npi_str = str(review.npi)
                if npi_str not in reviews_by_npi:
                    reviews_by_npi[npi_str] = {
                        'reviews': [],
                        'relevant_count': 0,
                        'total_count': 0
                    }
                
                # Check if review is relevant (contains any keyword)
                is_relevant = False
                if keyword_list and review.review_text:
                    review_text_lower = review.review_text.lower()
                    is_relevant = any(keyword in review_text_lower for keyword in keyword_list)
                
                # Access review_rating directly - it should be loaded by the query
                try:
                    review_rating_value = review.review_rating
                except AttributeError as e:
                    logger.error(f"❌ [Reviews Debug] AttributeError on review ID {review.id}, NPI {review.npi}, index {review.review_index}: {e}")
                    logger.error(f"❌ [Reviews Debug] Review object type: {type(review)}")
                    logger.error(f"❌ [Reviews Debug] Review has review_rating: {hasattr(review, 'review_rating')}")
                    logger.error(f"❌ [Reviews Debug] Review __dict__ keys: {list(review.__dict__.keys())}")
                    # Re-raise to see full stack trace
                    raise
                
                # Debug logging for Theodore's reviews
                if str(review.npi) == '1811916455' and review.review_index in [1, 111]:
                    logger.info(f"🔍 [Reviews Debug] Theodore review_index {review.review_index}: review_rating={review_rating_value}, type={type(review_rating_value).__name__}, has_attr={hasattr(review, 'review_rating')}")
                
                review_data = {
                    'id': review.id,
                    'npi': review.npi,
                    'first_name': review.first_name,
                    'last_name': review.last_name,
                    'review_text': review.review_text,
                    'review_author': review.review_author,
                    'review_date': review.review_date,
                    'review_index': review.review_index,
                    'review_rating': review_rating_value,  # Include star rating (1-5, or None if not available)
                    'is_relevant': is_relevant  # Add boolean flag
                }
                
                # Limit to 100 reviews per NPI
                if len(reviews_by_npi[npi_str]['reviews']) < 100:
                    reviews_by_npi[npi_str]['reviews'].append(review_data)
                    reviews_by_npi[npi_str]['total_count'] += 1
                    if is_relevant:
                        reviews_by_npi[npi_str]['relevant_count'] += 1
                
                # Detailed logging for Theodore Schwartz
                if npi_str == theodore_npi:
                    theodore_total_count += 1
                    if is_relevant:
                        theodore_relevant_count += 1
                        matched_keywords = [k for k in keyword_list if k in review.review_text.lower()]
                        logger.info(f"🔍 [Theodore Debug] Review #{review.review_index} is RELEVANT. Matched keywords: {matched_keywords[:3]}")
                        logger.info(f"🔍 [Theodore Debug] Review text preview: {review.review_text[:150]}...")
            
            # Log summary
            total_relevant = sum(data['relevant_count'] for data in reviews_by_npi.values())
            logger.info(f"✅ [Reviews] Grouped reviews for {len(reviews_by_npi)} NPIs, {total_relevant} relevant reviews found")
            
            # Detailed logging for Theodore Schwartz
            if theodore_npi in reviews_by_npi:
                theodore_data = reviews_by_npi[theodore_npi]
                logger.info(f"🔍 [Theodore Debug] _batch_fetch_reviews RESULT:")
                logger.info(f"🔍 [Theodore Debug]   - relevant_count: {theodore_data['relevant_count']}")
                logger.info(f"🔍 [Theodore Debug]   - total_count: {theodore_data['total_count']}")
                logger.info(f"🔍 [Theodore Debug]   - reviews list length: {len(theodore_data['reviews'])}")
                logger.info(f"🔍 [Theodore Debug]   - Manual count check: {theodore_relevant_count} relevant out of {theodore_total_count} processed")
            
            return reviews_by_npi
            
        except Exception as e:
            logger.error(f"❌ [Reviews] Error batch fetching reviews: {e}")
            return {}
