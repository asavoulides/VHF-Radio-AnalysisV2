import os
from datetime import datetime
import time

def get_most_recent_file(root_dir: str, extension: str = ".mp3") -> str | None:
    newest_file = None
    newest_mtime = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for file in filenames:
            path = os.path.join(dirpath, file)
            try:
                mtime = os.path.getmtime(path)
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_file = path
            except FileNotFoundError:
                continue

    return newest_file


def wait_until_file_complete(path):
    print(f"Checking for file: {path}")

    if not os.path.exists(path):
        print("File not found. Waiting...")
        while not os.path.exists(path):
            time.sleep(0.5)
        print("File showed up.")

    print("Watching file size...")
    last_size = os.path.getsize(path)
    print(f"Starting size: {last_size} bytes")
    last_change = time.time()

    while True:
        time.sleep(1)
        try:
            current_size = os.path.getsize(path)
        except FileNotFoundError:
            print("File disappeared. Waiting again...")
            continue

        if current_size == last_size:
            stable_for = time.time() - last_change
            print(f"No change. Stable for {stable_for:.1f} seconds.")
            if stable_for > 3:
                print("File is done.")
                return
        else:
            print(f"Size changed: {last_size} -> {current_size}")
            last_size = current_size
            last_change = time.time()


def wait_for_new_file(directory):
    seen = set()
    for root, _, files in os.walk(directory):
        for f in files:
            seen.add(os.path.join(root, f))

    while True:
        time.sleep(1)
        for root, _, files in os.walk(directory):
            for f in files:
                path = os.path.join(root, f)
                if path not in seen:
                    return path

def getFilename():
    today = datetime.now()
    date_str = f"{today.month}-{today.day}-{today.year}"
    return date_str



def _split_parts(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    return [part.strip() for part in base.split(";")]


def get_system(filename):
    parts = _split_parts(filename)
    if len(parts) >= 1:
        return parts[0]
    return ""


def get_department(filename):
    parts = _split_parts(filename)
    if len(parts) >= 2:
        return parts[1]
    return ""


def get_channel(filename):
    parts = _split_parts(filename)
    if len(parts) >= 3:
        return parts[2]
    return ""


def getPrompt(text):
    pass
