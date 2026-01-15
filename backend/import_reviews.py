#!/usr/bin/env python3
"""
Simple script to import Healthgrades review data from CSV into database
"""
import csv
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine, SessionLocal
from app.models import Base, HealthgradesReview

def create_table():
    """Create the healthgrades_reviews table if it doesn't exist"""
    print("📊 Creating healthgrades_reviews table if needed...")
    Base.metadata.create_all(bind=engine, tables=[HealthgradesReview.__table__])
    print("✅ Table ready")

def import_reviews(csv_path: str, batch_size: int = 1000):
    """Import reviews from CSV file into database"""
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found: {csv_path}")
        return False
    
    # Create table first
    create_table()
    
    # Create database session
    db = SessionLocal()
    
    try:
        print(f"📂 Reading CSV file: {csv_path}")
        
        # Count total rows first (for progress tracking)
        with open(csv_path, 'r', encoding='utf-8') as f:
            total_rows = sum(1 for _ in f) - 1  # Subtract header
        
        print(f"📋 Found {total_rows:,} reviews to import")
        
        # Read and import in batches
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            batch = []
            imported_count = 0
            
            for row in reader:
                # Create review object
                review = HealthgradesReview(
                    npi=int(row['npi']) if row['npi'] else None,
                    first_name=row['first_name'] or None,
                    last_name=row['last_name'] or None,
                    reviews_md_file=row['reviews_md_file'] or None,
                    review_index=int(row['review_index']) if row['review_index'] else None,
                    review_text=row['review_text'] or None,
                    review_author=row['review_author'] or None,
                    review_date=row['review_date'] or None,
                    review_rating=int(row['review_rating']) if row.get('review_rating') and row['review_rating'].strip() else None
                )
                
                batch.append(review)
                
                # Commit batch
                if len(batch) >= batch_size:
                    db.bulk_save_objects(batch)
                    db.commit()
                    imported_count += len(batch)
                    print(f"   ✓ Imported {imported_count:,} / {total_rows:,} reviews ({(imported_count/total_rows*100):.1f}%)")
                    batch = []
            
            # Commit remaining
            if batch:
                db.bulk_save_objects(batch)
                db.commit()
                imported_count += len(batch)
                print(f"   ✓ Imported {imported_count:,} / {total_rows:,} reviews (100.0%)")
        
        print(f"\n🎉 Successfully imported {imported_count:,} reviews!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    # Default CSV path
    csv_path = Path(__file__).parent.parent / "data" / "healthgrades" / "reviews_scraper" / "npi_reviews_mapping.csv"
    
    # Allow override from command line
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    
    print("=" * 60)
    print("🏥 Healthgrades Review Import Tool")
    print("=" * 60)
    print(f"CSV file: {csv_path}")
    print()
    
    success = import_reviews(str(csv_path))
    
    if success:
        print("\n✅ Import completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Import failed!")
        sys.exit(1)

