"""
Medical School Service

Service for getting medical school information for any doctor using web scraping.
"""

import os
import requests
import json
import time
import re
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import random
from .medical_school_ranking_service import MedicalSchoolRankingService


class MedicalSchoolService:
    """Service for retrieving medical school information for doctors via web scraping."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ranking_service = MedicalSchoolRankingService(db)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.rate_limit_delay = 2  # seconds between requests
    
    def get_medical_school_for_doctor(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """Get medical school info for a doctor by ID."""
        # TODO: Implement logic to get doctor info from database first
        pass
    
    def get_medical_school_for_npi(self, npi: str) -> Optional[Dict[str, Any]]:
        """Get medical school info for a provider by NPI."""
        # TODO: Implement logic to get provider info from database first
        pass
    
    def search_medical_school_by_provider_info(
        self,
        npi: str,
        first_name: str,
        last_name: str,
        city: str,
        state: str,
        specialty: str
    ) -> Dict[str, Any]:
        """
        Search for medical school information using web scraping from multiple sources.
        
        Args:
            npi: Provider's NPI number
            first_name: Provider's first name
            last_name: Provider's last name
            city: Provider's city
            state: Provider's state
            specialty: Provider's specialty
            
        Returns:
            Dictionary containing medical school information from all sources
        """
        print(f"🔍 Starting medical school search for {first_name} {last_name} (NPI: {npi})")
        
        # Try multiple sources
        all_results = []
        
        # 1. Doximity
        doximity_result = self._scrape_doximity(first_name, last_name, city, state, specialty)
        if doximity_result:
            all_results.append(doximity_result)
        
        # 2. Healthgrades
        healthgrades_result = self._scrape_healthgrades(first_name, last_name, city, state, specialty)
        if healthgrades_result:
            all_results.append(healthgrades_result)
        
        # 3. Vitals
        vitals_result = self._scrape_vitals(first_name, last_name, city, state, specialty)
        if vitals_result:
            all_results.append(vitals_result)
        
        # 4. WebMD
        webmd_result = self._scrape_webmd(first_name, last_name, city, state, specialty)
        if webmd_result:
            all_results.append(webmd_result)
        
        # 5. General web search (using DuckDuckGo)
        web_search_result = self._search_web_general(first_name, last_name, city, state, specialty)
        if web_search_result:
            all_results.append(web_search_result)
        
        # Aggregate and score results
        aggregated_result = self._aggregate_results(all_results, first_name, last_name)
        
        # Enhance with ranking information
        ranking_info = None
        if aggregated_result.get('medical_school'):
            ranking_info = self.ranking_service.get_school_stats(aggregated_result['medical_school'])
        
        return {
            'npi': npi,
            'provider_name': f"{first_name} {last_name}",
            'location': f"{city}, {state}",
            'specialty': specialty,
            'total_sources_checked': len(all_results),
            'successful_sources': len([r for r in all_results if r.get('medical_school')]),
            'medical_school': aggregated_result.get('medical_school'),
            'graduation_year': aggregated_result.get('graduation_year'),
            'confidence': aggregated_result.get('confidence', 0.0),
            'sources': all_results,
            'best_source': aggregated_result.get('best_source'),
            'all_medical_schools_found': aggregated_result.get('all_medical_schools', []),
            'ranking_info': ranking_info
        }
    
    def _scrape_doximity(self, first_name: str, last_name: str, city: str, state: str, specialty: str) -> Optional[Dict[str, Any]]:
        """Scrape medical school info from Doximity."""
        try:
            print(f"  📋 Checking Doximity for {first_name} {last_name}")
            # Doximity search URL pattern
            search_url = f"https://www.doximity.com/pub/{first_name.lower()}-{last_name.lower()}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return self._extract_medical_school_from_html(soup, 'Doximity', search_url, first_name, last_name)
            
            time.sleep(self.rate_limit_delay)
            return None
        except Exception as e:
            print(f"  ❌ Doximity error: {str(e)}")
            return None
    
    def _scrape_healthgrades(self, first_name: str, last_name: str, city: str, state: str, specialty: str) -> Optional[Dict[str, Any]]:
        """Scrape medical school info from Healthgrades."""
        try:
            print(f"  📋 Checking Healthgrades for {first_name} {last_name}")
            # Healthgrades search URL pattern
            search_url = f"https://www.healthgrades.com/physician/dr-{first_name.lower()}-{last_name.lower()}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return self._extract_medical_school_from_html(soup, 'Healthgrades', search_url, first_name, last_name)
            
            time.sleep(self.rate_limit_delay)
            return None
        except Exception as e:
            print(f"  ❌ Healthgrades error: {str(e)}")
            return None
    
    def _scrape_vitals(self, first_name: str, last_name: str, city: str, state: str, specialty: str) -> Optional[Dict[str, Any]]:
        """Scrape medical school info from Vitals."""
        try:
            print(f"  📋 Checking Vitals for {first_name} {last_name}")
            # Vitals search URL pattern
            search_url = f"https://www.vitals.com/doctors/Dr_{first_name}_{last_name}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return self._extract_medical_school_from_html(soup, 'Vitals', search_url, first_name, last_name)
            
            time.sleep(self.rate_limit_delay)
            return None
        except Exception as e:
            print(f"  ❌ Vitals error: {str(e)}")
            return None
    
    def _scrape_webmd(self, first_name: str, last_name: str, city: str, state: str, specialty: str) -> Optional[Dict[str, Any]]:
        """Scrape medical school info from WebMD."""
        try:
            print(f"  📋 Checking WebMD for {first_name} {last_name}")
            # WebMD search URL pattern
            search_url = f"https://doctor.webmd.com/physician/{first_name.lower()}-{last_name.lower()}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return self._extract_medical_school_from_html(soup, 'WebMD', search_url, first_name, last_name)
            
            time.sleep(self.rate_limit_delay)
            return None
        except Exception as e:
            print(f"  ❌ WebMD error: {str(e)}")
            return None
    
    def _search_web_general(self, first_name: str, last_name: str, city: str, state: str, specialty: str) -> Optional[Dict[str, Any]]:
        """Search general web using DuckDuckGo for medical school info."""
        try:
            print(f"  📋 Checking general web search for {first_name} {last_name}")
            # Use DuckDuckGo for general search
            query = f"{first_name} {last_name} medical school education {city} {state}"
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return self._extract_medical_school_from_html(soup, 'DuckDuckGo', search_url, first_name, last_name)
            
            time.sleep(self.rate_limit_delay)
            return None
        except Exception as e:
            print(f"  ❌ Web search error: {str(e)}")
            return None
    
    def _extract_medical_school_from_html(self, soup: BeautifulSoup, source: str, url: str, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
        """Extract medical school information from HTML content."""
        try:
            # Get all text content
            text_content = soup.get_text().lower()
            
            # Medical school patterns
            medical_school_patterns = [
                r'received his medical degree from ([^,\n\.]+)',
                r'received her medical degree from ([^,\n\.]+)',
                r'graduated from ([^,\n\.]+) medical school',
                r'attended ([^,\n\.]+) school of medicine',
                r'education: ([^,\n\.]+) medical school',
                r'medical school: ([^,\n\.]+)',
                r'earned his medical degree at ([^,\n\.]+)',
                r'earned her medical degree at ([^,\n\.]+)',
                r'medical degree at ([^,\n\.]+)',
                r'doctor of medicine.*?from ([^,\n\.]+)',
                r'md.*?from ([^,\n\.]+)',
            ]
            
            # Graduation year patterns
            graduation_year_patterns = [
                r'graduated in (\d{4})',
                r'graduation year: (\d{4})',
                r'class of (\d{4})',
                r'(\d{4}) graduate',
                r'received.*degree.*(\d{4})',
                r'(\d{4}).*medical school',
            ]
            
            # Verify this page is about the correct doctor
            if first_name.lower() not in text_content or last_name.lower() not in text_content:
                return None
            
            best_match = {
                'medical_school': None,
                'graduation_year': None,
                'confidence': 0.0,
                'source': source,
                'source_url': url
            }
            
            # Look for medical school mentions
            for pattern in medical_school_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    school_name = match.strip()
                    school_name = self._clean_school_name(school_name)
                    
                    if school_name and len(school_name) > 5:
                        # Calculate confidence based on source and patterns
                        confidence = 0.5  # Base confidence
                        
                        # Boost confidence for authoritative medical sources
                        if source in ['Doximity', 'Healthgrades', 'Vitals']:
                            confidence += 0.3
                        elif source == 'WebMD':
                            confidence += 0.2
                        
                        # Boost confidence for prestigious schools
                        if any(keyword in school_name.lower() for keyword in ['harvard', 'johns hopkins', 'stanford', 'yale', 'columbia', 'mayo']):
                            confidence += 0.1
                        
                        # Look for graduation year
                        graduation_year = None
                        for year_pattern in graduation_year_patterns:
                            year_matches = re.findall(year_pattern, text_content, re.IGNORECASE)
                            if year_matches:
                                try:
                                    year = int(year_matches[0])
                                    if 1950 <= year <= 2030:
                                        graduation_year = year
                                        break
                                except ValueError:
                                    continue
                        
                        if confidence > best_match['confidence']:
                            best_match = {
                                'medical_school': school_name,
                                'graduation_year': graduation_year,
                                'confidence': min(confidence, 1.0),
                                'source': source,
                                'source_url': url
                            }
            
            return best_match if best_match['medical_school'] else None
            
        except Exception as e:
            print(f"  ❌ HTML extraction error from {source}: {str(e)}")
            return None
    
    def _aggregate_results(self, all_results: List[Dict[str, Any]], first_name: str, last_name: str) -> Dict[str, Any]:
        """Aggregate results from multiple sources and determine the best match."""
        if not all_results:
            return {
                'medical_school': None,
                'graduation_year': None,
                'confidence': 0.0,
                'best_source': None,
                'all_medical_schools': []
            }
        
        # Collect all medical schools found
        all_medical_schools = []
        for result in all_results:
            if result.get('medical_school'):
                all_medical_schools.append({
                    'school': result['medical_school'],
                    'year': result.get('graduation_year'),
                    'source': result.get('source'),
                    'confidence': result.get('confidence', 0.0)
                })
        
        # Find the best match (highest confidence)
        best_result = max(all_results, key=lambda x: x.get('confidence', 0.0))
        
        # If we have multiple sources with the same school, boost confidence
        school_counts = {}
        for result in all_results:
            if result.get('medical_school'):
                school = result['medical_school'].lower()
                school_counts[school] = school_counts.get(school, 0) + 1
        
        # Boost confidence for schools mentioned by multiple sources
        if best_result.get('medical_school'):
            school_name = best_result['medical_school'].lower()
            if school_counts.get(school_name, 0) > 1:
                best_result['confidence'] = min(best_result['confidence'] + 0.2, 1.0)
        
        return {
            'medical_school': best_result.get('medical_school'),
            'graduation_year': best_result.get('graduation_year'),
            'confidence': best_result.get('confidence', 0.0),
            'best_source': best_result.get('source'),
            'all_medical_schools': all_medical_schools
        }
    
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
