"""
CMS data utility functions.

Helper functions for parsing and extracting CMS provider data.
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def extract_cms_tot_srvcs(cms_data: Optional[Dict]) -> Optional[Dict[str, int]]:
    """
    Extract NPI to Tot_Srvcs mapping from CMS data for clinical volume scoring.
    
    Args:
        cms_data: CMS data dictionary containing 'results' list of provider records
        
    Returns:
        Dictionary mapping NPI (string) to Tot_Srvcs (int), or None if no valid data
    """
    if not cms_data or not isinstance(cms_data, dict):
        return None
    
    cms_providers = cms_data.get('results', [])
    if not isinstance(cms_providers, list) or not cms_providers:
        return None
    
    cms_tot_srvcs = {}
    for provider in cms_providers:
        npi = provider.get('Rndrng_NPI')
        if not npi:
            continue
            
        try:
            tot_srvcs = int(provider.get('Tot_Srvcs', 0)) if provider.get('Tot_Srvcs') else 0
            cms_tot_srvcs[str(npi)] = tot_srvcs
        except (ValueError, TypeError):
            continue
    
    if cms_tot_srvcs:
        logger.info(f"Extracted {len(cms_tot_srvcs)} NPIs with Tot_Srvcs from CMS data")
        return cms_tot_srvcs
    
    return None

