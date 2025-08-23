from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger, UniqueConstraint
from sqlalchemy.sql import func
from .base import Base

class VumediContent(Base):
    """Model for Vumedi medical content data."""
    
    __tablename__ = "vumedi_content"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False, index=True)
    author = Column(String(500), nullable=True, index=True)
    date = Column(String(100), nullable=True)
    views = Column(String(100), nullable=True)  # Keep as string since it includes "views" text
    duration = Column(String(20), nullable=True)
    link = Column(Text, nullable=False, index=True)  # Remove unique constraint
    thumbnail = Column(Text, nullable=True)
    featuring = Column(String(500), nullable=True)
    specialty = Column(String(200), nullable=True, index=True)
    specialty_url = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    
    # Add unique constraint on title + specialty combination
    __table_args__ = (
        UniqueConstraint('title', 'specialty', name='uq_vumedi_title_specialty'),
    )
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<VumediContent(id={self.id}, title='{self.title[:50]}...', specialty='{self.specialty}')>"
