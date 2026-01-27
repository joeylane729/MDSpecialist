from sqlalchemy import Column, String, Text, Index
from .base import Base

class ICD10Code(Base):
    """Model for ICD-10 codes and their descriptions."""
    
    __tablename__ = "icd10_codes"
    
    # ICD-10 Code (primary key)
    code = Column(String(20), nullable=False, primary_key=True, index=True)
    
    # Description
    description = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<ICD10Code(code={self.code}, description={self.description[:50] if self.description else None}...)>"
