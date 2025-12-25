from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
from dotenv import load_dotenv
from app.api.endpoints import npi, specialist_recommendation, npi_ranking, medical_analysis, preauth_letter, reviews
import os
import logging

# Load environment variables from .env file (for local development only)
# In production, environment variables are set by the deployment platform
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# API version - single source of truth
API_VERSION = "1.0.1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up MDSpecialist API")
    yield
    # Shutdown
    logger.info("Shutting down MDSpecialist API")

# Configure CORS origins
def get_cors_origins() -> List[str]:
    """Get CORS origins from environment and defaults."""
    origins = []
    
    # Base origins from environment variable
    base_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins.extend([origin.strip() for origin in base_origins.split(",") if origin.strip()])
    
    # Add Railway domain if available
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        origins.append(f"https://{railway_domain}")
    
    # Add Vercel frontend domain
    origins.append("https://md-specialist.vercel.app")
    
    # Remove duplicates and filter out empty strings
    return list(set([origin for origin in origins if origin.strip()]))

cors_origins = get_cors_origins()
logger.info(f"CORS origins configured: {cors_origins}")

# Create FastAPI app
app = FastAPI(
    title="MDSpecialist API",
    description="AI-powered medical specialist recommendation system",
    version=API_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(npi.router, prefix="/api/v1/npi", tags=["npi"])
app.include_router(specialist_recommendation.router, prefix="/api/v1", tags=["specialist-recommendations"])
app.include_router(npi_ranking.router, prefix="/api/v1", tags=["npi-ranking"])
app.include_router(medical_analysis.router, prefix="/api/v1", tags=["medical-analysis"])
app.include_router(preauth_letter.router, prefix="/api/v1", tags=["preauth-letter"])
app.include_router(reviews.router, prefix="/api/v1", tags=["reviews"])

@app.get("/")
async def root():
    return {"message": "MDSpecialist API is running", "version": API_VERSION}

@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "message": "MDSpecialist API is running", "version": API_VERSION}
