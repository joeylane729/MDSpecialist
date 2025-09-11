from sqlalchemy import Column, String, Text, Integer, TIMESTAMP
from .base import BaseModel

class NPIProvider(BaseModel):
    """NPI Provider model mapping to the PostgreSQL npi_providers table."""
    
    __tablename__ = "npi_providers"
    
    # Primary key (auto-generated)
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core NPI information
    npi = Column(String(10), index=True)
    entity_type_code = Column(String(1))
    replacement_npi = Column(String(10))
    employer_identification_number = Column(String(20))
    
    # Provider organization information
    provider_organization_name = Column(Text)
    
    # Individual provider information
    provider_last_name = Column(String(100), index=True)
    provider_first_name = Column(String(100), index=True)
    provider_middle_name = Column(String(100))
    provider_name_prefix_text = Column(String(10))
    provider_name_suffix_text = Column(String(10))
    provider_credential_text = Column(Text)
    
    # Other organization information
    provider_other_organization_name = Column(Text)
    provider_other_organization_name_type_code = Column(String(1))
    provider_other_last_name = Column(String(100))
    provider_other_first_name = Column(String(100))
    provider_other_middle_name = Column(String(100))
    provider_other_name_prefix_text = Column(String(10))
    provider_other_name_suffix_text = Column(String(10))
    provider_other_credential_text = Column(Text)
    provider_other_last_name_type_code = Column(String(1))
    
    # Mailing address
    provider_first_line_business_mailing_address = Column(Text)
    provider_second_line_business_mailing_address = Column(Text)
    provider_business_mailing_address_city_name = Column(String(100))
    provider_business_mailing_address_state_name = Column(Text, index=True)
    provider_business_mailing_address_postal_code = Column(Text)
    provider_business_mailing_address_country_code = Column(Text)
    provider_business_mailing_address_telephone_number = Column(String(20))
    provider_business_mailing_address_fax_number = Column(String(20))
    
    # Practice location address
    provider_first_line_business_practice_location_address = Column(Text)
    provider_second_line_business_practice_location_address = Column(Text)
    provider_business_practice_location_address_city_name = Column(String(100), index=True)
    provider_business_practice_location_address_state_name = Column(Text, index=True)
    provider_business_practice_location_address_postal_code = Column(Text)
    provider_business_practice_location_address_country_code = Column(Text)
    provider_business_practice_location_address_telephone_number = Column(String(20))
    provider_business_practice_location_address_fax_number = Column(String(20))
    
    # Dates
    provider_enumeration_date = Column(String(10))
    last_update_date = Column(String(10))
    npi_deactivation_reason_code = Column(String(2))
    npi_deactivation_date = Column(String(10))
    npi_reactivation_date = Column(String(10))
    
    # Provider details
    provider_sex_code = Column(String(1))
    authorized_official_last_name = Column(String(100))
    authorized_official_first_name = Column(String(100))
    authorized_official_middle_name = Column(String(100))
    authorized_official_title_or_position = Column(Text)
    authorized_official_telephone_number = Column(String(20))
    
    # Healthcare provider taxonomy codes (primary and secondary)
    healthcare_provider_taxonomy_code_1 = Column(String(10), index=True)
    provider_license_number_1 = Column(String(20))
    provider_license_number_state_code_1 = Column(Text, index=True)
    healthcare_provider_primary_taxonomy_switch_1 = Column(String(1))
    
    healthcare_provider_taxonomy_code_2 = Column(String(10))
    provider_license_number_2 = Column(String(20))
    provider_license_number_state_code_2 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_2 = Column(String(1))
    
    healthcare_provider_taxonomy_code_3 = Column(String(10))
    provider_license_number_3 = Column(String(20))
    provider_license_number_state_code_3 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_3 = Column(String(1))
    
    healthcare_provider_taxonomy_code_4 = Column(String(10))
    provider_license_number_4 = Column(String(20))
    provider_license_number_state_code_4 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_4 = Column(String(1))
    
    healthcare_provider_taxonomy_code_5 = Column(String(10))
    provider_license_number_5 = Column(String(20))
    provider_license_number_state_code_5 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_5 = Column(String(1))
    
    # Additional taxonomy codes (6-15)
    healthcare_provider_taxonomy_code_6 = Column(String(10))
    provider_license_number_6 = Column(String(20))
    provider_license_number_state_code_6 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_6 = Column(String(1))
    
    healthcare_provider_taxonomy_code_7 = Column(String(10))
    provider_license_number_7 = Column(String(20))
    provider_license_number_state_code_7 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_7 = Column(String(1))
    
    healthcare_provider_taxonomy_code_8 = Column(String(10))
    provider_license_number_8 = Column(String(20))
    provider_license_number_state_code_8 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_8 = Column(String(1))
    
    healthcare_provider_taxonomy_code_9 = Column(String(10))
    provider_license_number_9 = Column(String(20))
    provider_license_number_state_code_9 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_9 = Column(String(1))
    
    healthcare_provider_taxonomy_code_10 = Column(String(10))
    provider_license_number_10 = Column(String(20))
    provider_license_number_state_code_10 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_10 = Column(String(1))
    
    healthcare_provider_taxonomy_code_11 = Column(String(10))
    provider_license_number_11 = Column(String(20))
    provider_license_number_state_code_11 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_11 = Column(String(1))
    
    healthcare_provider_taxonomy_code_12 = Column(String(10))
    provider_license_number_12 = Column(String(20))
    provider_license_number_state_code_12 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_12 = Column(String(1))
    
    healthcare_provider_taxonomy_code_13 = Column(String(10))
    provider_license_number_13 = Column(String(20))
    provider_license_number_state_code_13 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_13 = Column(String(1))
    
    healthcare_provider_taxonomy_code_14 = Column(String(10))
    provider_license_number_14 = Column(String(20))
    provider_license_number_state_code_14 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_14 = Column(String(1))
    
    healthcare_provider_taxonomy_code_15 = Column(String(10))
    provider_license_number_15 = Column(String(20))
    provider_license_number_state_code_15 = Column(Text)
    healthcare_provider_primary_taxonomy_switch_15 = Column(String(1))
    
    # Other provider identifiers (1-50)
    other_provider_identifier_1 = Column(String(20))
    other_provider_identifier_type_code_1 = Column(String(2))
    other_provider_identifier_state_1 = Column(String(2))
    other_provider_identifier_issuer_1 = Column(String(100))
    
    # ... (other identifiers 2-50 would go here, but keeping it concise)
    
    # Organization details
    is_sole_proprietor = Column(String(1))
    is_organization_subpart = Column(String(1))
    parent_organization_lbn = Column(Text)
    parent_organization_tin = Column(String(20))
    
    # Authorized official details
    authorized_official_name_prefix_text = Column(String(10))
    authorized_official_name_suffix_text = Column(String(10))
    authorized_official_credential_text = Column(Text)
    
    # Taxonomy groups
    healthcare_provider_taxonomy_group_1 = Column(String(50))
    healthcare_provider_taxonomy_group_2 = Column(String(50))
    healthcare_provider_taxonomy_group_3 = Column(String(50))
    healthcare_provider_taxonomy_group_4 = Column(String(50))
    healthcare_provider_taxonomy_group_5 = Column(String(50))
    healthcare_provider_taxonomy_group_6 = Column(String(50))
    healthcare_provider_taxonomy_group_7 = Column(String(50))
    healthcare_provider_taxonomy_group_8 = Column(String(50))
    healthcare_provider_taxonomy_group_9 = Column(String(50))
    healthcare_provider_taxonomy_group_10 = Column(String(50))
    healthcare_provider_taxonomy_group_11 = Column(String(50))
    healthcare_provider_taxonomy_group_12 = Column(String(50))
    healthcare_provider_taxonomy_group_13 = Column(String(50))
    healthcare_provider_taxonomy_group_14 = Column(String(50))
    healthcare_provider_taxonomy_group_15 = Column(String(50))
    
    # Certification
    certification_date = Column(String(10))
    
    # Timestamps
    created_at = Column(TIMESTAMP)
    
    @property
    def full_name(self):
        """Get provider's full name."""
        if self.provider_middle_name:
            return f"{self.provider_first_name} {self.provider_middle_name} {self.provider_last_name}"
        return f"{self.provider_first_name} {self.provider_last_name}"
    
    @property
    def display_name(self):
        """Get provider's display name with credentials."""
        name = self.full_name
        if self.provider_credential_text:
            return f"{name}, {self.provider_credential_text}"
        return name
    
    @property
    def location_summary(self):
        """Get location summary."""
        parts = [self.provider_business_practice_location_address_city_name, 
                self.provider_business_practice_location_address_state_name]
        return ", ".join(filter(None, parts))
    
    @property
    def is_individual(self):
        """Check if this is an individual provider (not organization)."""
        return self.entity_type_code == "1"
    
    @property
    def is_organization(self):
        """Check if this is an organization provider."""
        return self.entity_type_code == "2"
