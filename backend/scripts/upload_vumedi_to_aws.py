#!/usr/bin/env python3
"""
Upload vumedi_content_consolidated.csv to the database.
Simple script that creates a table and inserts all data as-is.
"""

import os
import sys
import csv
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def upload_csv():
    """Upload the consolidated Vumedi CSV to database"""
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Error: DATABASE_URL not found in environment variables")
        return
    
    # Create SQLAlchemy engine
    engine = create_engine(database_url)
    
    # Path to CSV file
    csv_path = Path(__file__).parent.parent.parent / 'data' / 'vumedi-scraping' / 'vumedi_content_consolidated.csv'
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found at {csv_path}")
        return
    
    print(f"📂 Reading CSV from: {csv_path}")
    
    # Read CSV to get column names and data
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        column_names = reader.fieldnames
        rows = list(reader)
    
    print(f"📊 Found {len(rows)} rows and {len(column_names)} columns")
    print(f"📋 Columns: {', '.join(column_names)}")
    
    # Drop existing table if it exists
    print("\n🗑️  Dropping existing table if it exists...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS vumedi_content_consolidated CASCADE"))
        conn.commit()
    
    # Create table with all columns as TEXT
    print("📋 Creating table vumedi_content_consolidated...")
    create_table_sql = f"""
    CREATE TABLE vumedi_content_consolidated (
        {', '.join([f'"{col}" TEXT' for col in column_names])}
    )
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    print("✅ Table created successfully")
    
    # Insert data in batches
    batch_size = 1000
    total_inserted = 0
    
    print(f"\n📥 Inserting data in batches of {batch_size}...")
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        # Build insert statement
        placeholders = ', '.join([f':{col}' for col in column_names])
        insert_sql = f"""
        INSERT INTO vumedi_content_consolidated ({', '.join([f'"{col}"' for col in column_names])})
        VALUES ({placeholders})
        """
        
        with engine.connect() as conn:
            for row in batch:
                conn.execute(text(insert_sql), row)
            conn.commit()
        
        total_inserted += len(batch)
        print(f"   Inserted {total_inserted}/{len(rows)} rows...")
    
    print(f"\n✅ Successfully inserted {total_inserted} rows!")
    
    # Verify the data
    print("\n🔍 Verifying data...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM vumedi_content_consolidated"))
        count = result.scalar()
        print(f"✅ Table contains {count} rows")
    
    print("\n🎉 Upload complete!")

if __name__ == "__main__":
    upload_csv()

