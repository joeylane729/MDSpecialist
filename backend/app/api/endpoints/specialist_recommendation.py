"""
Specialist Recommendation API Endpoints

FastAPI endpoints for specialist recommendation functionality.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from ...services.specialist_recommendation_service import SpecialistRecommendationService
from ...models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/specialist-recommendation", tags=["specialist-recommendation"])

# Pydantic models for API
class SpecialistRecommendationRequest(BaseModel):
    """Request model for specialist recommendations."""
    patient_input: str = Field(..., description="Patient description, symptoms, conditions, etc.")
    location_preference: Optional[str] = Field(None, description="Preferred location for specialist")
    insurance_preference: Optional[str] = Field(None, description="Insurance requirements")
    urgency_level: str = Field("medium", description="Urgency level: low, medium, high, emergency")
    max_recommendations: int = Field(10, ge=1, le=50, description="Maximum number of recommendations")

class SpecialistRecommendationResponse(BaseModel):
    """Response model for specialist recommendations."""
    patient_profile: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    total_candidates_found: int
    processing_time_ms: int
    retrieval_strategies_used: List[str]
    timestamp: datetime

class SpecialistSearchRequest(BaseModel):
    """Request model for specialist search."""
    specialty: str = Field(..., description="Medical specialty to search for")
    location: Optional[str] = Field(None, description="Location filter")
    top_k: int = Field(20, ge=1, le=100, description="Number of results to return")

class ServiceStatsResponse(BaseModel):
    """Response model for service statistics."""
    pinecone_index_name: str
    total_vectors: int
    index_dimension: int
    index_metric: str
    service_status: str
    last_updated: datetime

# Dependency to get service instance
def get_specialist_service() -> SpecialistRecommendationService:
    """Get specialist recommendation service instance."""
    return SpecialistRecommendationService()

@router.post("/recommendations", response_model=SpecialistRecommendationResponse)
async def get_specialist_recommendations(
    request: SpecialistRecommendationRequest,
    service: SpecialistRecommendationService = Depends(get_specialist_service)
):
    """
    Get specialist recommendations for a patient.
    
    This endpoint processes patient input and returns ranked specialist recommendations
    using multiple retrieval strategies and intelligent ranking.
    """
    try:
        logger.info(f"Received recommendation request for patient: {request.patient_input[:100]}...")
        
        # Get recommendations
        response = await service.get_specialist_recommendations(
            patient_input=request.patient_input,
            location_preference=request.location_preference,
            insurance_preference=request.insurance_preference,
            urgency_level=request.urgency_level,
            max_recommendations=request.max_recommendations
        )
        
        # Convert to response model
        return SpecialistRecommendationResponse(
            patient_profile={
                "symptoms": response.patient_profile.symptoms,
                "conditions": response.patient_profile.conditions,
                "specialties_needed": response.patient_profile.specialties_needed,
                "urgency_level": response.patient_profile.urgency_level,
                "location_preference": response.patient_profile.location_preference,
                "insurance_preference": response.patient_profile.insurance_preference,
                "additional_notes": response.patient_profile.additional_notes
            },
            recommendations=[
                {
                    "specialist_id": rec.specialist_id,
                    "name": rec.name,
                    "specialty": rec.specialty,
                    "relevance_score": rec.relevance_score,
                    "confidence_score": rec.confidence_score,
                    "reasoning": rec.reasoning,
                    "metadata": rec.metadata
                }
                for rec in response.recommendations
            ],
            total_candidates_found=response.total_candidates_found,
            processing_time_ms=response.processing_time_ms,
            retrieval_strategies_used=response.retrieval_strategies_used,
            timestamp=response.timestamp
        )
        
    except Exception as e:
        logger.error(f"Error in specialist recommendations endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@router.get("/specialist/{specialist_id}")
async def get_specialist_by_id(
    specialist_id: str,
    service: SpecialistRecommendationService = Depends(get_specialist_service)
):
    """
    Get detailed information about a specific specialist.
    
    Args:
        specialist_id: Unique identifier for the specialist
        
    Returns:
        Specialist details or 404 if not found
    """
    try:
        specialist = await service.get_specialist_by_id(specialist_id)
        
        if not specialist:
            raise HTTPException(status_code=404, detail="Specialist not found")
        
        return specialist
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving specialist {specialist_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving specialist: {str(e)}")

@router.post("/search")
async def search_specialists_by_specialty(
    request: SpecialistSearchRequest,
    service: SpecialistRecommendationService = Depends(get_specialist_service)
):
    """
    Search for specialists by specialty and optional location.
    
    Args:
        request: Search request with specialty and optional location
        
    Returns:
        List of specialist records matching the criteria
    """
    try:
        specialists = await service.search_specialists_by_specialty(
            specialty=request.specialty,
            location=request.location,
            top_k=request.top_k
        )
        
        return {
            "specialty": request.specialty,
            "location": request.location,
            "results": specialists,
            "total_found": len(specialists)
        }
        
    except Exception as e:
        logger.error(f"Error searching specialists: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching specialists: {str(e)}")

@router.get("/stats", response_model=ServiceStatsResponse)
async def get_service_stats(
    service: SpecialistRecommendationService = Depends(get_specialist_service)
):
    """
    Get statistics about the specialist recommendation service.
    
    Returns:
        Service statistics including Pinecone index information
    """
    try:
        stats = service.get_service_stats()
        
        return ServiceStatsResponse(
            pinecone_index_name=stats["pinecone_index_name"],
            total_vectors=stats["total_vectors"],
            index_dimension=stats["index_dimension"],
            index_metric=stats["index_metric"],
            service_status=stats["service_status"],
            last_updated=datetime.fromisoformat(stats["last_updated"])
        )
        
    except Exception as e:
        logger.error(f"Error getting service stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting service stats: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the specialist recommendation service.
    
    Returns:
        Simple health status
    """
    return {
        "status": "healthy",
        "service": "specialist-recommendation",
        "timestamp": datetime.now().isoformat()
    }

# Additional utility endpoints
@router.get("/specialties")
async def get_available_specialties():
    """
    Get list of available medical specialties.
    
    Returns:
        List of available specialties
    """
    specialties = [
        "cardiology", "dermatology", "endocrinology", "gastroenterology",
        "neurology", "orthopedics", "psychiatry", "pulmonology",
        "urology", "oncology", "pediatrics", "gynecology",
        "ophthalmology", "otolaryngology", "radiology", "pathology"
    ]
    
    return {
        "specialties": specialties,
        "total_count": len(specialties)
    }

@router.get("/urgency-levels")
async def get_urgency_levels():
    """
    Get available urgency levels.
    
    Returns:
        List of available urgency levels
    """
    urgency_levels = ["low", "medium", "high", "emergency"]
    
    return {
        "urgency_levels": urgency_levels,
        "descriptions": {
            "low": "Routine or preventive care",
            "medium": "Standard medical care needed",
            "high": "Urgent medical attention required",
            "emergency": "Immediate medical attention required"
        }
    }
