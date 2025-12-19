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
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📋 [REVIEWS API] Received request for NPI: {npi} (type: {type(npi).__name__}), limit: {limit}")
    
    reviews = db.query(HealthgradesReview).filter(
        HealthgradesReview.npi == npi
    ).order_by(
        HealthgradesReview.review_index
    ).limit(limit).all()
    
    logger.info(f"📋 [REVIEWS API] Found {len(reviews)} reviews for NPI {npi}")
    
    if not reviews:
        # Log a sample of NPIs in the database for debugging
        sample_npis = db.query(HealthgradesReview.npi).distinct().limit(5).all()
        logger.warning(f"⚠️ [REVIEWS API] No reviews found for NPI {npi}. Sample NPIs in DB: {[n[0] for n in sample_npis]}")
        return []
    
    return reviews


@router.get("/reviews/{npi}/count")
async def get_review_count(
    npi: int,
    db: Session = Depends(get_db)
):
    """Get the total count of reviews for a provider"""
    from sqlalchemy import func
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📊 [REVIEWS COUNT API] Received request for NPI: {npi} (type: {type(npi).__name__})")
    
    count = db.query(func.count(HealthgradesReview.id)).filter(
        HealthgradesReview.npi == npi
    ).scalar()
    
    logger.info(f"📊 [REVIEWS COUNT API] Found {count or 0} reviews for NPI {npi}")
    
    return {"npi": npi, "review_count": count or 0}

