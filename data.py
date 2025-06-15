import json
import os
from datetime import datetime


class AudioMetadata:
    def __init__(self):
        # Ensure "archives" directory exists
        self.directory = "Logs"
        os.makedirs(self.directory, exist_ok=True)

        # Generate filename based on current date (day,month,year)
        today = datetime.now()
        date_str = f"{today.month}-{today.day}-{today.year}"

        self.filepath = os.path.join(self.directory, f"{date_str}.json")

        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def add_transcript(self, filename, transcript):
        if filename not in self.data:
            self.data[filename] = {}
        self.data[filename]["Transcript"] = transcript
        self._save()

    def add_time(self, filename, time_string):
        if filename not in self.data:
            self.data[filename] = {}
        self.data[filename]["Time"] = time_string
        self._save()

    def get_metadata(self, filename):
        return self.data.get(filename, {})

    def get_all(self):
        return self.data

    def clear(self):
        """Clear all existing metadata and overwrite the JSON file."""
        self.data = {}
        self._save()
