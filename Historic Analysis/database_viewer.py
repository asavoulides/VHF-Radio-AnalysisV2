#!/usr/bin/env python3
"""
Historic Police Scanner Database Viewer
A high-performance Flask application for querying and analyzing large police scanner databases

Features:
- Pagination for handling large datasets (configurable page size)
- Advanced filtering (date range, incident type, address, transcript search)
- SQL query builder with safety checks
- Export to CSV
- Statistics dashboard
- Optimized for databases with 100K+ records
"""

import os
import sqlite3
import csv
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from io import StringIO, BytesIO

# Configuration
DB_PATH = Path(__file__).parent.parent / "Logs" / "audio_metadata.db"
PAGE_SIZE = 50  # Records per page (adjustable)
MAX_EXPORT = 10000  # Maximum records for CSV export

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_database_stats():
    """Get overall database statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}

    # Total records
    cursor.execute("SELECT COUNT(*) as total FROM audio_metadata")
    stats["total_records"] = cursor.fetchone()[0]

    # Date range
    cursor.execute(
        "SELECT MIN(date_created) as first_date, MAX(date_created) as last_date FROM audio_metadata"
    )
    result = cursor.fetchone()
    stats["first_date"] = result[0]
    stats["last_date"] = result[1]

    # Incident type breakdown
    cursor.execute(
        """
        SELECT incident_type, COUNT(*) as count 
        FROM audio_metadata 
        WHERE incident_type IS NOT NULL AND incident_type != 'unknown'
        GROUP BY incident_type 
        ORDER BY count DESC 
        LIMIT 10
    """
    )
    stats["top_incident_types"] = [dict(row) for row in cursor.fetchall()]

    # Records by date (last 30 days)
    cursor.execute(
        """
        SELECT date_created, COUNT(*) as count 
        FROM audio_metadata 
        WHERE date_created >= date('now', '-30 days')
        GROUP BY date_created 
        ORDER BY date_created DESC
    """
    )
    stats["recent_activity"] = [dict(row) for row in cursor.fetchall()]

    # Database file size
    if DB_PATH.exists():
        stats["db_size_mb"] = DB_PATH.stat().st_size / (1024 * 1024)
    else:
        stats["db_size_mb"] = 0

    conn.close()
    return stats


def build_query(filters, page=1, page_size=PAGE_SIZE):
    """Build SQL query based on filters with pagination"""
    base_query = """
        SELECT id, date_created, time_recorded, transcript, incident_type, 
               address, formatted_address, system, department, channel, 
               frequency, confidence, latitude, longitude, 
               property_owner, property_price, filename
        FROM audio_metadata
        WHERE 1=1
    """

    params = []
    conditions = []

    # Date range filter
    if filters.get("start_date"):
        conditions.append("date_created >= ?")
        params.append(filters["start_date"])

    if filters.get("end_date"):
        conditions.append("date_created <= ?")
        params.append(filters["end_date"])

    # Incident type filter
    if filters.get("incident_type") and filters["incident_type"] != "all":
        conditions.append("incident_type = ?")
        params.append(filters["incident_type"])

    # Transcript search (case-insensitive)
    if filters.get("transcript_search"):
        conditions.append("transcript LIKE ?")
        params.append(f"%{filters['transcript_search']}%")

    # Address search (case-insensitive)
    if filters.get("address_search"):
        conditions.append("(address LIKE ? OR formatted_address LIKE ?)")
        search_term = f"%{filters['address_search']}%"
        params.append(search_term)
        params.append(search_term)

    # System filter
    if filters.get("system") and filters["system"] != "all":
        conditions.append("system = ?")
        params.append(filters["system"])

    # Confidence threshold
    if filters.get("min_confidence"):
        conditions.append("confidence >= ?")
        params.append(float(filters["min_confidence"]))

    # Add conditions to query
    if conditions:
        base_query += " AND " + " AND ".join(conditions)

    # Order by
    order_by = filters.get("order_by", "date_created DESC, time_recorded DESC")
    base_query += f" ORDER BY {order_by}"

    # Pagination
    offset = (page - 1) * page_size
    base_query += f" LIMIT {page_size} OFFSET {offset}"

    return base_query, params


def get_count_query(filters):
    """Get total count query for pagination"""
    base_query = "SELECT COUNT(*) as total FROM audio_metadata WHERE 1=1"

    params = []
    conditions = []

    if filters.get("start_date"):
        conditions.append("date_created >= ?")
        params.append(filters["start_date"])

    if filters.get("end_date"):
        conditions.append("date_created <= ?")
        params.append(filters["end_date"])

    if filters.get("incident_type") and filters["incident_type"] != "all":
        conditions.append("incident_type = ?")
        params.append(filters["incident_type"])

    if filters.get("transcript_search"):
        conditions.append("transcript LIKE ?")
        params.append(f"%{filters['transcript_search']}%")

    if filters.get("address_search"):
        conditions.append("(address LIKE ? OR formatted_address LIKE ?)")
        search_term = f"%{filters['address_search']}%"
        params.append(search_term)
        params.append(search_term)

    if filters.get("system") and filters["system"] != "all":
        conditions.append("system = ?")
        params.append(filters["system"])

    if filters.get("min_confidence"):
        conditions.append("confidence >= ?")
        params.append(float(filters["min_confidence"]))

    if conditions:
        base_query += " AND " + " AND ".join(conditions)

    return base_query, params


@app.route("/")
def index():
    """Main database viewer page"""
    return render_template("database_viewer.html")


@app.route("/api/stats")
def api_stats():
    """Get database statistics"""
    try:
        stats = get_database_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/filters")
def api_filters():
    """Get available filter options"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get unique incident types
        cursor.execute(
            """
            SELECT DISTINCT incident_type 
            FROM audio_metadata 
            WHERE incident_type IS NOT NULL AND incident_type != ''
            ORDER BY incident_type
        """
        )
        incident_types = [row[0] for row in cursor.fetchall()]

        # Get unique systems
        cursor.execute(
            """
            SELECT DISTINCT system 
            FROM audio_metadata 
            WHERE system IS NOT NULL AND system != ''
            ORDER BY system
        """
        )
        systems = [row[0] for row in cursor.fetchall()]

        conn.close()

        return jsonify({"incident_types": incident_types, "systems": systems})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/query")
def api_query():
    """Execute query and return paginated results"""
    try:
        # Get filters from request
        filters = {
            "start_date": request.args.get("start_date"),
            "end_date": request.args.get("end_date"),
            "incident_type": request.args.get("incident_type"),
            "transcript_search": request.args.get("transcript_search"),
            "address_search": request.args.get("address_search"),
            "system": request.args.get("system"),
            "min_confidence": request.args.get("min_confidence"),
            "order_by": request.args.get(
                "order_by", "date_created DESC, time_recorded DESC"
            ),
        }

        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", PAGE_SIZE))

        # Limit page size for safety
        page_size = min(page_size, 500)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get total count
        count_query, count_params = get_count_query(filters)
        cursor.execute(count_query, count_params)
        total_records = cursor.fetchone()[0]

        # Get paginated results
        query, params = build_query(filters, page, page_size)
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]

        conn.close()

        total_pages = (total_records + page_size - 1) // page_size

        return jsonify(
            {
                "results": results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_records": total_records,
                    "total_pages": total_pages,
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export")
def api_export():
    """Export query results to CSV"""
    try:
        # Get filters from request
        filters = {
            "start_date": request.args.get("start_date"),
            "end_date": request.args.get("end_date"),
            "incident_type": request.args.get("incident_type"),
            "transcript_search": request.args.get("transcript_search"),
            "address_search": request.args.get("address_search"),
            "system": request.args.get("system"),
            "min_confidence": request.args.get("min_confidence"),
            "order_by": request.args.get(
                "order_by", "date_created DESC, time_recorded DESC"
            ),
        }

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check total count
        count_query, count_params = get_count_query(filters)
        cursor.execute(count_query, count_params)
        total_records = cursor.fetchone()[0]

        if total_records > MAX_EXPORT:
            conn.close()
            return (
                jsonify(
                    {
                        "error": f"Too many records to export ({total_records}). Maximum is {MAX_EXPORT}. Please refine your filters."
                    }
                ),
                400,
            )

        # Get all results (no pagination for export)
        query, params = build_query(filters, page=1, page_size=MAX_EXPORT)
        cursor.execute(query, params)
        results = cursor.fetchall()

        # Create CSV
        output = StringIO()
        if results:
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            for row in results:
                writer.writerow(dict(row))

        conn.close()

        # Convert to bytes for download
        csv_data = output.getvalue()
        output.close()

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"police_scanner_export_{timestamp}.csv"

        # Return as downloadable file
        return send_file(
            BytesIO(csv_data.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/record/<int:record_id>")
def api_record_detail(record_id):
    """Get detailed information for a single record"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM audio_metadata WHERE id = ?", (record_id,))
        result = cursor.fetchone()

        conn.close()

        if result:
            return jsonify(dict(result))
        else:
            return jsonify({"error": "Record not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def point_in_polygon(lat, lng, polygon):
    """Check if a point is inside a polygon using ray casting algorithm

    Args:
        lat: Latitude of the point
        lng: Longitude of the point
        polygon: List of [lat, lng] coordinate pairs defining the polygon
    """
    if not polygon or len(polygon) < 3:
        return False

    # Point to test
    x, y = lng, lat  # Use lng as x and lat as y for geographic coordinates

    # Polygon vertices
    n = len(polygon)
    inside = False

    # Ray casting algorithm
    j = n - 1
    for i in range(n):
        xi, yi = (
            polygon[i][1],
            polygon[i][0],
        )  # polygon[i][1] is lng (x), polygon[i][0] is lat (y)
        xj, yj = polygon[j][1], polygon[j][0]

        # Check if point is on an edge
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


@app.route("/api/map_query", methods=["POST"])
def api_map_query():
    """Query incidents within a drawn polygon on map"""
    try:
        print("\n=== MAP QUERY REQUEST ===")
        data = request.json
        print(f"Request data: {data}")

        polygon = data.get("polygon", [])  # Array of [lat, lng] points
        filters = data.get("filters", {})

        print(f"Polygon points: {len(polygon)}")
        print(f"Filters: {filters}")

        if not polygon or len(polygon) < 3:
            print("ERROR: Invalid polygon")
            return jsonify({"error": "Invalid polygon - need at least 3 points"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build base query with filters
        base_query = "SELECT * FROM audio_metadata WHERE 1=1"
        params = []

        # Add standard filters
        if filters.get("start_date"):
            base_query += " AND date_created >= ?"
            params.append(filters["start_date"])

        if filters.get("end_date"):
            base_query += " AND date_created <= ?"
            params.append(filters["end_date"])

        if filters.get("incident_type") and filters["incident_type"] != "all":
            base_query += " AND incident_type = ?"
            params.append(filters["incident_type"])

        if filters.get("system") and filters["system"] != "all":
            base_query += " AND system = ?"
            params.append(filters["system"])

        # Get all records with lat/lng (we'll filter by polygon in Python)
        base_query += " AND latitude IS NOT NULL AND longitude IS NOT NULL"
        base_query += " ORDER BY date_created DESC, time_recorded DESC"

        print(f"Executing query: {base_query}")
        print(f"Query params: {params}")

        cursor.execute(base_query, params)
        all_results = cursor.fetchall()

        print(f"Found {len(all_results)} records with lat/lng")

        # Filter by polygon
        filtered_results = []
        for row in all_results:
            row_dict = dict(row)
            lat = row_dict.get("latitude")
            lng = row_dict.get("longitude")

            if lat is not None and lng is not None:
                if point_in_polygon(float(lat), float(lng), polygon):
                    filtered_results.append(row_dict)

        conn.close()

        print(f"Filtered to {len(filtered_results)} records within polygon")
        print("=== END MAP QUERY ===\n")

        return jsonify({"results": filtered_results, "total": len(filtered_results)})
    except Exception as e:
        print(f"ERROR in map_query: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/audio/<int:record_id>")
def api_audio(record_id):
    """Serve audio file for a specific record"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT filepath FROM audio_metadata WHERE id = ?", (record_id,))
        result = cursor.fetchone()

        conn.close()

        if not result or not result["filepath"]:
            return jsonify({"error": "Audio file not found"}), 404

        filepath = Path(result["filepath"])

        if not filepath.exists():
            return jsonify({"error": "Audio file does not exist on disk"}), 404

        # Serve the audio file
        return send_file(
            str(filepath),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name=filepath.name,
        )
    except Exception as e:
        print(f"ERROR serving audio: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 70)
    print("📊 HISTORIC POLICE SCANNER DATABASE VIEWER")
    print("=" * 70)
    print()
    print(f"Database: {DB_PATH}")
    print(f"Database exists: {DB_PATH.exists()}")

    if DB_PATH.exists():
        stats = get_database_stats()
        print(f"Total records: {stats['total_records']:,}")
        print(f"Date range: {stats['first_date']} to {stats['last_date']}")
        print(f"Database size: {stats['db_size_mb']:.2f} MB")

    print()
    print("🌐 Starting web interface...")
    print("   URL: http://localhost:5001")
    print()
    print("=" * 70)

    app.run(host="0.0.0.0", port=5001, debug=False)
