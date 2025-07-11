import os
from datetime import datetime
import time
from pydub import AudioSegment


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


def is_file_locked(path):
    try:
        with open(path, "a+b") as f:
            f.seek(0, os.SEEK_END)
            original_size = f.tell()

            # Temporarily append a byte and immediately undo it
            f.write(b"_")
            f.flush()
            f.truncate(original_size)
        return False
    except Exception:
        return True


def wait_until_file_complete(path):

    while is_file_locked(path):
        print(f"{path} is locked... waiting")
        time.sleep(1)

    print("✅ File is unlocked and ready.")


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


def prependTime(path):
    audio = AudioSegment.from_file(path)
    silence = AudioSegment.silent(duration=500)  # 1 second
    combined = silence + audio
    combined.export(path, format=path.split(".")[-1])


def getPrompt(text):
    pass
