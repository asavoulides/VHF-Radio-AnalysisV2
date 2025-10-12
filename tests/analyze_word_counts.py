import sys
sys.path.append(r"c:\Users\alexa\OneDrive\Desktop\Folders\Scripts\Python\Local Police Scanner Analysis")

import sqlite3
from pathlib import Path

# Connect to database
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get transcripts of different lengths
cursor.execute("""
    SELECT 
        LENGTH(transcript) - LENGTH(REPLACE(transcript, ' ', '')) + 1 as word_count,
        COUNT(*) as count,
        SUM(CASE WHEN incident_type = 'unknown' THEN 1 ELSE 0 END) as unknown_count
    FROM audio_metadata
    WHERE transcript IS NOT NULL AND transcript != ''
    GROUP BY word_count
    ORDER BY word_count
    LIMIT 30
""")

rows = cursor.fetchall()

print("\n" + "="*80)
print("WORD COUNT ANALYSIS")
print("="*80 + "\n")
print(f"{'Words':<10} {'Total':<10} {'Unknown':<10} {'% Unknown':<10}")
print("-" * 80)

for word_count, total, unknown_count in rows:
    pct = (unknown_count / total * 100) if total > 0 else 0
    print(f"{word_count:<10} {total:<10} {unknown_count:<10} {pct:>6.1f}%")

# Now get some longer transcripts that are still unknown
print("\n" + "="*80)
print("SAMPLE LONGER TRANSCRIPTS STILL MARKED 'unknown':")
print("="*80 + "\n")

cursor.execute("""
    SELECT id, transcript, incident_type
    FROM audio_metadata
    WHERE incident_type = 'unknown'
    AND transcript IS NOT NULL
    AND LENGTH(transcript) - LENGTH(REPLACE(transcript, ' ', '')) + 1 >= 10
    LIMIT 10
""")

long_unknown = cursor.fetchall()
for incident_id, transcript, incident_type in long_unknown:
    word_count = len(transcript.split())
    print(f"ID: {incident_id} ({word_count} words)")
    print(f"Transcript: {transcript[:200]}")
    print("-" * 80)

conn.close()
