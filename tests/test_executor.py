"""
Test Progressive Loading System with Database Cleanup
Combined utility for testing progressive loading and cleaning up test data
"""

import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = r"C:\Proscan\Recordings"
DB_PATH = r"Logs\audio_metadata.db"


def get_today_folder():
    """Get today's recording folder"""
    today = datetime.now()
    formatted = f"{today.month:02d}-{today.day:02d}-{today.year % 100:02d}"
    return os.path.join(BASE_DIR, formatted)


def find_test_file():
    """Find an existing MP3 file to use as test source"""
    today_folder = get_today_folder()
    if not os.path.exists(today_folder):
        print(f"❌ Today's folder doesn't exist: {today_folder}")
        return None

    # Look for any MP3 file in Middlesex subfolder
    middlesex_folder = os.path.join(today_folder, "Middlesex")
    if os.path.exists(middlesex_folder):
        for file in os.listdir(middlesex_folder):
            if file.lower().endswith(".mp3") and "#TEST-" not in file:
                return os.path.join(middlesex_folder, file)

    # Fallback: any non-test MP3 in today's folder
    for root, dirs, files in os.walk(today_folder):
        for file in files:
            if file.lower().endswith(".mp3") and "#TEST-" not in file:
                return os.path.join(root, file)

    return None


def create_test_filename():
    """Create a unique test filename"""
    now = datetime.now()
    return f"Middlesex; Municipalities - Newton; Police Department; NFM; 470.837500; ID; #TEST-{now.strftime('%H%M%S')}.mp3"


def simulate_new_file():
    """Simulate a new audio file being created by ProScan"""
    print("🧪 TEST: Simulating new audio file creation...\n")

    # Step 1: Find source file to copy
    print("📂 Step 1: Finding existing MP3 to use as test...")
    source_file = find_test_file()
    if not source_file:
        print("❌ No MP3 files found to use as test source!")
        print(f"   Please make sure there are existing files in: {get_today_folder()}")
        return False

    print(f"✓ Found source: {os.path.basename(source_file)}")
    print(f"  Size: {os.path.getsize(source_file):,} bytes\n")

    # Step 2: Create destination path
    today_folder = get_today_folder()
    middlesex_folder = os.path.join(today_folder, "Middlesex")
    os.makedirs(middlesex_folder, exist_ok=True)

    test_filename = create_test_filename()
    dest_file = os.path.join(middlesex_folder, test_filename)

    print(f"📝 Step 2: Creating test file...")
    print(f"   Destination: {test_filename}")

    # Step 3: Copy file to simulate ProScan creating it
    print(f"\n⏱️  Step 3: Copying file (simulating ProScan recording)...")
    start_time = time.time()

    try:
        shutil.copy2(source_file, dest_file)
        copy_time = time.time() - start_time
        print(f"✓ File created in {copy_time:.2f}s")
        print(f"  Full path: {dest_file}\n")

        print("👀 Step 4: Watch the app.py terminal for processing logs...")
        print("   You should see:")
        print("   1. ⚡ [INSTANT] Processing {filename}")
        print("   2. ⚡ [INSTANT] ✓ Incident {id} card created IMMEDIATELY")
        print("   3. ⚡ [INSTANT] ✓ Background task submitted")
        print("   4. [Background] ✨ Thread started")
        print("   5. [Background] Transcribing audio...")
        print("   6. [Background] ✓ Transcription complete\n")

        print("✅ TEST FILE CREATED SUCCESSFULLY!")
        print(f"   File: {test_filename}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}\n")

        return True

    except Exception as e:
        print(f"❌ Error creating test file: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_files_only():
    """Clean up test audio files only (not database records)"""
    print("\n🧹 Cleaning up test audio files...\n")

    today_folder = get_today_folder()
    middlesex_folder = os.path.join(today_folder, "Middlesex")

    if not os.path.exists(middlesex_folder):
        print("No test files to clean up.")
        return 0

    deleted_count = 0
    for file in os.listdir(middlesex_folder):
        if "#TEST-" in file and file.lower().endswith(".mp3"):
            filepath = os.path.join(middlesex_folder, file)
            try:
                os.remove(filepath)
                print(f"✓ Deleted audio: {file}")
                deleted_count += 1
            except Exception as e:
                print(f"✗ Failed to delete {file}: {e}")

    if deleted_count == 0:
        print("No test audio files found.")
    else:
        print(f"\n✅ Deleted {deleted_count} test audio file(s)")

    return deleted_count


def cleanup_database_records():
    """Clean up test records from database"""
    print("\n🗄️  Cleaning up test database records...\n")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return 0

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Find test records
        cursor.execute("""
            SELECT id, filename, original_filename 
            FROM audio_metadata 
            WHERE filename LIKE '%#TEST-%' OR original_filename LIKE '%#TEST-%'
            ORDER BY id
        """)

        test_records = cursor.fetchall()

        if not test_records:
            print("No test records found in database.")
            conn.close()
            return 0

        print(f"Found {len(test_records)} test record(s):")
        for record_id, filename, orig_filename in test_records:
            display_name = filename or orig_filename or f"ID {record_id}"
            print(f"  - ID {record_id}: {display_name}")

        print()
        confirm = input("Delete these records from database? (y/N): ").strip().lower()

        if confirm == 'y':
            # Delete the records
            cursor.execute("""
                DELETE FROM audio_metadata 
                WHERE filename LIKE '%#TEST-%' OR original_filename LIKE '%#TEST-%'
            """)

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            print(f"\n✅ Deleted {deleted_count} database record(s)")
            return deleted_count
        else:
            print("\n❌ Cancelled - no database records deleted")
            conn.close()
            return 0

    except Exception as e:
        print(f"❌ Error cleaning database: {e}")
        import traceback
        traceback.print_exc()
        return 0


def cleanup_all():
    """Clean up both test files and database records"""
    print("\n🧹 COMPLETE CLEANUP: Files + Database Records\n")
    print("=" * 70)

    # Step 1: Clean audio files
    audio_deleted = cleanup_test_files_only()

    # Step 2: Clean database
    db_deleted = cleanup_database_records()

    # Summary
    print("\n" + "=" * 70)
    print("CLEANUP SUMMARY:")
    print(f"  Audio files deleted: {audio_deleted}")
    print(f"  Database records deleted: {db_deleted}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("🧪 PROGRESSIVE LOADING TEST & CLEANUP UTILITY")
    print("=" * 70)
    print()
    print("This utility helps you test and clean up the progressive loading system.")
    print()
    print("PREREQUISITES:")
    print("  1. app.py should be running (file processor)")
    print("  2. scanner_dashboard.py should be running (web interface)")
    print("  3. Browser open to http://localhost:5000/live (optional)")
    print()
    print("=" * 70)
    print()

    while True:
        print("\nOPTIONS:")
        print("  1. Create new test file (simulate recording)")
        print("  2. Clean up test audio files ONLY (keeps DB records)")
        print("  3. Clean up test database records ONLY (keeps audio files)")
        print("  4. Complete cleanup (audio files + database records)")
        print("  5. Exit")
        print()

        choice = input("Enter your choice (1-5): ").strip()
        print()

        if choice == "1":
            success = simulate_new_file()
            if success:
                print("\n" + "=" * 70)
                print("✅ TEST COMPLETE - Check app.py logs and dashboard!")
                print("=" * 70)

        elif choice == "2":
            cleanup_test_files_only()

        elif choice == "3":
            cleanup_database_records()

        elif choice == "4":
            cleanup_all()

        elif choice == "5":
            print("👋 Exiting...")
            break

        else:
            print("❌ Invalid choice. Please select 1-5.")


if __name__ == "__main__":
    main()
