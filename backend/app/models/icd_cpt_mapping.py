from sqlalchemy import Column, String, Text, Index
from .base import BaseModel

class IcdCptMapping(BaseModel):
    """Model for ICD-10 to CPT code crosswalk mappings."""
    
    __tablename__ = "icd_cpt_mappings"
    
    # CPT Code (HCPCS Code)
    cpt_code = Column(String(20), nullable=False, index=True)
    
    # ICD-10 Code
    icd10_code = Column(String(20), nullable=False, index=True)
    
    # Additional fields that might be in the Excel files
    # (will be populated based on actual column names)
    description = Column(Text, nullable=True)
    additional_field = Column(Text, nullable=True)
    
    # Composite index for fast lookups
    __table_args__ = (
        Index('idx_cpt_icd10', 'cpt_code', 'icd10_code'),
    )
    
    def __repr__(self):
        return f"<IcdCptMapping(cpt={self.cpt_code}, icd10={self.icd10_code})>"
