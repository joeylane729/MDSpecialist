from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from ...database import get_db

router = APIRouter()

@router.get("/test")
async def test_database_connection(db: Session = Depends(get_db)):
    """Test database connection and return basic info."""
    try:
        # Test a simple query
        result = db.execute(text("SELECT COUNT(*) FROM npi_providers"))
        count = result.scalar()
        
        return {
            "status": "success",
            "message": "Connected to PostgreSQL successfully",
            "total_providers": count,
            "database_type": "PostgreSQL"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}",
            "error_type": type(e).__name__
        }

@router.get("/simple-stats")
async def get_simple_stats(db: Session = Depends(get_db)):
    """Get simple database statistics."""
    try:
        # Get total providers
        result = db.execute(text("SELECT COUNT(*) FROM npi_providers"))
        total = result.scalar()
        
        # Get sample provider
        result = db.execute(text("SELECT npi, provider_first_name, provider_last_name FROM npi_providers LIMIT 1"))
        sample = result.fetchone()
        
        return {
            "total_providers": total,
            "sample_provider": {
                "npi": sample[0] if sample else None,
                "name": f"{sample[1]} {sample[2]}" if sample else None
            },
            "database": "PostgreSQL"
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }
