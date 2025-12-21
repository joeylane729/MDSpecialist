#!/usr/bin/env python3
"""
Script to check reviews for a specific doctor with keyword filtering
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models.healthgrades_review import HealthgradesReview

def check_reviews_for_npi(npi: str, keywords: str):
    """Check reviews for a specific NPI with keyword filtering"""
    db = next(get_db())
    
    # Parse keywords
    keyword_list = [k.strip().lower() for k in keywords.split(' OR ') if k.strip()]
    print(f"🔍 Searching for NPI: {npi}")
    print(f"📋 Keywords: {keyword_list}")
    print()
    
    # Get all reviews for this NPI
    all_reviews = db.query(HealthgradesReview).filter(
        HealthgradesReview.npi == int(npi)
    ).order_by(HealthgradesReview.review_index).all()
    
    print(f"📊 Total reviews found: {len(all_reviews)}")
    print()
    
    # Filter by keywords
    relevant_reviews = []
    for review in all_reviews:
        if review.review_text:
            review_text_lower = review.review_text.lower()
            if any(keyword in review_text_lower for keyword in keyword_list):
                relevant_reviews.append(review)
    
    print(f"✅ Relevant reviews (containing keywords): {len(relevant_reviews)}")
    print()
    
    # Show sample relevant reviews
    if relevant_reviews:
        print("📝 Sample relevant reviews:")
        print("-" * 80)
        for i, review in enumerate(relevant_reviews[:5], 1):
            print(f"\n{i}. Review #{review.review_index}")
            print(f"   Author: {review.review_author}")
            print(f"   Date: {review.review_date}")
            print(f"   Text preview: {review.review_text[:200]}...")
            # Highlight keywords
            text_lower = review.review_text.lower()
            found_keywords = [kw for kw in keyword_list if kw in text_lower]
            print(f"   Contains keywords: {', '.join(found_keywords)}")
    else:
        print("❌ No relevant reviews found")
        print()
        print("📝 Sample of all reviews (first 3):")
        for i, review in enumerate(all_reviews[:3], 1):
            print(f"\n{i}. Review #{review.review_index}")
            print(f"   Text preview: {review.review_text[:200] if review.review_text else 'No text'}...")
    
    db.close()
    return len(relevant_reviews), len(all_reviews)

if __name__ == "__main__":
    # Theodore Schwartz NPI from logs
    npi = "1811916455"
    keywords = "pituitary adenoma OR pituitary tumor OR pituitary tumour OR pituitary neoplasm OR pituitary microadenoma OR pituitary macroadenoma"
    
    relevant_count, total_count = check_reviews_for_npi(npi, keywords)
    print()
    print("=" * 80)
    print(f"📊 SUMMARY:")
    print(f"   Total reviews: {total_count}")
    print(f"   Relevant reviews: {relevant_count}")
    print(f"   Percentage: {(relevant_count / total_count * 100) if total_count > 0 else 0:.1f}%")

