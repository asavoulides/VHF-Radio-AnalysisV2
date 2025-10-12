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
import public_property_info


base_dir = r"C:\Proscan\Recordings"
Data = AudioMetadata()
seen_files = set()
seen_lock = threading.Lock()
background_executor = ThreadPoolExecutor(
    max_workers=20, thread_name_prefix="background"
)


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


def process_file_progressive(filepath):
    """
    Progressive loading: Create incident card instantly, process everything else in background
    """
    filename = os.path.basename(filepath)
    meta = Data.get_metadata(filename, filepath)
    if meta.get("already_processed"):
        print(f"[Thread] Skipping {filename}, already processed")
        return None

    system = utils.get_system(filename)
    if system != "Middlesex":
        print("[Thread] Skipping non-Middlesex file:", filename)
        return None
    

    print(f"Processing {filename} - ")
    created_time = datetime.fromtimestamp(GetTimeCreated(filepath)).strftime("%H:%M:%S")

    # Get basic metadata (INSTANT - no API calls)
    department = utils.get_department(filename)
    channel = utils.get_channel(filename)
    modulation = utils.get_modulation(filename)
    frequency = utils.get_frequency(filename)
    tgid = utils.get_tgid(filename)

    # ⚡ STEP 1: CREATE INCIDENT CARD IMMEDIATELY with minimal data
    # NO transcription, NO geocoding, NO LLM - just create the card!
    print(
        f"Creating incident card NOW for {filename} (before any processing)"
    )
    incident_id = Data.add_metadata(
        filename,
        created_time,
        "[Processing...]",  # Placeholder transcript
        system,
        department,
        channel,
        modulation,
        frequency,
        tgid,
        filepath,
        0.0,  # confidence - will be updated
        "unknown",  # incident_type - will be updated
        None,  # address - will be updated
        None,  # latitude - will be updated
        None,  # longitude - will be updated
        None,  # formatted_address - will be updated
        None,  # maps_link - will be updated
        None,  # streetview_url - will be updated
        None,  # property_owner - will be updated
        None,  # property_price - will be updated
    )

    print(
        f"✓ Incident {incident_id} card created IMMEDIATELY - visible in GUI NOW!"
    )

    # add_metadata already commits the transaction, no need to commit again

    # ⚡ STEP 2: Queue ALL processing (transcript, LLM, geocoding) to background
    # This includes transcription which can be slow
    try:
        print(
            f"About to submit background task for incident {incident_id}"
        )
        future = background_executor.submit(
            process_all_operations,
            incident_id,
            filename,
            filepath,
            created_time,
            system,
            department,
            channel,
            modulation,
            frequency,
            tgid,
        )
        print(f"✓ Background task submitted: {future}")
    except Exception as e:
        print(f"[ERROR] Failed to submit background task: {e}")
        import traceback

        traceback.print_exc()

    return incident_id


def process_all_operations(
    incident_id,
    filename,
    filepath,
    created_time,
    system,
    department,
    channel,
    modulation,
    frequency,
    tgid,
):
    """
    ⚡ Background worker: Process ALL operations (transcript, LLM, geocoding, property) and update database incrementally
    This runs AFTER the incident card is already visible in the GUI
    """
    import threading

    print(f"[Background] Thread started: {threading.current_thread().name}")
    print(f"[Background] Starting ALL operations for incident {incident_id}")

    try:

        # STEP 1: Get transcript (can be slow - API call to Deepgram)
        transcript = ""
        confidence = 0.0
        address = None

        try:
            print(f"[Background] Transcribing audio for incident {incident_id}...")
            transcription_result = api.getTranscript(filepath)

            if transcription_result:
                if isinstance(transcription_result, dict):
                    transcript = transcription_result.get("transcript", "")
                    confidence = transcription_result.get("confidence", 0.0)
                    address = transcription_result.get("address", None)
                else:
                    transcript = transcription_result

                print(
                    f"[Background] ✓ Transcription complete for incident {incident_id}"
                )
                # Update database immediately with transcript
                Data.update_transcript(incident_id, transcript, confidence, address)
            else:
                print(f"[Background] ✗ Transcription failed for incident {incident_id}")
                Data.update_transcript(incident_id, "[Transcription Failed]", 0.0, None)
        except Exception as trans_error:
            print(
                f"[Background] ✗ Transcription error for incident {incident_id}: {trans_error}"
            )
            Data.update_transcript(incident_id, "[Transcription Error]", 0.0, None)

        # STEP 2: Classify incident type (can be slow with LLM)
        incident_type = "unknown"
        if transcript and transcript.strip():
            try:
                print(f"[Background] Classifying incident {incident_id}...")
                incident_type = incident_helper.classify_incident(transcript)
                print(
                    f"[Background] ✓ Classified incident {incident_id} as: {incident_type}"
                )
                # Update immediately
                Data.update_incident_type(incident_id, incident_type)
            except Exception as e:
                print(f"[Background] ✗ Classification failed for {incident_id}: {e}")

        # STEP 3: Geocode address (slow - API call)
        latitude = None
        longitude = None
        formatted_address = None
        maps_link = None
        streetview_url = None

        if address and address.strip():
            try:
                print(
                    f"[Background] Geocoding address for incident {incident_id}: {address}"
                )
                result = location_services.geocode_newton(address)
                if result:
                    lat, lng, formatted_addr, url = result
                    latitude = lat
                    longitude = lng
                    formatted_address = formatted_addr or address
                    maps_link = url
                    print(
                        f"[Background] ✓ Geocoded incident {incident_id}: ({lat:.4f}, {lng:.4f})"
                    )

                    # Update immediately
                    Data.update_location_info(
                        incident_id, latitude, longitude, formatted_address, maps_link
                    )

                    # STEP 4: Generate Street View URL
                    try:
                        streetview_url = location_services.streetview_url(lat, lng)
                        print(
                            f"[Background] ✓ Generated Street View for incident {incident_id}"
                        )
                        Data.update_streetview(incident_id, streetview_url)
                    except Exception as sv_error:
                        print(
                            f"[Background] ✗ Street View failed for {incident_id}: {sv_error}"
                        )

                    # STEP 5: Property lookup (slow - GIS API call)
                    try:
                        print(
                            f"[Background] Looking up property for incident {incident_id}"
                        )
                        owner, price = public_property_info.identify_at_lonlat(lng, lat)
                        if owner or price:
                            print(
                                f"[Background] ✓ Property found for incident {incident_id}: {owner}, ${price:,}"
                                if price
                                else owner
                            )
                            Data.update_property_info(incident_id, owner, price)
                    except Exception as prop_error:
                        print(
                            f"[Background] ✗ Property lookup failed for {incident_id}: {prop_error}"
                        )
                else:
                    print(f"[Background] ✗ Geocoding failed for incident {incident_id}")
            except Exception as e:
                print(f"[Background] ✗ Geocoding error for incident {incident_id}: {e}")

        print(f"[Background] ✓ Completed ALL operations for incident {incident_id}")

    except Exception as e:
        print(f"[Background] ✗ Fatal error processing incident {incident_id}: {e}")
        import traceback

        traceback.print_exc()


def process_file(filepath):
    filename = os.path.basename(filepath)
    meta = Data.get_metadata(filename, filepath)
    if meta.get("already_processed"):
        print(f"[Thread] Skipping {filename}, already processed")
        return None
    system = utils.get_system(filename)
    
    if system != "Middlesex":
        print("[Thread] Skipping non-Middlesex file:", filename)
        return None
    
    print(f"[Thread] Transcribing {filename}")
    # print(f"[Debug] Full filepath: {filepath}")
    # print(f"[Debug] File exists: {os.path.exists(filepath)}")
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
    streetview_url = None
    property_owner = None
    property_price = None

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
                # Generate Street View URL
                try:
                    streetview_url = location_services.streetview_url(lat, lng)
                    print(f"[StreetView] ✓ Generated Street View URL")
                except Exception as sv_error:
                    print(
                        f"[StreetView] ✗ Error generating Street View URL: {sv_error}"
                    )
                print(f"[Geocoding] ✓ Found coordinates: ({lat:.4f}, {lng:.4f})")

                # Property lookup using Newton GIS
                try:
                    print(
                        f"[PropertyLookup] Getting property info for coordinates: ({lat:.4f}, {lng:.4f})"
                    )
                    owner, price = public_property_info.identify_at_lonlat(lng, lat)
                    if owner:
                        property_owner = owner
                        print(f"[PropertyLookup] ✓ Owner: {owner}")
                    if price:
                        property_price = price
                        print(f"[PropertyLookup] ✓ Assessed Value: ${price:,}")
                    if owner or price:
                        print(f"[PropertyLookup] ✓ Property info retrieved")
                    else:
                        print(f"[PropertyLookup] ✗ No property info found")
                except Exception as prop_error:
                    print(
                        f"[PropertyLookup] ✗ Error getting property info: {prop_error}"
                    )
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
        "streetview_url": streetview_url,
        "property_owner": property_owner,
        "property_price": property_price,
        "system": system,
        "department": department,
        "channel": channel,
        "modulation": modulation,
        "frequency": frequency,
        "tgid": tgid,
        "filepath": filepath,
    }


def wait_and_process(filepath):
    """Process new file with progressive loading"""
    print(f"[Watcher] Waiting for {filepath} to finish...")
    utils.wait_until_file_complete(filepath)
    print(f"[Watcher] File done: {filepath}")

    # Use progressive loading
    incident_id = process_file_progressive(filepath)

    if incident_id:
        print(
            f"[Watcher] ✓ Incident {incident_id} created and queued for background processing"
        )
    else:
        print(f"[Watcher] No incident created for {filepath} - skipping")


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
            item.get("streetview_url", None),
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
