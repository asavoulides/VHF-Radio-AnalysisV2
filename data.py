import json
import os
from datetime import datetime
import utils


class AudioMetadata:
    def __init__(self):
        self.directory = "Logs"
        os.makedirs(self.directory, exist_ok=True)
        date_str = utils.getFilename()
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

    def add_metadata(
        self, filename, time_string, transcript, system, department, channel, filepath
    ):
        self.data[filename] = {
            "Time": time_string,
            "Transcript": transcript,
            "System": system,
            "Department": department,
            "Channel": channel,
            "Filepath": filepath,
        }
        self._save()

    def get_metadata(self, filename):
        return self.data.get(filename, {})

    def get_all(self):
        return self.data

    def clear(self):
        self.data = {}
        self._save()
