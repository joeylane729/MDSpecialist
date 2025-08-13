from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class TalkBase(BaseModel):
    """Base talk schema."""
    title: str = Field(..., min_length=1, max_length=500)
    event_name: Optional[str] = Field(None, max_length=200)
    event_type: Optional[str] = Field(None, max_length=100)
    event_date: Optional[date] = None
    year: Optional[int] = Field(None, ge=1900, le=2030)
    venue: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    country: Optional[str] = Field(None, max_length=100)
    abstract: Optional[str] = None
    presentation_type: Optional[str] = Field(None, max_length=100)
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    audience_size: Optional[int] = Field(None, ge=0)
    recording_url: Optional[str] = Field(None, max_length=500)
    slides_url: Optional[str] = Field(None, max_length=500)

class TalkCreate(TalkBase):
    """Schema for creating a new talk."""
    doctor_id: int

class TalkResponse(TalkBase):
    """Schema for talk response."""
    id: int
    doctor_id: int
    year_display: str
    location_display: str
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True
