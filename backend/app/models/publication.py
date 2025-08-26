from sqlalchemy import Column, String, Text, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class Publication(BaseModel):
    """Publication model for doctor publications."""
    
    __tablename__ = "publications"
    
    # Publication Details
    title = Column(String(500), nullable=False)
    authors = Column(Text)  # Comma-separated author list
    journal = Column(String(200))
    publication_type = Column(String(100))  # peer_reviewed, journal_article, book_chapter, etc.
    publication_date = Column(Date)
    year = Column(Integer)
    volume = Column(String(50))
    issue = Column(String(50))
    pages = Column(String(50))
    doi = Column(String(200))
    url = Column(String(500))
    
    # Content
    abstract = Column(Text)
    keywords = Column(Text)
    
    # Metrics
    citation_count = Column(Integer, default=0)
    impact_factor = Column(Integer)
    
    # Journal Reference
    journal_id = Column(Integer, ForeignKey("journals.id"))
    
    # Relationships
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    doctor = relationship("Doctor", back_populates="publications")
    journal = relationship("Journal", back_populates="publications")
    
    @property
    def citation_display(self):
        """Get citation display text."""
        if self.citation_count is None:
            return "0"
        return str(self.citation_count)
    
    @property
    def year_display(self):
        """Get year display."""
        if self.year:
            return str(self.year)
        elif self.publication_date:
            return str(self.publication_date.year)
        return "N/A"
