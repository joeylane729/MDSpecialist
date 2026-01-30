#!/usr/bin/env python3
"""
Convert ConsolidatedCodeList.txt to CSV, skipping the copyright/legal header.
The file is tab-separated; header row is on line 27 (after 26 lines of preamble).
"""

import csv
from pathlib import Path

# File paths
INPUT_FILE = Path(__file__).parent / "ConsolidatedCodeList.txt"
OUTPUT_FILE = Path(__file__).parent / "ConsolidatedCodeList.csv"

# Number of preamble lines to skip (copyright, legal text, blank line)
PREAMBLE_LINES = 26


def main():
    with open(INPUT_FILE, "r", encoding="utf-8", newline="") as f_in:
        # Skip preamble
        for _ in range(PREAMBLE_LINES):
            next(f_in)

        # Next line is the header (tab-separated)
        header_line = next(f_in)
        if not header_line.strip():
            header_line = next(f_in)  # skip blank line if present
        fieldnames = [h.strip() for h in header_line.strip().split("\t")]

        with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(fieldnames)

            for line in f_in:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                row = [field.strip() for field in line.split("\t")]
                # Pad or trim to match header length so CSV is uniform
                if len(row) < len(fieldnames):
                    row.extend([""] * (len(fieldnames) - len(row)))
                elif len(row) > len(fieldnames):
                    row = row[: len(fieldnames)]
                writer.writerow(row)

    print(f"Wrote {OUTPUT_FILE} ({len(fieldnames)} columns)")


if __name__ == "__main__":
    main()
