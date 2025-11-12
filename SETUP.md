# JellyStream Setup Guide

## Project Overview

JellyStream is an automated Jellyfin streaming platform that scrapes German content from SerienStream and Aniworld, generates Jellyfin-compatible folder structures with .strm files, and provides a streaming API backend to serve the content.

## Architecture

```
JellyStream/
├── sites/
│   ├── serienstream/          # SerienStream scraper & scripts
│   │   ├── config.py          # Site-specific config (JELLYFIN_OUTPUT_DIR, etc.)
│   │   ├── 1_catalog_scraper.py
│   │   ├── 2_url_season_episode_num.py
│   │   ├── 3_language_streamurl.py
│   │   ├── 4_json_structurer.py
│   │   ├── 5_updater.py
│   │   ├── 6_main.py          # Run full pipeline
│   │   ├── 7_jellyfin_structurer.py  # Generate .strm files
│   │   └── data/
│   │       └── final_series_data.json
│   └── aniworld/              # Aniworld scraper & scripts (same structure)
├── api/
│   ├── main.py               # Flask API entry point
│   ├── redirector.py         # Stream redirect logic
│   ├── data_loader.py        # Loads series data from JSON
│   └── providers/            # Stream provider handlers (VOE, Vidoza, etc.)
└── utils/
    └── manual_updater.py     # CLI tool for updating individual series
```

## Current Database Status

### SerienStream
- **Series:** 10,276
- **Episodes:** 253,972
- **Movies:** 1,603
- **Database:** `sites/serienstream/data/final_series_data.json` (162 MB)
- **Jellyfin folder:** `/media/jellyfin/serienstream/`

### Aniworld
- **Series:** 2,279
- **Episodes:** 26,795
- **Movies:** 695
- **Database:** `sites/aniworld/data/final_series_data.json` (75 MB)
- **Jellyfin folder:** `/media/jellyfin/aniworld/`

**Note:** Database files are NOT in git (too large). Backups are stored locally in `backup/` folder.

## Infrastructure

### Current Setup (Proxmox LXC containers)

1. **Code Server (192.168.1.153)**
   - Where this project lives: `/root/projects/JellyStream/`
   - VS Code server for development
   - Can run scrapers and API for testing

2. **Jellyfin Server (192.168.1.110 / hostname: jellyfin)**
   - Jellyfin media server
   - Should have project cloned to: `/opt/JellyStream/`
   - Streaming API backend runs here
   - Media folders: `/media/jellyfin/serienstream/` and `/media/jellyfin/aniworld/`

### SSH Access
- SSH key for Jellyfin server: `~/.ssh/id_ed25519_jellyfin`
- SSH config: `ssh jellyfin` connects to Jellyfin server
- GitHub SSH key: `~/.ssh/github_jellyfin`

## Known Issues & Current State

### ⚠️ Critical Issue: Wrong API URL in .strm Files

**Problem:** The .strm files currently point to `http://192.168.1.153:3000/stream/redirect/{id}` (code server IP) instead of `http://localhost:3000/stream/redirect/{id}`.

**Impact:** Jellyfin cannot play streams because it's trying to reach the wrong server.

**Why it happened:** The `7_jellyfin_structurer.py` script was run with the wrong `api_base_url` parameter.

**Solution needed:**
1. Update `7_jellyfin_structurer.py` to use `localhost:3000` as default
2. Regenerate all .strm files with correct localhost URLs
3. Rebuild Jellyfin LXC cleanly with proper setup

### Current Jellyfin State
- Jellyfin was reinstalled after database corruption
- Library scan is running (currently at ~8k series)
- Once scan completes, all series will be indexed but won't play due to wrong URLs

## Configuration Files

### sites/serienstream/config.py
```python
SITE_URL = "https://serienstream.sx"
JELLYFIN_OUTPUT_DIR = "/media/jellyfin/serienstream"
```

### sites/aniworld/config.py
```python
SITE_URL = "https://aniworld.to"
JELLYFIN_OUTPUT_DIR = "/media/jellyfin/aniworld"
```

### 7_jellyfin_structurer.py (FIXED)
Both structurer scripts now have:
```python
def __init__(self, output_dir=None, api_base_url="http://localhost:3000/api/stream/redirect"):
    self.output_dir = Path(output_dir) if output_dir else Path(config.JELLYFIN_OUTPUT_DIR)
```

**Important:** The `api_base_url` should be `localhost:3000` because Jellyfin and the API run on the same server.

## Workflow

### 1. Scraping New Content
```bash
cd /root/projects/JellyStream/sites/serienstream
python3 6_main.py  # Run full pipeline
```

### 2. Generating Jellyfin Structure
```bash
cd /root/projects/JellyStream/sites/serienstream
python3 7_jellyfin_structurer.py  # Creates .strm files
```

### 3. Running the Streaming API
```bash
cd /root/projects/JellyStream/api
python3 main.py  # Starts Flask server on port 3000
```

### 4. Updating Individual Series
```bash
cd /root/projects/JellyStream/utils
python3 manual_updater.py
# Interactive CLI for updating specific series when streams expire
```

## Progress Tracking

Each site has independent progress tracking:
- SerienStream: `/media/jellyfin/serienstream/.structure_progress.json`
- Aniworld: `/media/jellyfin/aniworld/.structure_progress.json`

This prevents the structurer from regenerating already-created folders.

## Next Steps (TODO)

### Immediate Fix Required
1. **Recreate Jellyfin LXC cleanly**
   - Fresh Jellyfin installation
   - Clone JellyStream project from GitHub
   - Setup Python environment and dependencies
   - Copy database files from backup

2. **Fix API URL Configuration**
   - Verify `7_jellyfin_structurer.py` uses `localhost:3000`
   - Update both serienstream and aniworld configs if needed

3. **Regenerate Folder Structures**
   - Clear existing folders: `rm -rf /media/jellyfin/serienstream/* /media/jellyfin/aniworld/*`
   - Clear progress files: `rm -f /media/jellyfin/*/. structure_progress.json`
   - Run structurer for serienstream: `python3 7_jellyfin_structurer.py`
   - Run structurer for aniworld: `python3 7_jellyfin_structurer.py`

4. **Setup Streaming API as Service**
   - Create systemd service for the API backend
   - Ensure it starts on boot
   - Configure to use the correct database files

5. **Jellyfin Library Scan**
   - Add libraries pointing to `/media/jellyfin/serienstream` and `/media/jellyfin/aniworld`
   - Disable metadata/image downloads (recommended)
   - Start scan

### Long-term Improvements
- Automate scraper updates (cron job)
- Monitor for expired streams
- Add logging and error handling
- Create backup/restore scripts
- Add rate limiting to API
- Implement caching for stream URLs

## GitHub Repository

- **Repo:** `git@github.com:Macro002/JellyStream.git`
- **SSH Key:** `~/.ssh/github_jellyfin`
- **Git Config:**
  - User: Macro002
  - Email: discordtesting209@gmail.com

### Pushing Changes
```bash
cd /root/projects/JellyStream
git add .
git commit -m "Description of changes"
GIT_SSH_COMMAND="ssh -i ~/.ssh/github_jellyfin -o IdentitiesOnly=yes" git push
```

## Troubleshooting

### Jellyfin won't start
- Check systemd status: `systemctl status jellyfin`
- Check logs: `journalctl -u jellyfin -n 50`
- Verify directories exist and have correct permissions

### Streams return 404
- Verify API is running: `curl http://localhost:3000/health`
- Check if episode ID exists in database
- Verify API is loading correct database files

### Progress file shows wrong count
- Delete progress file: `rm /media/jellyfin/{site}/.structure_progress.json`
- Rerun structurer script

### .strm files have wrong URLs
- Check `7_jellyfin_structurer.py` line 42 for correct `api_base_url`
- Regenerate all folders after fixing the URL

## Important Notes

- **Always backup database files before major changes**
- **Never commit database files to git** (they're 75-162 MB each)
- **The API must run on the Jellyfin server** (not the code server)
- **.strm files must use localhost URLs** since Jellyfin makes local requests
- **Each site has independent progress tracking** - don't mix them up

## Session History Context

This project was set up across multiple sessions:
1. Initial scraper development for SerienStream and Aniworld
2. Created automated structure generator
3. Built streaming API with provider support
4. Developed manual updater tool
5. Fixed hardcoded path bugs in structurer scripts
6. Set up GitHub repository for version control
7. Identified critical issue with wrong API URLs in .strm files

**Current blocker:** Need to rebuild Jellyfin LXC and regenerate all .strm files with correct localhost URLs.
