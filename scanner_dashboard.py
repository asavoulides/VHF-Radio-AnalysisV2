#!/usr/bin/env python3
"""
Police Scanner Web Dashboard - FIXED EDITION

A lightweight web interface for monitoring police scanner transcriptions.
COMPREHENSIVE FIXES for websocket connectivity and real-time updates.
"""

import sqlite3
import threading
import time
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    send_file,
    redirect,
    url_for,
)
from flask_socketio import SocketIO, emit
import utils
from incident_helper import LABELS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Thread-safe database lock
db_lock = threading.Lock()

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "scanner_dashboard_secret_2025"
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=20,  # Reduced from 60 - faster detection of dead connections
    ping_interval=10,  # Reduced from 25 - more frequent keepalives
    max_http_buffer_size=10**6,  # 1MB buffer limit
    async_mode="threading",  # Explicit threading mode
    logger=False,
    engineio_logger=False,
)

# Global variables for monitoring
monitoring_thread = None
monitoring_active = False
connected_clients = set()
last_modified_time = None


class PoliceScannerDashboard:
    """Simple Police Scanner Web Dashboard with Thread Safety"""

    def __init__(self):
        # Use environment variable for database path (main database, not backup)
        db_path = os.getenv("DB_PATH", "Logs/audio_metadata.db")
        self.db_path = Path(db_path)
        self.current_date = utils.getFilename().replace("_", "")

    def get_connection(self):
        """Get thread-safe database connection with row factory"""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-threading
            timeout=30.0,  # 30-second timeout for locks
        )
        conn.row_factory = sqlite3.Row
        return conn

    def get_database_modification_time(self):
        """Get the last modification time of the database file"""
        try:
            if self.db_path.exists():
                return self.db_path.stat().st_mtime
            return None
        except Exception as e:
            print(f"Error getting database modification time: {e}")
            return None

    def get_latest_record_info(self):
        """Get the latest record ID and timestamp for change detection"""
        with db_lock:  # Thread-safe database access
            conn = self.get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    SELECT MAX(id) as max_id, 
                           MAX(date_created || ' ' || time_recorded) as latest_time,
                           COUNT(*) as total_count
                    FROM audio_metadata 
                    WHERE date_created = ?
                """,
                    (self.current_date,),
                )

                result = cursor.fetchone()

                if result:
                    return {
                        "max_id": result[0] or 0,
                        "latest_time": result[1] or "",
                        "total_count": result[2] or 0,
                    }
                return {"max_id": 0, "latest_time": "", "total_count": 0}
            except Exception as e:
                print(f"Error getting latest record info: {e}")
                return {"max_id": 0, "latest_time": "", "total_count": 0}
            finally:
                conn.close()

    def get_basic_stats(self):
        """Get basic statistics for today's data"""
        with db_lock:  # Thread-safe database access
            conn = self.get_connection()
            cursor = conn.cursor()
            today = self.current_date

            try:
                # Total incidents today
                cursor.execute(
                    "SELECT COUNT(*) as total_today FROM audio_metadata WHERE date_created = ?",
                    (today,),
                )
                total_today = cursor.fetchone()[0]

                # Recent activity (last 2 hours)
                cursor.execute(
                    """
                    SELECT COUNT(*) as recent_activity 
                    FROM audio_metadata 
                    WHERE date_created = ? 
                    AND time_recorded >= strftime('%H:%M:%S', 'now', '-2 hours')
                    """,
                    (today,),
                )
                recent_activity = cursor.fetchone()[0]

                # High priority incidents (life-threatening and urgent public safety)
                cursor.execute(
                    """
                    SELECT COUNT(*) as high_priority_count
                    FROM audio_metadata 
                    WHERE date_created = ? 
                    AND (
                        incident_type IN (
                            'Medical',
                            'Structure Fire', 
                            'Brush/Vehicle Fire',
                            'Fire Alarm',
                            'Weapons/Shots Fired',
                            'Assault/Domestic',
                            'Motor Vehicle Accident',
                            'Gas/Electrical Hazard',
                            'Hazmat',
                            'Missing Person',
                            'Alarm (Burglar/Panic)'
                        )
                        OR incident_type LIKE '%emergency%'
                        OR incident_type LIKE '%Emergency%'
                    )
                    """,
                    (today,),
                )
                high_priority_count = cursor.fetchone()[0]

                # Calculate high priority percentage
                high_priority_percentage = 0
                if total_today > 0:
                    high_priority_percentage = round(
                        (high_priority_count / total_today) * 100
                    )

                # Active locations (unique addresses with incidents today)
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT formatted_address) as unique_locations
                    FROM audio_metadata 
                    WHERE date_created = ? 
                    AND formatted_address IS NOT NULL 
                    AND formatted_address != '' 
                    AND formatted_address != 'Unknown'
                    """,
                    (today,),
                )
                unique_locations = cursor.fetchone()[0]

                return {
                    "total_today": total_today,
                    "recent_activity": recent_activity,
                    "high_priority_percentage": high_priority_percentage,
                    "unique_locations": unique_locations,
                }
            except Exception as e:
                print(f"Error getting stats: {e}")
                return {
                    "total_today": 0,
                    "recent_activity": 0,
                    "high_priority_percentage": 0,
                    "unique_locations": 0,
                }
            finally:
                conn.close()

    def get_incidents(self):
        """Get today's incidents, excluding those with empty transcripts"""
        with db_lock:  # Thread-safe database access
            conn = self.get_connection()
            cursor = conn.cursor()
            today = self.current_date

            try:
                cursor.execute(
                    """
                    SELECT id, transcript, address, formatted_address, 
                           incident_type, system, department, channel,
                           time_recorded, filepath, original_filename, filename,
                           date_created, latitude, longitude,
                           confidence, frequency, modulation, tgid, maps_link, streetview_url
                    FROM audio_metadata 
                    WHERE date_created = ? AND transcript IS NOT NULL AND transcript != ''
                    ORDER BY time_recorded DESC, id DESC
                """,
                    (today,),
                )

                incidents = []
                for row in cursor.fetchall():
                    incident = dict(row)

                    # Handle transcript content
                    transcript = incident.get("transcript", "")
                    if not transcript or transcript in ["", "[EMPTY_TRANSCRIPT]"]:
                        incident["content"] = "[No audio content detected]"
                    elif transcript.startswith("[PLACEHOLDER]"):
                        incident["content"] = "[Processing audio...]"
                    else:
                        incident["content"] = transcript

                    # Handle confidence value (ensure it's properly formatted)
                    confidence = incident.get("confidence", 0.0)
                    try:
                        incident["confidence"] = (
                            float(confidence) if confidence is not None else 0.0
                        )
                    except (ValueError, TypeError):
                        incident["confidence"] = 0.0

                    # Handle frequency value (ensure it's properly formatted)
                    frequency = incident.get("frequency", "")
                    if frequency and frequency != "":
                        try:
                            freq_val = float(frequency)
                            incident["frequency"] = f"{freq_val:.4f} MHz"
                        except (ValueError, TypeError):
                            incident["frequency"] = (
                                str(frequency) if frequency else "Unknown"
                            )
                    else:
                        incident["frequency"] = "Unknown"

                    # Handle audio filename
                    audio_filename = (
                        incident.get("filename")
                        or incident.get("original_filename")
                        or f"incident_{incident['id']}.mp3"
                    )

                    if audio_filename and incident.get("filepath"):
                        incident["audio_filename"] = quote(audio_filename)
                        incident["has_audio"] = True
                    else:
                        incident["audio_filename"] = f"incident_{incident['id']}.mp3"
                        incident["has_audio"] = False

                    # Handle coordinates
                    try:
                        if incident.get("latitude") and incident.get("longitude"):
                            incident["latitude"] = float(incident["latitude"])
                            incident["longitude"] = float(incident["longitude"])
                        else:
                            incident["latitude"] = None
                            incident["longitude"] = None
                    except (ValueError, TypeError):
                        incident["latitude"] = None
                        incident["longitude"] = None

                    incidents.append(incident)

                return incidents
            except Exception as e:
                print(f"Error getting incidents: {e}")
                return []
            finally:
                conn.close()


# Initialize dashboard
dashboard = PoliceScannerDashboard()


# ===== ROUTES =====


@app.route("/")
def index():
    """Redirect root to live dashboard"""
    return redirect(url_for("live_updates"))


@app.route("/live")
def live_updates():
    """Live updates page"""
    return render_template("index.html", current_date=dashboard.current_date)


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    """Serve audio files for playback"""
    try:
        decoded_filename = unquote(filename)
        incident_id = request.args.get("incident_id")

        # Get filepath from database
        with db_lock:
            conn = dashboard.get_connection()
            cursor = conn.cursor()

            # If incident_id is provided, find the EXACT record (CRITICAL FIX)
            if incident_id:
                cursor.execute(
                    "SELECT filepath FROM audio_metadata WHERE id = ? AND filepath IS NOT NULL AND LENGTH(filepath) > 0",
                    (incident_id,),
                )
                result = cursor.fetchone()
                print(f"🎵 Audio request by ID {incident_id}: {decoded_filename}")
            else:
                # Fallback: search by filename (but this can find wrong files!)
                cursor.execute(
                    "SELECT filepath FROM audio_metadata WHERE filename = ? AND filepath IS NOT NULL AND LENGTH(filepath) > 0 ORDER BY id DESC LIMIT 1",
                    (decoded_filename,),
                )
                result = cursor.fetchone()

                # If not found, try original_filename
                if not result:
                    cursor.execute(
                        "SELECT filepath FROM audio_metadata WHERE original_filename = ? AND filepath IS NOT NULL AND LENGTH(filepath) > 0 ORDER BY id DESC LIMIT 1",
                        (decoded_filename,),
                    )
                    result = cursor.fetchone()
                print(f"🎵 Audio request by filename: {decoded_filename}")

            conn.close()

        if result and result[0]:
            filepath = Path(result[0])
            print(f"🎵 Serving: {filepath}")

            if filepath.exists():
                return send_file(
                    str(filepath), mimetype="audio/mpeg", as_attachment=False
                )
            else:
                print(f"❌ Audio file not found at path: {filepath}")
                return jsonify({"error": f"Audio file not found at {filepath}"}), 404
        else:
            print(f"❌ No database record found for audio: {decoded_filename}")
            return jsonify({"error": "Audio file not in database"}), 404

    except Exception as e:
        print(f"❌ Audio serve error: {e}")
        return jsonify({"error": "Audio serve error"}), 500
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident_types")
def api_incident_types():
    """Get incident type breakdown and available filter options"""
    try:
        with db_lock:
            conn = dashboard.get_connection()
            cursor = conn.cursor()
            today = dashboard.current_date

            # Get count of each non-unknown incident type for today
            cursor.execute(
                """
                SELECT incident_type, COUNT(*) as count
                FROM audio_metadata 
                WHERE date_created = ? 
                AND incident_type IS NOT NULL 
                AND incident_type != 'unknown'
                AND incident_type != ''
                GROUP BY incident_type
                ORDER BY count DESC
            """,
                (today,),
            )

            incident_types = []
            for row in cursor.fetchall():
                incident_type = row[0]
                count = row[1]
                # Only include types that are in our canonical LABELS list
                if incident_type in LABELS:
                    incident_types.append(
                        {
                            "type": incident_type,
                            "count": count,
                            "formatted": incident_type.replace("/", " / "),
                        }
                    )

            conn.close()

            return jsonify(
                {
                    "incident_types": incident_types,
                    "total_non_unknown": sum(item["count"] for item in incident_types),
                    "available_labels": [
                        label for label in LABELS if label != "unknown"
                    ],
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incidents/filtered/<incident_type>")
def api_incidents_filtered(incident_type):
    """Get incidents filtered by specific incident type"""
    try:
        # Validate incident type
        if incident_type not in LABELS:
            return jsonify({"error": "Invalid incident type"}), 400

        with db_lock:
            conn = dashboard.get_connection()
            cursor = conn.cursor()
            today = dashboard.current_date

            cursor.execute(
                """
                SELECT id, transcript, address, formatted_address, 
                       incident_type, system, department, channel,
                       time_recorded, filepath, original_filename, filename,
                       date_created, latitude, longitude,
                       confidence, frequency, modulation, tgid, maps_link, streetview_url
                FROM audio_metadata 
                WHERE date_created = ? AND incident_type = ?
                ORDER BY time_recorded DESC, id DESC
            """,
                (today, incident_type),
            )

            incidents = []
            for row in cursor.fetchall():
                incident = dict(row)

                # Handle transcript content
                transcript = incident.get("transcript", "")
                if not transcript or transcript in ["", "[EMPTY_TRANSCRIPT]"]:
                    incident["content"] = "[No audio content detected]"
                elif transcript.startswith("[PLACEHOLDER]"):
                    incident["content"] = "[Processing audio...]"
                else:
                    incident["content"] = transcript

                # Handle confidence value
                confidence = incident.get("confidence", 0.0)
                try:
                    incident["confidence"] = (
                        float(confidence) if confidence is not None else 0.0
                    )
                except (ValueError, TypeError):
                    incident["confidence"] = 0.0

                # Handle frequency value
                frequency = incident.get("frequency", "")
                if frequency and frequency != "":
                    try:
                        freq_val = float(frequency)
                        incident["frequency"] = f"{freq_val:.4f} MHz"
                    except (ValueError, TypeError):
                        incident["frequency"] = (
                            str(frequency) if frequency else "Unknown"
                        )
                else:
                    incident["frequency"] = "Unknown"

                # Handle audio filename
                audio_filename = (
                    incident.get("filename")
                    or incident.get("original_filename")
                    or f"incident_{incident['id']}.mp3"
                )

                if audio_filename and incident.get("filepath"):
                    incident["audio_filename"] = quote(audio_filename)
                    incident["has_audio"] = True
                else:
                    incident["audio_filename"] = f"incident_{incident['id']}.mp3"
                    incident["has_audio"] = False

                # Handle coordinates
                try:
                    if incident.get("latitude") and incident.get("longitude"):
                        incident["latitude"] = float(incident["latitude"])
                        incident["longitude"] = float(incident["longitude"])
                    else:
                        incident["latitude"] = None
                        incident["longitude"] = None
                except (ValueError, TypeError):
                    incident["latitude"] = None
                    incident["longitude"] = None

                incidents.append(incident)

            conn.close()
            return jsonify(
                {
                    "incidents": incidents,
                    "count": len(incidents),
                    "incident_type": incident_type,
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    """Get basic statistics"""
    try:
        stats = dashboard.get_basic_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/incidents")
def api_incidents():
    """Get today's incidents"""
    try:
        incidents = dashboard.get_incidents()
        return jsonify({"incidents": incidents, "count": len(incidents)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    """Health check endpoint with monitoring status"""
    try:
        latest_info = dashboard.get_latest_record_info()
        return jsonify(
            {
                "status": "healthy",
                "monitoring_active": monitoring_active,
                "connected_clients": len(connected_clients),
                "latest_record_info": latest_info,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/latest")
def api_latest():
    """Get latest record information for real-time checking"""
    try:
        latest_info = dashboard.get_latest_record_info()
        return jsonify(latest_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/force_update")
def api_force_update():
    """Force trigger a simulated update for testing"""
    try:
        # Get latest record
        latest_info = dashboard.get_latest_record_info()

        # Force broadcast latest incidents to all connected clients
        if connected_clients:
            incidents = dashboard.get_incidents()
            socketio.emit(
                "forced_update",
                {
                    "incidents": incidents[:5],  # Send latest 5 incidents
                    "count": len(incidents),
                    "latest_info": latest_info,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return jsonify(
                {
                    "status": "update_forced",
                    "latest_info": latest_info,
                    "connected_clients": len(connected_clients),
                    "monitoring_active": monitoring_active,
                }
            )
        else:
            return jsonify({"status": "no_connected_clients"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/audio_info")
def api_debug_audio_info():
    """Debug endpoint to check audio file availability"""
    try:
        with db_lock:
            conn = dashboard.get_connection()
            cursor = conn.cursor()

            # Get a few recent records with filepaths
            cursor.execute(
                """
                SELECT filename, original_filename, filepath, id
                FROM audio_metadata 
                WHERE date_created = ? 
                AND filepath IS NOT NULL 
                AND LENGTH(filepath) > 0
                ORDER BY id DESC
                LIMIT 5
                """,
                (dashboard.current_date,),
            )

            audio_info = []
            for row in cursor.fetchall():
                filename, original_filename, filepath, record_id = row
                file_exists = Path(filepath).exists() if filepath else False

                audio_info.append(
                    {
                        "id": record_id,
                        "filename": filename,
                        "original_filename": original_filename,
                        "filepath": filepath,
                        "file_exists": file_exists,
                        "audio_url": f"/audio/{quote(filename)}" if filename else None,
                    }
                )

            conn.close()

            return jsonify(
                {
                    "audio_files": audio_info,
                    "proscan_directory_exists": Path("C:/Proscan/Recordings").exists(),
                    "current_working_directory": str(Path.cwd()),
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/status")
def api_debug_status():
    """Get detailed debug status"""
    try:
        latest_info = dashboard.get_latest_record_info()
        db_mtime = dashboard.get_database_modification_time()

        return jsonify(
            {
                "monitoring_active": monitoring_active,
                "connected_clients": len(connected_clients),
                "current_date": dashboard.current_date,
                "latest_record_info": latest_info,
                "db_modification_time": db_mtime,
                "db_exists": dashboard.db_path.exists(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lower_volume")
def api_lower_volume():
    """API endpoint to lower system volume"""
    try:
        import volume_control

        success = volume_control.lower_system_volume()
        if success:
            return jsonify({"status": "volume_lowered"})
        else:
            return jsonify({"status": "failed_to_lower_volume"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== WEBSOCKET EVENTS =====


@socketio.on("connect")
def handle_connect():
    """Handle client connection with enhanced monitoring"""
    global monitoring_thread, connected_clients

    print(f"✅ Client connected: {request.sid}")
    connected_clients.add(request.sid)

    # Start enhanced monitoring thread if not already running
    if monitoring_thread is None or not monitoring_thread.is_alive():
        monitoring_thread = threading.Thread(
            target=enhanced_monitor_database, daemon=True
        )
        monitoring_thread.start()

    # Send initial data to new client immediately
    try:
        stats = dashboard.get_basic_stats()
        emit("stats_update", stats)

        incidents = dashboard.get_incidents()
        emit("initial_data", {"incidents": incidents, "count": len(incidents)})

        # Send connection confirmation
        emit(
            "connection_confirmed",
            {"status": "connected", "timestamp": datetime.now().isoformat()},
        )

    except Exception as e:
        emit("error", {"message": str(e)})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnect"""
    global connected_clients

    print(f"❌ Client disconnected: {request.sid}")
    connected_clients.discard(request.sid)


@socketio.on("request_update")
def handle_update_request():
    """Handle manual update request with immediate response"""
    try:
        print(f"🔄 Manual update requested by {request.sid}")

        stats = dashboard.get_basic_stats()
        emit("stats_update", stats)

        incidents = dashboard.get_incidents()
        emit("data_update", incidents)

        # Also send latest record info for debugging
        latest_info = dashboard.get_latest_record_info()
        emit("debug_info", latest_info)

    except Exception as e:
        emit("error", {"message": str(e)})


@socketio.on("ping")
def handle_ping():
    """Handle ping for connection testing"""
    emit("pong", {"timestamp": datetime.now().isoformat()})


@socketio.on("request_live_check")
def handle_live_check():
    """Handle live status check from frontend"""
    try:
        latest_info = dashboard.get_latest_record_info()
        emit(
            "live_status",
            {
                "active": monitoring_active,
                "latest_info": latest_info,
                "connected_clients": len(connected_clients),
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        emit("error", {"message": str(e)})


@socketio.on("check_for_updates")
def handle_check_for_updates():
    """Handle manual check for updates request from frontend"""
    try:
        print(f"🔄 Manual check for updates requested by {request.sid}")

        # Get current stats and send to client
        stats = dashboard.get_basic_stats()
        emit("stats_update", stats)

        # Get latest incidents and send to client
        incidents = dashboard.get_incidents()
        emit("data_update", incidents)

        # Send latest record info for debugging
        latest_info = dashboard.get_latest_record_info()
        emit("debug_info", latest_info)

    except Exception as e:
        emit("error", {"message": str(e)})


@socketio.on("request_live_incidents")
def handle_request_live_incidents():
    """Handle request for live incidents from frontend, excluding empty transcripts"""
    try:
        print(f"📡 Live incidents requested by {request.sid}")

        # Send all today's incidents, excluding those with empty transcripts
        incidents = [
            incident for incident in dashboard.get_incidents() if incident["transcript"]
        ]
        emit("initial_data", {"incidents": incidents, "count": len(incidents)})

    except Exception as e:
        emit("error", {"message": str(e)})


# ===== ENHANCED BACKGROUND MONITORING =====


def enhanced_monitor_database():
    """Enhanced real-time database monitoring with proper error handling and thread safety"""
    global monitoring_active, last_modified_time, connected_clients

    monitoring_active = True
    print(f"🔥 ENHANCED monitoring started for {dashboard.current_date}")
    print(f"📡 Monitoring every 2 seconds with proper error handling")

    last_known_id = None
    last_db_mtime = None
    consecutive_errors = 0
    max_errors = 5

    while monitoring_active:
        conn = None  # Initialize connection variable
        try:
            # Method 1: Database file modification time check (fastest)
            current_db_mtime = dashboard.get_database_modification_time()
            db_file_changed = (
                last_db_mtime is not None
                and current_db_mtime is not None
                and current_db_mtime != last_db_mtime
            )

            if last_db_mtime is None:
                last_db_mtime = current_db_mtime

            # Method 2: Record ID check with proper thread safety
            with db_lock:  # Thread-safe database access
                conn = dashboard.get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT MAX(id) as max_id FROM audio_metadata WHERE date_created = ?",
                    (dashboard.current_date,),
                )

                result = cursor.fetchone()
                current_max_id = result[0] if result and result[0] else 0

            # Detect changes
            id_changed = last_known_id is not None and current_max_id > last_known_id

            if last_known_id is None:
                last_known_id = current_max_id
                print(f"📊 Monitoring initialized - Latest ID: {current_max_id}")

            # Debug logging every 60 seconds (reduced frequency) - removed for production

            # If ANY change detected
            if db_file_changed or id_changed:
                print(
                    f"🆕 CHANGE DETECTED! DB file changed: {db_file_changed}, ID changed: {id_changed}"
                )
                print(f"📈 ID: {last_known_id} → {current_max_id}")

                # Update modification time
                last_db_mtime = current_db_mtime

                # Get new records if ID changed
                if id_changed and current_max_id > last_known_id:
                    with db_lock:  # Thread-safe database access
                        cursor.execute(
                            """
                            SELECT id, transcript, address, formatted_address, 
                                   incident_type, system, department, channel,
                                   time_recorded, filepath, original_filename, filename,
                                   date_created, latitude, longitude,
                                   confidence, frequency, modulation, tgid, maps_link, streetview_url
                            FROM audio_metadata 
                            WHERE date_created = ? AND id > ?
                            ORDER BY id ASC
                        """,
                            (dashboard.current_date, last_known_id),
                        )

                        new_records = cursor.fetchall()

                    if new_records:
                        # Process new records for broadcast
                        new_incidents = []
                        for row in new_records:
                            incident = dict(row)

                            # Handle transcript content
                            transcript = incident.get("transcript", "")
                            if not transcript or transcript in [
                                "",
                                "[EMPTY_TRANSCRIPT]",
                            ]:
                                incident["content"] = "[No audio content detected]"
                            elif transcript.startswith("[PLACEHOLDER]"):
                                incident["content"] = "[Processing audio...]"
                            else:
                                incident["content"] = transcript

                            # Handle confidence value (ensure it's properly formatted)
                            confidence = incident.get("confidence", 0.0)
                            try:
                                incident["confidence"] = (
                                    float(confidence) if confidence is not None else 0.0
                                )
                            except (ValueError, TypeError):
                                incident["confidence"] = 0.0

                            # Handle frequency value (ensure it's properly formatted)
                            frequency = incident.get("frequency", "")
                            if frequency and frequency != "":
                                try:
                                    freq_val = float(frequency)
                                    incident["frequency"] = f"{freq_val:.4f} MHz"
                                except (ValueError, TypeError):
                                    incident["frequency"] = (
                                        str(frequency) if frequency else "Unknown"
                                    )
                            else:
                                incident["frequency"] = "Unknown"

                            # Handle audio filename
                            audio_filename = (
                                incident.get("filename")
                                or incident.get("original_filename")
                                or f"incident_{incident['id']}.mp3"
                            )

                            if audio_filename and incident.get("filepath"):
                                incident["audio_filename"] = quote(audio_filename)
                                incident["has_audio"] = True
                            else:
                                incident["audio_filename"] = (
                                    f"incident_{incident['id']}.mp3"
                                )
                                incident["has_audio"] = False

                            # Handle coordinates
                            try:
                                if incident.get("latitude") and incident.get(
                                    "longitude"
                                ):
                                    incident["latitude"] = float(incident["latitude"])
                                    incident["longitude"] = float(incident["longitude"])
                                else:
                                    incident["latitude"] = None
                                    incident["longitude"] = None
                            except (ValueError, TypeError):
                                incident["latitude"] = None
                                incident["longitude"] = None

                            new_incidents.append(incident)

                        # Update last known ID
                        last_known_id = current_max_id

                        # INSTANT BROADCAST to all connected clients
                        if connected_clients and new_incidents:
                            print(
                                f"📡 INSTANT BROADCAST: {len(new_incidents)} new records to {len(connected_clients)} clients"
                            )
                            socketio.emit("new_incidents", new_incidents)

                            # Update stats
                            stats = dashboard.get_basic_stats()
                            socketio.emit("stats_update", stats)

                            # Send heartbeat
                            socketio.emit(
                                "heartbeat",
                                {
                                    "timestamp": datetime.now().isoformat(),
                                    "new_count": len(new_incidents),
                                    "total_clients": len(connected_clients),
                                },
                            )

                # Even if no new records, broadcast a heartbeat on file change
                elif db_file_changed and connected_clients:
                    print("💓 Database file changed - sending heartbeat")
                    socketio.emit(
                        "heartbeat",
                        {
                            "timestamp": datetime.now().isoformat(),
                            "new_count": 0,
                            "file_changed": True,
                            "total_clients": len(connected_clients),
                        },
                    )

            # Close connection in finally block
            if conn:
                conn.close()
                conn = None

            consecutive_errors = 0  # Reset error counter on success

            # Send periodic heartbeat to show monitoring is active (reduced frequency)
            if connected_clients and int(time.time()) % 60 == 0:  # Every 60 seconds
                socketio.emit(
                    "monitoring_heartbeat",
                    {
                        "timestamp": datetime.now().isoformat(),
                        "monitoring_active": True,
                        "current_max_id": current_max_id,
                        "connected_clients": len(connected_clients),
                        "db_modification_time": current_db_mtime,
                    },
                )

            # Reduced polling frequency for stability
            time.sleep(2.0)  # Check every 2 seconds

        except Exception as e:
            consecutive_errors += 1
            print(
                f"❌ Database monitoring error ({consecutive_errors}/{max_errors}): {e}"
            )

            # CRITICAL: Always close connection on error
            if conn:
                try:
                    conn.close()
                except:
                    pass  # Connection might already be closed
                conn = None

            # If too many consecutive errors, try to restart
            if consecutive_errors >= max_errors:
                print(
                    f"⚠️  Too many errors ({consecutive_errors}), restarting monitoring..."
                )
                time.sleep(5)
                consecutive_errors = 0
            else:
                time.sleep(1)  # Shorter wait on error for faster recovery


def monitor_database_changes():
    """Legacy function - redirects to enhanced monitor"""
    enhanced_monitor_database()


# ===== APPLICATION STARTUP =====

if __name__ == "__main__":
    print("🌐 Live Dashboard: http://localhost:5000/live")

    try:
        # Show basic info
        stats = dashboard.get_basic_stats()
        latest_info = dashboard.get_latest_record_info()
        print(f"📊 Total records: {stats['total_today']}")
        print(f"🔢 Latest record ID: {latest_info['max_id']}")
        print(f"⏰ Latest time: {latest_info['latest_time']}")
    except Exception as e:
        print(f"⚠️  Database connection issue: {e}")

    print()
    print("🔴 Starting FIXED professional monitoring...")

    # Start the application
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
