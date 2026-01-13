"""
CMS data utility functions.

Helper functions for parsing and extracting CMS provider data.
"""

from typing import Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


def extract_cms_tot_srvcs(
    cms_data: Optional[Dict], 
    valid_npis: Optional[Set[str]] = None
) -> Optional[Dict[str, int]]:
    """
    Extract NPI to Tot_Srvcs mapping from CMS data for clinical volume scoring.
    
    Args:
        cms_data: CMS data dictionary containing 'results' list of provider records
        valid_npis: Optional set of valid NPI strings to filter by (e.g., neurosurgeons only).
                    If provided, only NPIs in this set will be included. This prevents
                    non-specialist providers (labs, facilities) from inflating the maximum.
        
    Returns:
        Dictionary mapping NPI (string) to Tot_Srvcs (int), or None if no valid data
    """
    if not cms_data or not isinstance(cms_data, dict):
        return None
    
    cms_providers = cms_data.get('results', [])
    if not isinstance(cms_providers, list) or not cms_providers:
        return None
    
    total_providers = len(cms_providers)
    cms_tot_srvcs = {}
    filtered_count = 0
    
    for provider in cms_providers:
        npi = provider.get('Rndrng_NPI')
        if not npi:
            continue
        
        npi_str = str(npi)
        
        # Filter to only include valid NPIs (neurosurgeons) if provided
        if valid_npis and npi_str not in valid_npis:
            filtered_count += 1
            # Log if this is a known provider we're looking for (like Theodore Schwartz)
            if npi_str in ['1811916455']:
                logger.warning(f"⚠️  CMS FILTER: NPI {npi_str} (Theodore Schwartz) was EXCLUDED - not in valid_npis set")
                logger.info(f"📊 valid_npis contains {len(valid_npis)} NPIs, sample: {list(valid_npis)[:10]}")
            continue
            
        try:
            tot_srvcs = int(provider.get('Tot_Srvcs', 0)) if provider.get('Tot_Srvcs') else 0
            cms_tot_srvcs[npi_str] = tot_srvcs
        except (ValueError, TypeError):
            continue
    
    if cms_tot_srvcs:
        if valid_npis:
            logger.info(f"Extracted {len(cms_tot_srvcs)} NPIs with Tot_Srvcs from CMS data "
                       f"(filtered from {total_providers} total providers, excluded {filtered_count} non-specialist providers)")
        else:
            logger.info(f"Extracted {len(cms_tot_srvcs)} NPIs with Tot_Srvcs from CMS data")
        return cms_tot_srvcs
    
    return None

