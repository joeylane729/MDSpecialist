"""
Medical School Service

Service for finding medical school information for doctors via web scraping.
"""

import requests
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup
from .medical_school_ranking_service import MedicalSchoolRankingService


class MedicalSchoolService:
    """Service for finding medical school information for doctors."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ranking_service = MedicalSchoolRankingService(db)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def find_medical_school(self, first_name: str, last_name: str, city: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Search for a doctor and find their medical school.
        
        Returns:
            Dict with school_name and rank if found, None if no match
        """
        # Search for doctor using web scraping
        medical_school = self._scrape_doctor_medical_school(first_name, last_name, city, state)
        
        if not medical_school:
            return None
        
        # Check if the found school matches one in our database
        ranking = self.ranking_service.get_ranking_by_school_name(medical_school)
        
        if ranking:
            return {
                'school_name': ranking.school_listed,
                'rank': ranking.rank
            }
        
        return None
    
    def _scrape_doctor_medical_school(self, first_name: str, last_name: str, city: str, state: str) -> Optional[str]:
        """Scrape medical school from web search."""
        try:
            # Search for doctor using DuckDuckGo
            query = f"{first_name} {last_name} medical school education {city} {state}"
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            
            response = self.session.get(search_url, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text_content = soup.get_text().lower()
            
            # Medical school patterns
            patterns = [
                r'received his medical degree from ([^,\n\.]+)',
                r'received her medical degree from ([^,\n\.]+)',
                r'graduated from ([^,\n\.]+) medical school',
                r'attended ([^,\n\.]+) school of medicine',
                r'medical school: ([^,\n\.]+)',
                r'earned his medical degree at ([^,\n\.]+)',
                r'earned her medical degree at ([^,\n\.]+)',
                r'medical degree at ([^,\n\.]+)',
            ]
            
            # Verify this is about the correct doctor
            if first_name.lower() not in text_content or last_name.lower() not in text_content:
                return None
            
            # Look for medical school mentions
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    school_name = match.strip()
                    if school_name and len(school_name) > 5:
                        return school_name
            
            return None
            
        except Exception:
            return None
