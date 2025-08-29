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
    urgency_level: str = Field(..., description="Urgency level: low, medium, high, emergency")
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

class RecommendationResponseSchema(BaseModel):
    """Schema for complete recommendation response."""
    patient_profile: PatientProfileSchema = Field(..., description="Processed patient profile")
    recommendations: List[SpecialistRecommendationSchema] = Field(..., description="Ranked specialist recommendations")
    total_candidates_found: int = Field(..., ge=0, description="Total candidates found during retrieval")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")
    retrieval_strategies_used: List[str] = Field(..., description="Retrieval strategies used")
    timestamp: datetime = Field(..., description="Response timestamp")
    medical_analysis: Optional[Dict[str, Any]] = Field(None, description="Comprehensive medical analysis results")

class SpecialistRecommendationRequestSchema(BaseModel):
    """Schema for specialist recommendation request."""
    patient_input: str = Field(..., min_length=1, description="Patient description, symptoms, conditions, etc.")
    location_preference: Optional[str] = Field(None, description="Preferred location for specialist")

    urgency_level: str = Field("medium", description="Urgency level: low, medium, high, emergency")
    max_recommendations: int = Field(10, ge=1, le=50, description="Maximum number of recommendations")

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

class UrgencyLevelsResponseSchema(BaseModel):
    """Schema for urgency levels response."""
    urgency_levels: List[str] = Field(..., description="List of available urgency levels")
    descriptions: Dict[str, str] = Field(..., description="Descriptions for each urgency level")

# Validation schemas
class UrgencyLevelValidator:
    """Validator for urgency levels."""
    VALID_LEVELS = ["low", "medium", "high", "emergency"]
    
    @classmethod
    def validate(cls, level: str) -> bool:
        """Validate urgency level."""
        return level.lower() in cls.VALID_LEVELS

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
