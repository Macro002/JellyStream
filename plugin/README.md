# JellyStream Jellyfin Plugin

Manual updater plugin for Aniworld and SerienStream series.

## Features

- **Manual Series Updater**: Plugin interface to update series streams on-demand
- **Python Script Integration**: Uses existing Python scrapers from /opt/JellyStream
- **Dual Site Support**: Works with both Aniworld and SerienStream
- **Automatic .strm Regeneration**: Updates database and regenerates .strm files in one click

## Building the Plugin

### Prerequisites

- .NET 8.0 SDK
- Jellyfin 10.9.x
- Python 3.11+ with dependencies (already installed on Jellyfin server)
- JellyStream project at /opt/JellyStream on Jellyfin server

### Build Steps

```bash
cd plugin/JellyStream
dotnet restore
dotnet build --configuration Release
```

This will create a DLL at: `bin/Release/net8.0/JellyStream.dll`

## Installation

1. **Build the plugin** (see above)

2. **Copy to Jellyfin plugins directory:**
   ```bash
   # On Debian/Ubuntu
   sudo mkdir -p /var/lib/jellyfin/plugins/JellyStream
   sudo cp bin/Release/net8.0/* /var/lib/jellyfin/plugins/JellyStream/
   ```

3. **Restart Jellyfin:**
   ```bash
   sudo systemctl restart jellyfin
   ```

4. **Configure the plugin:**
   - Go to Jellyfin Dashboard → Plugins → JellyStream
   - Verify paths are correct:
     - Aniworld Data: `/opt/JellyStream/sites/aniworld/data/final_series_data.json`
     - SerienStream Data: `/opt/JellyStream/sites/serienstream/data/final_series_data.json`
     - Aniworld Jellyfin Path: `/media/jellyfin/aniworld`
     - SerienStream Jellyfin Path: `/media/jellyfin/serienstream`

## Usage

1. Navigate to: **Dashboard → Plugins → JellyStream**

2. Select site (Aniworld or SerienStream)

3. Search for the series you want to update

4. Click **Update Series** button

5. Wait for completion (shows progress and results)

## How It Works

### Update Flow

1. User selects series from plugin UI in Jellyfin
2. Plugin finds series in database at /opt/JellyStream
3. Creates temporary catalog with single series
4. Runs Python scraper scripts sequentially:
   - `2_url_season_episode_num.py` - Analyzes season/episode structure
   - `3_language_streamurl.py` - Extracts stream URLs and languages
   - `4_json_structurer.py` - Structures the data
5. Updates the series entry in main database
6. Regenerates .strm files in /media/jellyfin/{site}/
7. Returns success status to UI

### Architecture

- **Plugin**: C# Jellyfin plugin (this project)
- **Scrapers**: Python scripts at /opt/JellyStream/sites/{site}/
- **Database**: JSON files at /opt/JellyStream/sites/{site}/data/
- **Media Files**: .strm files at /media/jellyfin/{site}/

## Development

### Project Structure

```
JellyStream/
├── Plugin.cs                      # Main plugin entry point
├── Configuration/
│   └── PluginConfiguration.cs     # Settings model (paths)
├── Api/
│   ├── SeriesController.cs        # List series endpoint
│   ├── UpdateController.cs        # Update series endpoint (calls Python)
│   └── StrmRegenerator.cs         # .strm file generator
└── Web/
    ├── index.html                 # Plugin UI
    ├── jellystream.js             # Frontend logic
    └── jellystream.css            # Styling
```

### API Endpoints

- `GET /JellyStream/Series/List?site={aniworld|serienstream}` - Get all series
- `POST /JellyStream/Update/Series?name={name}&site={site}` - Update a series

## Troubleshooting

**Plugin doesn't appear in Jellyfin:**
- Check Jellyfin logs: `/var/log/jellyfin/`
- Verify .NET 8.0 is installed
- Ensure file permissions are correct

**Update fails:**
- Check that database paths are correct in plugin settings
- Verify network connectivity to aniworld.to / serienstream.to
- Check Jellyfin logs for detailed error messages

**No .strm files created:**
- Verify Jellyfin media paths are correct
- Check file system permissions
- Ensure redirect IDs are being extracted correctly

## License

Part of the JellyStream project.
