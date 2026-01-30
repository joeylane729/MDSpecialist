#!/usr/bin/env python3
"""
Load ConsolidatedCodeList.csv into the database using PostgreSQL COPY.
Creates a new table (cpt_consolidated), does not use an existing one.
Uses COPY for bulk load; CSV format is standard (quote only when needed).
"""

import os
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Load env before importing app (app.database reads DATABASE_URL)
from dotenv import load_dotenv
load_dotenv(backend_dir.parent / ".env")
load_dotenv(backend_dir / ".env")

from sqlalchemy import text
from app.database import engine
from app.models import Base, CptConsolidated


# CSV path (same repo)
CSV_PATH = backend_dir.parent / "data" / "ama-cpt-codes" / "ConsolidatedCodeList.csv"

# COPY column list: order must match CSV columns
# CSV columns: Concept Id, CPT Code, Long, Medium, Short, Consumer, Spanish Consumer,
#              Current Descriptor Effective Date, Test Name, Lab Name, Manufacturer Name
COPY_COLUMNS = (
    "concept_id",
    "cpt_code",
    "long_desc",
    "medium_desc",
    "short_desc",
    "consumer_desc",
    "spanish_consumer_desc",
    "current_descriptor_effective_date",
    "test_name",
    "lab_name",
    "manufacturer_name",
)


def main():
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL not set. Set it in .env or environment.")
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    print(f"📂 CSV: {CSV_PATH}")
    print(f"📊 Rows (approx): {sum(1 for _ in open(CSV_PATH, encoding='utf-8')) - 1}")

    # Create new table (drop if exists so we don't use an existing one)
    print("\n🗑️  Dropping table cpt_consolidated if it exists...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS cpt_consolidated CASCADE"))
        conn.commit()

    print("📋 Creating table cpt_consolidated...")
    Base.metadata.create_all(bind=engine, tables=[CptConsolidated.__table__])
    print("✅ Table created.")

    # COPY from CSV using raw connection (required for COPY)
    copy_sql = f"""
    COPY cpt_consolidated ({", ".join(COPY_COLUMNS)})
    FROM STDIN
    WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '')
    """
    print("\n📥 Loading data via COPY...")
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            cur.copy_expert(copy_sql, f)
        conn.commit()
    finally:
        conn.close()

    # Count rows
    with engine.connect() as conn:
        r = conn.execute(text("SELECT COUNT(*) FROM cpt_consolidated")).scalar()
        print(f"✅ Loaded {r:,} rows into cpt_consolidated.")

    print("Done.")


if __name__ == "__main__":
    main()
