import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import AudioMetadata
import api
import utils

base_dir = "C:/Proscan/Recordings"
Data = AudioMetadata()
seen_files = set()
seen_lock = threading.Lock()


def GetPathForRecordingsToday():
    today = datetime.now()
    formatted = f"{today.month:02d}-{today.day:02d}-{today.year % 100:02d}"
    return os.path.join(base_dir, formatted)


def GetAllFilesForToday():
    root_dir = GetPathForRecordingsToday()
    all_files = []

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(".mp3"):
                all_files.append(os.path.join(dirpath, filename))

    return all_files


def GetTimeCreated(filepath):
    return os.path.getctime(filepath)


def process_file(filepath):
    filename = os.path.basename(filepath)
    meta = Data.get_metadata(filename)

    if "Transcript" in meta:
        print(f"[Thread] Skipping {filename}, already transcribed.")
        return None

    print(f"[Thread] Transcribing {filename}")
    created_time = datetime.fromtimestamp(GetTimeCreated(filepath)).strftime("%H:%M:%S")
    transcript = api.getTranscript(filepath)
    system = utils.get_system(filename)
    department = utils.get_department(filename)
    channel = utils.get_channel(filename)

    return {
        "filename": filename,
        "time": created_time,
        "transcript": transcript,
        "system": system,
        "department": department,
        "channel": channel,
        "filepath": filepath,
    }


def wait_and_process(filepath):
    print(f"[Watcher] Waiting for {filepath} to finish...")
    utils.wait_until_file_complete(filepath)
    print(f"[Watcher] File done: {filepath}")

    result = process_file(filepath)
    if result:
        Data.add_metadata(
            result["filename"],
            result["time"],
            result["transcript"],
            result["system"],
            result["department"],
            result["channel"],
            result["filepath"],
        )


def startup():
    files = sorted(GetAllFilesForToday(), key=GetTimeCreated)

    if not files:
        print("No files found at startup.")
        return

    print(f"🔁 Startup mode: processing {len(files)} files...")
    utils.wait_until_file_complete(files[-1])

    results = []

    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    for item in sorted(results, key=lambda x: x["time"]):
        Data.add_metadata(
            item["filename"],
            item["time"],
            item["transcript"],
            item["system"],
            item["department"],
            item["channel"],
            item["filepath"],
        )

    with seen_lock:
        seen_files.update(files)


def monitor_new_files():
    print("📡 Monitoring for new files...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            all_files = GetAllFilesForToday()
            new_files = []

            with seen_lock:
                for file in all_files:
                    if file not in seen_files:
                        seen_files.add(file)
                        new_files.append(file)

            for file in new_files:
                executor.submit(wait_and_process, file)

            time.sleep(1)


def main():
    startup()
    monitor_new_files()


if __name__ == "__main__":
    main()
