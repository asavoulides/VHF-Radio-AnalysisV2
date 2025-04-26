from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor
from data import AudioMetadata
import api
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

Data = AudioMetadata()

MAX_THREADS = 5
executor = ThreadPoolExecutor(max_workers=MAX_THREADS)


def GetPathForRecordingsToday():
    now = datetime.now()
    formatted_date = f"{now.month:02d}-{now.day:02d}-{now.year % 100:02d}"
    return f"C:/ProScan/Recordings/{formatted_date}/Middlesex/"


def GetTimeCreated(filepath):
    return datetime.fromtimestamp(os.path.getctime(filepath)).strftime("%H:%M:%S")


def process_file(filepath):
    filename = os.path.basename(filepath)

    existing_metadata = Data.get_metadata(filename)
    if "Transcript" in existing_metadata:
        print(f"[Monitor] Skipping {filename}, already processed.")
        return

    print(f"[Monitor] Transcribing {filename}")

    # Retry logic for permission errors
    max_retries = 5
    retry_delay = 5 # seconds

    for attempt in range(max_retries):
        try:
            transcript = api.getTranscript(filepath)
            break  # Success, exit loop
        except PermissionError:
            print(
                f"[Monitor] Permission denied for {filename}. Retrying ({attempt + 1}/{max_retries})..."
            )
            time.sleep(retry_delay)
    else:
        # After retries fail
        print(f"[Monitor] Failed to access {filename} after {max_retries} attempts.")
        transcript = "Transcription failed: File access denied."

    created_time = GetTimeCreated(filepath)
    print(f"Transcript for {filename}: {transcript}")

    Data.add_time(filename, created_time)
    Data.add_transcript(filename, transcript)

    print(f"[Monitor] Finished processing {filename}")


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".mp3"):
            executor.submit(process_file, event.src_path)


def monitor_directory(path):
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path, recursive=False)
    observer.start()
    print(f"[Monitor] Watching directory: {path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("[Monitor] Stopped monitoring.")
    observer.join()


if __name__ == "__main__":
    monitor_directory(GetPathForRecordingsToday())
