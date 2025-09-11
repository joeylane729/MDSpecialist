"""
Medical School Ranking Service

Service for working with medical school rankings data.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from ..models.medical_school_ranking import MedicalSchoolRanking


class MedicalSchoolRankingService:
    """Service for medical school ranking operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_ranking_by_school_name(self, school_name: str) -> Optional[MedicalSchoolRanking]:
        """Get medical school ranking by school name."""
        if not school_name:
            return None
        
        school_name_lower = school_name.lower().strip()
        
        # Try matching against school name or full official name
        return self.db.query(MedicalSchoolRanking).filter(
            or_(
                MedicalSchoolRanking.school_listed.ilike(f"%{school_name_lower}%"),
                MedicalSchoolRanking.full_official_name.ilike(f"%{school_name_lower}%")
            )
        ).first()
    
    def get_ranking_by_rank(self, rank: int) -> Optional[MedicalSchoolRanking]:
        """Get medical school ranking by rank number."""
        return self.db.query(MedicalSchoolRanking).filter(
            MedicalSchoolRanking.rank == rank
        ).first()
    
    def get_top_schools(self, limit: int = 10) -> List[MedicalSchoolRanking]:
        """Get top N medical schools by rank."""
        return self.db.query(MedicalSchoolRanking).order_by(
            MedicalSchoolRanking.rank
        ).limit(limit).all()
    
    
    def get_school_tier(self, school_name: str) -> Optional[str]:
        """Get the tier classification for a medical school."""
        ranking = self.get_ranking_by_school_name(school_name)
        if not ranking:
            return None
        
        if ranking.rank <= 10:
            return "top_10"
        elif ranking.rank <= 25:
            return "top_25"
        elif ranking.rank <= 50:
            return "top_50"
        elif ranking.rank <= 100:
            return "top_100"
        else:
            return "other"
    
    def get_school_stats(self, school_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stats for a medical school."""
        ranking = self.get_ranking_by_school_name(school_name)
        if not ranking:
            return None
        
        return {
            'rank': ranking.rank,
            'school_name': ranking.school_listed,
            'full_name': ranking.full_official_name,
            'city': ranking.city,
            'state': ranking.state_region,
            'mcat_score': ranking.mcat_score,
            'gpa': ranking.gpa,
            'tier': self.get_school_tier(school_name),
            'needs_review': ranking.needs_review
        }
    
    def search_schools(self, query: str, limit: int = 10) -> List[MedicalSchoolRanking]:
        """Search medical schools by name."""
        if not query:
            return []
        
        query_lower = query.lower().strip()
        
        return self.db.query(MedicalSchoolRanking).filter(
            or_(
                MedicalSchoolRanking.school_listed.ilike(f"%{query_lower}%"),
                MedicalSchoolRanking.full_official_name.ilike(f"%{query_lower}%")
            )
        ).order_by(MedicalSchoolRanking.rank).limit(limit).all()
