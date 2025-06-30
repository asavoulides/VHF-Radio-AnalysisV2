from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import AudioMetadata
import api

Data = AudioMetadata()


def GetPathForRecordingsToday() -> str:
    today = datetime.now()
    formatted = f"{today.month:02d}-{today.day:02d}-{today.year % 100:02d}"
    return os.path.join("C:/ProScan/Recordings", formatted)


def GetAllFilesForToday() -> list[str]:
    root_dir = GetPathForRecordingsToday()
    all_files = []

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(".mp3"):
                all_files.append(os.path.join(dirpath, filename))

    return all_files


def GetTimeCreated(filepath: str) -> float:
    return os.path.getctime(filepath)


def process_file(filepath: str):
    filename = os.path.basename(filepath)
    meta = Data.get_metadata(filename)

    if "Transcript" in meta:
        print(f"[Thread] Skipping {filename}, already transcribed.")
        return None

    print(f"[Thread] Transcribing {filename}")
    created_time = datetime.fromtimestamp(GetTimeCreated(filepath)).strftime("%H:%M:%S")
    transcript = api.getTranscript(filepath)

    return {"filename": filename, "time": created_time, "transcript": transcript}


def main():
    files = sorted(GetAllFilesForToday(), key=GetTimeCreated)
    results = []

    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    for item in sorted(results, key=lambda x: x["time"]):
        Data.add_time(item["filename"], item["time"])
        Data.add_transcript(item["filename"], item["transcript"])


if __name__ == "__main__":
    main()
