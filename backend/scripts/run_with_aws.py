#!/usr/bin/env python3
"""
Script to create the npi_medical_school_mapping table using AWS Aurora.

Run this with: python scripts/run_with_aws.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the parent directory to the path so we can import our models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.npi_medical_school_mapping import NPIMedicalSchoolMapping
from app.models.base import Base

def create_table():
    """Create the npi_medical_school_mapping table."""
    
    # Get database URL from environment (AWS Aurora)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Error: DATABASE_URL environment variable not set")
        print("Make sure you're running this with DATABASE_URL set to your AWS Aurora connection string")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        print("🔗 Connecting to AWS Aurora database...")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Create the table
        print("📋 Creating npi_medical_school_mapping table...")
        NPIMedicalSchoolMapping.__table__.create(engine, checkfirst=True)
        
        print("✅ Table 'npi_medical_school_mapping' created successfully!")
        
        # Verify table exists and show structure
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'npi_medical_school_mapping'
                ORDER BY ordinal_position
            """))
            
            print("\n📊 Table structure:")
            print("Column Name          | Data Type | Nullable | Default")
            print("-" * 60)
            for row in result:
                print(f"{row[0]:<20} | {row[1]:<9} | {row[2]:<8} | {row[3] or 'None'}")
            
            # Check if table is empty
            result = conn.execute(text("SELECT COUNT(*) FROM npi_medical_school_mapping"))
            count = result.scalar()
            print(f"\n📈 Table is currently empty ({count} rows)")
            
            return True
                
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Creating NPI Medical School Mapping Table")
    print("=" * 50)
    
    success = create_table()
    
    if success:
        print("\n🎉 Table creation completed successfully!")
        print("\nTable 'npi_medical_school_mapping' is ready to use.")
        print("You can now populate it with NPI numbers and medical school IDs.")
    else:
        print("\n💥 Table creation failed!")
        sys.exit(1)
