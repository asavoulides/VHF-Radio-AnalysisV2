"""
Test Progressive Loading System - SIMPLE VERSION
Simulates adding a new audio file to test the ultra-fast card creation and background processing

DIFFERENCE FROM test_executor.py:
- test_progressive_loading.py (THIS FILE): Simple, focused testing
  - Quick create/cleanup workflow
  - Automatic database cleanup when cleaning files
  - Best for: Quick testing cycles during development

- test_executor.py: Advanced testing with granular control
  - Menu-based interface with 5 options
  - Separate controls for audio files vs database records
  - Can clean audio WITHOUT cleaning database (or vice versa)
  - Best for: Debugging specific issues, forensic analysis

USAGE:
    python tests/test_progressive_loading.py

    Option 1: Create test file → Watch progressive loading work
    Option 2: Cleanup → Removes both audio files AND database records automatically
"""

import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = r"C:\Proscan\Recordings"
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"  # Absolute path
TEST_SOURCE_FILE = None  # Will find an existing file to copy


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
    # Format: Middlesex; Municipalities - Newton; Police Department; NFM; 470.837500; ID; #TEST.mp3
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

        # Step 4: Watch for processing
        print("👀 Step 4: Watch the app.py terminal for processing logs...")
        print("   You should see:")
        print("   1. ⚡ [INSTANT] Processing {filename}")
        print("   2. ⚡ [INSTANT] ✓ Incident {id} card created IMMEDIATELY")
        print("   3. ⚡ [INSTANT] ✓ Background task submitted")
        print("   4. [Background] ✨ Thread started")
        print("   5. [Background] Transcribing audio...")
        print("   6. [Background] ✓ Transcription complete")
        print("   7. [Database] ✓ Updated incident {id} transcript\n")

        print("📊 Step 5: Check the dashboard...")
        print("   - Open browser to: http://localhost:5000/live")
        print("   - You should see a new card appear INSTANTLY")
        print("   - Card will show '[Processing...]' for a few seconds")
        print("   - Then it will update with the real transcript\n")

        print("✅ TEST FILE CREATED SUCCESSFULLY!")
        print(f"   File: {test_filename}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
        print(
            f"\n💡 TIP: You can run this script multiple times to test progressive loading"
        )
        print(f"   Each run creates a new unique test file.\n")

        return True

    except Exception as e:
        print(f"❌ Error creating test file: {e}")
        import traceback

        traceback.print_exc()
        return False


def cleanup_test_files():
    """Clean up test files AND database records (complete cleanup)"""
    print("\n🧹 CLEANUP: Removing test audio files AND database records...\n")
    print("=" * 70)

    # Step 1: Clean up audio files
    print("\n📂 STEP 1: Cleaning audio files...")
    today_folder = get_today_folder()
    middlesex_folder = os.path.join(today_folder, "Middlesex")

    audio_deleted = 0
    if os.path.exists(middlesex_folder):
        for file in os.listdir(middlesex_folder):
            if "#TEST-" in file and file.lower().endswith(".mp3"):
                filepath = os.path.join(middlesex_folder, file)
                try:
                    os.remove(filepath)
                    print(f"  ✓ Deleted audio: {file}")
                    audio_deleted += 1
                except Exception as e:
                    print(f"  ✗ Failed to delete {file}: {e}")

    if audio_deleted == 0:
        print("  No test audio files found.")
    else:
        print(f"  ✅ Deleted {audio_deleted} audio file(s)")

    # Step 2: Clean up database records
    print(f"\n🗄️  STEP 2: Cleaning database records...")

    if not os.path.exists(DB_PATH):
        print(f"  ⚠️  Database not found: {DB_PATH}")
        print("\n" + "=" * 70)
        print(
            f"CLEANUP SUMMARY: {audio_deleted} audio files deleted, 0 DB records deleted"
        )
        print("=" * 70)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Find test records
        cursor.execute(
            """
            SELECT id, filename, original_filename 
            FROM audio_metadata 
            WHERE filename LIKE '%#TEST-%' OR original_filename LIKE '%#TEST-%'
            ORDER BY id
        """
        )

        test_records = cursor.fetchall()

        if not test_records:
            print("  No test records found in database.")
            db_deleted = 0
        else:
            print(f"  Found {len(test_records)} test record(s):")
            for record_id, filename, orig_filename in test_records:
                display_name = filename or orig_filename or f"ID {record_id}"
                print(f"    - ID {record_id}: {display_name}")

            # Delete the records automatically (no confirmation needed for test cleanup)
            cursor.execute(
                """
                DELETE FROM audio_metadata 
                WHERE filename LIKE '%#TEST-%' OR original_filename LIKE '%#TEST-%'
            """
            )

            db_deleted = cursor.rowcount
            conn.commit()
            print(f"  ✅ Deleted {db_deleted} database record(s)")

        conn.close()

    except Exception as e:
        print(f"  ❌ Error cleaning database: {e}")
        import traceback

        traceback.print_exc()
        db_deleted = 0

    # Summary
    print("\n" + "=" * 70)
    print("CLEANUP SUMMARY:")
    print(f"  Audio files deleted: {audio_deleted}")
    print(f"  Database records deleted: {db_deleted}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("🧪 PROGRESSIVE LOADING TEST UTILITY (SIMPLE VERSION)")
    print("=" * 70)
    print()
    print("ABOUT THIS TOOL:")
    print("  This is the SIMPLE test utility for quick testing cycles.")
    print("  Cleanup automatically removes BOTH audio files AND database records.")
    print()
    print("  For advanced testing with granular control, use:")
    print("  → python tests/test_executor.py")
    print()
    print("=" * 70)
    print()
    print("This script simulates ProScan creating a new audio file.")
    print("Use this to test the ultra-fast progressive loading system.")
    print()
    print("PREREQUISITES:")
    print("  1. app.py must be running (file processor)")
    print("  2. scanner_dashboard.py must be running (web interface)")
    print("  3. Browser should be open to http://localhost:5000/live")
    print()
    print("=" * 70)
    print()

    # Ask user what to do
    print("OPTIONS:")
    print("  1. Create a new test file (simulate new recording)")
    print("  2. Complete cleanup (removes audio files + database records)")
    print("  3. Exit")
    print()

    choice = input("Enter your choice (1-3): ").strip()
    print()

    if choice == "1":
        success = simulate_new_file()
        if success:
            print("\n" + "=" * 70)
            print("✅ TEST COMPLETE - Check the logs and dashboard!")
            print("=" * 70)
    elif choice == "2":
        cleanup_test_files()
    elif choice == "3":
        print("👋 Exiting...")
    else:
        print("❌ Invalid choice. Please run again and select 1, 2, or 3.")


if __name__ == "__main__":
    main()
