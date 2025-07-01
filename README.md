# 📻 ProScan Radio Transcript Processor

A high-performance Python tool for transcribing and tagging real-time police and fire scanner audio recordings from ProScan. This project continuously monitors ProScan’s output directory, transcribes new `.mp3` files using an external API, and organizes the results with detailed metadata including system, department, and channel.

---

##  Features

- **Real-Time Monitoring**: Detects and transcribes new `.mp3` scanner recordings as they appear  
- **Automated Transcription**: Uses `api.getTranscript()` to convert speech to text  
- **Metadata Enrichment**: Classifies each recording by:  
  - System  
  - Department  
  - Channel  
- **Transcript Tracking**: Avoids reprocessing already-transcribed files  
- **Multithreaded Processing**: Fast startup with up to 40 transcription threads  
- **Thread-Safe File Handling**: Locks and watches files to avoid premature processing  
- **Modular Codebase**: Easily extendable for UI, database, or analytics integration  

---

##  Folder Structure

```
C:/Proscan/Recordings/
├── 07-01-25/
│   ├── Boston_PD_Ch1_01-06-30.mp3
│   ├── FireDept_Engine3_01-07-45.mp3
│   └── ...
```

ProScan stores recordings in folders by date. This script processes only today’s folder based on your system time.

---

##  How It Works

### 1. Startup Phase

- Scans today’s folder for all `.mp3` files  
- Waits for the latest file to finish writing  
- Transcribes each file concurrently using up to 40 threads  
- Tags and saves metadata (filename, timestamp, transcript, system, department, channel)  

### 2. Monitoring Phase

- Every second, checks for new files not yet seen  
- Waits for each to unlock before processing  
- Transcribes and saves metadata in real time  

---

##  Sample Output

```json
"Massachusetts State Police; Troop H- Boston (Local); Tunnel Dispatch - H9; #28.mp3": {
  "Time": "02:01:13",
  "Transcript": "",
  "System": "Massachusetts State Police",
  "Department": "Troop H- Boston (Local)",
  "Channel": "Tunnel Dispatch - H9",
  "Filepath": "C:/Proscan/Recordings\\07-01-25\\Massachusetts State Police\\Massachusetts State Police; Troop H- Boston (Local); Tunnel Dispatch - H9; #28.mp3"
```

---

##  File Overview

- `app.py`: Main runner that handles scanning, threading, and transcription  
- `data.py`: Contains `AudioMetadata`, a class for managing transcript metadata  
- `api.py`: Defines `getTranscript(path)` — your transcription backend (e.g., Deepgram, Whisper, etc.)  
- `utils.py`: Contains helpers like:
  - `wait_until_file_complete(path)`
  - `get_system(filename)`
  - `get_department(filename)`
  - `get_channel(filename)`

---

##  Requirements

To run this project, ensure you have:

- Python 3.9+
- Custom or external transcription API
- A working ProScan setup with recordings saved to `C:/Proscan/Recordings`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

##  Usage

1. Clone the repository:

```bash
git clone https://github.com/your-username/proscan-transcriber
cd proscan-transcriber
```

2. Run the main script:

```bash
python app.py
```

>  Make sure ProScan is running and actively recording.

---

##  Ideal Use Cases

- Live dashboard for police/fire activity  
- Searchable transcript archive  
- Real-time public safety event detection  
- Transparent dispatch monitoring for journalism or policy  

---
