from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from the backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database URL from environment variable - default to PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://joeylane@localhost:5432/concierge_md")
print(f"DEBUG: Using DATABASE_URL: {DATABASE_URL}")

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
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
    """Create all tables in the database."""
    # For PostgreSQL, we don't need to create the NPI table since it already exists
    # Only create the app-specific tables if they don't exist
    try:
        # Import models to ensure they're registered with Base
        from .models import Doctor, Publication, Talk, DoctorDiagCache, DiagSnapshot, RawSource, VumediContent
        
        # Create only the app-specific tables (exclude NPI table)
        Base.metadata.create_all(bind=engine, tables=[
            Doctor.__table__,
            Publication.__table__,
            Talk.__table__,
            DoctorDiagCache.__table__,
            DiagSnapshot.__table__,
            RawSource.__table__,
            VumediContent.__table__
        ])
        print("App tables created successfully")
    except Exception as e:
        print(f"Note: Some tables may already exist: {e}")

def drop_tables():
    """Drop all tables in the database."""
    # Be careful with this in production!
    Base.metadata.drop_all(bind=engine)
