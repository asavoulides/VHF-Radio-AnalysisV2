#!/usr/bin/env python3
"""
Police Scanner Data Processing Module (idempotent + NULL-safe)
"""
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AudioMetadata:
    """Handles audio metadata storage and retrieval"""

    def __init__(self):
        # Use environment variable for database path
        db_path = os.getenv("DB_PATH", "Logs/audio_metadata.db")
        self.directory = os.path.dirname(db_path) or "."
        os.makedirs(self.directory, exist_ok=True)
        self.db_path = db_path
        self._init_database()

    # ----------------------------- schema & indexes -----------------------------

    def _init_database(self):
        """Initialize the SQLite database and create tables if they don't exist,
        dedupe by filepath, then enforce a UNIQUE(filepath) index so UPSERT works.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create main table (if missing)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audio_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                time_recorded TEXT NOT NULL,
                transcript TEXT,
                confidence REAL DEFAULT 0.0,
                incident_type TEXT DEFAULT 'unknown',
                address TEXT,
                formatted_address TEXT,
                maps_link TEXT,
                system TEXT,
                department TEXT,
                channel TEXT,
                modulation TEXT,
                frequency TEXT,
                tgid TEXT,
                filepath TEXT,
                date_created TEXT NOT NULL,
                original_filename TEXT,
                latitude REAL,
                longitude REAL
            )
            """
        )

        # Backfill missing cols for older DBs (no-ops if present)
        for col, decl in [
            ("latitude", "REAL"),
            ("longitude", "REAL"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE audio_metadata ADD COLUMN {col} {decl}")
            except sqlite3.OperationalError:
                pass

        # Incidents table (unchanged)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE,
                time_recorded TEXT NOT NULL,
                address TEXT,
                formatted_address TEXT,
                incident_type TEXT,
                description TEXT,
                priority INTEGER,
                units_involved TEXT,
                latitude REAL,
                longitude REAL,
                audio_file_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (audio_file_id) REFERENCES audio_metadata (id)
            )
            """
        )

        # Helpful indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_time_recorded ON audio_metadata(time_recorded)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_formatted_address ON audio_metadata(formatted_address)"
        )
        # Incidents time index (guard both variants)
        cursor.execute("PRAGMA table_info(incidents)")
        incidents_columns = [row[1] for row in cursor.fetchall()]
        if "time_recorded" in incidents_columns:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_time_recorded ON incidents(time_recorded)"
            )
        elif "timestamp" in incidents_columns:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp)"
            )

        # --- Deduplicate existing rows by filepath (keep newest id) ---
        # If filepath is NULL in some old rows, ignore those in grouping.
        cursor.execute(
            """
            DELETE FROM audio_metadata
            WHERE filepath IS NOT NULL
              AND id NOT IN (
                    SELECT MAX(id) FROM audio_metadata
                    WHERE filepath IS NOT NULL
                    GROUP BY filepath
              )
              AND filepath IN (
                    SELECT filepath FROM audio_metadata
                    WHERE filepath IS NOT NULL
                    GROUP BY filepath
                    HAVING COUNT(*) > 1
              )
            """
        )

        # --- Enforce UNIQUE(filepath) for reliable UPSERTs ---
        # Note: this will fail if any remaining duplicates exist, but we just cleaned them.
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_audio_metadata_filepath ON audio_metadata(filepath)"
        )

        conn.commit()
        conn.close()

    # ------------------------------- utilities ---------------------------------

    def _extract_date_from_filepath(self, filepath):
        """Extract the recording date from the file path like '09-18-25' -> '9-18-2025'"""
        import re

        if not filepath:
            return None

        m = re.search(r"(\d{2})-(\d{2})-(\d{2})", filepath)
        if m:
            month, day, year = m.groups()
            full_year = f"20{year}"
            return f"{int(month)}-{int(day)}-{full_year}"
        return None

    # ------------------------------- read path ---------------------------------

    def get_metadata(self, filename, filepath):
        """Return latest row for this file+date and a boolean already_processed
       that is True if any row exists (even if transcript is NULL/empty)."""
        date_from_path = self._extract_date_from_filepath(filepath)
        if not date_from_path:
            today = datetime.now()
            date_from_path = f"{today.month}-{today.day}-{today.year}"
    
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT *
                FROM audio_metadata
                WHERE filepath = ?
                  AND date_created = ?
                ORDER BY time_recorded DESC
                LIMIT 1
                """,
                (filepath, date_from_path),
            )
            row = cursor.fetchone()
            if not row:
                return {"already_processed": False}
    
            data = dict(row)
            data["already_processed"] = True   # row exists ⇒ processed, regardless of transcript
            return data
        finally:
            conn.close()


    # --------------------------------- write -----------------------------------

    def add_metadata(
        self,
        filename,
        time_recorded,
        transcript,
        system,
        department,
        channel,
        modulation,
        frequency,
        tgid,
        filepath,
        confidence=0.0,
        incident_type="unknown",
        address=None,
        latitude=None,
        longitude=None,
        formatted_address=None,
        maps_link=None,
    ):
        """Insert once per filepath. If row exists, do nothing.
           A NULL/empty transcript still counts as 'processed'."""
        # Compute date first, before touching the DB
        date_created = self._extract_date_from_filepath(filepath)
        if not date_created:
            today = datetime.now()
            date_created = f"{today.month}-{today.day}-{today.year}"
    
        conn = None
        try:
            # Open connection first, then create cursor
            conn = sqlite3.connect(self.db_path, timeout=30)
            # Optional but helpful for concurrency with many threads:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
    
            cursor.execute(
                """
                INSERT INTO audio_metadata
                    (filename, time_recorded, transcript, confidence, incident_type,
                     address, formatted_address, maps_link, system, department, channel,
                     modulation, frequency, tgid, filepath, date_created, original_filename,
                     latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO NOTHING
                """,
                (
                    filename,
                    time_recorded,
                    transcript,                     # may be NULL/empty; still "processed"
                    float(confidence or 0.0),
                    incident_type or "unknown",
                    address,
                    formatted_address,
                    maps_link,
                    system,
                    department,
                    channel,
                    modulation,
                    frequency,
                    tgid,
                    filepath,
                    date_created,
                    filename,                       # original_filename
                    latitude,
                    longitude,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(f"[Database] Skipped insert (already exists): {filename}")
            else:
                print(f"[Database] Inserted metadata for {filename} on {date_created}")
        except sqlite3.Error as e:
            print(f"SQLite error in add_metadata for {filename}: {e}")
        finally:
            if conn is not None:
                conn.close()
    