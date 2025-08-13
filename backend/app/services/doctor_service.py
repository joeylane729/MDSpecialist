from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ..models.doctor import Doctor
from ..schemas.doctor import DoctorCreate, DoctorUpdate
import sys
import os

# Add shared directory to path for scoring functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
from scoring import calculate_overall_grade

class DoctorService:
    """Service for managing doctor data and operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_doctor(self, doctor_id: int) -> Optional[Doctor]:
        """Get a doctor by ID."""
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
    
    def get_doctors(
        self, 
        skip: int = 0, 
        limit: int = 100,
        specialty: Optional[str] = None,
        metro_area: Optional[str] = None
    ) -> List[Doctor]:
        """Get doctors with optional filtering."""
        query = self.db.query(Doctor)
        
        if specialty:
            query = query.filter(Doctor.specialty.ilike(f"%{specialty}%"))
        
        if metro_area:
            query = query.filter(Doctor.metro_area.ilike(f"%{metro_area}%"))
        
        return query.offset(skip).limit(limit).all()
    
    def create_doctor(self, doctor_data: DoctorCreate) -> Doctor:
        """Create a new doctor."""
        doctor = Doctor(**doctor_data.dict())
        self.db.add(doctor)
        self.db.commit()
        self.db.refresh(doctor)
        return doctor
    
    def update_doctor(self, doctor_id: int, doctor_data: DoctorUpdate) -> Optional[Doctor]:
        """Update an existing doctor."""
        doctor = self.get_doctor(doctor_id)
        if not doctor:
            return None
        
        update_data = doctor_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(doctor, field, value)
        
        self.db.commit()
        self.db.refresh(doctor)
        return doctor
    
    def delete_doctor(self, doctor_id: int) -> bool:
        """Delete a doctor."""
        doctor = self.get_doctor(doctor_id)
        if not doctor:
            return False
        
        self.db.delete(doctor)
        self.db.commit()
        return True
    
    def search_doctors_by_diagnosis(
        self, 
        diagnosis: str, 
        metro_area: str,
        location_radius: Optional[float] = None,
        specialty: Optional[str] = None,
        max_results: int = 20
    ) -> List[Doctor]:
        """Search for doctors based on diagnosis and location."""
        # Start with basic query
        query = self.db.query(Doctor)
        
        # Filter by metro area
        if metro_area:
            query = query.filter(Doctor.metro_area.ilike(f"%{metro_area}%"))
        
        # Filter by specialty if specified
        if specialty:
            query = query.filter(Doctor.specialty.ilike(f"%{specialty}%"))
        
        # Get all matching doctors
        doctors = query.limit(max_results * 2).all()  # Get more than needed for ranking
        
        # Convert to dictionaries for scoring
        doctor_dicts = []
        for doctor in doctors:
            doctor_dict = {
                'id': doctor.id,
                'first_name': doctor.first_name,
                'last_name': doctor.last_name,
                'specialty': doctor.specialty,
                'subspecialty': doctor.subspecialty,
                'medical_school_tier': doctor.medical_school_tier,
                'residency_tier': doctor.residency_tier,
                'fellowship_programs': doctor.fellowship_programs or [],
                'board_certifications': doctor.board_certifications or [],
                'years_experience': doctor.years_experience,
                'clinical_years': doctor.clinical_years,
                'research_years': doctor.research_years,
                'teaching_years': doctor.teaching_years,
                'leadership_roles': doctor.leadership_roles or [],
                'awards': doctor.awards or [],
                'website_mentions': doctor.website_mentions,
                'patient_reviews': doctor.patient_reviews or [],
                'social_media': doctor.social_media or {},
                'directory_listings': doctor.directory_listings or [],
                'location': {
                    'metro_area': doctor.metro_area,
                    'state': doctor.state
                },
                'publications': [],  # Will be populated if needed
                'talks': []  # Will be populated if needed
            }
            doctor_dicts.append(doctor_dict)
        
        # Create patient location for scoring
        patient_location = {
            'metro_area': metro_area,
            'state': None  # Could be extracted from metro_area if needed
        }
        
        # Import and use scoring function
        try:
            from scoring import rank_doctors
            ranked_doctors = rank_doctors(doctor_dicts, patient_location)
        except ImportError:
            # Fallback if scoring module not available
            ranked_doctors = doctor_dicts[:max_results]
        
        # Get the top results
        top_doctor_ids = [d['id'] for d in ranked_doctors[:max_results]]
        
        # Return the actual doctor objects in ranked order
        ranked_doctors_objects = []
        for doctor_id in top_doctor_ids:
            doctor = self.get_doctor(doctor_id)
            if doctor:
                # Add ranking information
                for ranked_doc in ranked_doctors:
                    if ranked_doc['id'] == doctor_id:
                        doctor.overall_grade = ranked_doc.get('overall_grade')
                        doctor.rank = ranked_doc.get('rank')
                        break
                ranked_doctors_objects.append(doctor)
        
        return ranked_doctors_objects
    
    def get_doctor_with_details(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """Get a doctor with all related details."""
        doctor = self.get_doctor(doctor_id)
        if not doctor:
            return None
        
        # Convert to dictionary and add computed properties
        doctor_dict = {
            'id': doctor.id,
            'first_name': doctor.first_name,
            'last_name': doctor.last_name,
            'middle_name': doctor.middle_name,
            'title': doctor.title,
            'specialty': doctor.specialty,
            'subspecialty': doctor.subspecialty,
            'email': doctor.email,
            'phone': doctor.phone,
            'website': doctor.website,
            'address_line1': doctor.address_line1,
            'address_line2': doctor.address_line2,
            'city': doctor.city,
            'state': doctor.state,
            'zip_code': doctor.zip_code,
            'metro_area': doctor.metro_area,
            'latitude': doctor.latitude,
            'longitude': doctor.longitude,
            'medical_school': doctor.medical_school,
            'medical_school_tier': doctor.medical_school_tier,
            'graduation_year': doctor.graduation_year,
            'residency_program': doctor.residency_program,
            'residency_tier': doctor.residency_tier,
            'fellowship_programs': doctor.fellowship_programs,
            'board_certifications': doctor.board_certifications,
            'years_experience': doctor.years_experience,
            'clinical_years': doctor.clinical_years,
            'research_years': doctor.research_years,
            'teaching_years': doctor.teaching_years,
            'leadership_roles': doctor.leadership_roles,
            'awards': doctor.awards,
            'website_mentions': doctor.website_mentions,
            'patient_reviews': doctor.patient_reviews,
            'social_media': doctor.social_media,
            'directory_listings': doctor.directory_listings,
            'full_name': doctor.full_name,
            'display_name': doctor.display_name,
            'location_summary': doctor.location_summary,
            'created_at': doctor.created_at,
            'updated_at': doctor.updated_at
        }
        
        return doctor_dict
