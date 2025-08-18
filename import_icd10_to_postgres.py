import psycopg2

# --- CONFIG ---
DB_NAME = 'concierge_md'
DB_USER = 'joeylane'
DB_PASSWORD = ''
DB_HOST = 'localhost'
DB_PORT = 5432
ICD10_FILE = 'icd10cm_codes_2026.txt'

# --- MAIN ---
def main():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cur = conn.cursor()

    with open(ICD10_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Split on first whitespace (tab or spaces)
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            code, desc = parts
            try:
                cur.execute(
                    "INSERT INTO icd10_codes (code, description) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
                    (code, desc)
                )
            except Exception as e:
                print(f"Error inserting {code}: {e}")
    conn.commit()
    cur.close()
    conn.close()
    print('Import complete!')

if __name__ == '__main__':
    main()
