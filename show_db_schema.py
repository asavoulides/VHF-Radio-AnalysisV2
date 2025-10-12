#!/usr/bin/env python3
"""
Script to display all database table columns and schema information
"""

import sqlite3
from pathlib import Path


def show_database_schema():
    """Display all database tables and their column information"""

    # Connect to the database
    db_path = Path("Logs/audio_metadata.db")
    if not db_path.exists():
        print("❌ Database not found at", db_path)
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print("🗄️  DATABASE TABLES AND COLUMNS")
        print("=" * 60)

        for table_tuple in tables:
            table_name = table_tuple[0]
            print(f"\n📋 Table: {table_name}")
            print("-" * 40)

            # Get column information for this table
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            print("Column Info: (ID, Name, Type, NotNull, Default, PrimaryKey)")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                pk_marker = " [PK]" if is_pk else ""
                null_marker = " [NOT NULL]" if not_null else ""
                default_marker = f" [DEFAULT: {default_val}]" if default_val else ""
                print(
                    f"  {col_id}: {col_name} ({col_type}){pk_marker}{null_marker}{default_marker}"
                )

        # Get sample record count
        cursor.execute("SELECT COUNT(*) FROM audio_metadata")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total Records: {count:,}")

        # Show some sample data structure
        print(f"\n🔍 Sample Record Structure (Latest Entry):")
        print("-" * 40)
        cursor.execute("SELECT * FROM audio_metadata ORDER BY id DESC LIMIT 1")
        sample = cursor.fetchone()

        if sample:
            # Get column names
            cursor.execute("PRAGMA table_info(audio_metadata)")
            col_info = cursor.fetchall()
            col_names = [col[1] for col in col_info]

            for i, value in enumerate(sample):
                if i < len(col_names):
                    col_name = col_names[i]
                    display_value = (
                        str(value)[:50] + "..."
                        if value and len(str(value)) > 50
                        else value
                    )
                    print(f"  {col_name}: {display_value}")

        conn.close()
        print("\n✅ Database schema displayed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error reading database: {e}")
        conn.close()
        return False


if __name__ == "__main__":
    show_database_schema()
