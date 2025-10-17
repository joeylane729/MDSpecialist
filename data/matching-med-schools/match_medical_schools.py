#!/usr/bin/env python3
"""
Simple script to match medical schools using GPT
Run this once to populate the npi_medical_school_mapping table
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.medical_school_matching_service import MedicalSchoolMatchingService

async def main():
    """Run the medical school matching process"""
    print("🚀 Starting Medical School Matching Process")
    print("=" * 50)
    print("⏳ Initializing service...")
    
    try:
        print("📦 Creating service instance...")
        service = MedicalSchoolMatchingService()
        print("✅ Service created successfully!")
        
        print("🔄 Starting matching process...")
        await service.match_all_medical_schools()
        print("\n✅ Medical school matching completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during matching: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
