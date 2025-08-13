from sqlalchemy import Column, String, Text, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class RawSource(BaseModel):
    """Raw data sources for tracking data provenance."""
    
    __tablename__ = "raw_sources"
    
    # Source Information
    source_name = Column(String(200), nullable=False)  # PubMed, hospital website, etc.
    source_type = Column(String(100))  # api, web_scrape, manual_entry, etc.
    source_url = Column(String(500))
    
    # Data Content
    raw_data = Column(JSON)  # Raw data from source
    data_hash = Column(String(64))  # Hash of raw data for change detection
    
    # Processing Status
    status = Column(String(50), default="pending")  # pending, processed, failed
    processing_notes = Column(Text)
    
    # Metadata
    last_fetched = Column(DateTime)
    fetch_frequency_hours = Column(Integer)  # How often to refresh this source
    
    # Relationships
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    
    @property
    def is_active(self):
        """Check if source is active and should be fetched."""
        return self.status != "failed" and self.fetch_frequency_hours > 0
    
    @property
    def next_fetch_time(self):
        """Calculate when this source should be fetched next."""
        if not self.last_fetched or not self.fetch_frequency_hours:
            return None
        
        from datetime import timedelta
        return self.last_fetched + timedelta(hours=self.fetch_frequency_hours)
