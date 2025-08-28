from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import match, doctors, health, npi, specialist_recommendation
import os

# Create FastAPI app
app = FastAPI(
    title="ConciergeMD API",
    description="AI-powered medical specialist recommendation system",
    version="1.0.0"
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

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(match.router, prefix="/api/v1", tags=["match"])
app.include_router(doctors.router, prefix="/api/v1", tags=["doctors"])
app.include_router(npi.router, prefix="/api/v1/npi", tags=["npi"])
app.include_router(specialist_recommendation.router, prefix="/api/v1", tags=["specialist-recommendations"])

@app.get("/")
async def root():
    return {"message": "ConciergeMD API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
