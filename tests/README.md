# Test Utilities for Progressive Loading System

This directory contains two test utilities for validating the ultra-fast progressive loading system.

## 📋 Overview

Both utilities simulate ProScan creating new audio files to test the progressive loading pipeline:
1. Card appears instantly (50ms)
2. Background processing begins
3. Transcription completes (3-5s)
4. Database updates
5. Frontend displays real transcript

---

## 🚀 Quick Reference

### Simple Testing (Most Common)
```bash
python tests/test_progressive_loading.py
```
**Use when:** You just want to quickly test and cleanup

### Advanced Testing (Debugging)
```bash
python tests/test_executor.py
```
**Use when:** You need granular control over cleanup or want to inspect database separately

---

## 📄 test_progressive_loading.py - SIMPLE VERSION

### Purpose
Quick and easy testing for normal development workflow.

### Features
- ✅ Create test audio files
- ✅ **Automatic complete cleanup** (audio files + database records together)
- ✅ Simple 3-option menu
- ✅ No confirmation prompts (streamlined workflow)

### Menu Options
1. **Create test file** - Simulates ProScan recording new file
2. **Complete cleanup** - Removes BOTH audio files AND database records automatically
3. **Exit**

### When to Use
- ✅ Daily development testing
- ✅ Quick validation after code changes
- ✅ When you want clean slate after testing
- ✅ Continuous integration testing

### Example Workflow
```bash
# Test the system
python tests/test_progressive_loading.py
# Choose option 1 to create test
# Watch it work in dashboard
# Choose option 2 to cleanup everything
# Done!
```

---

## 🔧 test_executor.py - ADVANCED VERSION

### Purpose
Granular control for debugging and forensic analysis.

### Features
- ✅ Create test audio files
- ✅ **Separate cleanup options** for audio vs database
- ✅ Complete cleanup option
- ✅ Database record inspection before deletion
- ✅ Confirmation prompts for safety
- ✅ Loop-based menu (multiple operations without restart)

### Menu Options
1. **Create test file** - Simulates ProScan recording
2. **Clean audio files ONLY** - Keeps database records for inspection
3. **Clean database records ONLY** - Keeps audio files for re-testing
4. **Complete cleanup** - Removes both (with confirmation)
5. **Exit**

### When to Use
- ✅ Debugging database issues
- ✅ Testing with orphaned database records
- ✅ Keeping test audio for multiple runs
- ✅ Forensic analysis of progressive loading
- ✅ Testing database cleanup logic independently

### Example Workflow
```bash
# Debug database behavior
python tests/test_executor.py

# Create test file (option 1)
# Watch processing
# Delete ONLY database record (option 3) to test orphan handling
# Re-test with same audio file
# Later, cleanup audio (option 2)
# Exit when done (option 5)
```

---

## 🔍 Key Differences Summary

| Feature | test_progressive_loading.py | test_executor.py |
|---------|----------------------------|------------------|
| **Complexity** | Simple (3 options) | Advanced (5 options) |
| **Cleanup Mode** | Automatic (audio + DB together) | Granular (separate controls) |
| **Confirmations** | None (auto-delete) | Yes (asks before DB delete) |
| **Menu Style** | Single-use | Loop-based (multiple operations) |
| **Best For** | Quick testing cycles | Debugging & analysis |
| **Database Inspection** | No | Yes (shows records before delete) |
| **Can keep audio but clean DB?** | No | Yes |
| **Can keep DB but clean audio?** | No | Yes |

---

## 🎯 Which One Should I Use?

### Use `test_progressive_loading.py` if:
- ✅ You're doing regular development testing
- ✅ You want to test and cleanup quickly
- ✅ You don't need to inspect database separately
- ✅ You want the simplest workflow

### Use `test_executor.py` if:
- ✅ You're debugging a specific issue
- ✅ You need to test orphaned database records
- ✅ You want to reuse test audio files
- ✅ You need to inspect database state
- ✅ You're doing forensic analysis

---

## 📝 Test File Naming

Both utilities create test files with this pattern:
```
Middlesex; Municipalities - Newton; Police Department; NFM; 470.837500; ID; #TEST-HHMMSS.mp3
```

Example: `#TEST-143052.mp3` (created at 14:30:52)

This pattern ensures:
- Test files are easily identifiable
- Each test file has unique timestamp
- Won't conflict with real ProScan recordings
- Easy to find in database (`filename LIKE '%#TEST-%'`)

---

## ⚙️ Prerequisites

Before running either test utility:

1. **app.py must be running** (file processor with progressive loading)
2. **scanner_dashboard.py must be running** (web interface)
3. **Browser open to http://localhost:5000/live** (optional but recommended)
4. **At least one real audio file exists** in today's ProScan folder (used as template)

---

## 🐛 Troubleshooting

### "No MP3 files found to use as test source"
- Make sure ProScan has recorded at least one real file today
- Check that `C:\Proscan\Recordings\MM-DD-YY\Middlesex\` folder exists

### "Database not found"
- Verify `Logs/audio_metadata.db` exists
- Make sure app.py has run at least once

### Test files not appearing in dashboard
- Check that app.py is running (watch for console output)
- Verify scanner_dashboard.py is running
- Refresh browser page

### Database records not deleted
- Make sure no other process has the database open
- Check file permissions on `Logs/audio_metadata.db`

---

## 📊 Expected Output

### When Creating Test File
```
🧪 TEST: Simulating new audio file creation...

📂 Step 1: Finding existing MP3 to use as test...
✓ Found source: [real_file.mp3]
  Size: 45,678 bytes

📝 Step 2: Creating test file...
   Destination: #TEST-143052.mp3

⏱️  Step 3: Copying file...
✓ File created in 0.05s

✅ TEST FILE CREATED SUCCESSFULLY!
```

### When Cleaning Up (test_progressive_loading.py)
```
🧹 CLEANUP: Removing test audio files AND database records...

📂 STEP 1: Cleaning audio files...
  ✓ Deleted audio: #TEST-143052.mp3
  ✅ Deleted 1 audio file(s)

🗄️  STEP 2: Cleaning database records...
  Found 1 test record(s):
    - ID 375529: #TEST-143052.mp3
  ✅ Deleted 1 database record(s)

CLEANUP SUMMARY:
  Audio files deleted: 1
  Database records deleted: 1
```

---

## 🎉 Success Indicators

After creating a test file, you should see in **app.py console**:
```
⚡ [INSTANT] Processing #TEST-143052.mp3
⚡ [INSTANT] ✓ Incident 375529 card created IMMEDIATELY
[Background] ✨ Thread started: background_0
[Background] ✓ Transcription complete for incident 375529
[Database] ✓ Updated incident 375529 transcript
```

In the **dashboard (browser)**:
1. New card appears instantly with "[Processing...]"
2. After 3-5 seconds, real transcript appears
3. Card shows all metadata (time, frequency, etc.)

---

## 💡 Pro Tips

1. **Create multiple test files** to test concurrent processing (ThreadPoolExecutor)
2. **Use test_executor.py option 3** to test orphaned database record handling
3. **Keep test audio files** during debugging to avoid re-transcription costs
4. **Run cleanup** before committing code to avoid test data in database
5. **Check dashboard monitoring logs** for real-time update broadcasts

---

## 📚 Related Documentation

- Progressive loading architecture: See `SPEED_OPTIMIZATION.md` (if exists)
- Main application: `app.py` (line 69-295)
- Dashboard monitoring: `scanner_dashboard.py` (line 915-990)
- Database schema: Run `python show_db_schema.py`
