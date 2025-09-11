#!/usr/bin/env python3
"""
Load Medical School Rankings Data

Script to load medical school rankings from CSV into the database.
"""

import os
import sys
import csv
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, engine
from app.models.medical_school_ranking import MedicalSchoolRanking
from sqlalchemy.orm import Session


def load_medical_school_rankings():
    """Load medical school rankings from CSV file into database."""
    
    print("🏥 Loading Medical School Rankings Data")
    print("=" * 50)
    
    # Get the path to the CSV file
    csv_file_path = Path(__file__).parent.parent.parent / "data" / "MED SCHOOL RANKINGS.csv"
    
    if not csv_file_path.exists():
        print(f"❌ CSV file not found at: {csv_file_path}")
        return False
    
    print(f"📁 Reading from: {csv_file_path}")
    
    # Create the table if it doesn't exist
    MedicalSchoolRanking.metadata.create_all(bind=engine)
    print("✅ Database table created/verified")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Clear existing data
        db.query(MedicalSchoolRanking).delete()
        print("🗑️  Cleared existing medical school rankings data")
        
        # Load data from CSV
        loaded_count = 0
        skipped_count = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                try:
                    # Parse the data
                    rank = int(row['Rank']) if row['Rank'] else None
                    school_listed = row['School (as listed)'].strip()
                    city = row['City'].strip() if row['City'] else None
                    state_region = row['State/Region'].strip() if row['State/Region'] else None
                    
                    # Parse MCAT score (handle empty values)
                    mcat_score = None
                    if row['MCAT'] and row['MCAT'].strip():
                        try:
                            mcat_score = float(row['MCAT'])
                        except ValueError:
                            pass
                    
                    # Parse GPA (handle empty values)
                    gpa = None
                    if row['GPA'] and row['GPA'].strip():
                        try:
                            gpa = float(row['GPA'])
                        except ValueError:
                            pass
                    
                    full_official_name = row['Full Official Name (best-effort)'].strip() if row['Full Official Name (best-effort)'] else None
                    needs_review = row['Needs Review?'].strip().upper() == 'TRUE' if row['Needs Review?'] else False
                    
                    # Create the record
                    medical_school = MedicalSchoolRanking(
                        rank=rank,
                        school_listed=school_listed,
                        city=city,
                        state_region=state_region,
                        mcat_score=mcat_score,
                        gpa=gpa,
                        full_official_name=full_official_name,
                        needs_review=needs_review
                    )
                    
                    db.add(medical_school)
                    loaded_count += 1
                    
                    if loaded_count % 20 == 0:
                        print(f"  📊 Loaded {loaded_count} records...")
                        
                except Exception as e:
                    print(f"  ⚠️  Skipped row {loaded_count + skipped_count + 1}: {str(e)}")
                    skipped_count += 1
                    continue
        
        # Commit all changes
        db.commit()
        print(f"✅ Successfully loaded {loaded_count} medical school rankings")
        
        if skipped_count > 0:
            print(f"⚠️  Skipped {skipped_count} records due to errors")
        
        # Verify the data
        total_in_db = db.query(MedicalSchoolRanking).count()
        print(f"📊 Total records in database: {total_in_db}")
        
        # Show some sample data
        print("\n📋 Sample of loaded data:")
        sample_schools = db.query(MedicalSchoolRanking).order_by(MedicalSchoolRanking.rank).limit(5).all()
        for school in sample_schools:
            print(f"  {school.rank}. {school.school_listed} ({school.city}, {school.state_region}) - MCAT: {school.mcat_score}, GPA: {school.gpa}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading data: {str(e)}")
        db.rollback()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = load_medical_school_rankings()
    if success:
        print("\n🎉 Medical school rankings data loaded successfully!")
    else:
        print("\n💥 Failed to load medical school rankings data!")
        sys.exit(1)
