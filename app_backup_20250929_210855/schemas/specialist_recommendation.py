"""
Pydantic schemas for specialist recommendation functionality.

This module defines the data models used for API requests and responses
in the specialist recommendation system.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class PatientProfileSchema(BaseModel):
    """Schema for patient profile."""
    symptoms: List[str] = Field(..., description="List of patient symptoms")
    conditions: List[str] = Field(..., description="List of medical conditions")
    specialties_needed: List[str] = Field(..., description="Required medical specialties")

    location_preference: Optional[str] = Field(None, description="Preferred location")

    additional_notes: Optional[str] = Field(None, description="Additional patient notes")

class SpecialistRecommendationSchema(BaseModel):
    """Schema for individual specialist recommendation."""
    specialist_id: str = Field(..., description="Unique specialist identifier")
    name: str = Field(..., description="Specialist name")
    specialty: str = Field(..., description="Medical specialty")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasoning: str = Field(..., description="Human-readable reasoning for recommendation")
    metadata: Dict[str, Any] = Field(..., description="Additional specialist metadata")

class TreatmentRankingSchema(BaseModel):
    """Schema for treatment-specific ranking results."""
    name: str = Field(..., description="Treatment option name")
    ranked_providers: List[str] = Field(..., description="List of NPI numbers ranked by relevance")
    explanation: str = Field(..., description="Explanation of ranking for this treatment")
    provider_links: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific content links")

class TreatmentRankingsResponseSchema(BaseModel):
    """Schema for treatment-specific rankings response."""
    treatment_rankings: Dict[str, TreatmentRankingSchema] = Field(..., description="Rankings grouped by treatment option")
    total_treatments: int = Field(..., ge=0, description="Total number of treatments ranked")
    message: str = Field(..., description="Response message")

class RecommendationResponseSchema(BaseModel):
    """Schema for complete recommendation response."""
    patient_profile: Dict[str, Any] = Field(..., description="Unified patient profile and medical analysis results")
    recommendations: List[SpecialistRecommendationSchema] = Field(..., description="Ranked specialist recommendations")
    total_candidates_found: int = Field(..., ge=0, description="Total candidates found during retrieval")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")
    retrieval_strategies_used: List[str] = Field(..., description="Retrieval strategies used")
    timestamp: datetime = Field(..., description="Response timestamp")
    shared_specialist_information: Optional[Dict[str, Any]] = Field(None, description="Treatment-grouped Pinecone data for NPI ranking")

class SpecialistRecommendationRequestSchema(BaseModel):
    """Schema for specialist recommendation request."""
    patient_input: str = Field(..., min_length=1, description="Patient description, symptoms, conditions, etc.")
    location_preference: Optional[str] = Field(None, description="Preferred location for specialist")




class SpecialistSearchRequestSchema(BaseModel):
    """Schema for specialist search request."""
    specialty: str = Field(..., min_length=1, description="Medical specialty to search for")
    location: Optional[str] = Field(None, description="Location filter")
    top_k: int = Field(20, ge=1, le=100, description="Number of results to return")

class SpecialistSearchResponseSchema(BaseModel):
    """Schema for specialist search response."""
    specialty: str = Field(..., description="Searched specialty")
    location: Optional[str] = Field(None, description="Location filter applied")
    results: List[Dict[str, Any]] = Field(..., description="Search results")
    total_found: int = Field(..., ge=0, description="Total number of results found")

class ServiceStatsSchema(BaseModel):
    """Schema for service statistics."""
    pinecone_index_name: str = Field(..., description="Pinecone index name")
    total_vectors: int = Field(..., ge=0, description="Total vectors in index")
    index_dimension: int = Field(..., ge=0, description="Vector dimension")
    index_metric: str = Field(..., description="Distance metric used")
    service_status: str = Field(..., description="Service health status")
    last_updated: datetime = Field(..., description="Last update timestamp")

class HealthCheckSchema(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(..., description="Check timestamp")

class SpecialtiesResponseSchema(BaseModel):
    """Schema for available specialties response."""
    specialties: List[str] = Field(..., description="List of available specialties")
    total_count: int = Field(..., ge=0, description="Total number of specialties")

# Validation schemas

class SpecialtyValidator:
    """Validator for medical specialties."""
    VALID_SPECIALTIES = [
        "cardiology", "dermatology", "endocrinology", "gastroenterology",
        "neurology", "orthopedics", "psychiatry", "pulmonology",
        "urology", "oncology", "pediatrics", "gynecology",
        "ophthalmology", "otolaryngology", "radiology", "pathology"
    ]
    
    @classmethod
    def validate(cls, specialty: str) -> bool:
        """Validate medical specialty."""
        return specialty.lower() in cls.VALID_SPECIALTIES

# Error schemas
class ErrorResponseSchema(BaseModel):
    """Schema for error responses."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

class ValidationErrorSchema(BaseModel):
    """Schema for validation errors."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Any = Field(..., description="Value that failed validation")
