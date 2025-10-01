"""
NPI Medical School Mapping Model

Database model for mapping NPI providers to medical school rankings.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


class NPIMedicalSchoolMapping(Base):
    """Model for mapping NPI providers to medical school rankings."""
    
    __tablename__ = "npi_medical_school_mapping"
    
    id = Column(Integer, primary_key=True, index=True)
    npi = Column(String(10), nullable=False, index=True)
    medical_school_id = Column(Integer, ForeignKey('medical_school_rankings.id'), nullable=False, index=True)
    
    # Ensure unique NPI entries (one medical school per NPI)
    __table_args__ = (
        UniqueConstraint('npi', name='uq_npi_medical_school_mapping'),
    )
    
    # Relationship to medical school ranking
    medical_school = relationship("MedicalSchoolRanking", backref="npi_mappings")
    
    def __repr__(self):
        return f"<NPIMedicalSchoolMapping(npi='{self.npi}', medical_school_id={self.medical_school_id})>"
