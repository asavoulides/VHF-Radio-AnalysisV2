from datetime import datetime
import os
import json
from data import AudioMetadata
import api

metaData = AudioMetadata()

# Required for file structure used
def GetPathForRecordingsToday():
    now = datetime.now()
    formatted_date = f"{now.month}-{now.day}-{now.year % 100}"
    return f"C:/ProScan/Recordings/{formatted_date}/Middlesex/04-13-25 00-08-11 - Middlesex - Police Department.mp3"


def GetTimeCreated(filepath):
    unixTime = os.path.getctime(filepath)
    dt = datetime.fromtimestamp(unixTime)
    return dt.strftime("%H:%M:%S")  # Format without microseconds


def main():
    metaData.clear()
    print(api.getTranscript(GetPathForRecordingsToday()))



main()