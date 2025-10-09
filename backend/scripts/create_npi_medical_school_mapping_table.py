#!/usr/bin/env python3
"""
Script to create the npi_medical_school_mapping table in Railway database.

This script creates a new table that maps NPI numbers to medical school ranking IDs.
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
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Error: DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        print("🔗 Connecting to Railway database...")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Create the table
        print("📋 Creating npi_medical_school_mapping table...")
        NPIMedicalSchoolMapping.__table__.create(engine, checkfirst=True)
        
        print("✅ Table 'npi_medical_school_mapping' created successfully!")
        
        # Verify table exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'npi_medical_school_mapping'
            """))
            
            if result.fetchone():
                print("✅ Table verification successful")
                
                # Show table structure
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
                
                return True
            else:
                print("❌ Table verification failed")
                return False
                
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
