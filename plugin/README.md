# JellyStream Jellyfin Plugin

Manual updater plugin for Aniworld and SerienStream series.

## Features

- **Manual Series Updater**: Web UI to update series streams on-demand
- **Native C# Implementation**: No Python dependencies, all scraping logic ported to C#
- **Dual Site Support**: Works with both Aniworld and SerienStream
- **Automatic .strm Regeneration**: Updates database and regenerates .strm files in one click

## Building the Plugin

### Prerequisites

- .NET 8.0 SDK
- Jellyfin 10.9.x

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

1. Loads series database from JSON file
2. Scrapes all episodes from the source site
3. Extracts new stream URLs and languages
4. Updates database with new stream data
5. Regenerates .strm files with fresh redirect IDs
6. Shows summary of updated episodes

### Scraping Logic

- **Aniworld**: Scrapes from `aniworld.to`, extracts language mappings and hoster links
- **SerienStream**: Scrapes from `serienstream.to`, similar extraction logic
- **Language Priority**: Deutsch → German Sub → English Sub (configurable in code)

## Development

### Project Structure

```
JellyStream/
├── Plugin.cs                      # Main plugin entry point
├── Configuration/
│   └── PluginConfiguration.cs     # Settings model
├── Api/
│   ├── SeriesController.cs        # List series endpoint
│   └── UpdateController.cs        # Update series endpoint
├── Scrapers/
│   ├── AniworldUpdater.cs         # Aniworld scraping logic
│   ├── SerienstreamUpdater.cs     # SerienStream scraping logic
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
