#!/usr/bin/env python3
"""
Load US News and Healthgrades data into the concierge_md database
"""

import csv
import psycopg2
from pathlib import Path
import sys

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'database': 'concierge_md',
    'user': 'joeylane',
    'port': 5432
}

def load_usnews_data():
    """Load US News data from CSV into usnews_data table"""
    print("Loading US News data...")
    
    csv_file = Path('scraping/usnews/mapping/npi_verification_results_enhanced.csv')
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return False
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Clear existing data
        cur.execute("DELETE FROM usnews_data")
        print("Cleared existing US News data")
        
        # Load new data
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            insert_query = """
                INSERT INTO usnews_data (npi, first_name, last_name, markdown_file, 
                                       medical_school, residency, fellowship, certifications)
                VALUES (%(npi)s, %(first_name)s, %(last_name)s, %(markdown_file)s,
                        %(medical_school)s, %(residency)s, %(fellowship)s, %(certifications)s)
            """
            
            rows_loaded = 0
            for row in reader:
                # Convert empty strings to None for better database handling
                for key in row:
                    if row[key] == '' or row[key] == 'None':
                        row[key] = None
                
                cur.execute(insert_query, row)
                rows_loaded += 1
                
                if rows_loaded % 1000 == 0:
                    print(f"Loaded {rows_loaded} US News records...")
        
        conn.commit()
        print(f"Successfully loaded {rows_loaded} US News records")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error loading US News data: {e}")
        return False

def load_healthgrades_data():
    """Load Healthgrades data from CSV into healthgrades_data table"""
    print("Loading Healthgrades data...")
    
    csv_file = Path('scraping/healthgrades/neuro_specialists_verification_results.csv')
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return False
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Clear existing data
        cur.execute("DELETE FROM healthgrades_data")
        print("Cleared existing Healthgrades data")
        
        # Load new data
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            insert_query = """
                INSERT INTO healthgrades_data (npi, first_name, last_name, filenames, 
                                            specialties, medical_school, residency, fellowship, 
                                            certifications, matching_method, matching_notes)
                VALUES (%(npi)s, %(first_name)s, %(last_name)s, %(filenames)s,
                        %(specialties)s, %(medical_school)s, %(residency)s, %(fellowship)s,
                        %(certifications)s, %(matching_method)s, %(matching_notes)s)
            """
            
            rows_loaded = 0
            for row in reader:
                # Convert empty strings to None for better database handling
                for key in row:
                    if row[key] == '' or row[key] == 'None':
                        row[key] = None
                
                cur.execute(insert_query, row)
                rows_loaded += 1
                
                if rows_loaded % 1000 == 0:
                    print(f"Loaded {rows_loaded} Healthgrades records...")
        
        conn.commit()
        print(f"Successfully loaded {rows_loaded} Healthgrades records")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error loading Healthgrades data: {e}")
        return False

def verify_data():
    """Verify the loaded data"""
    print("\nVerifying loaded data...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Check US News data
        cur.execute("SELECT COUNT(*) FROM usnews_data")
        usnews_count = cur.fetchone()[0]
        print(f"US News records: {usnews_count}")
        
        # Check Healthgrades data
        cur.execute("SELECT COUNT(*) FROM healthgrades_data")
        hg_count = cur.fetchone()[0]
        print(f"Healthgrades records: {hg_count}")
        
        # Sample data
        print("\nSample US News record:")
        cur.execute("SELECT npi, first_name, last_name, medical_school FROM usnews_data LIMIT 1")
        sample = cur.fetchone()
        if sample:
            print(f"  NPI: {sample[0]}, Name: {sample[1]} {sample[2]}, Med School: {sample[3][:50]}...")
        
        print("\nSample Healthgrades record:")
        cur.execute("SELECT npi, first_name, last_name, specialties FROM healthgrades_data LIMIT 1")
        sample = cur.fetchone()
        if sample:
            print(f"  NPI: {sample[0]}, Name: {sample[1]} {sample[2]}, Specialties: {sample[3][:50]}...")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error verifying data: {e}")

if __name__ == "__main__":
    print("Starting data loading process...")
    
    success1 = load_usnews_data()
    success2 = load_healthgrades_data()
    
    if success1 and success2:
        verify_data()
        print("\n✅ Data loading completed successfully!")
    else:
        print("\n❌ Data loading failed!")
        sys.exit(1)
