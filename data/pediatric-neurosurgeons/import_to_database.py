#!/usr/bin/env python3
"""Import pediatric neurosurgeon certification mappings to database"""

import os
import sys
import csv
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import from backend
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / 'backend' / '.env')

# Import from backend directly
from backend.app.database import SessionLocal, engine
from backend.app.models import Base
from backend.app.models.pediatric_neurosurgeon_certification import PediatricNeurosurgeonCertification
from sqlalchemy import text

def create_table():
    """Create the table if it doesn't exist"""
    print("Creating table if it doesn't exist...")
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ Table ready")
    except Exception as e:
        print(f"⚠️  Error creating table: {e}")
        raise

def import_certifications(csv_path, batch_size=1000):
    """Import certifications from CSV to database using bulk operations"""
    
    db = SessionLocal()
    
    try:
        # Create table
        create_table()
        
        # Pre-load all existing NPIs into a set for fast lookup
        print("\nLoading existing NPIs from npi_providers...")
        result = db.execute(text("SELECT DISTINCT npi FROM npi_providers WHERE npi IS NOT NULL"))
        existing_npis = {row[0] for row in result}
        print(f"✅ Found {len(existing_npis)} NPIs in database")
        
        # Read CSV and prepare data
        print(f"\nReading CSV from {csv_path}...")
        records = []
        skipped_missing_npi = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                npi = row.get('NPI', '').strip()
                if not npi:
                    skipped_missing_npi += 1
                    continue
                
                # Skip if NPI doesn't exist in npi_providers
                if npi not in existing_npis:
                    skipped_missing_npi += 1
                    continue
                
                # Parse matched status
                matched_str = row.get('Matched', 'No').strip()
                matched = matched_str.lower() == 'yes'
                
                # Parse CSV fields
                csv_name = row.get('Name (CSV)', '').strip() or None
                city = row.get('City', '').strip() or None
                state_province = row.get('State / Province', '').strip() or None
                country = row.get('Country', '').strip() or None
                certificate_number = row.get('Certificate #', '').strip() or None
                year_certified = row.get('Year Certified/Re-Certified', '').strip() or None
                certified_through = row.get('Certified Through', '').strip() or None
                
                records.append({
                    'npi': npi,
                    'matched': matched,
                    'csv_name': csv_name,
                    'city': city,
                    'state_province': state_province,
                    'country': country,
                    'certificate_number': certificate_number,
                    'year_certified': year_certified,
                    'certified_through': certified_through
                })
        
        print(f"✅ Prepared {len(records)} records to import")
        print(f"  Skipped {skipped_missing_npi} records with missing/invalid NPIs")
        
        # Use bulk upsert with PostgreSQL INSERT ... ON CONFLICT
        print(f"\nImporting {len(records)} records using bulk upsert...")
        
        # Build SQL for bulk upsert
        upsert_sql = """
        INSERT INTO pediatric_neurosurgeon_certifications 
            (npi, matched, csv_name, city, state_province, country, certificate_number, year_certified, certified_through, created_at, updated_at)
        VALUES 
            (:npi, :matched, :csv_name, :city, :state_province, :country, :certificate_number, :year_certified, :certified_through, NOW(), NOW())
        ON CONFLICT (npi) 
        DO UPDATE SET
            matched = EXCLUDED.matched,
            csv_name = EXCLUDED.csv_name,
            city = EXCLUDED.city,
            state_province = EXCLUDED.state_province,
            country = EXCLUDED.country,
            certificate_number = EXCLUDED.certificate_number,
            year_certified = EXCLUDED.year_certified,
            certified_through = EXCLUDED.certified_through,
            updated_at = NOW()
        """
        
        # Execute in batches
        total_inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.execute(text(upsert_sql), batch)
            db.commit()
            
            total_inserted += len(batch)
            print(f"  Processed {total_inserted}/{len(records)} records...", end='\r')
        
        print(f"\n✅ Import completed!")
        print(f"  Total records imported: {total_inserted}")
        
        # Verify
        print("\n🔍 Verifying import...")
        result = db.execute(text("SELECT COUNT(*) FROM pediatric_neurosurgeon_certifications"))
        count = result.scalar()
        matched_result = db.execute(text("SELECT COUNT(*) FROM pediatric_neurosurgeon_certifications WHERE matched = true"))
        matched_count = matched_result.scalar()
        print(f"  Total records in database: {count}")
        print(f"  Matched records: {matched_count}")
        print(f"  Unmatched records: {count - matched_count}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during import: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    csv_path = script_dir / "pediatric_neurosurgeons_npi_matched.csv"
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    import_certifications(csv_path)
