from datetime import datetime
import os
import json
from data import AudioMetadata
import api

Data = AudioMetadata()


# Required for file structure used
def GetPathForRecordingsToday():
    now = datetime.now()
    formatted_date = f"{now.month:02d}-{now.day:02d}-{now.year % 100:02d}"
    return f"C:/ProScan/Recordings/{formatted_date}/Middlesex/"


def GetAllFilesForToday():
    target_dir = GetPathForRecordingsToday()
    all_files = []

    for dirpath, dirnames, filenames in os.walk(target_dir):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            all_files.append(full_path)

    return all_files


def GetTimeCreated(filepath):
    unixTime = os.path.getctime(filepath)
    dt = datetime.fromtimestamp(unixTime)
    return dt.strftime("%H:%M:%S")  # Format without microseconds


def main():
    files = GetAllFilesForToday()

    for filepath in files:
        if filepath.lower().endswith(".mp3"):
            # Use just the filename (not full path) as the key in the JSON
            filename = os.path.basename(filepath)

            # Get time and transcript
            created_time = GetTimeCreated(filepath)
            transcript = api.getTranscript(filepath)

            # Add to Data
            Data.add_time(filename, created_time)
            Data.add_transcript(filename, transcript)





main()
