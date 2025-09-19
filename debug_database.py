#!/usr/bin/env python3
"""
Deep database analysis for incident filtering debug
"""

import sqlite3
import os
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def analyze_database():
    """Comprehensive database analysis"""

    # Connect to database using environment variable
    db_path_str = os.getenv("DB_PATH", "Logs/audio_metadata.db")
    db_path = Path(db_path_str)
    if not db_path.exists():
        print(f"ERROR: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("=== DATABASE SCHEMA ANALYSIS ===")
    cursor.execute("PRAGMA table_info(audio_metadata)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"Column: {col[1]}, Type: {col[2]}, NotNull: {col[3]}, Default: {col[4]}")

    print("\n=== INCIDENT TYPE ANALYSIS ===")
    cursor.execute(
        """
        SELECT DISTINCT incident_type, COUNT(*) as count 
        FROM audio_metadata 
        WHERE date_created = "9-18-2025" 
        GROUP BY incident_type 
        ORDER BY count DESC
    """
    )
    incident_types = cursor.fetchall()
    print("Distinct incident types in today's data:")
    for it in incident_types:
        print(f'  "{it[0]}" -> {it[1]} records')

    print("\n=== NULL/EMPTY INCIDENT TYPES ===")
    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM audio_metadata 
        WHERE date_created = "9-18-2025" 
        AND (incident_type IS NULL OR incident_type = "" OR incident_type = "unknown")
    """
    )
    null_count = cursor.fetchone()[0]
    print(f"Records with null/empty/unknown incident_type: {null_count}")

    print("\n=== SAMPLE RECORDS FOR EACH TYPE ===")
    for incident_type, count in incident_types[:10]:  # Top 10 types
        cursor.execute(
            """
            SELECT id, transcript, formatted_address 
            FROM audio_metadata 
            WHERE date_created = "9-18-2025" 
            AND incident_type = ? 
            LIMIT 2
        """,
            (incident_type,),
        )
        samples = cursor.fetchall()
        print(f'\nType: "{incident_type}" ({count} records)')
        for sample in samples:
            transcript_preview = (
                sample[1][:60] + "..."
                if sample[1] and len(sample[1]) > 60
                else sample[1]
            )
            print(f"  ID: {sample[0]}, Transcript: {transcript_preview}")
            print(f"  Address: {sample[2]}")

    print("\n=== DATA QUALITY CHECKS ===")

    # Check for special characters or encoding issues
    cursor.execute(
        """
        SELECT DISTINCT incident_type 
        FROM audio_metadata 
        WHERE date_created = "9-18-2025" 
        AND incident_type IS NOT NULL
        AND incident_type != ""
        AND incident_type != "unknown"
    """
    )
    all_types = [row[0] for row in cursor.fetchall()]

    print("Incident types with potential issues:")
    for incident_type in all_types:
        if any(ord(c) > 127 for c in incident_type):
            print(f'  Non-ASCII characters in: "{incident_type}"')
        if incident_type.startswith(" ") or incident_type.endswith(" "):
            print(f'  Leading/trailing spaces in: "{incident_type}"')
        if "\\" in incident_type or '"' in incident_type:
            print(f'  Special characters in: "{incident_type}"')

    print("\n=== TOTAL RECORDS SUMMARY ===")
    cursor.execute(
        'SELECT COUNT(*) FROM audio_metadata WHERE date_created = "9-18-2025"'
    )
    total = cursor.fetchone()[0]
    print(f"Total records for today: {total}")

    non_unknown_count = sum(
        count for _, count in incident_types if _ not in [None, "", "unknown"]
    )
    print(f"Non-unknown incident types: {non_unknown_count}")

    conn.close()


if __name__ == "__main__":
    analyze_database()
