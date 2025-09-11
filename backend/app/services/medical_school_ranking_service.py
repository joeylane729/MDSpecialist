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
        """Get medical school ranking by school name (fuzzy matching)."""
        if not school_name:
            return None
        
        school_name_lower = school_name.lower().strip()
        
        # Try exact match first
        exact_match = self.db.query(MedicalSchoolRanking).filter(
            MedicalSchoolRanking.school_listed.ilike(f"%{school_name_lower}%")
        ).first()
        
        if exact_match:
            return exact_match
        
        # Try matching against full official name
        official_match = self.db.query(MedicalSchoolRanking).filter(
            MedicalSchoolRanking.full_official_name.ilike(f"%{school_name_lower}%")
        ).first()
        
        if official_match:
            return official_match
        
        # Try fuzzy matching with common variations
        fuzzy_terms = self._extract_fuzzy_terms(school_name_lower)
        for term in fuzzy_terms:
            match = self.db.query(MedicalSchoolRanking).filter(
                or_(
                    MedicalSchoolRanking.school_listed.ilike(f"%{term}%"),
                    MedicalSchoolRanking.full_official_name.ilike(f"%{term}%")
                )
            ).first()
            if match:
                return match
        
        return None
    
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
    
    def get_schools_by_tier(self, tier: str) -> List[MedicalSchoolRanking]:
        """Get medical schools by tier (top_10, top_25, top_50, top_100)."""
        tier_limits = {
            'top_10': 10,
            'top_25': 25,
            'top_50': 50,
            'top_100': 100
        }
        
        limit = tier_limits.get(tier, 100)
        return self.db.query(MedicalSchoolRanking).filter(
            MedicalSchoolRanking.rank <= limit
        ).order_by(MedicalSchoolRanking.rank).all()
    
    def get_schools_by_location(self, state: str = None, city: str = None) -> List[MedicalSchoolRanking]:
        """Get medical schools by location."""
        query = self.db.query(MedicalSchoolRanking)
        
        if state:
            query = query.filter(MedicalSchoolRanking.state_region.ilike(f"%{state}%"))
        
        if city:
            query = query.filter(MedicalSchoolRanking.city.ilike(f"%{city}%"))
        
        return query.order_by(MedicalSchoolRanking.rank).all()
    
    def get_schools_by_mcat_range(self, min_mcat: float = None, max_mcat: float = None) -> List[MedicalSchoolRanking]:
        """Get medical schools by MCAT score range."""
        query = self.db.query(MedicalSchoolRanking)
        
        if min_mcat is not None:
            query = query.filter(MedicalSchoolRanking.mcat_score >= min_mcat)
        
        if max_mcat is not None:
            query = query.filter(MedicalSchoolRanking.mcat_score <= max_mcat)
        
        return query.order_by(MedicalSchoolRanking.rank).all()
    
    def get_schools_by_gpa_range(self, min_gpa: float = None, max_gpa: float = None) -> List[MedicalSchoolRanking]:
        """Get medical schools by GPA range."""
        query = self.db.query(MedicalSchoolRanking)
        
        if min_gpa is not None:
            query = query.filter(MedicalSchoolRanking.gpa >= min_gpa)
        
        if max_gpa is not None:
            query = query.filter(MedicalSchoolRanking.gpa <= max_gpa)
        
        return query.order_by(MedicalSchoolRanking.rank).all()
    
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
                MedicalSchoolRanking.full_official_name.ilike(f"%{query_lower}%"),
                MedicalSchoolRanking.city.ilike(f"%{query_lower}%"),
                MedicalSchoolRanking.state_region.ilike(f"%{query_lower}%")
            )
        ).order_by(MedicalSchoolRanking.rank).limit(limit).all()
    
    def _extract_fuzzy_terms(self, school_name: str) -> List[str]:
        """Extract fuzzy search terms from school name."""
        terms = []
        
        # Common medical school name patterns
        patterns = [
            r'university of (\w+)',
            r'(\w+) university',
            r'(\w+) medical school',
            r'(\w+) school of medicine',
            r'(\w+) college of medicine',
            r'(\w+) medical center',
            r'(\w+) health sciences',
            r'(\w+) medical college'
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, school_name, re.IGNORECASE)
            terms.extend(matches)
        
        # Add the original name
        terms.append(school_name)
        
        # Add individual words
        words = school_name.split()
        terms.extend(words)
        
        return list(set(terms))  # Remove duplicates
