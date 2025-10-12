#!/usr/bin/env python3
"""
ChatGPT Prompter - Formats today's police scanner transcripts for ChatGPT analysis
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


Prompt = """Below is an automated transcript of PD/FD Radio. Keeping in mind potential errors in the transcription process, give me a summary of the events that have occurred ordered from most to least severe. Do NOT use python or any unique way of displaying such data, instead use normal"""


def get_todays_transcripts():
    """
    Retrieves all transcripts for the current day from the database,
    formatted for ChatGPT with department labels.

    Returns:
        str: Formatted string with all transcripts, each prefixed by department

    Example output:
        Police Department
        "495 responding code 3"

        Fire Department
        "Engine 1 on scene"
    """
    # Get database path
    db_path = os.getenv("DB_PATH", "Logs/audio_metadata.db")

    if not os.path.exists(db_path):
        return f"❌ Database not found at {db_path}"

    # Get today's date in the format used by the database (M-D-YYYY)
    today = datetime.now()
    today_str = f"{today.month}-{today.day}-{today.year}"

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Query all records for today with department and transcript
        # Order by time to maintain chronological order
        cursor.execute(
            """
            SELECT department, transcript, time_recorded
            FROM audio_metadata
            WHERE date_created = ?
            AND transcript IS NOT NULL
            AND transcript != ''
            ORDER BY time_recorded ASC
        """,
            (today_str,),
        )

        records = cursor.fetchall()

        if not records:
            return f"No transcripts found for today ({today_str})"

        # Format the output
        output_lines = []
        output_lines.append(
            f"=== Police Scanner Transcripts for {today.strftime('%B %d, %Y')} ===\n"
        )
        output_lines.append(f"Total transcripts: {len(records)}\n")
        output_lines.append("=" * 60 + "\n")

        for department, transcript, time_recorded in records:
            # Use department name or default to "Unknown Department"
            dept_name = department if department else "Unknown Department"

            # Format each entry
            output_lines.append(f"{dept_name}")
            output_lines.append(f'"{transcript}"\n')

        result = "\n".join(output_lines)

        conn.close()
        return result

    except Exception as e:
        conn.close()
        return f"❌ Error retrieving transcripts: {e}"


def get_todays_transcripts_by_department():
    """
    Retrieves today's transcripts grouped by department.

    Returns:
        dict: Dictionary with departments as keys and lists of transcripts as values
    """
    # Get database path
    db_path = os.getenv("DB_PATH", "Logs/audio_metadata.db")

    if not os.path.exists(db_path):
        return {"error": f"Database not found at {db_path}"}

    # Get today's date
    today = datetime.now()
    today_str = f"{today.month}-{today.day}-{today.year}"

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT department, transcript, time_recorded
            FROM audio_metadata
            WHERE date_created = ?
            AND transcript IS NOT NULL
            AND transcript != ''
            ORDER BY department, time_recorded ASC
        """,
            (today_str,),
        )

        records = cursor.fetchall()

        # Group by department
        by_department = {}
        for department, transcript, time_recorded in records:
            dept_name = department if department else "Unknown Department"

            if dept_name not in by_department:
                by_department[dept_name] = []

            by_department[dept_name].append(
                {"time": time_recorded, "transcript": transcript}
            )

        conn.close()
        return by_department

    except Exception as e:
        conn.close()
        return {"error": str(e)}


def save_todays_transcripts_to_file(filename=None):
    """
    Saves today's transcripts to a text file.

    Args:
        filename (str, optional): Output filename. If None, auto-generates based on date.

    Returns:
        str: Path to the saved file or error message
    """
    if filename is None:
        today = datetime.now()
        filename = f"transcripts_{today.strftime('%Y-%m-%d')}.txt"

    # Get the formatted transcripts
    content = get_todays_transcripts()

    # Save to file
    try:
        output_path = Path(filename)
        output_path.write_text(content, encoding="utf-8")
        return f"✅ Transcripts saved to: {output_path.absolute()}"
    except Exception as e:
        return f"❌ Error saving file: {e}"


def print_todays_transcripts():
    """
    Prints today's transcripts to console.
    Useful for quick viewing or piping to clipboard.
    """
    print(get_todays_transcripts())


# -- Public API --


def get_gpt_prompt_link():
    """
    Returns a link to the ChatGPT prompt with today's transcripts.
    Uses a global variable 'prompt' to store the generated text.
    """
    global prompt
    transcripts = get_todays_transcripts()

    if transcripts.startswith("❌"):
        return transcripts  # Return error message immediately

    import urllib.parse

    encoded_prompt = urllib.parse.quote(prompt)

    # Return URL with encoded global prompt
    return f"https://chat.openai.com/?q={encoded_prompt}"


def open_gpt_prompt_in_browser():
    """
    Opens the ChatGPT prompt link in the default web browser.
    This will automatically launch a browser window with today's transcripts
    pre-loaded in the ChatGPT interface.

    Returns:
        str: Success or error message
    """
    import webbrowser

    # Get the prompt link
    link = get_gpt_prompt_link()

    # Check if there was an error
    if link.startswith("❌"):
        print(link)
        return link

    # Open the link in the default browser
    try:
        print(f"🌐 Opening ChatGPT with today's transcripts in your browser...")
        webbrowser.open(link)
        print(f"✅ Browser opened successfully!")
        return "✅ Browser opened successfully!"
    except Exception as e:
        error_msg = f"❌ Error opening browser: {e}"
        print(error_msg)
        return error_msg


if __name__ == "__main__":
    # When run directly, open the prompt in browser
    print_todays_transcripts()
