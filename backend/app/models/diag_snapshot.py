from sqlalchemy import Column, String, Text, Integer, Float, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class DiagSnapshot(BaseModel):
    """Snapshot of diagnosis search for analytics and tracking."""
    
    __tablename__ = "diag_snapshots"
    
    # Search Parameters
    diagnosis = Column(String(500), nullable=False)
    metro_area = Column(String(100), nullable=False)
    location_radius = Column(Float)  # in miles
    user_location = Column(JSON)  # User's location data
    
    # Search Results
    total_doctors_found = Column(Integer)
    search_duration_ms = Column(Integer)  # Search execution time
    
    # User Context
    user_agent = Column(String(500))
    ip_address = Column(String(45))  # IPv4 or IPv6
    session_id = Column(String(100))
    
    # Analytics
    result_clicked = Column(Boolean, default=False)
    doctor_selected = Column(Integer, ForeignKey("doctors.id"))
    
    # Relationships
    cache_entries = relationship("DoctorDiagCache", back_populates="diag_snapshot")
    
    @property
    def search_summary(self):
        """Get search summary for display."""
        radius_str = f" within {self.location_radius} miles" if self.location_radius else ""
        return f"{self.diagnosis} in {self.metro_area}{radius_str}"
