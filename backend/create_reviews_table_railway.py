#!/usr/bin/env python3
"""
Create the healthgrades_reviews table on Railway database
Run this with Railway's DATABASE_URL environment variable set
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine, SessionLocal
from app.models import Base, HealthgradesReview

def create_table():
    """Create the healthgrades_reviews table if it doesn't exist"""
    print("🔧 Creating healthgrades_reviews table on Railway database...")
    print(f"📍 Database: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")
    
    try:
        Base.metadata.create_all(bind=engine, tables=[HealthgradesReview.__table__])
        print("✅ Table created successfully!")
        
        # Verify the table exists
        db = SessionLocal()
        count = db.query(HealthgradesReview).count()
        print(f"✅ Verified: Table exists with {count} reviews")
        db.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🏥 Create Healthgrades Reviews Table")
    print("=" * 60)
    
    if create_table():
        print("\n✅ Success! Now redeploy Railway backend.")
        print("   The reviews endpoint should work after redeployment.")
        sys.exit(0)
    else:
        print("\n❌ Failed to create table")
        sys.exit(1)

