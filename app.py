localTranscript = True

import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import AudioMetadata
import api
from datetime import datetime, timedelta
import utils

base_dir = "C:/Proscan/Recordings"
Data = AudioMetadata()
seen_files = set()
seen_lock = threading.Lock()
Data = None


def midnight_updater():
    global Data, seen_files

    while True:
        # Get current time
        now = datetime.now()
        # Calculate next midnight
        next_midnight = datetime.combine(now.date(), datetime.min.time()) + timedelta(
            days=1
        )
        # Sleep until exactly midnight
        sleep_seconds = (next_midnight - now).total_seconds()
        print(f"⏳ Sleeping until midnight update in {int(sleep_seconds)} seconds...")
        time.sleep(sleep_seconds)

        # It's now 00:00:00 — perform the update
        print("🕛 It's midnight! Updating metadata and clearing seen files.")
        Data = AudioMetadata()  # Reload metadata for new day
        with seen_lock:
            seen_files.clear()


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
    transcription_result = api.getTranscript(filepath)

    # Check if transcription failed
    if not transcription_result:
        print(f"[Thread] Skipping {filename} - transcription failed")
        return None

    # Extract transcript, confidence, incident type, and address from the result
    if isinstance(transcription_result, dict):
        transcript = transcription_result.get("transcript", "")
        confidence = transcription_result.get("confidence", 0.0)
        incident_type = transcription_result.get("incident_type", "unknown")
        address = transcription_result.get("address", None)
    else:
        # Backward compatibility if api returns just a string
        transcript = transcription_result
        confidence = 0.0
        incident_type = "unknown"
        address = None

    # Check if transcript is empty or just whitespace
    if not transcript or not transcript.strip():
        print(f"[Thread] Skipping {filename} - empty transcript")
        return None

    system = utils.get_system(filename)
    department = utils.get_department(filename)
    channel = utils.get_channel(filename)
    modulation = utils.get_modulation(filename)
    frequency = utils.get_frequency(filename)
    tgid = utils.get_tgid(filename)

    return {
        "filename": filename,
        "time": created_time,
        "transcript": transcript,
        "confidence": confidence,
        "incident_type": incident_type,
        "address": address,
        "system": system,
        "department": department,
        "channel": channel,
        "modulation": modulation,
        "frequency": frequency,
        "tgid": tgid,
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
            result["modulation"],
            result["frequency"],
            result["tgid"],
            result["filepath"],
            result.get("confidence", 0.0),
            result.get("incident_type", "unknown"),
            result.get("address", None),
        )
    else:
        print(f"[Watcher] No data to save for {filepath} - skipping JSON entry")


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
        # Double-check transcript is not empty before adding to metadata
        if item["transcript"] and item["transcript"].strip():
            Data.add_metadata(
                item["filename"],
                item["time"],
                item["transcript"],
                item["system"],
                item["department"],
                item["channel"],
                item["modulation"],
                item["frequency"],
                item["tgid"],
                item["filepath"],
                item.get("confidence", 0.0),
                item.get("incident_type", "unknown"),
                item.get("address", None),
            )
        else:
            print(f"[Startup] Skipping {item['filename']} - empty transcript")

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
    global Data
    Data = AudioMetadata()

    threading.Thread(target=midnight_updater, daemon=True).start()
    startup()
    monitor_new_files()


if __name__ == "__main__":
    main()
