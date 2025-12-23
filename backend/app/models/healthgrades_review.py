from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import BIGINT
from .base import Base
from datetime import datetime


class HealthgradesReview(Base):
    """Model for Healthgrades review data"""
    __tablename__ = "healthgrades_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    npi = Column(BIGINT, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    reviews_md_file = Column(String(255))
    review_index = Column(Integer)
    review_text = Column(Text)
    review_author = Column(String(255))
    review_date = Column(String(50))  # Store as string since format varies
    review_rating = Column(Integer)  # Star rating (1-5)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<HealthgradesReview(npi={self.npi}, review_index={self.review_index})>"

