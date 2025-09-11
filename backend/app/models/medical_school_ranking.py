"""
Medical School Ranking Model

Database model for medical school rankings data.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from .base import Base


class MedicalSchoolRanking(Base):
    """Model for medical school rankings data."""
    
    __tablename__ = "medical_school_rankings"
    
    id = Column(Integer, primary_key=True, index=True)
    rank = Column(Integer, nullable=False, index=True)
    school_listed = Column(String(255), nullable=False)
    city = Column(String(100), nullable=True)
    state_region = Column(String(50), nullable=True)
    mcat_score = Column(Float, nullable=True)
    gpa = Column(Float, nullable=True)
    full_official_name = Column(Text, nullable=True)
    needs_review = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<MedicalSchoolRanking(rank={self.rank}, school='{self.school_listed}')>"
