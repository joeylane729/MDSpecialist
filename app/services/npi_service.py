from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List, Optional, Dict, Any
import sys
import os

# Import scoring functions from app directory

class NPIService:
    """Service for querying NPI provider data from PostgreSQL."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_provider_by_npi(self, npi: str) -> Optional[Dict[str, Any]]:
        """Get a provider by NPI number using raw SQL."""
        try:
            result = self.db.execute(text("""
                SELECT * FROM npi_providers WHERE npi = :npi
            """), {"npi": npi})
            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return None
        except Exception as e:
            print(f"Error getting provider by NPI: {e}")
            return None
    
    def get_providers_by_state(self, state: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get providers by state using raw SQL."""
        try:
            result = self.db.execute(text("""
                SELECT * FROM npi_providers 
                WHERE provider_business_practice_location_address_state_name ILIKE :state
                LIMIT :limit
            """), {"state": f"%{state}%", "limit": limit})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            print(f"Error getting providers by state: {e}")
            return []
    
    def get_providers_by_city(self, city: str, state: str = None, limit: int = 100) -> List[NPIProvider]:
        """Get providers by city and optionally state."""
        query = self.db.query(NPIProvider).filter(
            NPIProvider.provider_business_practice_location_address_city_name.ilike(f"%{city}%")
        )
        
        if state:
            query = query.filter(
                NPIProvider.provider_business_practice_location_address_state_name.ilike(f"%{state}%")
            )
        
        return query.limit(limit).all()
    
    def get_providers_by_taxonomy(self, taxonomy_code: str, limit: int = 100) -> List[NPIProvider]:
        """Get providers by taxonomy code."""
        return self.db.query(NPIProvider).filter(
            NPIProvider.healthcare_provider_taxonomy_code_1 == taxonomy_code
        ).limit(limit).all()
    
    def search_providers_by_name(self, name: str, limit: int = 100) -> List[NPIProvider]:
        """Search providers by name (first or last)."""
        return self.db.query(NPIProvider).filter(
            (NPIProvider.provider_first_name.ilike(f"%{name}%")) |
            (NPIProvider.provider_last_name.ilike(f"%{name}%"))
        ).limit(limit).all()
    
    def get_providers_by_metro_area(self, metro_area: str, limit: int = 100) -> List[NPIProvider]:
        """Get providers by metro area (approximated by city/state)."""
        # This is a simplified metro area search - in practice you'd want a proper metro area mapping
        return self.db.query(NPIProvider).filter(
            NPIProvider.provider_business_practice_location_address_city_name.ilike(f"%{metro_area}%")
        ).limit(limit).all()
    
    def search_providers_by_diagnosis_and_location(
        self, 
        diagnosis: str, 
        metro_area: str,
        state: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for providers based on diagnosis and location."""
        
        # Start with location-based query
        query = self.db.query(NPIProvider)
        
        # Filter by location
        if metro_area:
            query = query.filter(
                NPIProvider.provider_business_practice_location_address_city_name.ilike(f"%{metro_area}%")
            )
        
        if state:
            query = query.filter(
                NPIProvider.provider_business_practice_location_address_state_name.ilike(f"%{state}%")
            )
        
        # Filter to only individual providers (not organizations)
        query = query.filter(NPIProvider.entity_type_code == "1")
        
        # Get more than needed for ranking
        providers = query.limit(max_results * 3).all()
        
        # Convert to dictionaries for processing
        provider_dicts = []
        for provider in providers:
            provider_dict = {
                'id': provider.id,
                'npi': provider.npi,
                'first_name': provider.provider_first_name,
                'last_name': provider.provider_last_name,
                'middle_name': provider.provider_middle_name,
                'credentials': provider.provider_credential_text,
                'specialty': self._get_specialty_from_taxonomy(provider.healthcare_provider_taxonomy_code_1),
                'subspecialty': self._get_specialty_from_taxonomy(provider.healthcare_provider_taxonomy_code_2),
                'city': provider.provider_business_practice_location_address_city_name,
                'state': provider.provider_business_practice_location_address_state_name,
                'zip_code': provider.provider_business_practice_location_address_postal_code,
                'phone': provider.provider_business_practice_location_address_telephone_number,
                'address': provider.provider_first_line_business_practice_location_address,
                'taxonomy_codes': self._get_all_taxonomy_codes(provider),
                'license_number': provider.provider_license_number_1,
                'license_state': provider.provider_license_number_state_code_1,
                'full_name': provider.full_name,
                'display_name': provider.display_name,
                'location_summary': provider.location_summary,
                'is_individual': provider.is_individual,
                'is_organization': provider.is_organization
            }
            provider_dicts.append(provider_dict)
        
        # Try to use scoring if available
        try:
            from ..scoring import rank_doctors
            # Create patient location for scoring
            patient_location = {
                'metro_area': metro_area,
                'state': state
            }
            ranked_providers = rank_doctors(provider_dicts, patient_location)
            return ranked_providers[:max_results]
        except ImportError:
            # Fallback if scoring module not available
            return provider_dicts[:max_results]
    
    def get_provider_details(self, npi: str) -> Optional[Dict[str, Any]]:
        """Get detailed provider information."""
        provider = self.get_provider_by_npi(npi)
        if not provider:
            return None
        
        return {
            'id': provider.id,
            'npi': provider.npi,
            'first_name': provider.provider_first_name,
            'last_name': provider.provider_last_name,
            'middle_name': provider.provider_middle_name,
            'credentials': provider.provider_credential_text,
            'organization_name': provider.provider_organization_name,
            'city': provider.provider_business_practice_location_address_city_name,
            'state': provider.provider_business_practice_location_address_state_name,
            'zip_code': provider.provider_business_practice_location_address_postal_code,
            'phone': provider.provider_business_practice_location_address_telephone_number,
            'fax': provider.provider_business_practice_location_address_fax_number,
            'address': provider.provider_first_line_business_practice_location_address,
            'address2': provider.provider_second_line_business_practice_location_address,
            'taxonomy_codes': self._get_all_taxonomy_codes(provider),
            'license_numbers': self._get_all_license_numbers(provider),
            'full_name': provider.full_name,
            'display_name': provider.display_name,
            'location_summary': provider.location_summary,
            'is_individual': provider.is_individual,
            'is_organization': provider.is_organization,
            'enumeration_date': provider.provider_enumeration_date,
            'last_update_date': provider.last_update_date
        }
    
    def get_taxonomy_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get taxonomy code suggestions based on query."""
        # This would need a taxonomy lookup table for proper suggestions
        # For now, return some common taxonomy codes
        common_taxonomies = [
            "207Q00000X",  # Family Medicine
            "207R00000X",  # Internal Medicine
            "207T00000X",  # Neurological Surgery
            "207X00000X",  # Orthopaedic Surgery
            "208D00000X",  # General Practice
            "208G00000X",  # Thoracic Surgery
            "208M00000X",  # Hospitalist
            "208U00000X",  # Clinical Pharmacology
        ]
        
        return [t for t in common_taxonomies if query.lower() in t.lower()][:limit]
    
    def get_state_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get state suggestions based on query using raw SQL."""
        try:
            result = self.db.execute(text("""
                SELECT DISTINCT provider_business_practice_location_address_state_name
                FROM npi_providers 
                WHERE provider_business_practice_location_address_state_name ILIKE :query
                LIMIT :limit
            """), {"query": f"%{query}%", "limit": limit})
            
            states = result.fetchall()
            return [state[0] for state in states if state[0]]
        except Exception as e:
            print(f"Error getting state suggestions: {e}")
            return []
    
    def get_city_suggestions(self, query: str, state: str = None, limit: int = 10) -> List[str]:
        """Get city suggestions based on query using raw SQL."""
        try:
            if state:
                sql = """
                    SELECT DISTINCT provider_business_practice_location_address_city_name
                    FROM npi_providers 
                    WHERE provider_business_practice_location_address_city_name ILIKE :query
                      AND provider_business_practice_location_address_state_name ILIKE :state
                    LIMIT :limit
                """
                result = self.db.execute(text(sql), {"query": f"%{query}%", "state": f"%{state}%", "limit": limit})
            else:
                sql = """
                    SELECT DISTINCT provider_business_practice_location_address_city_name
                    FROM npi_providers 
                    WHERE provider_business_practice_location_address_city_name ILIKE :query
                    LIMIT :limit
                """
                result = self.db.execute(text(sql), {"query": f"%{query}%", "limit": limit})
            
            cities = result.fetchall()
            return [city[0] for city in cities if city[0]]
        except Exception as e:
            print(f"Error getting city suggestions: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics using raw SQL."""
        try:
            # Get total providers
            result = self.db.execute(text("SELECT COUNT(*) FROM npi_providers"))
            total_providers = result.scalar()
            
            # Get individual providers
            result = self.db.execute(text("SELECT COUNT(*) FROM npi_providers WHERE entity_type_code = '1'"))
            individual_providers = result.scalar()
            
            # Get organization providers
            result = self.db.execute(text("SELECT COUNT(*) FROM npi_providers WHERE entity_type_code = '2'"))
            organization_providers = result.scalar()
            
            # Get state distribution
            result = self.db.execute(text("""
                SELECT provider_business_practice_location_address_state_name, COUNT(*) as count
                FROM npi_providers 
                WHERE provider_business_practice_location_address_state_name IS NOT NULL
                GROUP BY provider_business_practice_location_address_state_name
                ORDER BY count DESC
                LIMIT 10
            """))
            state_counts = result.fetchall()
            
            return {
                'total_providers': total_providers,
                'individual_providers': individual_providers,
                'organization_providers': organization_providers,
                'top_states': [{'state': state, 'count': count} for state, count in state_counts]
            }
        except Exception as e:
            print(f"Error getting NPI statistics: {e}")
            return {
                'total_providers': 0,
                'individual_providers': 0,
                'organization_providers': 0,
                'top_states': [],
                'error': str(e)
            }
    
    def _get_specialty_from_taxonomy(self, taxonomy_code: str) -> str:
        """Convert taxonomy code to specialty name."""
        if not taxonomy_code:
            return "Unknown"
        
        # This is a simplified mapping - in practice you'd want a complete taxonomy lookup
        taxonomy_mapping = {
            "207Q00000X": "Family Medicine",
            "207R00000X": "Internal Medicine",
            "207T00000X": "Neurological Surgery",
            "207X00000X": "Orthopaedic Surgery",
            "208D00000X": "General Practice",
            "208G00000X": "Thoracic Surgery",
            "208M00000X": "Hospitalist",
            "208U00000X": "Clinical Pharmacology",
        }
        
        return taxonomy_mapping.get(taxonomy_code, f"Specialty ({taxonomy_code})")
    
    def _get_all_taxonomy_codes(self, provider: NPIProvider) -> List[str]:
        """Get all taxonomy codes for a provider."""
        codes = []
        for i in range(1, 16):
            code = getattr(provider, f'healthcare_provider_taxonomy_code_{i}')
            if code:
                codes.append(code)
        return codes
    
    def _get_all_license_numbers(self, provider: NPIProvider) -> List[Dict[str, str]]:
        """Get all license numbers for a provider."""
        licenses = []
        for i in range(1, 16):
            license_num = getattr(provider, f'provider_license_number_{i}')
            license_state = getattr(provider, f'provider_license_number_state_code_{i}')
            if license_num and license_state:
                licenses.append({
                    'number': license_num,
                    'state': license_state
                })
        return licenses
