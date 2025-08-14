from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from app.database import create_tables, get_db
from app.api.endpoints import health, match, doctors, npi
from app.services.mock_data_service import MockDataService

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="ConciergeMD API",
    description="API for matching patients with medical specialists based on objective criteria",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router, tags=["Health"])
app.include_router(match.router, prefix="/api/v1", tags=["Matching"])
app.include_router(doctors.router, prefix="/api/v1", tags=["Doctors"])
app.include_router(npi.router, prefix="/api/v1/npi", tags=["NPI Providers"])

@app.on_event("startup")
async def startup_event():
    """Initialize database and create tables on startup."""
    try:
        create_tables()
        print("Database tables created successfully")
        print("Using PostgreSQL with NPI data - no mock data needed")
            
    except Exception as e:
        print(f"Error during startup: {e}")

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to ConciergeMD API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/healthz"
    }

@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "ConciergeMD API",
        "version": "1.0.0",
        "description": "API for matching patients with medical specialists",
        "endpoints": {
            "health": "/healthz",
            "match": "/api/v1/match",
            "doctors": "/api/v1/doctors",
            "docs": "/docs"
        }
    }

@app.get("/test-db")
async def test_database_connection():
    """Test database connection directly."""
    try:
        from app.database import get_db
        db = next(get_db())
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
