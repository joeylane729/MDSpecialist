from sqlalchemy import Column, String, Text, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class DoctorDiagCache(BaseModel):
    """Cache for doctor-diagnosis matches to improve performance."""
    
    __tablename__ = "doctor_diag_cache"
    
    # Cache Key
    diagnosis = Column(String(500), nullable=False)
    metro_area = Column(String(100), nullable=False)
    location_radius = Column(Float)  # in miles
    
    # Cached Results
    doctor_ids = Column(JSON)  # List of ranked doctor IDs
    scores = Column(JSON)  # Dictionary of doctor_id: score
    grades = Column(JSON)  # Dictionary of doctor_id: grade
    
    # Metadata
    cache_hit_count = Column(Integer, default=0)
    last_accessed = Column(Integer)  # Unix timestamp
    
    # Relationships
    diag_snapshot_id = Column(Integer, ForeignKey("diag_snapshots.id"))
    diag_snapshot = relationship("DiagSnapshot", back_populates="cache_entries")
    
    @property
    def cache_key(self):
        """Generate cache key for this entry."""
        radius_str = f"_{self.location_radius}" if self.location_radius else ""
        return f"{self.diagnosis}_{self.metro_area}{radius_str}"
    
    def increment_hit_count(self):
        """Increment the cache hit count."""
        self.cache_hit_count += 1
