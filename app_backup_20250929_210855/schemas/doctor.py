from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date

class DoctorBase(BaseModel):
    """Base doctor schema."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    specialty: str = Field(..., min_length=1, max_length=200)
    subspecialty: Optional[str] = Field(None, max_length=200)
    
    # Contact Information
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    
    # Location Information
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)
    metro_area: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

class DoctorCreate(DoctorBase):
    """Schema for creating a new doctor."""
    pass

class DoctorUpdate(BaseModel):
    """Schema for updating a doctor."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, min_length=1, max_length=200)
    subspecialty: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)
    metro_area: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

class DoctorResponse(DoctorBase):
    """Schema for doctor response."""
    id: int
    full_name: str
    display_name: str
    location_summary: str
    overall_grade: Optional[str] = None
    rank: Optional[int] = None
    
    # Professional Information
    medical_school: Optional[str] = None
    medical_school_tier: Optional[str] = None
    graduation_year: Optional[int] = None
    residency_program: Optional[str] = None
    residency_tier: Optional[str] = None
    fellowship_programs: Optional[List[Dict[str, Any]]] = None
    board_certifications: Optional[List[str]] = None
    years_experience: Optional[int] = None
    
    # Experience Details
    clinical_years: Optional[int] = None
    research_years: Optional[int] = None
    teaching_years: Optional[int] = None
    leadership_roles: Optional[List[str]] = None
    awards: Optional[List[str]] = None
    
    # Online Presence
    website_mentions: Optional[int] = None
    patient_reviews: Optional[List[Dict[str, Any]]] = None
    social_media: Optional[Dict[str, Any]] = None
    directory_listings: Optional[List[str]] = None
    
    # Timestamps
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True

class DoctorListResponse(BaseModel):
    """Schema for list of doctors response."""
    doctors: List[DoctorResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
