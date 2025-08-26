from sqlalchemy import Column, String, Text, Integer, Float, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel

class Journal(BaseModel):
    """Journal model for storing journal rankings and metadata."""
    
    __tablename__ = "journals"
    
    # Basic Journal Information
    source_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(1000), nullable=False, index=True)
    journal_type = Column(String(200))  # journal, conference, etc.
    issn = Column(String(500))  # Can have multiple ISSNs separated by commas
    publisher = Column(String(1000))
    
    # Open Access Information
    open_access = Column(Boolean, default=False)
    open_access_diamond = Column(Boolean, default=False)
    
    # Impact Metrics
    rank = Column(Integer)
    sjr_score = Column(Float)  # SCImago Journal Rank
    sjr_quartile = Column(String(10))  # Q1, Q2, Q3, Q4
    h_index = Column(Integer)
    
    # Publication Volume
    total_docs_2024 = Column(Integer)
    total_docs_3years = Column(Integer)
    total_references = Column(Integer)
    total_citations_3years = Column(Integer)
    citable_docs_3years = Column(Integer)
    
    # Citation Metrics
    citations_per_doc_2years = Column(Float)
    refs_per_doc = Column(Float)
    
    # Additional Metrics
    female_percentage = Column(Float)
    overton_score = Column(Integer)
    sdg_count = Column(Integer)
    
    # Geographic Information
    country = Column(String(200))
    region = Column(String(200))
    
    # Coverage and Classification
    coverage_period = Column(String(500))  # e.g., "1950-2025"
    categories = Column(Text)  # Subject categories with quartiles
    areas = Column(Text)  # Broad subject areas
    
    # Relationships
    publications = relationship("Publication", back_populates="journal")
    
    def __repr__(self):
        return f"<Journal(title='{self.title}', rank={self.rank}, sjr_quartile='{self.sjr_quartile}')>"
    
    @property
    def is_top_tier(self):
        """Check if journal is top tier (Q1)."""
        return self.sjr_quartile == 'Q1'
    
    @property
    def impact_display(self):
        """Get formatted impact score display."""
        if self.sjr_score:
            return f"{self.sjr_score:,.0f}"
        return "N/A"
    
    @property
    def quartile_display(self):
        """Get formatted quartile display."""
        if self.sjr_quartile:
            return f"{self.sjr_quartile}"
        return "N/A"
