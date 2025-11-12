#!/usr/bin/env python3
"""
Aniworld Site Configuration
"""

# Site settings
SITE_NAME = "Aniworld"
BASE_URL = "https://aniworld.to"

# Data paths (relative to this file)
DATA_DIR = "data"
LOGS_DIR = "logs"

# Output files
CATALOG_OUTPUT = f"{DATA_DIR}/tmp_name_url.json"
SEASON_EPISODE_OUTPUT = f"{DATA_DIR}/tmp_season_episode_data.json"
STREAMS_OUTPUT = f"{DATA_DIR}/tmp_episode_streams.json"
FINAL_OUTPUT = f"{DATA_DIR}/final_aniworld_data.json"

# Jellyfin settings
JELLYFIN_OUTPUT_DIR = "/media/jellyfin/aniworld"

# Language priority (anime-specific)
# Aniworld has: German (dub), German Sub, English Sub
LANGUAGE_PRIORITY = ["Deutsch", "German Sub", "English Sub"]

# Provider priority (anime-specific)
# Aniworld typically has: VOE, Filemoon, Vidmoly
PROVIDER_PRIORITY = ["VOE", "Filemoon", "Vidmoly"]

# Scraping settings
REQUEST_DELAY = 0.5  # seconds between requests
BATCH_SIZE = 100  # series per batch
RETRY_COUNT = 3

# Logging
LOG_LEVEL = "INFO"
