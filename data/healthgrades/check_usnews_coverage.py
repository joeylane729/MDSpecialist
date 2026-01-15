#!/usr/bin/env python3
"""
Check if the 38 newly updated doctors already have US News data.
If they all do, we don't need to run matching for them.
"""
import sys
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

def check_usnews_coverage():
    """Check if the 38 newly updated doctors have US News data"""
    
    db = next(get_db())
    try:
        # Get the 38 NPIs that were recently updated in healthgrades_data
        print("🔍 Finding recently updated NPIs in healthgrades_data...")
        result = db.execute(text("""
            SELECT DISTINCT npi, first_name, last_name
            FROM healthgrades_data
            WHERE updated_at > NOW() - INTERVAL '1 hour'
              AND filenames IS NOT NULL
              AND filenames != 'None with neuro specialties'
            ORDER BY npi
        """))
        
        updated_doctors = result.fetchall()
        print(f"📊 Found {len(updated_doctors)} recently updated doctors")
        
        if not updated_doctors:
            print("❌ No recently updated doctors found. Try increasing the time interval.")
            return
        
        # Extract NPIs
        updated_npis = [str(row[0]) for row in updated_doctors]
        
        # Check if they have US News data
        print(f"\n🔍 Checking if these {len(updated_npis)} NPIs have US News data...")
        
        # Check medical school data
        placeholders = ','.join([f':npi{i}' for i in range(len(updated_npis))])
        params = {f'npi{i}': npi for i, npi in enumerate(updated_npis)}
        
        usnews_medical_school = db.execute(text(f"""
            SELECT npi, medical_school
            FROM usnews_data
            WHERE npi IN ({placeholders})
              AND medical_school IS NOT NULL 
              AND medical_school != ''
        """), params).fetchall()
        
        usnews_residency = db.execute(text(f"""
            SELECT npi, residency
            FROM usnews_data
            WHERE npi IN ({placeholders})
              AND residency IS NOT NULL 
              AND residency != ''
        """), params).fetchall()
        
        # Count results
        npis_with_usnews_med_school = set(str(row[0]) for row in usnews_medical_school)
        npis_with_usnews_residency = set(str(row[0]) for row in usnews_residency)
        npis_with_usnews_any = npis_with_usnews_med_school | npis_with_usnews_residency
        
        print(f"\n📊 RESULTS:")
        print(f"   Total recently updated doctors: {len(updated_npis)}")
        print(f"   ✅ With US News medical_school data: {len(npis_with_usnews_med_school)}")
        print(f"   ✅ With US News residency data: {len(npis_with_usnews_residency)}")
        print(f"   ✅ With ANY US News data: {len(npis_with_usnews_any)}")
        print(f"   ❌ Without US News data: {len(updated_npis) - len(npis_with_usnews_any)}")
        
        # Show breakdown
        if len(npis_with_usnews_any) == len(updated_npis):
            print(f"\n✅ ALL {len(updated_npis)} doctors have US News data!")
            print("   → No matching needed - US News data takes priority")
        else:
            npis_without_usnews = set(updated_npis) - npis_with_usnews_any
            print(f"\n⚠️  {len(npis_without_usnews)} doctors do NOT have US News data:")
            print("   These need matching:")
            for npi in sorted(npis_without_usnews):
                doctor = next((d for d in updated_doctors if str(d[0]) == npi), None)
                name = f"{doctor[1]} {doctor[2]}" if doctor else "Unknown"
                print(f"      - NPI: {npi} ({name})")
        
        # Also show which ones have US News data for reference
        if npis_with_usnews_any:
            print(f"\n✅ {len(npis_with_usnews_any)} doctors WITH US News data (won't need matching):")
            for npi in sorted(npis_with_usnews_any)[:5]:
                doctor = next((d for d in updated_doctors if str(d[0]) == npi), None)
                name = f"{doctor[1]} {doctor[2]}" if doctor else "Unknown"
                print(f"      - NPI: {npi} ({name})")
            if len(npis_with_usnews_any) > 5:
                print(f"      ... and {len(npis_with_usnews_any) - 5} more")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_usnews_coverage()

