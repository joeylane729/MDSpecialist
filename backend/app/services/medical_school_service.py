"""
Medical School Service

Service for getting medical school information for any doctor in our backend.
"""

import os
import requests
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session


class MedicalSchoolService:
    """Service for retrieving medical school information for doctors."""
    
    def __init__(self, db: Session):
        self.db = db
        self.google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY') or os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
        self.google_search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID') or os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
    
    def get_medical_school_for_doctor(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """Get medical school info for a doctor by ID."""
        # TODO: Implement logic
        pass
    
    def get_medical_school_for_npi(self, npi: str) -> Optional[Dict[str, Any]]:
        """Get medical school info for a provider by NPI."""
        # TODO: Implement logic
        pass
    
    def search_medical_school_by_provider_info(
        self,
        npi: str,
        first_name: str,
        last_name: str,
        city: str,
        state: str,
        specialty: str
    ) -> Optional[Dict[str, Any]]:
        """
        Search for medical school information using Google Custom Search API.
        
        Args:
            npi: Provider's NPI number
            first_name: Provider's first name
            last_name: Provider's last name
            city: Provider's city
            state: Provider's state
            specialty: Provider's specialty
            
        Returns:
            Dictionary containing medical school information and search results, or None if error
        """
        if not self.google_api_key or not self.google_search_engine_id:
            return {
                'error': 'Google Custom Search API credentials not configured',
                'medical_school': None,
                'confidence': 0.0,
                'raw_results': []
            }
        
        # Construct search query: first_name + last_name + "received medical degree usnews" + specialty + city + state
        query = f"{first_name} {last_name} received medical degree usnews {specialty} {city} {state}"
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.google_search_engine_id,
                'q': query,
                'num': 10  # Get up to 10 results for analysis
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract medical school information from search results
                medical_school_info = self._extract_medical_school_from_results(
                    data.get('items', []),
                    first_name,
                    last_name
                )
                
                return {
                    'npi': npi,
                    'provider_name': f"{first_name} {last_name}",
                    'search_query': query,
                    'total_results': data.get('searchInformation', {}).get('totalResults', 0),
                    'search_time': data.get('searchInformation', {}).get('searchTime', 0),
                    'medical_school': medical_school_info.get('school_name'),
                    'graduation_year': medical_school_info.get('graduation_year'),
                    'confidence': medical_school_info.get('confidence', 0.0),
                    'source_url': medical_school_info.get('source_url'),
                    'source_title': medical_school_info.get('source_title'),
                    'raw_results': data.get('items', [])[:3]  # Include first 3 raw results for debugging
                }
            else:
                return {
                    'error': f"Google API request failed with status {response.status_code}",
                    'response_text': response.text[:200],
                    'medical_school': None,
                    'confidence': 0.0,
                    'raw_results': []
                }
                
        except requests.RequestException as e:
            return {
                'error': f"Network error during Google API request: {str(e)}",
                'medical_school': None,
                'confidence': 0.0,
                'raw_results': []
            }
        except Exception as e:
            return {
                'error': f"Unexpected error during medical school search: {str(e)}",
                'medical_school': None,
                'confidence': 0.0,
                'raw_results': []
            }
    
    def _extract_medical_school_from_results(
        self,
        search_results: list,
        first_name: str,
        last_name: str
    ) -> Dict[str, Any]:
        """
        Extract medical school information from Google search results.
        
        Args:
            search_results: List of search result items from Google API
            first_name: Provider's first name for verification
            last_name: Provider's last name for verification
            
        Returns:
            Dictionary with extracted medical school information
        """
        medical_school_patterns = [
            # Common patterns for medical school mentions
            r'received his medical degree from ([^,\n\.]+)',
            r'received her medical degree from ([^,\n\.]+)',
            r'graduated from ([^,\n\.]+) medical school',
            r'attended ([^,\n\.]+) school of medicine',
            r'education: ([^,\n\.]+) medical school',
            r'medical school: ([^,\n\.]+)',
            r'earned his medical degree at ([^,\n\.]+)',
            r'earned her medical degree at ([^,\n\.]+)',
            r'medical degree at ([^,\n\.]+)',
        ]
        
        graduation_year_patterns = [
            r'graduated in (\d{4})',
            r'graduation year: (\d{4})',
            r'class of (\d{4})',
            r'(\d{4}) graduate',
            r'received.*degree.*(\d{4})',
        ]
        
        best_match = {
            'school_name': None,
            'graduation_year': None,
            'confidence': 0.0,
            'source_url': None,
            'source_title': None
        }
        
        import re
        
        for result in search_results:
            # Check if this result mentions the doctor's name
            snippet = result.get('snippet', '').lower()
            title = result.get('title', '').lower()
            full_text = f"{title} {snippet}".lower()
            
            # Verify this result is about the correct doctor
            name_match_score = 0
            if first_name.lower() in full_text:
                name_match_score += 1
            if last_name.lower() in full_text:
                name_match_score += 1
            
            # Skip results that don't mention the doctor's name
            if name_match_score == 0:
                continue
            
            confidence_score = name_match_score * 0.3  # Base confidence from name matching
            
            # Look for medical school mentions
            for pattern in medical_school_patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    school_name = match.strip()
                    
                    # Clean up the school name
                    school_name = self._clean_school_name(school_name)
                    
                    if school_name and len(school_name) > 5:  # Valid school name
                        # Check for 100% confidence rule: US News + "received his/her medical degree from..." + both names present
                        is_usnews = 'usnews' in result.get('displayLink', '').lower()
                        has_received_degree_pattern = any(
                            re.search(received_pattern, full_text, re.IGNORECASE) 
                            for received_pattern in [
                                r'received his medical degree from',
                                r'received her medical degree from'
                            ]
                        )
                        has_both_names = (first_name.lower() in full_text and last_name.lower() in full_text)
                        
                        if is_usnews and has_received_degree_pattern and has_both_names:
                            confidence_score = 1.0  # 100% confidence
                        else:
                            # Standard confidence scoring
                            # Boost confidence for authoritative sources
                            if any(source in result.get('displayLink', '').lower() for source in ['doximity', 'healthgrades', 'vitals']):
                                confidence_score += 0.3
                            elif 'wikipedia' in result.get('displayLink', '').lower():
                                confidence_score += 0.2
                            
                            # Boost confidence for medical school keywords
                            if any(keyword in school_name.lower() for keyword in ['harvard', 'johns hopkins', 'stanford', 'yale', 'columbia']):
                                confidence_score += 0.1
                        
                        if confidence_score > best_match['confidence']:
                            # Look for graduation year in the same result
                            graduation_year = None
                            for year_pattern in graduation_year_patterns:
                                year_matches = re.findall(year_pattern, full_text, re.IGNORECASE)
                                if year_matches:
                                    try:
                                        graduation_year = int(year_matches[0])
                                        if 1950 <= graduation_year <= 2030:  # Reasonable year range
                                            break
                                    except ValueError:
                                        continue
                            
                            best_match = {
                                'school_name': school_name,
                                'graduation_year': graduation_year,
                                'confidence': confidence_score,
                                'source_url': result.get('link'),
                                'source_title': result.get('title')
                            }
        
        return best_match
    
    def _clean_school_name(self, school_name: str) -> str:
        """
        Clean and normalize medical school name.
        
        Args:
            school_name: Raw school name extracted from text
            
        Returns:
            Cleaned school name
        """
        if not school_name:
            return ""
        
        # Remove common suffixes and prefixes
        school_name = school_name.strip()
        
        # Remove HTML tags if any
        import re
        school_name = re.sub(r'<[^>]+>', '', school_name)
        
        # Remove extra whitespace
        school_name = re.sub(r'\s+', ' ', school_name)
        
        # Remove trailing punctuation
        school_name = school_name.rstrip('.,;:')
        
        # Common replacements - use word boundaries to avoid partial matches
        import re
        
        # Replace abbreviations with full forms, using word boundaries
        school_name = re.sub(r'\buniv\b', 'University', school_name, flags=re.IGNORECASE)
        school_name = re.sub(r'\bcoll\b', 'College', school_name, flags=re.IGNORECASE)
        school_name = re.sub(r'\bmed sch\b', 'Medical School', school_name, flags=re.IGNORECASE)
        school_name = re.sub(r'\bsch of med\b', 'School of Medicine', school_name, flags=re.IGNORECASE)
        
        return school_name.strip()
