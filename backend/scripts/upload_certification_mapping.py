#!/usr/bin/env python3
"""
Upload npi_to_md_mapping.csv to database as npi_certification_mapping_results table.
Super simple - just copies the CSV data as-is.
"""

import os
import sys
import csv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("❌ Error: DATABASE_URL environment variable not set")
    sys.exit(1)

# Path to CSV file
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, '..', '..', 'data', 'certificationmatters', 'npi_to_md_mapping.csv')

def upload_csv():
    """Upload CSV to database"""
    try:
        # Create engine
        engine = create_engine(database_url)
        
        print("🔗 Connecting to database...")
        with engine.connect() as conn:
            # Test connection
            conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Read CSV to get column names and data
        print(f"📖 Reading CSV file: {csv_path}")
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        print(f"📊 Found {len(rows)} rows in CSV")
        
        # Get column names from CSV
        column_names = list(rows[0].keys()) if rows else []
        print(f"📋 Columns: {', '.join(column_names)}")
        
        # Create table (drop if exists first with CASCADE to clean up types)
        print("\n🗑️  Dropping existing table if it exists...")
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS npi_certification_mapping_results CASCADE"))
            conn.commit()
        
        # Create table with all columns as TEXT
        print("📋 Creating table npi_certification_mapping_results...")
        create_table_sql = f"""
        CREATE TABLE npi_certification_mapping_results (
            {', '.join([f'"{col}" TEXT' for col in column_names])}
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("✅ Table created successfully")
        
        # Insert data in batches
        print(f"\n📤 Inserting {len(rows)} rows...")
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            
            # Build INSERT statement
            placeholders = ', '.join([f':{col}' for col in column_names])
            insert_sql = f"""
            INSERT INTO npi_certification_mapping_results ({', '.join([f'"{col}"' for col in column_names])})
            VALUES ({placeholders})
            """
            
            with engine.connect() as conn:
                conn.execute(text(insert_sql), [dict(row) for row in batch])
                conn.commit()
            
            total_inserted += len(batch)
            print(f"  Inserted {total_inserted}/{len(rows)} rows...", end='\r')
        
        print(f"\n✅ Successfully inserted {total_inserted} rows")
        
        # Verify
        print("\n🔍 Verifying upload...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM npi_certification_mapping_results"))
            count = result.scalar()
            print(f"✅ Table contains {count} rows")
        
        print("\n✅ Upload complete!")
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: CSV file not found at {csv_path}")
        return False
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Uploading Certification Mapping CSV to Database")
    print("=" * 70)
    success = upload_csv()
    sys.exit(0 if success else 1)

