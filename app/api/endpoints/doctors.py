from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.doctor_service import DoctorService
from ...schemas.doctor import DoctorResponse, DoctorListResponse

router = APIRouter()

@router.get("/doctors/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific doctor.
    
    Returns comprehensive information including education, experience,
    publications, and other credentials.
    """
    try:
        doctor_service = DoctorService(db)
        doctor = doctor_service.get_doctor_with_details(doctor_id)
        
        if not doctor:
            raise HTTPException(
                status_code=404,
                detail=f"Doctor with ID {doctor_id} not found"
            )
        
        return doctor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get doctor: {str(e)}"
        )

@router.get("/doctors", response_model=DoctorListResponse)
async def get_doctors(
    skip: int = 0,
    limit: int = 20,
    specialty: Optional[str] = None,
    metro_area: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get a list of doctors with optional filtering.
    
    Supports pagination and filtering by specialty and metro area.
    """
    try:
        doctor_service = DoctorService(db)
        doctors = doctor_service.get_doctors(
            skip=skip,
            limit=limit,
            specialty=specialty,
            metro_area=metro_area
        )
        
        # Convert to response schemas
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
                created_at=doctor.created_at,
                updated_at=doctor.updated_at
            )
            doctor_responses.append(doctor_response)
        
        # Calculate pagination info
        total_count = len(doctor_responses)  # This should be a proper count query in production
        total_pages = (total_count + limit - 1) // limit
        current_page = (skip // limit) + 1
        
        return DoctorListResponse(
            doctors=doctor_responses,
            total_count=total_count,
            page=current_page,
            page_size=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get doctors: {str(e)}"
        )
