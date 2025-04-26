from datetime import datetime
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import AudioMetadata
import api
from utils import getPrompt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

Data = AudioMetadata()


def GetPathForRecordingsToday():
    now = datetime.now()
    formatted_date = f"{now.month:02d}-{now.day:02d}-{now.year % 100:02d}"
    return f"C:/ProScan/Recordings/{formatted_date}/Middlesex/"


def GetAllFilesForToday():
    target_dir = GetPathForRecordingsToday()
    all_files = []
    for dirpath, dirnames, filenames in os.walk(target_dir):
        for filename in filenames:
            if filename.lower().endswith(".mp3"):
                full_path = os.path.join(dirpath, filename)
                all_files.append(full_path)
    return all_files


def GetTimeCreated(filepath):
    return os.path.getctime(filepath)  # Return raw timestamp for sorting


def process_file(filepath):
    filename = os.path.basename(filepath)

    existing_metadata = Data.get_metadata(filename)
    if "Transcript" in existing_metadata:
        print(f"[Thread] Skipping {filename}, already transcribed.")
        return None  # Skip if already processed

    print(f"[Thread] Transcribing {filename}")
    created_time = datetime.fromtimestamp(GetTimeCreated(filepath)).strftime("%H:%M:%S")
    transcript = api.getTranscript(filepath)

    return {"filename": filename, "time": created_time, "transcript": transcript}


def main():
    files = GetAllFilesForToday()

    # Sort files by creation time before processing
    files_sorted = sorted(files, key=GetTimeCreated)

    results = []

    max_threads = 10
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {executor.submit(process_file, f): f for f in files_sorted}

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    # Sort results again just in case (since threads complete out of order)
    results_sorted = sorted(results, key=lambda x: x["time"])

    # Save in chronological order
    for item in results_sorted:
        Data.add_time(item["filename"], item["time"])
        Data.add_transcript(item["filename"], item["transcript"])

    # api.LLM_REQ(prepareLLMReq())


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            main()


def monitor_directory(path):
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path, recursive=False)
    observer.start()
    print(f"Started monitoring: {path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("Stopped monitoring.")
    observer.join()




if __name__ == "__main__":
    main()
    monitor_directory(GetPathForRecordingsToday)
