"""
Medical School Service

Simple service for getting medical school information for doctors.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from .medical_school_ranking_service import MedicalSchoolRankingService


class MedicalSchoolService:
    """Service for retrieving medical school information for doctors."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ranking_service = MedicalSchoolRankingService(db)
    
    def get_medical_school_info(self, school_name: str) -> Optional[Dict[str, Any]]:
        """Get medical school information and ranking by school name."""
        if not school_name:
            return None
        
        # Get ranking info from database
        ranking_info = self.ranking_service.get_school_stats(school_name)
        
        return {
            'school_name': school_name,
            'ranking_info': ranking_info
        }
    
    def search_medical_schools(self, query: str, limit: int = 10) -> list:
        """Search for medical schools by name."""
        return self.ranking_service.search_schools(query, limit)
    
    def get_top_medical_schools(self, limit: int = 10) -> list:
        """Get top medical schools by rank."""
        return self.ranking_service.get_top_schools(limit)
