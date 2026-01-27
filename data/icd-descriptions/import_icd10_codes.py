#!/usr/bin/env python3
"""Import ICD-10 codes and descriptions from Excel file to database.
Replaces all existing data in the icd10_codes table."""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Check for pandas and openpyxl
try:
    import pandas as pd
except ImportError:
    print("❌ Error: pandas is not installed. Please install it with: pip install pandas")
    sys.exit(1)

try:
    import openpyxl
except ImportError:
    print("❌ Error: openpyxl is not installed. Please install it with: pip install openpyxl")
    print("   openpyxl is required to read Excel (.xlsx) files")
    sys.exit(1)

# Add parent directory to path to import from backend
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / 'backend' / '.env')

# Import from backend directly
from backend.app.database import SessionLocal, engine
from backend.app.models import Base
from backend.app.models.icd10_code import ICD10Code
from sqlalchemy import text
import psycopg2
from psycopg2.extras import execute_values
from io import StringIO

def create_table():
    """Create the table if it doesn't exist"""
    print("Creating table if it doesn't exist...")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ Table ready")
    except Exception as e:
        print(f"⚠️  Error creating table: {e}")
        raise

def format_time(seconds):
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def import_icd10_codes():
    """Import ICD-10 codes from Excel file, replacing all existing data"""
    
    db = SessionLocal()
    overall_start_time = time.time()
    
    try:
        # Create table
        create_table()
        
        # Find Excel file
        excel_file = script_dir / "section111_valid_icd10_october2025 (1).xlsx"
        
        if not excel_file.exists():
            print(f"❌ Excel file not found: {excel_file}")
            return False
        
        print(f"\n📖 Reading Excel file: {excel_file.name}")
        read_start_time = time.time()
        
        # Read Excel file
        df = pd.read_excel(excel_file)
        
        read_time = time.time() - read_start_time
        print(f"✅ Read {len(df):,} rows in {format_time(read_time)}")
        
        # Display column info
        print(f"\n📋 Columns found: {df.columns.tolist()}")
        print(f"   First few rows:")
        print(df.head())
        
        # Map columns
        # Expected columns: CODE, SHORT DESCRIPTION, LONG DESCRIPTION, NF EXCL
        if 'CODE' not in df.columns:
            print("❌ Error: 'CODE' column not found in Excel file")
            return False
        
        # Prepare data - use LONG DESCRIPTION if available, otherwise SHORT DESCRIPTION
        description_col = None
        if 'LONG DESCRIPTION (VALID ICD-10 FY2026)' in df.columns:
            description_col = 'LONG DESCRIPTION (VALID ICD-10 FY2026)'
        elif 'SHORT DESCRIPTION (VALID ICD-10 FY2026)' in df.columns:
            description_col = 'SHORT DESCRIPTION (VALID ICD-10 FY2026)'
        elif 'LONG DESCRIPTION' in df.columns:
            description_col = 'LONG DESCRIPTION'
        elif 'SHORT DESCRIPTION' in df.columns:
            description_col = 'SHORT DESCRIPTION'
        elif 'DESCRIPTION' in df.columns:
            description_col = 'DESCRIPTION'
        
        if not description_col:
            print("❌ Error: No description column found in Excel file")
            print(f"   Available columns: {df.columns.tolist()}")
            return False
        
        print(f"\n📝 Using description column: {description_col}")
        
        # Prepare data for import
        print(f"\n🔄 Preparing data for import...")
        prep_start = time.time()
        
        # Clean and prepare data
        data = []
        for _, row in df.iterrows():
            code = str(row['CODE']).strip() if pd.notna(row['CODE']) else None
            description = str(row[description_col]).strip() if pd.notna(row[description_col]) else None
            
            # Skip rows with no code
            if not code or code == 'nan':
                continue
            
            # Normalize code (uppercase, remove extra spaces)
            code = code.upper().strip()
            
            data.append({
                'code': code,
                'description': description if description and description != 'nan' else None
            })
        
        prep_time = time.time() - prep_start
        print(f"✅ Prepared {len(data):,} records in {format_time(prep_time)}")
        
        if not data:
            print("❌ No valid data to import")
            return False
        
        # Get database connection parameters
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("❌ DATABASE_URL not found in environment variables")
            return False
        
        # Parse connection string
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password
        }
        
        print(f"\n🗑️  Deleting all existing records from icd10_codes table...")
        delete_start = time.time()
        
        try:
            # Connect using psycopg2 for efficient operations
            pg_conn = psycopg2.connect(**conn_params)
            pg_conn.autocommit = False
            cur = pg_conn.cursor()
            
            # Delete all existing records
            cur.execute("DELETE FROM icd10_codes")
            deleted_count = cur.rowcount
            pg_conn.commit()
            
            delete_time = time.time() - delete_start
            print(f"✅ Deleted {deleted_count:,} existing records in {format_time(delete_time)}")
            
        except Exception as e:
            pg_conn.rollback()
            print(f"⚠️  Error deleting existing records: {e}")
            print("   Continuing with import anyway...")
        finally:
            if 'pg_conn' in locals():
                pg_conn.close()
        
        # Create DataFrame for bulk insert
        import_df = pd.DataFrame(data)
        
        print(f"\n📤 Inserting {len(import_df):,} records into database...")
        insert_start = time.time()
        
        try:
            # Connect using psycopg2 for COPY
            pg_conn = psycopg2.connect(**conn_params)
            pg_conn.autocommit = False
            cur = pg_conn.cursor()
            
            # Prepare data for COPY using pandas to_csv
            print(f"   📤 Preparing data for COPY...")
            copy_prep_start = time.time()
            
            buffer = StringIO()
            import_df.to_csv(
                buffer,
                sep='\t',
                header=False,
                index=False,
                na_rep='\\N',
                quoting=0,
                escapechar='\\'
            )
            buffer.seek(0)
            
            copy_prep_time = time.time() - copy_prep_start
            print(f"   ✅ Data prepared in {format_time(copy_prep_time)}")
            
            # Use COPY FROM to load directly into main table
            print(f"   📥 Loading into icd10_codes table via COPY...")
            copy_load_start = time.time()
            cur.copy_from(
                buffer,
                'icd10_codes',
                columns=('code', 'description'),
                sep='\t',
                null='\\N'
            )
            
            copy_load_time = time.time() - copy_load_start
            pg_conn.commit()
            
            # Get count of inserted records
            cur.execute("SELECT COUNT(*) FROM icd10_codes")
            inserted_count = cur.fetchone()[0]
            
            print(f"   ✅ COPY completed: {inserted_count:,} records loaded in {format_time(copy_load_time)}")
            
        except Exception as e:
            pg_conn.rollback()
            print(f"\n❌ Error during import: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if 'pg_conn' in locals():
                pg_conn.close()
        
        # Verify import
        print(f"\n🔍 Verifying import...")
        verify_start = time.time()
        result = db.execute(text("SELECT COUNT(*) FROM icd10_codes"))
        count = result.scalar()
        verify_time = time.time() - verify_start
        print(f"   ✅ Total records in database: {count:,} (verification took {format_time(verify_time)})")
        
        # Show sample data
        print(f"\n📊 Sample records:")
        sample = db.execute(text("SELECT code, LEFT(description, 50) as desc FROM icd10_codes LIMIT 5"))
        for row in sample:
            print(f"   - {row[0]}: {row[1]}")
        
        total_time = time.time() - overall_start_time
        print(f"\n🎉 Import completed successfully!")
        print(f"   ⏱️  Total time: {format_time(total_time)}")
        print(f"   📊 Records imported: {count:,}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting ICD-10 codes import...")
    print("=" * 60)
    success = import_icd10_codes()
    print("=" * 60)
    if success:
        print("✅ Import completed successfully!")
        sys.exit(0)
    else:
        print("❌ Import failed!")
        sys.exit(1)
