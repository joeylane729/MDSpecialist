#!/usr/bin/env python3
"""
Update healthgrades_data table with new data for doctors who originally had
"None with neuro specialties" but now have actual files.
"""
import sys
import csv
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / 'backend' / '.env')

from backend.app.database import get_db
from sqlalchemy import text

def read_new_verification_results(csv_path):
    """Read the new verification results CSV and return as dict keyed by NPI"""
    results = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            npi = row['npi']
            # Only include doctors who now have actual filenames (not "None with neuro specialties")
            if row['filenames'] and row['filenames'] != 'None with neuro specialties':
                results[npi] = {
                    'npi': npi,
                    'first_name': row['first_name'],
                    'last_name': row['last_name'],
                    'filenames': row['filenames'],
                    'specialties': row['specialties'],
                    'medical_school': row['medical_school'],
                    'residency': row['residency'],
                    'fellowship': row['fellowship'],
                    'certifications': row['certifications'],
                    'matching_method': row['matching_method'],
                    'matching_notes': row['matching_notes']
                }
    return results

def find_records_to_update(db):
    """Find records in database that have 'None with neuro specialties'"""
    result = db.execute(text("""
        SELECT npi, first_name, last_name, filenames, specialties
        FROM healthgrades_data
        WHERE filenames = 'None with neuro specialties'
    """))
    return result.fetchall()

def preview_updates(db, new_data):
    """Preview what will be updated without actually updating"""
    db_records = find_records_to_update(db)
    
    updates = []
    for record in db_records:
        npi = record[0]
        if npi in new_data:
            updates.append({
                'npi': npi,
                'current_name': f"{record[1]} {record[2]}",
                'current_filenames': record[3],
                'current_specialties': record[4],
                'new_filenames': new_data[npi]['filenames'],
                'new_specialties': new_data[npi]['specialties'],
                'new_medical_school': new_data[npi]['medical_school'],
                'new_residency': new_data[npi]['residency'],
                'new_fellowship': new_data[npi]['fellowship'],
                'new_certifications': new_data[npi]['certifications'],
                'new_matching_method': new_data[npi]['matching_method'],
                'new_matching_notes': new_data[npi]['matching_notes']
            })
    
    return updates

def update_records(db, updates):
    """Update records in the database"""
    updated_count = 0
    
    for update in updates:
        npi = update['npi']
        db.execute(text("""
            UPDATE healthgrades_data
            SET 
                filenames = :filenames,
                specialties = :specialties,
                medical_school = :medical_school,
                residency = :residency,
                fellowship = :fellowship,
                certifications = :certifications,
                matching_method = :matching_method,
                matching_notes = :matching_notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE npi = :npi
              AND filenames = 'None with neuro specialties'
        """), {
            'npi': npi,
            'filenames': update['new_filenames'],
            'specialties': update['new_specialties'],
            'medical_school': update['new_medical_school'] if update['new_medical_school'] != 'None' else None,
            'residency': update['new_residency'] if update['new_residency'] != 'None' else None,
            'fellowship': update['new_fellowship'] if update['new_fellowship'] != 'None' else None,
            'certifications': update['new_certifications'] if update['new_certifications'] != 'None' else None,
            'matching_method': update['new_matching_method'],
            'matching_notes': update['new_matching_notes']
        })
        updated_count += 1
    
    db.commit()
    return updated_count

def main():
    print("=" * 80)
    print("Update healthgrades_data table for doctors with newly found neuro specialties")
    print("=" * 80)
    
    # Path to the new verification results CSV
    csv_path = script_dir / 'neuro_specialists_verification_results.csv'
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found at {csv_path}")
        return False
    
    print(f"\n📖 Reading new verification results from: {csv_path}")
    new_data = read_new_verification_results(csv_path)
    print(f"   Found {len(new_data)} doctors with actual filenames in new CSV")
    
    # Get database session
    db = next(get_db())
    
    try:
        print("\n🔍 Finding records in database with 'None with neuro specialties'...")
        db_records = find_records_to_update(db)
        print(f"   Found {len(db_records)} records with 'None with neuro specialties' in database")
        
        print("\n🔎 Matching records...")
        updates = preview_updates(db, new_data)
        print(f"   Found {len(updates)} records that need to be updated")
        
        if not updates:
            print("\n✅ No records need to be updated!")
            return True
        
        # Show preview
        print("\n" + "=" * 80)
        print("PREVIEW OF UPDATES (first 10):")
        print("=" * 80)
        for i, update in enumerate(updates[:10], 1):
            print(f"\n{i}. NPI: {update['npi']} - {update['current_name']}")
            print(f"   Current filenames: {update['current_filenames']}")
            print(f"   New filenames:     {update['new_filenames']}")
            print(f"   Current specialties: {update['current_specialties'] or '(None)'}")
            print(f"   New specialties:     {update['new_specialties']}")
            if update['new_medical_school'] and update['new_medical_school'] != 'None':
                print(f"   Medical School:      {update['new_medical_school']}")
            if update['new_residency'] and update['new_residency'] != 'None':
                print(f"   Residency:           {update['new_residency']}")
            if update['new_certifications'] and update['new_certifications'] != 'None':
                print(f"   Certifications:      {update['new_certifications']}")
        
        if len(updates) > 10:
            print(f"\n   ... and {len(updates) - 10} more records")
        
        print("\n" + "=" * 80)
        print(f"⚠️  Ready to update {len(updates)} records in the database")
        print("=" * 80)
        print("\nThis script will:")
        print("  ✓ Only update records where filenames = 'None with neuro specialties'")
        print("  ✓ Only update records that match NPIs in the new CSV")
        print("  ✓ Update: filenames, specialties, medical_school, residency, fellowship, certifications, matching_method, matching_notes")
        print("  ✓ Set updated_at to current timestamp")
        print("\n⚠️  PREVIEW MODE ONLY - No updates have been made yet")
        print("\nTo actually run the updates, call the script with --execute flag:")
        print("   python3 update_healthgrades_data.py --execute")
        
        # Don't proceed with updates unless --execute flag is present
        if '--execute' not in sys.argv:
            print("\n📋 Preview complete. Run with --execute to apply updates.")
            return True
        
        print("\n🚀 Proceeding with updates...")
        updated_count = update_records(db, updates)
        print(f"✅ Successfully updated {updated_count} records!")
        
        # Verify
        print("\n🔍 Verifying updates...")
        verify_result = db.execute(text("""
            SELECT COUNT(*) 
            FROM healthgrades_data
            WHERE filenames = 'None with neuro specialties'
        """))
        remaining_count = verify_result.scalar()
        print(f"   Records still with 'None with neuro specialties': {remaining_count}")
        print(f"   Records updated: {updated_count}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

