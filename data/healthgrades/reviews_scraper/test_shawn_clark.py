#!/usr/bin/env python3
"""Test script to scrape SHAWN CLARK's reviews with extra debugging"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.healthgrades.reviews_scraper.scrape_reviews import (
    setup_selenium_driver,
    extract_reviews_from_page,
    get_doctor_url,
    close_browser,
    save_reviews_to_markdown,
    save_reviews_to_csv
)

def test_shawn_clark():
    """Test scraping SHAWN CLARK's reviews"""
    npi = "1306849575"
    first_name = "SHAWN"
    last_name = "CLARK"
    filename = "hg_000008_SHAWN_CLARK.md"
    
    print(f"🧪 Testing SHAWN CLARK (NPI: {npi})")
    print("=" * 60)
    
    # Get URL
    url = get_doctor_url(npi, filename)
    if not url:
        print(f"❌ Could not find URL for {first_name} {last_name}")
        return
    
    print(f"✅ Found URL: {url}")
    
    # Setup browser
    driver = setup_selenium_driver()
    if not driver:
        print("❌ Failed to setup browser")
        return
    
    try:
        # Navigate to profile
        print(f"\n🌐 Navigating to: {url}")
        driver.get(url)
        time.sleep(3)
        
        # Handle popups
        print("🚫 Closing popups...")
        # Add popup handling code here if needed
        
        # Scroll to reviews section
        print("📜 Scrolling to reviews section...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(2)
        
        # Expand reviews
        print("🔽 Expanding reviews...")
        # Add review expansion code here
        
        # Extract reviews with extra debugging
        print("\n🔍 Extracting reviews (with extra debugging)...")
        reviews = extract_reviews_from_page(driver)
        
        print(f"\n📊 RESULTS:")
        print(f"   Total reviews extracted: {len(reviews)}")
        reviews_with_ratings = [r for r in reviews if r.get('rating')]
        print(f"   Reviews with ratings: {len(reviews_with_ratings)}")
        print(f"   Reviews without ratings: {len(reviews) - len(reviews_with_ratings)}")
        
        # Print first few reviews
        print(f"\n📝 First 5 reviews:")
        for i, review in enumerate(reviews[:5], 1):
            print(f"\n   Review {i}:")
            print(f"      Rating: {review.get('rating', 'N/A')}")
            print(f"      Author: {review.get('author', 'N/A')}")
            print(f"      Date: {review.get('date', 'N/A')}")
            print(f"      Text: {review.get('text', '')[:100]}...")
        
    finally:
        close_browser(driver)

if __name__ == "__main__":
    import time
    test_shawn_clark()

