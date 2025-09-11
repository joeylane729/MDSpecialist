from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from ..models.doctor import Doctor
from ..schemas.match import MatchRequest, MatchResponse
from ..schemas.doctor import DoctorResponse
from .doctor_service import DoctorService
# Temporarily disabled NPI service import
# from .npi_service import NPIService
import time

class MatchService:
    """Service for handling doctor matching logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.doctor_service = DoctorService(db)
        # self.npi_service = NPIService(db)  # Temporarily disabled
    
    def match_doctors(self, match_request: MatchRequest) -> MatchResponse:
        """Match patients with doctors based on diagnosis and location."""
        start_time = time.time()
        
        # Search for matching providers using NPI data
        providers = self.npi_service.search_providers_by_diagnosis_and_location(
            diagnosis=match_request.diagnosis,
            metro_area=match_request.metro_area,
            max_results=match_request.max_results
        )
        
        # Calculate search duration
        search_duration_ms = int((time.time() - start_time) * 1000)
        
        # Convert doctors to response schemas
        doctor_responses = []
        for doctor in doctors:
            doctor_response = DoctorResponse(
                id=doctor.id,
                first_name=doctor.first_name,
                last_name=doctor.last_name,
                middle_name=doctor.middle_name,
                title=doctor.title,
                specialty=doctor.specialty,
                subspecialty=doctor.subspecialty,
                email=doctor.email,
                phone=doctor.phone,
                website=doctor.website,
                address_line1=doctor.address_line1,
                address_line2=doctor.address_line2,
                city=doctor.city,
                state=doctor.state,
                zip_code=doctor.zip_code,
                metro_area=doctor.metro_area,
                latitude=doctor.latitude,
                longitude=doctor.longitude,
                medical_school=doctor.medical_school,
                medical_school_tier=doctor.medical_school_tier,
                graduation_year=doctor.graduation_year,
                residency_program=doctor.residency_program,
                residency_tier=doctor.residency_tier,
                fellowship_programs=doctor.fellowship_programs,
                board_certifications=doctor.board_certifications,
                years_experience=doctor.years_experience,
                clinical_years=doctor.clinical_years,
                research_years=doctor.research_years,
                teaching_years=doctor.teaching_years,
                leadership_roles=doctor.leadership_roles,
                awards=doctor.awards,
                website_mentions=doctor.website_mentions,
                patient_reviews=doctor.patient_reviews,
                social_media=doctor.social_media,
                directory_listings=doctor.directory_listings,
                full_name=doctor.full_name,
                display_name=doctor.display_name,
                location_summary=doctor.location_summary,
                overall_grade=getattr(doctor, 'overall_grade', None),
                rank=getattr(doctor, 'rank', None),
                created_at=doctor.created_at,
                updated_at=doctor.updated_at
            )
            doctor_responses.append(doctor_response)
        
        # Create search summary
        radius_str = f" within {match_request.location_radius} miles" if match_request.location_radius else ""
        search_summary = f"{match_request.diagnosis} in {match_request.metro_area}{radius_str}"
        
        return MatchResponse(
            diagnosis=match_request.diagnosis,
            metro_area=match_request.metro_area,
            location_radius=match_request.location_radius,
            total_doctors_found=len(doctor_responses),
            doctors=doctor_responses,
            search_summary=search_summary,
            search_duration_ms=search_duration_ms
        )
    
    def get_match_suggestions(self, diagnosis: str) -> List[str]:
        """Get suggested diagnoses based on partial input."""
        # This could be enhanced with a medical terminology database
        common_diagnoses = [
            "Type 2 Diabetes",
            "Hypertension",
            "Asthma",
            "Depression",
            "Anxiety",
            "Arthritis",
            "Heart Disease",
            "Cancer",
            "Stroke",
            "Chronic Kidney Disease"
        ]
        
        suggestions = []
        diagnosis_lower = diagnosis.lower()
        
        for common_diagnosis in common_diagnoses:
            if diagnosis_lower in common_diagnosis.lower():
                suggestions.append(common_diagnosis)
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def get_metro_suggestions(self, metro_input: str) -> List[str]:
        """Get suggested metro areas based on partial input."""
        # Temporarily using hardcoded suggestions until NPI service is fixed
        common_metros = [
            "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
            "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
            "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
            "Fort Worth, TX", "Columbus, OH", "Charlotte, NC", "San Francisco, CA",
            "Indianapolis, IN", "Seattle, WA", "Denver, CO", "Washington, DC"
        ]
        
        suggestions = []
        metro_input_lower = metro_input.lower()
        
        for metro in common_metros:
            if metro_input_lower in metro.lower():
                suggestions.append(metro)
        
        return suggestions[:5]
