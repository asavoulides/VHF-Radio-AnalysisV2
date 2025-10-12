# Historic Police Scanner Database Viewer

A high-performance web application for querying and analyzing large police scanner databases with 100K+ records.

## 🚀 Features

### Core Functionality
- **📊 Real-time Statistics** - Database overview with record counts, date ranges, and size
- **🔍 Advanced Filtering** - Multiple filter criteria for precise queries
- **📄 Pagination** - Handle large datasets efficiently (50 records per page)
- **📥 CSV Export** - Export query results (up to 10,000 records)
- **👁️ Detailed View** - Modal popup with complete record information
- **⚡ Optimized Performance** - Handles databases with millions of records

### Filter Options
1. **Date Range** - Filter by start and end dates
2. **Incident Type** - Filter by specific incident categories
3. **System** - Filter by radio system
4. **Transcript Search** - Full-text search in transcripts
5. **Address Search** - Search by location/address
6. **Confidence Threshold** - Filter by transcription confidence
7. **Sort Order** - Multiple sorting options (newest, oldest, confidence, type)

### Safety Features
- **SQL Injection Protection** - Parameterized queries
- **Export Limits** - Maximum 10,000 records per CSV export
- **Page Size Limits** - Maximum 500 records per page
- **Error Handling** - Graceful error messages

## 📋 Prerequisites

- Python 3.8+
- Flask (`pip install flask`)
- SQLite database (`Logs/audio_metadata.db`)

## 🎯 Quick Start

### 1. Installation
```bash
cd "Historic Analysis"
pip install flask
```

### 2. Run the Application
```bash
python database_viewer.py
```

### 3. Access the Interface
Open your browser to:
```
http://localhost:5001
```

**Note:** Port 5001 is used to avoid conflicts with the main dashboard (port 5000)

## 💻 Usage Guide

### Basic Workflow
1. **View Statistics** - Check database overview at the top
2. **Set Filters** - Configure search criteria
3. **Search** - Click "Search Database" button
4. **Navigate Results** - Use pagination controls
5. **View Details** - Click "View" on any record
6. **Export** - Click "Export to CSV" to download results

### Advanced Queries

#### Example 1: Find Medical Emergencies Last Month
```
Start Date: 2025-09-09
End Date: 2025-10-09
Incident Type: Medical
Sort By: Newest First
```

#### Example 2: High-Confidence Fire Incidents
```
Incident Type: Structure Fire
Min Confidence: 90
Sort By: Highest Confidence
```

#### Example 3: Search for Specific Location
```
Address Search: Washington St
Sort By: Newest First
```

#### Example 4: Find Specific Keyword in Transcripts
```
Transcript Search: vehicle accident
Sort By: Newest First
```

## 📊 Database Performance

### Optimization Strategies
1. **Indexed Queries** - Uses database indexes for fast lookups
2. **Pagination** - Loads only visible records (50 per page)
3. **Count Optimization** - Separate count query for pagination
4. **Lazy Loading** - Statistics loaded separately from results
5. **Connection Pooling** - Efficient database connection management

### Expected Performance
| Database Size | Query Time | Export Time (10K) |
|--------------|-----------|-------------------|
| 10K records | < 100ms | < 2s |
| 100K records | < 200ms | < 5s |
| 1M records | < 500ms | < 15s |
| 10M records | < 1s | < 30s |

## 🗂️ File Structure

```
Historic Analysis/
├── database_viewer.py          # Flask backend application
├── templates/
│   └── database_viewer.html    # Frontend interface
└── README.md                   # This file
```

## 🔧 Configuration

Edit `database_viewer.py` to customize:

```python
# Database path (relative to this directory)
DB_PATH = Path("../Logs/audio_metadata.db")

# Records per page (adjust for performance)
PAGE_SIZE = 50

# Maximum records for CSV export
MAX_EXPORT = 10000

# Server port (change if port 5001 is in use)
app.run(host='0.0.0.0', port=5001, debug=False)
```

## 📤 CSV Export Format

Exported CSV files include all visible columns:
- `id` - Record ID
- `date_created` - Date of incident
- `time_recorded` - Time of incident
- `transcript` - Full transcription text
- `incident_type` - Classified incident type
- `address` - Location address
- `formatted_address` - Geocoded address
- `system` - Radio system name
- `department` - Department name
- `channel` - Radio channel
- `frequency` - Frequency in MHz
- `confidence` - Transcription confidence %
- `latitude` - GPS latitude
- `longitude` - GPS longitude
- `property_owner` - Property owner (if available)
- `property_price` - Property assessment value
- `filename` - Original audio filename

Filename format: `police_scanner_export_YYYYMMDD_HHMMSS.csv`

## 🐛 Troubleshooting

### "Database not found" Error
**Problem:** `Database not found: ../Logs/audio_metadata.db`

**Solution:**
1. Check that `Logs/audio_metadata.db` exists in parent directory
2. Verify database path in `database_viewer.py`
3. Run from correct directory: `cd "Historic Analysis"`

### Slow Query Performance
**Problem:** Queries taking too long

**Solutions:**
1. Reduce page size (default 50)
2. Add more specific filters (date range, incident type)
3. Check database has indexes on commonly queried fields
4. Limit transcript/address searches to specific terms

### Export Fails with "Too many records"
**Problem:** Export rejected due to size

**Solutions:**
1. Add more restrictive filters
2. Break export into smaller date ranges
3. Increase `MAX_EXPORT` limit (may impact performance)

### Port Already in Use
**Problem:** Port 5001 already taken

**Solution:** Change port in `database_viewer.py`:
```python
app.run(host='0.0.0.0', port=5002, debug=False)  # Use different port
```

## 🔐 Security Considerations

### What's Protected
✅ SQL injection prevention (parameterized queries)
✅ Export size limits (prevents memory exhaustion)
✅ Page size limits (prevents excessive data transfer)
✅ Error message sanitization

### What's NOT Protected
⚠️ No authentication/authorization (runs locally)
⚠️ No encryption (use VPN if accessing remotely)
⚠️ No rate limiting (trusted local users only)

**Recommendation:** Use only on trusted local networks or add authentication layer for production.

## 📈 Performance Tips

1. **Use Date Ranges** - Always filter by date when possible
2. **Specific Incident Types** - Filter by type before searching
3. **Limit Text Searches** - Be specific with transcript/address searches
4. **Reasonable Page Sizes** - Don't increase page size beyond 200
5. **Export in Batches** - For large datasets, export in date ranges

## 🎨 Customization

### Change Color Scheme
Edit `database_viewer.html` CSS variables:
```css
/* Main gradient colors */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Accent color */
color: #667eea;
```

### Add New Filters
1. Add HTML input in filters section
2. Update `getFilters()` JavaScript function
3. Add parameter handling in `build_query()` Python function
4. Update SQL WHERE clause

### Customize Statistics
Edit `get_database_stats()` in `database_viewer.py` to add custom metrics.

## 🆚 Comparison with Main Dashboard

| Feature | Main Dashboard | Historic Viewer |
|---------|---------------|-----------------|
| **Purpose** | Real-time monitoring | Historic analysis |
| **Data** | Today only | All dates |
| **Updates** | Live (WebSocket) | On-demand |
| **Filters** | Basic | Advanced |
| **Export** | No | Yes (CSV) |
| **Performance** | < 100 records | 100K+ records |
| **Port** | 5000 | 5001 |

## 📚 Related Tools

- **Main Dashboard** (`scanner_dashboard.py`) - Real-time live monitoring
- **Test Utilities** (`tests/`) - Progressive loading testing
- **Data Processor** (`app.py`) - Audio file processing pipeline

## 💡 Pro Tips

1. **Bookmark Common Queries** - Save browser bookmarks with pre-filled URLs
2. **Use Browser Search** - Ctrl+F to search within current page results
3. **Export for Excel** - CSV files open directly in Excel/Google Sheets
4. **Check Statistics First** - Review database stats before complex queries
5. **Combine Filters** - Use multiple filters together for precise results

## 🔄 Future Enhancements

Potential improvements:
- [ ] Save/load custom filter presets
- [ ] Advanced analytics (charts, graphs)
- [ ] Batch operations (bulk delete, update)
- [ ] Custom column visibility
- [ ] Dark mode theme
- [ ] Saved searches
- [ ] Email export results
- [ ] Multi-database support
- [ ] User authentication

## 📞 Support

For issues or questions:
1. Check this README troubleshooting section
2. Review database schema: `python show_db_schema.py`
3. Check Flask logs in terminal
4. Verify database integrity with SQLite browser

---

**Made with ❤️ for analyzing police scanner data efficiently**
