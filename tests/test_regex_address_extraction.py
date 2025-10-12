"""
Test script to analyze address extraction coverage using regex vs database addresses.
This script queries the database to see:
1. How many transcripts have addresses extractable by regex alone (no LLM)
2. How many records have non-null addresses in the database
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import location_services
sys.path.insert(0, str(Path(__file__).parent.parent))

from location_services import _regex_extract

# Database path
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"


def test_regex_extraction():
    """Test how many transcripts can be extracted using ONLY regex (no LLM)."""

    print("=" * 80)
    print("ADDRESS EXTRACTION ANALYSIS - REGEX ONLY")
    print("=" * 80)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get total record count
    cursor.execute("SELECT COUNT(*) FROM audio_metadata")
    total_records = cursor.fetchone()[0]
    print(f"\n📊 Total Records: {total_records:,}")

    # Get records with non-null addresses
    cursor.execute(
        "SELECT COUNT(*) FROM audio_metadata WHERE address IS NOT NULL AND address != ''"
    )
    non_null_addresses = cursor.fetchone()[0]
    print(
        f"📍 Records with Non-Null Addresses: {non_null_addresses:,} ({non_null_addresses/total_records*100:.2f}%)"
    )

    # Get all transcripts
    cursor.execute(
        "SELECT id, transcript FROM audio_metadata WHERE transcript IS NOT NULL AND transcript != ''"
    )
    transcripts = cursor.fetchall()

    print(f"📝 Records with Transcripts: {len(transcripts):,}")

    # Test regex extraction on all transcripts
    print("\n" + "=" * 80)
    print("TESTING REGEX EXTRACTION (NO LLM)")
    print("=" * 80)

    regex_success = 0
    regex_failures = 0
    examples = []

    for record_id, transcript in transcripts:
        extracted = _regex_extract(transcript)

        if extracted:
            regex_success += 1
            # Store first 5 examples
            if len(examples) < 5:
                examples.append(
                    {
                        "id": record_id,
                        "transcript": (
                            transcript[:100] + "..."
                            if len(transcript) > 100
                            else transcript
                        ),
                        "extracted": extracted,
                    }
                )
        else:
            regex_failures += 1

    print(
        f"\n✅ Regex Extracted Addresses: {regex_success:,} ({regex_success/len(transcripts)*100:.2f}%)"
    )
    print(
        f"❌ Regex Failed to Extract: {regex_failures:,} ({regex_failures/len(transcripts)*100:.2f}%)"
    )

    # Show examples
    if examples:
        print("\n" + "=" * 80)
        print("REGEX EXTRACTION EXAMPLES")
        print("=" * 80)
        for i, ex in enumerate(examples, 1):
            print(f"\nExample {i} (ID: {ex['id']}):")
            print(f"  Transcript: {ex['transcript']}")
            print(f"  Extracted:  {ex['extracted']}")

    # Compare regex success to database addresses
    print("\n" + "=" * 80)
    print("COMPARISON ANALYSIS")
    print("=" * 80)

    print(f"\n📊 Database Addresses (Non-Null):    {non_null_addresses:,}")
    print(f"📊 Regex Extractable (from all):      {regex_success:,}")
    print(
        f"📊 Difference:                         {non_null_addresses - regex_success:,}"
    )

    if non_null_addresses > 0:
        print(
            f"\n💡 Regex Coverage of DB Addresses:    {regex_success/non_null_addresses*100:.2f}%"
        )
        print(
            f"💡 LLM Contribution (estimated):       {(non_null_addresses - regex_success)/non_null_addresses*100:.2f}%"
        )

    # Get some examples where database has address but regex didn't extract
    print("\n" + "=" * 80)
    print("ADDRESSES IN DATABASE BUT NOT EXTRACTED BY REGEX")
    print("=" * 80)

    cursor.execute(
        """
        SELECT id, transcript, address 
        FROM audio_metadata 
        WHERE address IS NOT NULL 
        AND address != '' 
        AND transcript IS NOT NULL 
        LIMIT 10
    """
    )

    db_addresses = cursor.fetchall()
    missed_count = 0

    for record_id, transcript, db_address in db_addresses:
        regex_result = _regex_extract(transcript) if transcript else None

        if not regex_result:
            missed_count += 1
            if missed_count <= 5:  # Show first 5 examples
                print(f"\nExample {missed_count} (ID: {record_id}):")
                print(
                    f"  Transcript:   {transcript[:80]}..."
                    if len(transcript) > 80
                    else f"  Transcript:   {transcript}"
                )
                print(f"  DB Address:   {db_address}")
                print(f"  Regex Result: None")

    conn.close()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_regex_extraction()
