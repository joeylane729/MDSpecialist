#!/usr/bin/env python3
"""
Add search key columns from CSV to the medical_school_rankings table.
This will add the search_key columns as new columns to the existing table.
"""

import os
import sys
import csv
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def main():
    print("🚀 Adding search keys to medical_school_rankings table...")
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL is not set in environment.")
        sys.exit(1)
    
    engine = create_engine(database_url)
    
    # Read the search keys CSV
    search_keys_file = "Medical Schools Search Keys.csv"
    print(f"📊 Reading search keys from {search_keys_file}...")
    
    try:
        df = pd.read_csv(search_keys_file)
        print(f"✅ Loaded {len(df)} rows from search keys CSV")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        sys.exit(1)
    
    # Get the search key column names (exclude the linking columns and invalid names)
    linking_columns = ['id', 'rank', 'school_listed', 'full_official_name', 'city', 'state_region']
    search_key_columns = [col for col in df.columns 
                         if col not in linking_columns 
                         and not col.startswith('Unnamed')
                         and not col.startswith('unnamed')
                         and ':' not in col]
    
    print(f"📊 Found search key columns: {search_key_columns}")
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # Add search key columns to the table if they don't exist
            print("🔧 Adding search key columns to table...")
            for col in search_key_columns:
                try:
                    conn.execute(text(f"ALTER TABLE medical_school_rankings ADD COLUMN {col} TEXT"))
                    print(f"✅ Added column: {col}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        print(f"⚠️ Column {col} already exists, skipping...")
                    else:
                        print(f"❌ Error adding column {col}: {e}")
                        raise
            
            # Update the table with search key values
            print("🔄 Updating search key values...")
            updated_count = 0
            
            for _, row in df.iterrows():
                school_id = row['id']
                
                # Build the SET clause for search key columns
                set_clauses = []
                params = {'school_id': school_id}
                
                for col in search_key_columns:
                    if pd.notna(row[col]) and str(row[col]).strip():
                        set_clauses.append(f"{col} = :{col}")
                        params[col] = str(row[col]).strip()
                
                if set_clauses:
                    update_sql = f"""
                        UPDATE medical_school_rankings 
                        SET {', '.join(set_clauses)}
                        WHERE id = :school_id
                    """
                    
                    result = conn.execute(text(update_sql), params)
                    if result.rowcount > 0:
                        updated_count += 1
            
            # Commit the transaction
            trans.commit()
            print(f"✅ Successfully updated {updated_count} schools with search keys")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"❌ Error updating table: {e}")
            raise
    
    print("🎉 Search keys successfully added to medical_school_rankings table!")

if __name__ == "__main__":
    main()
