#!/usr/bin/env python3
"""Super simple script to upload exclusions.csv to the database."""

import sys
import csv
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env
backend_dir = Path(__file__).parent.parent.parent / 'backend'
load_dotenv(backend_dir / '.env')

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# Drop and create table
print("🗄️  Creating table...")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS exclusions"))
    conn.execute(text("""
        CREATE TABLE exclusions (
            lastname TEXT,
            firstname TEXT,
            midname TEXT,
            busname TEXT,
            general TEXT,
            specialty TEXT,
            upin TEXT,
            npi TEXT,
            dob TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            excltype TEXT,
            excldate TEXT,
            reindate TEXT,
            waiverdate TEXT,
            wvrstate TEXT
        )
    """))
    conn.commit()

# Upload CSV
print("📊 Reading CSV...")
csv_file = Path(__file__).parent / 'exclusions.csv'
rows = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = [dict(row) for row in reader]

print(f"✅ Loaded {len(rows)} rows")
print("📤 Uploading to database...")

# Use raw connection for executemany (faster)
raw_conn = engine.raw_connection()
cursor = raw_conn.cursor()

cursor.executemany("""
    INSERT INTO exclusions VALUES (
        %(LASTNAME)s, %(FIRSTNAME)s, %(MIDNAME)s, %(BUSNAME)s, %(GENERAL)s, %(SPECIALTY)s,
        %(UPIN)s, %(NPI)s, %(DOB)s, %(ADDRESS)s, %(CITY)s, %(STATE)s, %(ZIP)s,
        %(EXCLTYPE)s, %(EXCLDATE)s, %(REINDATE)s, %(WAIVERDATE)s, %(WVRSTATE)s
    )
""", rows)

raw_conn.commit()
cursor.close()
raw_conn.close()

print(f"✅ Done! Uploaded {len(rows)} rows to 'exclusions' table")

