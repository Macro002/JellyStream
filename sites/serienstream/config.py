#!/usr/bin/env python3
"""
SerienStream Site Configuration
"""

# Site settings
SITE_NAME = "SerienStream"
BASE_URL = "https://serienstream.to"

# Data paths (relative to this file)
DATA_DIR = "data"
LOGS_DIR = "logs"

# Output files
CATALOG_OUTPUT = f"{DATA_DIR}/tmp_name_url.json"
SEASON_EPISODE_OUTPUT = f"{DATA_DIR}/tmp_season_episode_data.json"
STREAMS_OUTPUT = f"{DATA_DIR}/tmp_episode_streams.json"
FINAL_OUTPUT = f"{DATA_DIR}/final_series_data.json"

# Jellyfin settings
JELLYFIN_OUTPUT_DIR = "/media/jellyfin/serienstream"

# Language priority (used by structurer)
LANGUAGE_PRIORITY = ["Deutsch", "Englisch", "mit deutschen Untertiteln"]

# Provider priority
PROVIDER_PRIORITY = ["VOE", "Vidoza", "Streamtape"]

# Scraping settings
REQUEST_DELAY = 0.5  # seconds between requests
BATCH_SIZE = 100  # series per batch
RETRY_COUNT = 3

# Logging
LOG_LEVEL = "INFO"
