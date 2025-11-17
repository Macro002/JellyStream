# JellyStream Jellyfin Plugin

Jellyfin plugin interface for the manual_updater.py script.

## Features

- **Simple Wrapper**: Calls `utils/manual_updater.py` in plugin mode
- **Search Interface**: Search for series via Jellyfin UI
- **One-Click Updates**: Update series streams on-demand
- **Dual Site Support**: Works with both Aniworld and SerienStream
- **Automatic Everything**: All scraping, database updates, and .strm regeneration handled by Python script

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

### Architecture

The plugin is a **thin wrapper** around `manual_updater.py`:

```
Jellyfin UI → Plugin API → manual_updater.py → Database + .strm files
```

### Update Flow

1. User searches for series in Jellyfin plugin UI
2. Plugin calls: `python3 manual_updater.py --plugin --site X --search "query"`
3. User clicks "Update" on a series
4. Plugin calls: `python3 manual_updater.py --plugin --site X --series-name "Name" --json`
5. `manual_updater.py` handles everything:
   - Runs Python scraper scripts (2, 3, 4)
   - Updates database
   - Regenerates .strm files
   - Returns JSON result
6. Plugin parses JSON and shows result in UI

### Files

- **Plugin**: `/var/lib/jellyfin/plugins/JellyStream_1.0.0.0/` (C#)
- **Script**: `/opt/JellyStream/utils/manual_updater.py` (Python)
- **Scrapers**: `/opt/JellyStream/sites/{site}/` (Python)
- **Database**: `/opt/JellyStream/sites/{site}/data/final_series_data.json`
- **Media**: `/media/jellyfin/{site}/` (.strm files)

## Development

### Project Structure

```
JellyStream/
├── Plugin.cs                      # Main plugin entry point
├── Configuration/
│   └── PluginConfiguration.cs     # Settings model (paths)
├── Api/
│   ├── SeriesController.cs        # Search endpoint → calls manual_updater.py
│   └── UpdateController.cs        # Update endpoint → calls manual_updater.py
└── Web/
    ├── index.html                 # Plugin UI
    ├── jellystream.js             # Frontend logic
    └── jellystream.css            # Styling
```

### API Endpoints

- `GET /JellyStream/Series/Search?site={site}&query={text}` - Search for series
- `POST /JellyStream/Update/Series?name={name}&site={site}` - Update a series

Both endpoints call `manual_updater.py` with appropriate flags.

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
