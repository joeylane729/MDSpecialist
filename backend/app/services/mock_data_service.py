from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ..models.doctor import Doctor
from ..models.publication import Publication
from ..models.talk import Talk
from datetime import date, datetime
import json

class MockDataService:
    """Service for populating the database with mock data."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_mock_doctors(self) -> List[Doctor]:
        """Create mock doctor data for demonstration."""
        
        # Check if doctors already exist
        existing_doctors = self.db.query(Doctor).count()
        if existing_doctors > 0:
            return self.db.query(Doctor).all()
        
        mock_doctors = [
            {
                "first_name": "Sarah",
                "last_name": "Johnson",
                "title": "Dr.",
                "specialty": "Cardiology",
                "subspecialty": "Interventional Cardiology",
                "email": "sarah.johnson@heartcenter.com",
                "phone": "(555) 123-4567",
                "website": "https://drjohnsoncardiology.com",
                "address_line1": "123 Heart Center Dr",
                "city": "New York",
                "state": "NY",
                "zip_code": "10001",
                "metro_area": "New York, NY",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "medical_school": "Harvard Medical School",
                "medical_school_tier": "top_10",
                "graduation_year": 2005,
                "residency_program": "Massachusetts General Hospital",
                "residency_tier": "top_10",
                "fellowship_programs": [
                    {"program": "Stanford Interventional Cardiology", "tier": "top_10"}
                ],
                "board_certifications": ["Cardiovascular Disease", "Interventional Cardiology"],
                "years_experience": 18,
                "clinical_years": 15,
                "research_years": 12,
                "teaching_years": 8,
                "leadership_roles": ["Director of Cardiac Catheterization Lab"],
                "awards": ["American Heart Association Young Investigator Award"],
                "website_mentions": 45,
                "patient_reviews": [
                    {"rating": 5, "comment": "Excellent cardiologist"},
                    {"rating": 5, "comment": "Very knowledgeable and caring"}
                ],
                "social_media": {"twitter": 2500, "linkedin": 5000},
                "directory_listings": ["Healthgrades", "Vitals", "ZocDoc"]
            },
            {
                "first_name": "Michael",
                "last_name": "Chen",
                "title": "Dr.",
                "specialty": "Oncology",
                "subspecialty": "Hematologic Oncology",
                "email": "mchen@cancercenter.org",
                "phone": "(555) 234-5678",
                "website": "https://drchenoncology.com",
                "address_line1": "456 Cancer Center Blvd",
                "city": "Los Angeles",
                "state": "CA",
                "zip_code": "90210",
                "metro_area": "Los Angeles, CA",
                "latitude": 34.0522,
                "longitude": -118.2437,
                "medical_school": "Stanford University School of Medicine",
                "medical_school_tier": "top_10",
                "graduation_year": 2008,
                "residency_program": "UCLA Medical Center",
                "residency_tier": "top_25",
                "fellowship_programs": [
                    {"program": "MD Anderson Cancer Center", "tier": "top_10"}
                ],
                "board_certifications": ["Internal Medicine", "Medical Oncology"],
                "years_experience": 15,
                "clinical_years": 12,
                "research_years": 10,
                "teaching_years": 6,
                "leadership_roles": ["Associate Director of Clinical Research"],
                "awards": ["ASCO Young Investigator Award"],
                "website_mentions": 38,
                "patient_reviews": [
                    {"rating": 5, "comment": "Compassionate and thorough"},
                    {"rating": 4, "comment": "Great doctor, very knowledgeable"}
                ],
                "social_media": {"linkedin": 3000},
                "directory_listings": ["Healthgrades", "Vitals"]
            },
            {
                "first_name": "Emily",
                "last_name": "Rodriguez",
                "title": "Dr.",
                "specialty": "Neurology",
                "subspecialty": "Movement Disorders",
                "email": "erodriguez@neuroinstitute.edu",
                "phone": "(555) 345-6789",
                "website": "https://dremilyneuro.com",
                "address_line1": "789 Neurology Institute Way",
                "city": "Chicago",
                "state": "IL",
                "zip_code": "60601",
                "metro_area": "Chicago, IL",
                "latitude": 41.8781,
                "longitude": -87.6298,
                "medical_school": "Northwestern University Feinberg School of Medicine",
                "medical_school_tier": "top_25",
                "graduation_year": 2010,
                "residency_program": "University of Chicago Medical Center",
                "residency_tier": "top_25",
                "fellowship_programs": [
                    {"program": "Johns Hopkins Movement Disorders", "tier": "top_10"}
                ],
                "board_certifications": ["Neurology", "Movement Disorders"],
                "years_experience": 13,
                "clinical_years": 10,
                "research_years": 8,
                "teaching_years": 5,
                "leadership_roles": ["Director of Movement Disorders Clinic"],
                "awards": ["American Academy of Neurology Research Award"],
                "website_mentions": 32,
                "patient_reviews": [
                    {"rating": 5, "comment": "Excellent neurologist"},
                    {"rating": 5, "comment": "Very caring and knowledgeable"}
                ],
                "social_media": {"linkedin": 2000},
                "directory_listings": ["Healthgrades", "Vitals"]
            },
            {
                "first_name": "David",
                "last_name": "Thompson",
                "title": "Dr.",
                "specialty": "Orthopedics",
                "subspecialty": "Sports Medicine",
                "email": "dthompson@sportsmed.com",
                "phone": "(555) 456-7890",
                "website": "https://drthompsonsports.com",
                "address_line1": "321 Sports Medicine Plaza",
                "city": "Houston",
                "state": "TX",
                "zip_code": "77001",
                "metro_area": "Houston, TX",
                "latitude": 29.7604,
                "longitude": -95.3698,
                "medical_school": "Baylor College of Medicine",
                "medical_school_tier": "top_50",
                "graduation_year": 2012,
                "residency_program": "University of Texas Health Science Center",
                "residency_tier": "top_50",
                "fellowship_programs": [
                    {"program": "Hospital for Special Surgery", "tier": "top_25"}
                ],
                "board_certifications": ["Orthopedic Surgery", "Sports Medicine"],
                "years_experience": 11,
                "clinical_years": 9,
                "research_years": 6,
                "teaching_years": 4,
                "leadership_roles": ["Team Physician for Houston Rockets"],
                "awards": ["American Orthopedic Society for Sports Medicine Award"],
                "website_mentions": 28,
                "patient_reviews": [
                    {"rating": 4, "comment": "Great sports medicine doctor"},
                    {"rating": 5, "comment": "Helped me recover quickly"}
                ],
                "social_media": {"instagram": 1500, "linkedin": 1800},
                "directory_listings": ["Healthgrades", "Vitals"]
            },
            {
                "first_name": "Lisa",
                "last_name": "Wang",
                "title": "Dr.",
                "specialty": "Endocrinology",
                "subspecialty": "Diabetes and Metabolism",
                "email": "lwang@endocenter.com",
                "phone": "(555) 567-8901",
                "website": "https://drwangdiabetes.com",
                "address_line1": "654 Endocrine Center Dr",
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "metro_area": "Seattle, WA",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "medical_school": "University of Washington School of Medicine",
                "medical_school_tier": "top_25",
                "graduation_year": 2009,
                "residency_program": "University of Washington Medical Center",
                "residency_tier": "top_25",
                "fellowship_programs": [
                    {"program": "Joslin Diabetes Center", "tier": "top_10"}
                ],
                "board_certifications": ["Internal Medicine", "Endocrinology"],
                "years_experience": 14,
                "clinical_years": 11,
                "research_years": 9,
                "teaching_years": 7,
                "leadership_roles": ["Director of Diabetes Education Program"],
                "awards": ["Endocrine Society Outstanding Clinical Investigator"],
                "website_mentions": 35,
                "patient_reviews": [
                    {"rating": 5, "comment": "Excellent endocrinologist"},
                    {"rating": 5, "comment": "Very knowledgeable about diabetes"}
                ],
                "social_media": {"linkedin": 2200},
                "directory_listings": ["Healthgrades", "Vitals", "ZocDoc"]
            }
        ]
        
        doctors = []
        for mock_data in mock_doctors:
            doctor = Doctor(**mock_data)
            self.db.add(doctor)
            doctors.append(doctor)
        
        self.db.commit()
        
        # Refresh to get IDs
        for doctor in doctors:
            self.db.refresh(doctor)
        
        return doctors
    
    def create_mock_publications(self, doctors: List[Doctor]) -> List[Publication]:
        """Create mock publications for doctors."""
        
        # Check if publications already exist
        existing_pubs = self.db.query(Publication).count()
        if existing_pubs > 0:
            return self.db.query(Publication).all()
        
        mock_publications = [
            # Dr. Johnson (Cardiology)
            {
                "title": "Novel Approaches to Coronary Artery Disease Management",
                "authors": "Johnson, S., Smith, A., Brown, B.",
                "journal": "Journal of the American College of Cardiology",
                "publication_type": "peer_reviewed",
                "year": 2023,
                "doi": "10.1016/j.jacc.2023.01.001",
                "citation_count": 15,
                "doctor_id": 1
            },
            {
                "title": "Interventional Cardiology Techniques in Modern Practice",
                "authors": "Johnson, S., Wilson, C.",
                "journal": "Cardiovascular Interventions",
                "publication_type": "journal_article",
                "year": 2022,
                "doi": "10.1016/j.cvi.2022.05.002",
                "citation_count": 8,
                "doctor_id": 1
            },
            # Dr. Chen (Oncology)
            {
                "title": "Advances in Hematologic Malignancy Treatment",
                "authors": "Chen, M., Davis, R., Lee, K.",
                "journal": "Blood",
                "publication_type": "peer_reviewed",
                "year": 2023,
                "doi": "10.1182/blood.2023.02.001",
                "citation_count": 22,
                "doctor_id": 2
            },
            # Dr. Rodriguez (Neurology)
            {
                "title": "Movement Disorders: Current Understanding and Future Directions",
                "authors": "Rodriguez, E., Martinez, P.",
                "journal": "Neurology",
                "publication_type": "peer_reviewed",
                "year": 2022,
                "doi": "10.1212/wnl.2022.03.001",
                "citation_count": 12,
                "doctor_id": 3
            },
            # Dr. Thompson (Orthopedics)
            {
                "title": "Sports Medicine Rehabilitation Protocols",
                "authors": "Thompson, D., Anderson, J.",
                "journal": "American Journal of Sports Medicine",
                "publication_type": "journal_article",
                "year": 2023,
                "doi": "10.1177/ajsm.2023.04.001",
                "citation_count": 6,
                "doctor_id": 4
            },
            # Dr. Wang (Endocrinology)
            {
                "title": "Diabetes Management in the Digital Age",
                "authors": "Wang, L., Taylor, S., Garcia, M.",
                "journal": "Diabetes Care",
                "publication_type": "peer_reviewed",
                "year": 2023,
                "doi": "10.2337/dc23.01.001",
                "citation_count": 18,
                "doctor_id": 5
            }
        ]
        
        publications = []
        for mock_data in mock_publications:
            publication = Publication(**mock_data)
            self.db.add(publication)
            publications.append(publication)
        
        self.db.commit()
        
        # Refresh to get IDs
        for publication in publications:
            self.db.refresh(publication)
        
        return publications
    
    def create_mock_talks(self, doctors: List[Doctor]) -> List[Talk]:
        """Create mock talks for doctors."""
        
        # Check if talks already exist
        existing_talks = self.db.query(Talk).count()
        if existing_talks > 0:
            return self.db.query(Talk).all()
        
        mock_talks = [
            # Dr. Johnson
            {
                "title": "Innovations in Interventional Cardiology",
                "event_name": "American Heart Association Scientific Sessions",
                "event_type": "conference",
                "year": 2023,
                "venue": "Philadelphia Convention Center",
                "city": "Philadelphia",
                "state": "PA",
                "presentation_type": "keynote",
                "duration_minutes": 45,
                "audience_size": 500,
                "doctor_id": 1
            },
            # Dr. Chen
            {
                "title": "Emerging Therapies in Blood Cancers",
                "event_name": "American Society of Clinical Oncology Annual Meeting",
                "event_type": "conference",
                "year": 2023,
                "venue": "McCormick Place",
                "city": "Chicago",
                "state": "IL",
                "presentation_type": "oral",
                "duration_minutes": 20,
                "audience_size": 300,
                "doctor_id": 2
            },
            # Dr. Rodriguez
            {
                "title": "Movement Disorders: Clinical Pearls",
                "event_name": "American Academy of Neurology Annual Meeting",
                "event_type": "conference",
                "year": 2023,
                "venue": "Boston Convention Center",
                "city": "Boston",
                "state": "MA",
                "presentation_type": "oral",
                "duration_minutes": 15,
                "audience_size": 200,
                "doctor_id": 3
            },
            # Dr. Thompson
            {
                "title": "Sports Medicine Rehabilitation Strategies",
                "event_name": "American Orthopedic Society for Sports Medicine",
                "event_type": "conference",
                "year": 2023,
                "venue": "Washington State Convention Center",
                "city": "Seattle",
                "state": "WA",
                "presentation_type": "poster",
                "duration_minutes": 10,
                "audience_size": 150,
                "doctor_id": 4
            },
            # Dr. Wang
            {
                "title": "Digital Health in Diabetes Management",
                "event_name": "American Diabetes Association Scientific Sessions",
                "event_type": "conference",
                "year": 2023,
                "venue": "San Diego Convention Center",
                "city": "San Diego",
                "state": "CA",
                "presentation_type": "oral",
                "duration_minutes": 25,
                "audience_size": 250,
                "doctor_id": 5
            }
        ]
        
        talks = []
        for mock_data in mock_talks:
            talk = Talk(**mock_data)
            self.db.add(talk)
            talks.append(talk)
        
        self.db.commit()
        
        # Refresh to get IDs
        for talk in talks:
            self.db.refresh(talk)
        
        return talks
    
    def populate_database(self) -> Dict[str, int]:
        """Populate the database with all mock data."""
        print("Creating mock doctors...")
        doctors = self.create_mock_doctors()
        
        print("Creating mock publications...")
        publications = self.create_mock_publications(doctors)
        
        print("Creating mock talks...")
        talks = self.create_mock_talks(doctors)
        
        return {
            "doctors": len(doctors),
            "publications": len(publications),
            "talks": len(talks)
        }
