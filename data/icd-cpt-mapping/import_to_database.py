#!/usr/bin/env python3
"""Bulk import ICD-10 to CPT code crosswalk mappings from Excel files using fast pandas to_sql"""

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
from backend.app.models.icd_cpt_mapping import IcdCptMapping
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

def normalize_column_name(col_name):
    """Normalize column names to standard format"""
    if not col_name:
        return None
    
    col_lower = str(col_name).strip().lower()
    
    # Map common variations to standard names
    if 'cpt' in col_lower or 'hcpcs' in col_lower or 'procedure code' in col_lower:
        return 'cpt_code'
    elif 'icd' in col_lower or 'icd-10' in col_lower or 'diagnosis code' in col_lower:
        return 'icd10_code'
    elif 'description' in col_lower or 'desc' in col_lower:
        return 'description'
    else:
        # Return as-is for additional fields
        return str(col_name).strip()

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

def import_mappings(chunk_size=5000):
    """Import all Excel files from the icd-cpt-mapping folder using fast pandas to_sql"""
    
    db = SessionLocal()
    overall_start_time = time.time()
    
    try:
        # Create table
        create_table()
        
        # Get all Excel files in the directory
        excel_files = sorted(script_dir.glob("*.xlsx"))
        
        if not excel_files:
            print(f"❌ No Excel files found in {script_dir}")
            return False
        
        print(f"\n📁 Found {len(excel_files)} Excel files to import:")
        for f in excel_files:
            print(f"   - {f.name}")
        
        # Read all Excel files and combine
        all_dataframes = []
        total_rows = 0
        read_start_time = time.time()
        
        for file_idx, excel_file in enumerate(excel_files, 1):
            file_start_time = time.time()
            print(f"\n📖 [{file_idx}/{len(excel_files)}] Reading {excel_file.name}...")
            try:
                df = pd.read_excel(excel_file)
                file_read_time = time.time() - file_start_time
                print(f"   ✅ Loaded {len(df):,} rows, {len(df.columns)} columns in {format_time(file_read_time)}")
                print(f"   Columns: {', '.join(df.columns.tolist())}")
                
                # Map columns explicitly based on known structure
                # Expected: CPT Code, CPT Code Full Description, ICD-10-CM Code, ICD-10-CM Code Long Description
                column_mapping = {}
                for i, col in enumerate(df.columns):
                    col_lower = str(col).strip().lower()
                    if 'cpt' in col_lower and 'code' in col_lower and 'description' not in col_lower:
                        column_mapping[col] = 'cpt_code'
                    elif 'cpt' in col_lower and 'description' in col_lower:
                        column_mapping[col] = 'description'  # CPT description
                    elif 'icd' in col_lower and 'code' in col_lower and 'description' not in col_lower:
                        column_mapping[col] = 'icd10_code'
                    elif 'icd' in col_lower and 'description' in col_lower:
                        column_mapping[col] = 'additional_field'  # ICD-10 description
                    else:
                        # Fallback: use position
                        if i == 0:
                            column_mapping[col] = 'cpt_code'
                        elif i == 1:
                            column_mapping[col] = 'description'
                        elif i == 2:
                            column_mapping[col] = 'icd10_code'
                        elif i == 3:
                            column_mapping[col] = 'additional_field'
                
                df = df.rename(columns=column_mapping)
                
                # Ensure required columns exist (fallback to position if mapping failed)
                if 'cpt_code' not in df.columns and len(df.columns) >= 1:
                    df['cpt_code'] = df.iloc[:, 0].astype(str)
                    print(f"   ⚠️  Using first column as CPT code")
                
                if 'icd10_code' not in df.columns and len(df.columns) >= 3:
                    df['icd10_code'] = df.iloc[:, 2].astype(str)
                    print(f"   ⚠️  Using third column as ICD-10 code")
                
                # Handle description column (2nd column = CPT description)
                if 'description' not in df.columns and len(df.columns) >= 2:
                    df['description'] = df.iloc[:, 1]
                    print(f"   ⚠️  Using second column as description")
                
                # Handle additional field (4th column = ICD-10 description)
                if 'additional_field' not in df.columns and len(df.columns) >= 4:
                    df['additional_field'] = df.iloc[:, 3]
                    print(f"   ⚠️  Using fourth column as additional_field")
                
                # Ensure cpt_code and icd10_code are Series, not DataFrames
                if isinstance(df['cpt_code'], pd.DataFrame):
                    df['cpt_code'] = df['cpt_code'].iloc[:, 0]
                if isinstance(df['icd10_code'], pd.DataFrame):
                    df['icd10_code'] = df['icd10_code'].iloc[:, 0]
                
                # Clean data - remove rows with missing CPT or ICD-10 codes
                initial_count = len(df)
                df = df.dropna(subset=['cpt_code', 'icd10_code'])
                # Convert to string first, then filter empty strings
                df['cpt_code'] = df['cpt_code'].astype(str).str.strip()
                df['icd10_code'] = df['icd10_code'].astype(str).str.strip()
                df = df[df['cpt_code'] != '']
                df = df[df['icd10_code'] != '']
                df = df[df['cpt_code'] != 'nan']
                df = df[df['icd10_code'] != 'nan']
                cleaned_count = len(df)
                
                if initial_count != cleaned_count:
                    print(f"   ⚠️  Removed {initial_count - cleaned_count:,} rows with missing codes")
                
                # Convert to string and strip whitespace (already done above)
                df['cpt_code'] = df['cpt_code'].str[:20]
                df['icd10_code'] = df['icd10_code'].str[:20]
                
                # Handle description and additional_field
                if 'description' in df.columns:
                    df['description'] = df['description'].astype(str).fillna('').str.strip()
                    df['description'] = df['description'].replace('nan', '')
                else:
                    df['description'] = ''
                
                if 'additional_field' in df.columns:
                    df['additional_field'] = df['additional_field'].astype(str).fillna('').str.strip()
                    df['additional_field'] = df['additional_field'].replace('nan', '')
                else:
                    df['additional_field'] = ''
                
                # Select only the columns we need
                df = df[['cpt_code', 'icd10_code', 'description', 'additional_field']]
                
                all_dataframes.append(df)
                total_rows += len(df)
                
                elapsed = time.time() - read_start_time
                avg_time_per_file = elapsed / file_idx
                remaining_files = len(excel_files) - file_idx
                eta = avg_time_per_file * remaining_files
                print(f"   📊 Progress: {file_idx}/{len(excel_files)} files, {total_rows:,} total rows")
                print(f"   ⏱️  Elapsed: {format_time(elapsed)}, ETA: {format_time(eta)}")
                
            except Exception as e:
                print(f"   ❌ Error reading {excel_file.name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not all_dataframes:
            print("\n❌ No data loaded from any files")
            return False
        
        # Combine all dataframes
        combine_start_time = time.time()
        print(f"\n📊 Combining data from all files...")
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        combine_time = time.time() - combine_start_time
        print(f"   ✅ Total rows: {len(combined_df):,} (took {format_time(combine_time)})")
        
        # Remove duplicates based on CPT + ICD-10 combination
        dedup_start_time = time.time()
        initial_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['cpt_code', 'icd10_code'], keep='first')
        dedup_time = time.time() - dedup_start_time
        final_count = len(combined_df)
        
        if initial_count != final_count:
            print(f"   ⚠️  Removed {initial_count - final_count:,} duplicate rows (took {format_time(dedup_time)})")
        
        print(f"   ✅ Final count: {final_count:,} unique mappings")
        
        # Check existing records
        print(f"\n🔍 Checking existing records in database...")
        check_start = time.time()
        result = db.execute(text("SELECT COUNT(*) FROM icd_cpt_mappings"))
        existing_count = result.scalar()
        print(f"   ✅ Found {existing_count:,} existing records")
        
        if existing_count > 0:
            print(f"   ℹ️  Using 'append' mode - duplicates will be skipped")
            if_exists = 'append'
        else:
            print(f"   ℹ️  Using 'append' mode for first import")
            if_exists = 'append'
        
        # Use PostgreSQL COPY for ultra-fast bulk insert
        print(f"\n💾 Importing {final_count:,} mappings to database using PostgreSQL COPY...")
        print(f"   ⚙️  Chunk size: {chunk_size:,} rows per batch")
        print(f"   ⏱️  Started at {time.strftime('%H:%M:%S')}")
        
        import_start_time = time.time()
        
        # Get database URL from engine and convert to psycopg2 format
        # SQLAlchemy URL format: postgresql://user:pass@host:port/dbname
        db_url_obj = engine.url
        # Build connection parameters dict for psycopg2
        conn_params = {
            'host': db_url_obj.host,
            'port': db_url_obj.port or 5432,
            'database': db_url_obj.database,
            'user': db_url_obj.username,
            'password': db_url_obj.password
        }
        # Add SSL requirement for RDS (AWS requires SSL)
        if 'rds.amazonaws.com' in str(db_url_obj.host):
            conn_params['sslmode'] = 'require'
        
        try:
            # Connect using psycopg2 for COPY
            pg_conn = psycopg2.connect(**conn_params)
            pg_conn.autocommit = False
            cur = pg_conn.cursor()
            
            # Create temporary staging table
            print(f"   📋 Creating temporary staging table...")
            cur.execute("""
                CREATE TEMP TABLE icd_cpt_mappings_staging (
                    cpt_code VARCHAR(20),
                    icd10_code VARCHAR(20),
                    description TEXT,
                    additional_field TEXT
                )
            """)
            
            # Prepare data for COPY using pandas to_csv (much faster)
            print(f"   📤 Preparing data for COPY...")
            copy_start = time.time()
            
            # Use pandas to_csv to create tab-separated buffer (much faster than manual loop)
            buffer = StringIO()
            combined_df.to_csv(
                buffer,
                sep='\t',
                header=False,
                index=False,
                na_rep='\\N',
                quoting=0,  # No quoting
                escapechar='\\'
            )
            buffer.seek(0)
            
            prep_time = time.time() - copy_start
            print(f"   ✅ Data prepared in {format_time(prep_time)}")
            
            # Use COPY FROM to load into staging table
            print(f"   📥 Loading into staging table via COPY...")
            copy_load_start = time.time()
            cur.copy_from(
                buffer,
                'icd_cpt_mappings_staging',
                columns=('cpt_code', 'icd10_code', 'description', 'additional_field'),
                sep='\t',
                null='\\N'
            )
            
            copy_time = time.time() - copy_start
            print(f"   ✅ COPY completed in {format_time(copy_time)}")
            
            # Insert from staging to main table, skipping duplicates
            print(f"   🔄 Inserting from staging to main table (skipping duplicates)...")
            insert_start = time.time()
            
            # Use efficient INSERT with NOT EXISTS to skip duplicates
            # This is faster than DISTINCT ON for large datasets
            cur.execute("""
                INSERT INTO icd_cpt_mappings (cpt_code, icd10_code, description, additional_field, created_at, updated_at)
                SELECT 
                    s.cpt_code, s.icd10_code, s.description, s.additional_field, NOW(), NOW()
                FROM icd_cpt_mappings_staging s
                WHERE NOT EXISTS (
                    SELECT 1 FROM icd_cpt_mappings m
                    WHERE m.cpt_code = s.cpt_code
                    AND m.icd10_code = s.icd10_code
                )
            """)
            
            rows_inserted = cur.rowcount
            pg_conn.commit()
            insert_time = time.time() - insert_start
            
            print(f"   ✅ Inserted {rows_inserted:,} new records in {format_time(insert_time)}")
            
            cur.close()
            pg_conn.close()
            
            import_time = time.time() - import_start_time
            print(f"\n✅ Import completed!")
            print(f"   ⏱️  Total import time: {format_time(import_time)}")
            print(f"   📊 Rate: {final_count / import_time:.0f} rows/sec")
            print(f"   📊 New records inserted: {rows_inserted:,}")
            
        except Exception as e:
            print(f"\n❌ Error during COPY import: {e}")
            import traceback
            traceback.print_exc()
            if 'pg_conn' in locals():
                pg_conn.rollback()
                pg_conn.close()
            return False
        
        # Verify
        verify_start = time.time()
        print("\n🔍 Verifying import...")
        result = db.execute(text("SELECT COUNT(*) FROM icd_cpt_mappings"))
        count = result.scalar()
        verify_time = time.time() - verify_start
        print(f"   ✅ Total records in database: {count:,} (verification took {format_time(verify_time)})")
        
        # Show some stats
        stats_start = time.time()
        result = db.execute(text("SELECT COUNT(DISTINCT cpt_code) FROM icd_cpt_mappings"))
        unique_cpt = result.scalar()
        result = db.execute(text("SELECT COUNT(DISTINCT icd10_code) FROM icd_cpt_mappings"))
        unique_icd10 = result.scalar()
        stats_time = time.time() - stats_start
        print(f"   📊 Unique CPT codes: {unique_cpt:,}")
        print(f"   📊 Unique ICD-10 codes: {unique_icd10:,}")
        print(f"   ⏱️  Stats query took: {format_time(stats_time)}")
        
        total_time = time.time() - overall_start_time
        print(f"\n🎉 All done!")
        print(f"   ⏱️  Total time: {format_time(total_time)}")
        print(f"   📊 Records imported: {count - existing_count:,}")
        print(f"   📊 Total records in DB: {count:,}")
        
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
    print("🚀 Starting ICD-CPT mapping import...")
    print(f"⏱️  Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    success = import_mappings()
    if success:
        print("\n🎉 Import completed successfully!")
    else:
        print("\n❌ Import failed!")
        sys.exit(1)
