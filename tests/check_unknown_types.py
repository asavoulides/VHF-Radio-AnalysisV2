import sqlite3
from pathlib import Path
from datetime import datetime

# Connect to database
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get today's date
today = datetime.now().date()

# Query for unknown incident types
cursor.execute("""
    SELECT id, incident_type, transcript, date_created, filename
    FROM audio_metadata 
    WHERE date_created = date('now', 'localtime') 
    AND incident_type = 'unknown'
    ORDER BY id DESC
    LIMIT 10
""")

rows = cursor.fetchall()
total_unknown = len(rows)

print(f"\n{'='*80}")
print(f"INCIDENTS WITH 'unknown' TYPE TODAY: {total_unknown}")
print(f"{'='*80}\n")

for row in rows:
    incident_id, incident_type, transcript, date_created, filename = row
    trans_preview = transcript[:100] if transcript else "[NO TRANSCRIPT]"
    print(f"ID: {incident_id}")
    print(f"Filename: {filename}")
    print(f"Type: {incident_type}")
    print(f"Transcript: {trans_preview}...")
    print(f"Transcript Length: {len(transcript) if transcript else 0} chars")
    print("-" * 80)

# Get total count for today
cursor.execute("""
    SELECT COUNT(*) 
    FROM audio_metadata 
    WHERE date_created = date('now', 'localtime') 
    AND incident_type = 'unknown'
""")
total_count = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*) 
    FROM audio_metadata 
    WHERE date_created = date('now', 'localtime')
""")
all_count = cursor.fetchone()[0]

print(f"\n{'='*80}")
print(f"SUMMARY:")
print(f"Total incidents today: {all_count}")
print(f"Stuck on 'unknown': {total_count} ({total_count/all_count*100:.1f}%)")
print(f"{'='*80}\n")

conn.close()
