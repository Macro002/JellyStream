# JellyStream

A unified platform for streaming German series and anime through Jellyfin, with automated scraping, multi-site support, and a streaming API backend.

## Overview

JellyStream scrapes German streaming sites (SerienStream and Aniworld) for TV series and anime metadata, generates Jellyfin-compatible folder structures with .strm files, and provides a streaming API to serve the content.

### Current Status

**SerienStream** (Series): ✅ Implemented
- **10,276 series** indexed
- **253,972 episodes** + **1,603 movies**
- **Providers:** VOE, Vidoza, Doodstream
- **Languages:** German, English, German Subs

**Aniworld** (Anime): ✅ Implemented
- **2,279 series** indexed
- **26,795 episodes** + **695 movies**
- **Providers:** VOE, Vidoza
- **Languages:** German (dub), German Sub, English Sub

**FlareSolverr Integration**: 🚧 In Progress
- Cloudflare bypass for protected sites
- Currently being integrated for future-proofing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│          Source Sites (SerienStream, Aniworld)              │
│          serienstream.to  |  aniworld.to                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│         Site-Specific Scraping Pipelines                    │
│  sites/serienstream/        sites/aniworld/                 │
│  1. Catalog Scraper         1. Catalog Scraper              │
│  2. Season/Episode          2. Season/Episode               │
│  3. Language/Streams        3. Language/Streams             │
│  4. JSON Structurer         4. JSON Structurer              │
│  → final_series_data.json   → final_anime_data.json         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Jellyfin Structure Generators                  │
│  - Creates folder hierarchy per site                        │
│  - Generates .strm files with site-prefixed IDs             │
│  - Language prioritization per site                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Unified Streaming API                          │
│  - Flask-based multi-site API                               │
│  - Loads all site databases                                 │
│  - Multi-provider support (VOE, Vidoza, Filemoon, Vidmoly)  │
│  - HLS stream caching (1 hour)                              │
│  - Running on: http://192.168.1.153:3000                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Jellyfin Server                          │
│  - Multiple libraries (Series, Anime)                       │
│  - Plays .strm files via unified API                        │
│  - Running on: http://192.168.1.161:8096                    │
│  - Stack fix applied for large libraries (8MB thread stack) │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
JellyStream/
├── README.md                  # This file
├── SETUP.md                   # Detailed setup guide and troubleshooting
│
├── sites/                     # Site-specific scrapers
│   ├── serienstream/          # German series (10,276 series)
│   │   ├── 1_catalog_scraper.py
│   │   ├── 2_url_season_episode_num.py
│   │   ├── 3_language_streamurl.py
│   │   ├── 4_json_structurer.py
│   │   ├── 5_updater.py
│   │   ├── 6_main.py
│   │   ├── 7_jellyfin_structurer.py
│   │   ├── config.py         # Site-specific config
│   │   └── data/
│   │       └── final_series_data.json (162MB - not in git)
│   │
│   └── aniworld/             # Anime (2,279 series)
│       ├── 1-7_*.py          # Same pipeline structure
│       ├── config.py
│       └── data/
│           └── final_series_data.json (75MB - not in git)
│
├── api/                      # Unified streaming API
│   ├── main.py              # Flask server (multi-site support)
│   ├── data_loader.py       # Multi-database loader
│   ├── redirector.py        # Redirect resolver
│   ├── providers/           # Streaming providers
│   │   ├── voe.py          # VOE (both sites)
│   │   └── vidoza.py       # Vidoza (both sites)
│   └── downloader/
│       └── voe_dl.py       # VOE direct downloader
│
├── utils/                   # Shared utilities
│   └── manual_updater.py   # Interactive CLI for updating series
│
├── backup/                  # Database backups (not in git)
│
└── docs/                    # Documentation
    ├── TODO.md             # Project roadmap
    └── JELLYFIN_STACK_FIX.md  # Fix for large libraries
```

## Components

### 1. Site-Specific Scrapers

Each site in `sites/<sitename>/` follows the same pipeline:

1. **1_catalog_scraper.py** - Scrapes catalog (name, URL, year)
2. **2_url_season_episode_num.py** - Gets season/episode structure
3. **3_language_streamurl.py** - Fetches stream URLs per episode/language
4. **4_json_structurer.py** - Combines into final database
5. **5_updater.py** - Updates database with new content
6. **6_main.py** - Runs full pipeline
7. **7_jellyfin_structurer.py** - Generates Jellyfin folder structure

**Site Configs:**
- `config.py` - Site-specific settings (URL, languages, providers, paths)

### 2. Unified Streaming API

Located in `api/`:

**Core Files:**
- `main.py` - Flask API server with multi-site support
- `data_loader.py` - Loads all site databases
- `redirector.py` - Resolves stream redirects
- `providers/*.py` - Provider-specific stream extractors

**Endpoints:**
- `GET /stream/redirect/<id>` - Main streaming endpoint
- `GET /health` - API health check
- `GET /stats` - API statistics
- `GET /info/<id>` - Debug info for redirect ID
- `GET /test/<id>` - Test redirect resolution
- `GET /clear-cache` - Clear stream cache

**Multi-Site Support:**
- Automatically loads all `final_*_data.json` files from site directories
- Routes redirects to appropriate site based on ID
- Shared provider pool across all sites

### 3. Jellyfin Integration

**SerienStream Library:**
- Media directory: `/media/jellyfin/serienstream/`
- Structure: `Series Name (Year)/Season XX/Episode.strm`
- .strm files point to: `http://localhost:3000/stream/redirect/[id]`

**Aniworld Library:**
- Media directory: `/media/jellyfin/aniworld/`
- Structure: `Anime Name (Year)/Season XX/Episode.strm`
- .strm files point to: `http://localhost:3000/stream/redirect/[id]`

**Stack Overflow Fix:**
For large libraries (8,000+ series), apply Jellyfin stack fix:
```bash
mkdir -p /etc/systemd/system/jellyfin.service.d
cat > /etc/systemd/system/jellyfin.service.d/stack-size.conf << 'EOF'
[Service]
Environment="DOTNET_DefaultStackSize=8000000"
Environment="COMPlus_DefaultStackSize=8000000"
LimitSTACK=infinity
EOF

systemctl daemon-reload
systemctl restart jellyfin
```

See [docs/JELLYFIN_STACK_FIX.md](docs/JELLYFIN_STACK_FIX.md) for details.

## Quick Start

### Prerequisites

- Python 3.11+
- Jellyfin server
- 200MB+ disk space for databases

### 1. Install Dependencies

```bash
pip3 install flask requests beautifulsoup4
```

### 2. Run Scrapers (SerienStream Example)

```bash
cd sites/serienstream

# Test with small sample
python3 6_main.py --limit 10

# Full scrape (takes several hours)
python3 6_main.py
```

### 3. Generate Jellyfin Structure

```bash
cd sites/serienstream
python3 7_jellyfin_structurer.py --api-url http://192.168.1.153:3000/stream/redirect
```

### 4. Start Streaming API

```bash
cd api
python3 main.py

# Or install as systemd service (recommended)
# See deployment section below
```

### 5. Add Library to Jellyfin

1. Open Jellyfin: `http://192.168.1.161:8096`
2. Go to: Dashboard → Libraries → Add Library
3. Content type: TV Shows
4. Folder: `/media/jellyfin/serienstream`
5. Disable metadata downloads (recommended for performance)
6. Scan library

## Usage

### Update Series Database

```bash
cd sites/serienstream

# Update with new episodes only
python3 5_updater.py

# Full re-scrape
python3 6_main.py
```

### Monitor Streaming API

```bash
# Check API health
curl http://192.168.1.153:3000/health

# View statistics
curl http://192.168.1.153:3000/stats

# Test specific redirect
curl http://192.168.1.153:3000/test/<redirect_id>
```

## Deployment (Production)

### Deploy API as Systemd Service

```bash
# Copy API to /opt
sudo cp -r api /opt/streaming-api

# Create systemd service
sudo cat > /etc/systemd/system/streaming-api.service << 'EOF'
[Unit]
Description=Multi-Site Streaming API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/streaming-api
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /opt/streaming-api/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable streaming-api
sudo systemctl start streaming-api
sudo systemctl status streaming-api
```

## Adding New Sites

To add a new site (e.g., `aniworld`):

```bash
# 1. Clone serienstream structure
cp -r sites/serienstream sites/aniworld

# 2. Update config.py
cd sites/aniworld
nano config.py  # Change SITE_NAME, BASE_URL, language/provider priorities

# 3. Adapt scrapers to new site's HTML structure
# Modify selectors in 1_catalog_scraper.py, 2_*.py, 3_*.py as needed

# 4. Run pipeline
python3 6_main.py --limit 10  # Test first

# 5. API will auto-detect new database
cd ../../api
python3 main.py  # Loads both serienstream + aniworld databases
```

## Data Structure

### Site Database Format

Each site produces a `final_*_data.json` file:

```json
{
  "series": [
    {
      "name": "Series Name",
      "jellyfin_name": "Series Name (2020)",
      "url": "https://site.to/serie/stream/...",
      "seasons": {
        "season_1": {
          "episodes": {
            "episode_1": {
              "streams_by_language": {
                "Deutsch": [
                  {
                    "provider": "VOE",
                    "stream_url": "https://site.to/redirect/xyz123"
                  }
                ]
              }
            }
          }
        }
      }
    }
  ]
}
```

### Language Priority

**SerienStream:**
1. Deutsch (German audio)
2. Englisch (English audio)
3. mit deutschen Untertiteln (German subs)

**Aniworld:**
1. Deutsch (German dub)
2. German Sub (German subs)
3. English Sub (English subs)

### Provider Priority

**SerienStream:** VOE → Vidoza → Doodstream

**Aniworld:** VOE → Filemoon → Vidmoly

## Performance

### Scraping
- **Catalog:** ~2-3 requests/sec
- **Episodes:** ~1-2 requests/sec
- **Full scrape (10K series):** 8-12 hours

### API
- **Direct redirects:** <100ms
- **Stream resolution:** 1-3 seconds (cached 1 hour)
- **Concurrent streams:** 50-100 simultaneous

### Jellyfin Scan
- **Small (<1K series):** 5-15 minutes
- **Large (10K+ series):** 2-6 hours (requires stack fix)

## Troubleshooting

### API Won't Start

```bash
# Check if data files exist
ls sites/*/data/final_*.json

# Test data loader manually
cd api
python3 -c "from data_loader import DataLoader; loader = DataLoader(); loader.load()"
```

### Scrapers Fail

```bash
# Check site availability
curl https://serienstream.to

# Test with small limit first
python3 6_main.py --limit 5
```

### Jellyfin Stack Overflow

Apply stack fix (see Quick Start section 3 or [docs/JELLYFIN_STACK_FIX.md](docs/JELLYFIN_STACK_FIX.md))

### Streams Not Playing

```bash
# Verify API is running
curl http://192.168.1.153:3000/health

# Test specific redirect
curl http://192.168.1.153:3000/test/<redirect_id>

# Check API logs
tail -f api/logs/streaming_api.log
```

## Future Plans

See [docs/TODO.md](docs/TODO.md) for detailed roadmap.

**In Progress:**
- FlareSolverr integration for Cloudflare bypass
- Jellyfin LXC rebuild with proper localhost configuration

**Planned:**
- Additional providers (Filemoon, Vidmoly, Streamtape)
- Automatic daily updates (cron jobs)
- Web dashboard for monitoring
- Stream health checking and auto-updates

## License

Personal project - Use at your own risk.

## Disclaimer

This project is for educational purposes. Ensure you comply with all applicable laws and terms of service when using this software.
