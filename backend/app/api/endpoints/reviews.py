from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models.healthgrades_review import HealthgradesReview
from pydantic import BaseModel

router = APIRouter()


class ReviewResponse(BaseModel):
    """Response model for review data"""
    id: int
    npi: int
    first_name: Optional[str]
    last_name: Optional[str]
    review_index: Optional[int]
    review_text: Optional[str]
    review_author: Optional[str]
    review_date: Optional[str]
    
    class Config:
        from_attributes = True


@router.get("/reviews/{npi}", response_model=List[ReviewResponse])
async def get_reviews_by_npi(
    npi: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all reviews for a specific provider by NPI.
    Returns up to `limit` reviews (default 100).
    """
    reviews = db.query(HealthgradesReview).filter(
        HealthgradesReview.npi == npi
    ).order_by(
        HealthgradesReview.review_index
    ).limit(limit).all()
    
    if not reviews:
        return []
    
    return reviews


@router.get("/reviews/{npi}/count")
async def get_review_count(
    npi: int,
    db: Session = Depends(get_db)
):
    """Get the total count of reviews for a provider"""
    from sqlalchemy import func
    
    count = db.query(func.count(HealthgradesReview.id)).filter(
        HealthgradesReview.npi == npi
    ).scalar()
    
    return {"npi": npi, "review_count": count or 0}

