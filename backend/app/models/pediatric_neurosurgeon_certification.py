from sqlalchemy import Column, String, Text, Boolean
from .base import BaseModel

class PediatricNeurosurgeonCertification(BaseModel):
    """Model for pediatric neurosurgeon certification data from CSV matching."""
    
    __tablename__ = "pediatric_neurosurgeon_certifications"
    
    # NPI reference (stored as string with index, not FK constraint since npi_providers table may not have PK constraint)
    npi = Column(String(10), nullable=False, unique=True, index=True)
    
    # Matched status
    matched = Column(Boolean, nullable=False, index=True)
    
    # CSV data fields
    csv_name = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(50), nullable=True)
    country = Column(String(50), nullable=True)
    certificate_number = Column(String(50), nullable=True)
    year_certified = Column(Text, nullable=True)  # Can contain multiple years/newlines
    certified_through = Column(Text, nullable=True)  # Can contain dates or status
    
    # Removed relationship - no foreign key constraint exists between these tables
    # The npi column is used for lookups but is not a foreign key
    
    def __repr__(self):
        return f"<PediatricNeurosurgeonCertification(npi={self.npi}, matched={self.matched})>"

