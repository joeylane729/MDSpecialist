from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .doctor import DoctorResponse

class MatchRequest(BaseModel):
    """Schema for doctor matching request."""
    diagnosis: str = Field(..., min_length=1, max_length=500, description="Patient's diagnosis or condition")
    metro_area: str = Field(..., min_length=1, max_length=100, description="Metropolitan area for search")
    location_radius: Optional[float] = Field(None, ge=0, le=500, description="Search radius in miles (0-500)")
    specialty: Optional[str] = Field(None, max_length=200, description="Preferred medical specialty")
    subspecialty: Optional[str] = Field(None, max_length=200, description="Preferred medical subspecialty")
    max_results: Optional[int] = Field(20, ge=1, le=100, description="Maximum number of results to return")

class MatchResponse(BaseModel):
    """Schema for doctor matching response."""
    diagnosis: str
    metro_area: str
    location_radius: Optional[float]
    total_doctors_found: int
    doctors: List[DoctorResponse]
    search_summary: str
    search_duration_ms: Optional[int] = None
    
    class Config:
        from_attributes = True
