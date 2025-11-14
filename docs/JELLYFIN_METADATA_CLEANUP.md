# Jellyfin Metadata Cleanup Guide

## Problem

When generating a large number of series (.strm files) for Jellyfin, the metadata database can become corrupted with cached entries that persist even after:
- Deleting all media files from the library directory
- Removing and re-adding the library in Jellyfin UI
- Scanning the library multiple times

### Symptoms
- Jellyfin shows incorrect series/episode counts that don't match actual files
- Scan logs show `DirectoryNotFoundException` for non-existent series
- Library refresh doesn't update the counts
- Memory issues during scanning due to trying to process phantom entries

### Root Cause
Jellyfin caches all metadata in its SQLite database (`/var/lib/jellyfin/data/jellyfin.db`). The "Remove Library" function in the UI does NOT delete the cached entries from the database - it only removes the library configuration. This means old series, episodes, and seasons remain in the database tables.

## Solution

Direct database cleanup using SQLite queries.

### Prerequisites
1. Stop Jellyfin service: `systemctl stop jellyfin`
2. Install sqlite3: `apt install sqlite3`
3. Backup database (optional but recommended): `cp /var/lib/jellyfin/data/jellyfin.db /var/lib/jellyfin/data/jellyfin.db.backup`

### Step 1: Identify Library Path
Find the exact path pattern for your library:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT DISTINCT Path FROM BaseItems WHERE Path LIKE '%/media/jellyfin/YOUR_LIBRARY_NAME/%' LIMIT 5;"
```

### Step 2: Verify What Will Be Deleted
Count entries that will be removed:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/YOUR_LIBRARY_NAME/%';"
```

**IMPORTANT**: Verify this query targets ONLY the library you want to clean. Check that other libraries (like Aniworld) won't be affected:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/aniworld/%';"
```

### Step 3: Delete Cached Metadata
Execute cleanup queries:
```sql
-- Delete all items from the target library
DELETE FROM BaseItems WHERE Path LIKE "%/media/jellyfin/YOUR_LIBRARY_NAME/%";

-- Clean orphaned user data
DELETE FROM UserData WHERE ItemId NOT IN (SELECT Id FROM BaseItems);

-- Clean orphaned chapters
DELETE FROM Chapters WHERE ItemId NOT IN (SELECT Id FROM BaseItems);

-- Compact database
VACUUM;
```

Full command:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db <<EOF
DELETE FROM BaseItems WHERE Path LIKE "%/media/jellyfin/YOUR_LIBRARY_NAME/%";
DELETE FROM UserData WHERE ItemId NOT IN (SELECT Id FROM BaseItems);
DELETE FROM Chapters WHERE ItemId NOT IN (SELECT Id FROM BaseItems);
VACUUM;
EOF
```

### Step 4: Verify Cleanup
Check that entries were removed:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/YOUR_LIBRARY_NAME/%';"
```

Should return 0.

Verify other libraries are intact:
```bash
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/aniworld/%';"
```

Should return the correct count.

### Step 5: Restart Jellyfin
```bash
systemctl start jellyfin
```

### Step 6: Generate Fresh Structure
Now you can generate your .strm files and scan the library cleanly:
```bash
cd /opt/JellyStream/sites/YOUR_SITE
python3 7_jellyfin_structurer.py
```

Then scan the library in Jellyfin UI.

## Example: SerienStream Cleanup

Real-world example from SerienStream library with 10,276 series:

```bash
# Stop Jellyfin
systemctl stop jellyfin

# Clean SerienStream metadata (165,109 items removed)
sqlite3 /var/lib/jellyfin/data/jellyfin.db <<EOF
DELETE FROM BaseItems WHERE Path LIKE "%/media/jellyfin/serienstream/%";
DELETE FROM UserData WHERE ItemId NOT IN (SELECT Id FROM BaseItems);
DELETE FROM Chapters WHERE ItemId NOT IN (SELECT Id FROM BaseItems);
VACUUM;
EOF

# Result: Database size reduced from 3.2GB to 1.7GB

# Verify SerienStream is clean
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/serienstream/%';"
# Returns: 0

# Verify Aniworld is untouched
sqlite3 /var/lib/jellyfin/data/jellyfin.db "SELECT COUNT(*) FROM BaseItems WHERE Path LIKE '%/media/jellyfin/aniworld/%';"
# Returns: 61141 (2,279 series + episodes - correct)

# Restart Jellyfin
systemctl start jellyfin

# Generate fresh structure
cd /opt/JellyStream/sites/serienstream
python3 7_jellyfin_structurer.py

# Scan library in Jellyfin UI - works perfectly!
```

## Prevention

When working with large libraries (8,000+ series):
1. Generate in batches to avoid memory exhaustion
2. If you need to regenerate, do a database cleanup first
3. Monitor RAM/swap usage during initial scan
4. Consider disabling image downloads for very large libraries

## Notes

- Each library stores metadata separately based on Path in the database
- Libraries are isolated - cleaning one won't affect others (as long as path patterns are correct)
- The VACUUM command reclaims space and optimizes the database
- This process is safe as long as you verify the Path pattern matches only your target library
