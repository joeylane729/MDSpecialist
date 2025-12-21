from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
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


@router.get("/reviews/{npi}/search", response_model=List[ReviewResponse])
async def search_reviews_by_keywords(
    npi: int,
    keywords: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Search reviews for a provider by keywords.
    If keywords are provided, only returns reviews containing those keywords.
    If no keywords, returns all reviews (same as get_reviews_by_npi).
    
    Keywords should be separated by " OR " (e.g., "headache OR migraine").
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 [REVIEWS SEARCH API] NPI: {npi}, keywords: {keywords}, limit: {limit}")
    
    query = db.query(HealthgradesReview).filter(
        HealthgradesReview.npi == npi
    )
    
    if keywords:
        # Split by " OR " to get keyword variations (same as PubMed search)
        keyword_variations = [k.strip() for k in keywords.split(" OR ") if k.strip()]
        
        if keyword_variations:
            # Build ILIKE conditions for each keyword
            from sqlalchemy import or_
            
            conditions = []
            for keyword in keyword_variations:
                # Case-insensitive search in review_text
                conditions.append(
                    HealthgradesReview.review_text.ilike(f'%{keyword}%')
                )
            
            # Combine with OR (any keyword match counts)
            query = query.filter(or_(*conditions))
            logger.info(f"🔍 [REVIEWS SEARCH API] Searching with {len(keyword_variations)} keyword(s): {keyword_variations}")
    
    # Order by review_index and limit
    reviews = query.order_by(
        HealthgradesReview.review_index
    ).limit(limit).all()
    
    logger.info(f"🔍 [REVIEWS SEARCH API] Found {len(reviews)} matching reviews for NPI {npi}")
    
    return reviews


@router.get("/reviews/{npi}/search/count")
async def get_search_review_count(
    npi: int,
    keywords: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get the count of reviews matching the keywords"""
    from sqlalchemy import func, or_
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📊 [REVIEWS SEARCH COUNT API] NPI: {npi}, keywords: {keywords}")
    
    query = db.query(func.count(HealthgradesReview.id)).filter(
        HealthgradesReview.npi == npi
    )
    
    if keywords:
        keyword_variations = [k.strip() for k in keywords.split(" OR ") if k.strip()]
        
        if keyword_variations:
            from sqlalchemy import or_
            
            conditions = []
            for keyword in keyword_variations:
                conditions.append(
                    HealthgradesReview.review_text.ilike(f'%{keyword}%')
                )
            
            query = query.filter(or_(*conditions))
    
    count = query.scalar()
    
    logger.info(f"📊 [REVIEWS SEARCH COUNT API] Found {count or 0} matching reviews")
    
    return {
        "npi": npi,
        "keywords": keywords,
        "matching_review_count": count or 0
    }


@router.post("/reviews/batch")
async def batch_get_reviews(
    npis: List[int],
    keywords: Optional[str] = None,
    limit_per_npi: int = 100,
    db: Session = Depends(get_db)
) -> Dict[str, List[ReviewResponse]]:
    """
    Batch fetch reviews for multiple NPIs in a single query.
    Returns a dictionary mapping NPI to list of reviews.
    
    Similar to how PubMed articles are batched in the ranking API.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 [BATCH REVIEWS API] Fetching reviews for {len(npis)} NPIs with keywords: {keywords}")
    
    # Build query for all NPIs at once
    query = db.query(HealthgradesReview).filter(
        HealthgradesReview.npi.in_(npis)
    )
    
    # Add keyword filtering if provided
    if keywords:
        keyword_variations = [k.strip() for k in keywords.split(" OR ") if k.strip()]
        if keyword_variations:
            from sqlalchemy import or_
            conditions = []
            for keyword in keyword_variations:
                conditions.append(
                    HealthgradesReview.review_text.ilike(f'%{keyword}%')
                )
            query = query.filter(or_(*conditions))
            logger.info(f"🔍 [BATCH REVIEWS API] Filtering with {len(keyword_variations)} keyword(s)")
    
    # Fetch all reviews and group by NPI
    all_reviews = query.order_by(
        HealthgradesReview.npi,
        HealthgradesReview.review_index
    ).all()
    
    logger.info(f"📦 [BATCH REVIEWS API] Found {len(all_reviews)} total reviews across {len(npis)} NPIs")
    
    # Group by NPI and limit per NPI
    reviews_by_npi: Dict[str, List[ReviewResponse]] = {}
    for review in all_reviews:
        npi_str = str(review.npi)
        if npi_str not in reviews_by_npi:
            reviews_by_npi[npi_str] = []
        
        if len(reviews_by_npi[npi_str]) < limit_per_npi:
            reviews_by_npi[npi_str].append(ReviewResponse.model_validate(review))
    
    logger.info(f"✅ [BATCH REVIEWS API] Returning reviews for {len(reviews_by_npi)} NPIs")
    
    return reviews_by_npi

