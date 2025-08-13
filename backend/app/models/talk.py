from sqlalchemy import Column, String, Text, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class Talk(BaseModel):
    """Talk model for doctor presentations and talks."""
    
    __tablename__ = "talks"
    
    # Talk Details
    title = Column(String(500), nullable=False)
    event_name = Column(String(200))
    event_type = Column(String(100))  # conference, symposium, grand_rounds, etc.
    event_date = Column(Date)
    year = Column(Integer)
    
    # Location
    venue = Column(String(200))
    city = Column(String(100))
    state = Column(String(2))
    country = Column(String(100))
    
    # Content
    abstract = Column(Text)
    presentation_type = Column(String(100))  # keynote, oral, poster, etc.
    duration_minutes = Column(Integer)
    
    # Metrics
    audience_size = Column(Integer)
    recording_url = Column(String(500))
    slides_url = Column(String(500))
    
    # Relationships
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    doctor = relationship("Doctor", back_populates="talks")
    
    @property
    def year_display(self):
        """Get year display."""
        if self.year:
            return str(self.year)
        elif self.event_date:
            return str(self.event_date.year)
        return "N/A"
    
    @property
    def location_display(self):
        """Get location display."""
        parts = [self.city, self.state]
        if self.country and self.country != "USA":
            parts.append(self.country)
        return ", ".join(filter(None, parts))
