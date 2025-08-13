from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class PublicationBase(BaseModel):
    """Base publication schema."""
    title: str = Field(..., min_length=1, max_length=500)
    authors: Optional[str] = Field(None, description="Comma-separated author list")
    journal: Optional[str] = Field(None, max_length=200)
    publication_type: Optional[str] = Field(None, max_length=100)
    publication_date: Optional[date] = None
    year: Optional[int] = Field(None, ge=1900, le=2030)
    volume: Optional[str] = Field(None, max_length=50)
    issue: Optional[str] = Field(None, max_length=50)
    pages: Optional[str] = Field(None, max_length=50)
    doi: Optional[str] = Field(None, max_length=200)
    url: Optional[str] = Field(None, max_length=500)
    abstract: Optional[str] = None
    keywords: Optional[str] = None
    citation_count: Optional[int] = Field(None, ge=0)
    impact_factor: Optional[int] = Field(None, ge=0)

class PublicationCreate(PublicationBase):
    """Schema for creating a new publication."""
    doctor_id: int

class PublicationResponse(PublicationBase):
    """Schema for publication response."""
    id: int
    doctor_id: int
    citation_display: str
    year_display: str
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True
