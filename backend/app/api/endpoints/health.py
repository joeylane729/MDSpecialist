from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...database import get_db
from ...services.mock_data_service import MockDataService

router = APIRouter()

@router.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ConciergeMD API",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z"
    }

@router.post("/init")
async def initialize_database(db: Session = Depends(get_db)):
    """Initialize the database with mock data."""
    try:
        mock_service = MockDataService(db)
        result = mock_service.populate_database()
        
        return {
            "status": "success",
            "message": "Database initialized successfully",
            "data": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initialize database: {str(e)}"
        }
