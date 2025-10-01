import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import AudioMetadata
import api
from datetime import datetime, timedelta
import utils
import location_services
import incident_helper


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
    meta = Data.get_metadata(filename, filepath)
    if meta.get("already_processed"):
        print(
            f"[Thread] Skipping {filename}, already processed"
        )
        return None
    system = utils.get_system(filename)
    if system != "Middlesex":
        print("[Thread] Skipping non-Middlesex file:", filename)
        return None
    print(f"[Thread] Transcribing {filename}")
    created_time = datetime.fromtimestamp(GetTimeCreated(filepath)).strftime("%H:%M:%S")
    transcription_result = api.getTranscript(filepath)

    # Handle transcription result
    if not transcription_result:
        print(
            f"[Thread] Transcription failed for {filename}, proceeding with empty transcript."
        )
        transcript = ""
        confidence = 0.0
        incident_type = "unknown"
        address = None
    elif isinstance(transcription_result, dict):
        transcript = transcription_result.get("transcript", "")
        confidence = transcription_result.get("confidence", 0.0)
        incident_type = incident_helper.classify_incident(transcript)
        address = transcription_result.get("address", None)
    else:
        transcript = transcription_result
        confidence = 0.0
        incident_type = "unknown"
        address = None

    system = utils.get_system(filename)
    department = utils.get_department(filename)
    channel = utils.get_channel(filename)
    modulation = utils.get_modulation(filename)
    frequency = utils.get_frequency(filename)
    tgid = utils.get_tgid(filename)

    latitude = None
    longitude = None
    formatted_address = None
    maps_link = None

    if address and address.strip():
        try:
            print(f"[Geocoding] Looking up coordinates for: {address}")
            result = location_services.geocode_newton(address)
            if result:
                lat, lng, formatted_addr, url = result
                latitude = lat
                longitude = lng
                formatted_address = formatted_addr or address
                print(formatted_address)
                maps_link = url
                print(f"[Geocoding] ✓ Found coordinates: ({lat:.4f}, {lng:.4f})")
            else:
                print(f"[Geocoding] ✗ No coordinates found for: {address}")
        except Exception as e:
            print(f"[Geocoding] Error geocoding {address}: {e}")

    return {
        "filename": filename,
        "time": created_time,
        "transcript": transcript,
        "confidence": confidence,
        "incident_type": incident_type,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "formatted_address": formatted_address,
        "maps_link": maps_link,
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
            result.get("latitude", None),
            result.get("longitude", None),
            result.get("formatted_address", None),
            result.get("maps_link", None),
        )
        if not result["transcript"] or not result["transcript"].strip():
            print(f"[Watcher] Added {result['filename']} with empty transcript")
        else:
            print(f"[Thread] Confirmed {result['filename']} marked as processed in DB.")
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
        # Always add metadata entry, even if transcript is empty
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
            item.get("latitude", None),
            item.get("longitude", None),
            item.get("formatted_address", None),
            item.get("maps_link", None),
        )
        if not item["transcript"] or not str(item["transcript"]).strip():
            print(f"[Startup] Added {item['filename']} with empty transcript")

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
