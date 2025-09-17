import json
import os
from datetime import datetime
import utils


class AudioMetadata:
    def __init__(self):
        # self.directory = "Logs"
        self.directory = "C:\\Users\\alexa\\OneDrive\\Desktop\\Folders\\Scripts\\Python\\Local Police Scanner Analysis\\Logs"
        os.makedirs(self.directory, exist_ok=True)
        date_str = utils.getFilename()
        self.filepath = os.path.join(self.directory, f"{date_str}.json")
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    content = f.read().strip()
                    if content:  # Check if file has content
                        return json.loads(content)
                    else:
                        return {}  # Return empty dict for empty files
            except (json.JSONDecodeError, FileNotFoundError):
                print(
                    f"⚠️  Warning: Could not load {self.filepath}, starting with empty data"
                )
                return {}
        return {}

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def add_metadata(
        self,
        filename,
        time_string,
        transcript,
        system,
        department,
        channel,
        modulation,
        frequency,
        tgid,
        filepath,
        confidence=0.0,
        incident_type="unknown",
        address=None,
    ):
        # Check if transcript is empty, None, or just whitespace
        if not transcript or (isinstance(transcript, str) and not transcript.strip()):
            print(f"⚠️  Skipping {filename} - empty transcript, not adding to JSON")
            return

        self.data[filename] = {
            "Time": time_string,
            "Transcript": transcript,
            "Confidence": confidence,
            "Incident_Type": incident_type,
            "Address": address,
            "System": system,
            "Department": department,
            "Channel": channel,
            "Modulation": modulation,
            "Frequency": frequency,
            "TGID": tgid,
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
