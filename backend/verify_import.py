#!/usr/bin/env python3
"""Quick script to verify review import"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import HealthgradesReview
from sqlalchemy import func

db = SessionLocal()

try:
    # Total count
    total = db.query(func.count(HealthgradesReview.id)).scalar()
    print(f"✅ Total reviews in database: {total:,}")
    
    # Unique doctors
    unique_npis = db.query(func.count(func.distinct(HealthgradesReview.npi))).scalar()
    print(f"✅ Unique doctors with reviews: {unique_npis:,}")
    
    # Sample reviews
    print(f"\n📋 Sample reviews:")
    samples = db.query(HealthgradesReview).limit(3).all()
    for review in samples:
        print(f"  - Dr. {review.first_name} {review.last_name} (NPI: {review.npi})")
        print(f"    Review #{review.review_index}: {review.review_text[:100]}...")
        print(f"    Date: {review.review_date}, Author: {review.review_author or 'Anonymous'}")
        print()
    
    # Top reviewed doctors
    print(f"🏆 Top 5 most-reviewed doctors:")
    top_doctors = db.query(
        HealthgradesReview.npi,
        HealthgradesReview.first_name,
        HealthgradesReview.last_name,
        func.count(HealthgradesReview.id).label('review_count')
    ).group_by(
        HealthgradesReview.npi,
        HealthgradesReview.first_name,
        HealthgradesReview.last_name
    ).order_by(
        func.count(HealthgradesReview.id).desc()
    ).limit(5).all()
    
    for i, (npi, first, last, count) in enumerate(top_doctors, 1):
        print(f"  {i}. Dr. {first} {last} (NPI: {npi}): {count} reviews")
    
finally:
    db.close()

