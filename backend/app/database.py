from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

logger = logging.getLogger(__name__)

# Database URL from environment variable
# In production, this should be set by the deployment platform (Railway, Vercel, etc.)
# For local development, load_dotenv() should be called in the entrypoint (main.py or run script)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please set it in your environment or .env file (for local development)."
    )

# Log connection info (without exposing credentials)
db_host = DATABASE_URL.split("@")[1].split("/")[0].split(":")[0] if "@" in DATABASE_URL else "unknown"
logger.info(f"Database connection configured for host: {db_host}")

# Create engine with production-ready configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,    # Recycle connections after 5 minutes
    pool_size=10,        # Number of connections to keep in pool
    max_overflow=20,     # Maximum overflow connections
    pool_timeout=30,     # Seconds to wait before timing out on getting connection
    echo=False,          # Set to True for SQL query logging (dev only)
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Get Base from models
from .models import Base

def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """
    Create all tables in the database.
    
    ⚠️ WARNING: This is for development/testing only.
    In production, use Alembic migrations instead.
    
    For PostgreSQL, we don't need to create the NPI table since it already exists.
    Only creates app-specific tables if they don't exist.
    """
    # Only allow in development/testing environments
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        raise RuntimeError(
            "create_tables() should not be called in production. "
            "Use Alembic migrations instead."
        )
    
    try:
        # Import models to ensure they're registered with Base
        from .models import Doctor, NPIProvider, VumediContent
        
        # Create only the app-specific tables (exclude NPI table)
        Base.metadata.create_all(bind=engine, tables=[
            Doctor.__table__,
            VumediContent.__table__,
        ])
        logger.info("App tables created successfully")
    except Exception as e:
        logger.warning(f"Note: Some tables may already exist: {e}")

def drop_tables():
    """
    Drop all tables in the database.
    
    ⚠️ DANGER: This will delete all data!
    Only available in development/testing environments.
    """
    # Only allow in development/testing environments
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        raise RuntimeError(
            "drop_tables() cannot be called in production for safety reasons."
        )
    
    logger.warning("Dropping all tables - THIS WILL DELETE ALL DATA!")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")
