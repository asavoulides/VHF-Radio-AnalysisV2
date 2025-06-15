# Project in Development

**Project Objective**
Project is intended to add new functionalities to ProScan, a software used to organize data coming out of UHF/VHF radios such as the Uniden SDS 200. 

*Intended Additions*
Transcription Model
Compacting Long Term Storage
AI Overview About Events,

Data Flow:

RadioWaves (selected using scanner) --> SDS200 "demodulates" signals --> Communication to Server --> Server Directs Traffic to Proscan --> Proscan Logs Transmissions into Directory as MP3 Files --> Data Harvasted from MP3 Files using Metadata/Reverse Engineering File-Name's --> MP3 Files sent to Transcription API using multithreading for efficiency --> Transcriptions logged onto JSON file.


