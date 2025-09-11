from sqlalchemy import Column, String, Text, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class Doctor(BaseModel):
    """Doctor model representing medical specialists."""
    
    __tablename__ = "doctors"
    
    # Basic Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    middle_name = Column(String(100))
    title = Column(String(100))  # Dr., Prof., etc.
    specialty = Column(String(200), nullable=False)
    subspecialty = Column(String(200))
    
    # Contact Information
    email = Column(String(255))
    phone = Column(String(20))
    website = Column(String(500))
    
    # Location Information
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    metro_area = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Professional Information
    medical_school = Column(String(200))
    medical_school_tier = Column(String(50))  # top_10, top_25, top_50, top_100, other
    graduation_year = Column(Integer)
    residency_program = Column(String(200))
    residency_tier = Column(String(50))
    fellowship_programs = Column(JSON)  # List of fellowship programs
    board_certifications = Column(JSON)  # List of board certifications
    years_experience = Column(Integer)
    
    # Experience Details
    clinical_years = Column(Integer)
    research_years = Column(Integer)
    teaching_years = Column(Integer)
    leadership_roles = Column(JSON)  # List of leadership positions
    awards = Column(JSON)  # List of awards and honors
    
    # Online Presence
    website_mentions = Column(Integer, default=0)
    patient_reviews = Column(JSON)  # List of patient reviews
    social_media = Column(JSON)  # Social media presence
    directory_listings = Column(JSON)  # Professional directory listings
    
    # Relationships (commented out until Publication and Talk models are created)
    # publications = relationship("Publication", back_populates="doctor")
    # talks = relationship("Talk", back_populates="doctor")
    
    @property
    def full_name(self):
        """Get doctor's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        """Get doctor's display name with title."""
        if self.title:
            return f"{self.title} {self.full_name}"
        return self.full_name
    
    @property
    def location_summary(self):
        """Get location summary."""
        parts = [self.city, self.state]
        if self.metro_area:
            parts.append(f"({self.metro_area})")
        return ", ".join(filter(None, parts))
