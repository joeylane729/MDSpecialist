"""
Data models for specialist recommendation functionality.

This module contains the core data classes used throughout the specialist
recommendation system to avoid circular imports.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PatientProfile:
    """Structured patient profile for specialist matching."""
    symptoms: List[str]
    conditions: List[str]
    specialties_needed: List[str]
    urgency_level: str  # low, medium, high, emergency
    location_preference: Optional[str] = None

    additional_notes: Optional[str] = None

@dataclass
class SpecialistRecommendation:
    """Individual specialist recommendation with scoring."""
    specialist_id: str
    name: str
    specialty: str
    relevance_score: float
    confidence_score: float
    reasoning: str
    metadata: Dict[str, Any]

@dataclass
class RecommendationResponse:
    """Complete recommendation response."""
    patient_profile: PatientProfile
    recommendations: List[SpecialistRecommendation]
    total_candidates_found: int
    processing_time_ms: int
    retrieval_strategies_used: List[str]
    timestamp: datetime
    medical_analysis: Optional[Dict[str, Any]] = None
