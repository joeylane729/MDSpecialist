#!/usr/bin/env python3
"""
Verify cpt_consolidated table: row count, spot-checks vs CSV, no corruption.
"""

import csv
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir.parent / ".env")
load_dotenv(backend_dir / ".env")

from sqlalchemy import text
from app.database import engine

CSV_PATH = backend_dir.parent / "data" / "ama-cpt-codes" / "ConsolidatedCodeList.csv"
EXPECTED_ROWS = 11_529  # CSV data rows (excluding header)


def main():
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL not set.")
        sys.exit(1)

    ok = True

    with engine.connect() as conn:
        # 1. Row count
        count = conn.execute(text("SELECT COUNT(*) FROM cpt_consolidated")).scalar()
        print(f"📊 Row count: {count:,} (expected {EXPECTED_ROWS:,})")
        if count != EXPECTED_ROWS:
            print(f"   ❌ MISMATCH: expected {EXPECTED_ROWS}, got {count}")
            ok = False
        else:
            print("   ✅ Row count matches CSV.")

        # 2. No NULL cpt_code
        null_cpt = conn.execute(text(
            "SELECT COUNT(*) FROM cpt_consolidated WHERE cpt_code IS NULL OR TRIM(cpt_code) = ''"
        )).scalar()
        print(f"\n📋 Rows with NULL/empty cpt_code: {null_cpt}")
        if null_cpt > 0:
            print("   ❌ cpt_code should never be empty.")
            ok = False
        else:
            print("   ✅ All rows have cpt_code.")

        # 3. Sample first row (id=1 or first by id)
        row1 = conn.execute(text("""
            SELECT concept_id, cpt_code, LEFT(long_desc, 80) AS long_preview, short_desc
            FROM cpt_consolidated ORDER BY id LIMIT 1
        """)).fetchone()
        print(f"\n🔍 First row (DB): concept_id={row1[0]}, cpt_code={row1[1]!r}, short_desc={row1[3]!r}")

        # 4. Sample last row (by id)
        row_last = conn.execute(text("""
            SELECT concept_id, cpt_code, short_desc
            FROM cpt_consolidated ORDER BY id DESC LIMIT 1
        """)).fetchone()
        print(f"🔍 Last row (DB):  concept_id={row_last[0]}, cpt_code={row_last[1]!r}, short_desc={row_last[2]!r}")

        # 5. Spot-check: compare first 3 and last 2 rows to CSV
        csv_rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
        db_first3 = conn.execute(text("""
            SELECT concept_id, cpt_code, short_desc FROM cpt_consolidated ORDER BY id LIMIT 3
        """)).fetchall()
        db_last2 = conn.execute(text("""
            SELECT concept_id, cpt_code, short_desc FROM cpt_consolidated ORDER BY id DESC LIMIT 2
        """)).fetchall()

        for i, db_row in enumerate(db_first3):
            csv_row = csv_rows[i]
            if (str(db_row[0]) != csv_row["Concept Id"] or
                    str(db_row[1]) != csv_row["CPT Code"] or
                    (db_row[2] or "").strip() != (csv_row.get("Short") or "").strip()):
                print(f"   ❌ First-row mismatch at index {i}: DB {db_row} vs CSV concept_id={csv_row['Concept Id']!r} cpt_code={csv_row['CPT Code']!r}")
                ok = False
        if ok and len(db_first3) == 3:
            print("   ✅ First 3 rows match CSV.")

        # db_last2 is [row with max id, row with second max id]; reversed = [second-to-last, last]
        for i, db_row in enumerate(reversed(db_last2)):
            j = len(csv_rows) - 2 + i  # second-to-last CSV row, then last CSV row
            csv_row = csv_rows[j]
            if (str(db_row[0]) != csv_row["Concept Id"] or str(db_row[1]) != csv_row["CPT Code"]):
                print(f"   ❌ Last-row mismatch at CSV index {j}: DB {db_row} vs CSV concept_id={csv_row['Concept Id']!r} cpt_code={csv_row['CPT Code']!r}")
                ok = False
        if ok and len(db_last2) == 2:
            print("   ✅ Last 2 rows match CSV.")

        # 6. Distinct cpt_code count (sanity)
        distinct_cpt = conn.execute(text("SELECT COUNT(DISTINCT cpt_code) FROM cpt_consolidated")).scalar()
        print(f"\n📋 Distinct cpt_code values: {distinct_cpt:,}")

    if ok:
        print("\n✅ Verification passed: data looks correct.")
    else:
        print("\n❌ Verification failed: see above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
