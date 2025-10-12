import sqlite3
from pathlib import Path
from datetime import datetime

# Connect to database
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all dates with data
cursor.execute("""
    SELECT date_created, COUNT(*) as total, 
           SUM(CASE WHEN incident_type = 'unknown' THEN 1 ELSE 0 END) as unknown_count
    FROM audio_metadata
    GROUP BY date_created
    ORDER BY date_created DESC
    LIMIT 10
""")

rows = cursor.fetchall()

print(f"\n{'='*80}")
print(f"RECENT DATES WITH INCIDENT DATA:")
print(f"{'='*80}\n")
print(f"{'Date':<15} {'Total':<10} {'Unknown':<10} {'% Unknown':<10}")
print("-" * 80)

for date_created, total, unknown_count in rows:
    pct = (unknown_count / total * 100) if total > 0 else 0
    print(f"{date_created:<15} {total:<10} {unknown_count:<10} {pct:>6.1f}%")

print(f"\n{'='*80}")

# Get sample of unknown incidents from most recent date
if rows:
    most_recent_date = rows[0][0]
    print(f"\nSample 'unknown' incidents from {most_recent_date}:")
    print(f"{'='*80}\n")
    
    cursor.execute("""
        SELECT id, filename, transcript, incident_type
        FROM audio_metadata
        WHERE date_created = ? AND incident_type = 'unknown'
        ORDER BY id DESC
        LIMIT 5
    """, (most_recent_date,))
    
    unknown_samples = cursor.fetchall()
    for incident_id, filename, transcript, incident_type in unknown_samples:
        trans_preview = (transcript[:80] + "...") if transcript and len(transcript) > 80 else (transcript or "[NO TRANSCRIPT]")
        print(f"ID: {incident_id}")
        print(f"Filename: {filename}")
        print(f"Type: {incident_type}")
        print(f"Transcript: {trans_preview}")
        print("-" * 80)

conn.close()
