#!/usr/bin/env python3
"""
Police Scanner Data Processing Module
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
        self.directory = os.path.dirname(db_path)
        os.makedirs(self.directory, exist_ok=True)
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database and create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if table exists and has correct schema
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audio_metadata'"
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Create main metadata table with correct schema
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
        else:
            # Add missing columns if they don't exist
            try:
                cursor.execute("ALTER TABLE audio_metadata ADD COLUMN latitude REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE audio_metadata ADD COLUMN longitude REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create incidents table for processed incidents (optional)
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

        # Create index for faster queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_time_recorded ON audio_metadata(time_recorded)"
        )

        # Check if incidents table has time_recorded or timestamp column
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

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_formatted_address ON audio_metadata(formatted_address)"
        )

        conn.commit()
        conn.close()

    def get_metadata(self, filename):
        """Get metadata for a specific filename - only for today's date"""
        from datetime import datetime

        # Get today's date in the same format as the database
        today = datetime.now()
        today_str = f"{today.month}-{today.day}-{today.year}"

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM audio_metadata 
                WHERE filename = ? AND date_created = ?
                ORDER BY time_recorded DESC
                LIMIT 1
            """,
                (filename, today_str),
            )

            result = cursor.fetchone()
            if result:
                data = dict(result)
                # Convert transcript to "Transcript" key for backward compatibility
                if data.get("transcript"):
                    data["Transcript"] = data["transcript"]
                return data
            else:
                return {}  # Return empty dict if not found
        finally:
            conn.close()

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
        """Add metadata for an audio file with optional coordinates"""
        from datetime import datetime

        # Get today's date in the same format as the database: M-D-YYYY
        today = datetime.now()
        date_created = f"{today.month}-{today.day}-{today.year}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO audio_metadata 
                (filename, time_recorded, transcript, confidence, incident_type, 
                 address, formatted_address, maps_link, system, department, channel, modulation, frequency, 
                 tgid, filepath, date_created, original_filename, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    filename,
                    time_recorded,
                    transcript,
                    confidence,
                    incident_type,
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
                    filename,  # Use filename as original_filename
                    latitude,
                    longitude,
                ),
            )

            conn.commit()
            print(f"[Database] Added metadata for {filename} on {date_created}")

        except Exception as e:
            print(f"Error adding metadata for {filename}: {e}")
        finally:
            conn.close()
