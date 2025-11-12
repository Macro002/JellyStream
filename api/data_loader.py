#!/usr/bin/env python3
"""
data_loader.py - Multi-site data loader for Jellyfin Streaming Platform
Supports loading data from multiple streaming sites (SerienStream, Aniworld, etc.)
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

class DataLoader:
    def __init__(self, json_files: List[str] = None, site_name: str = None):
        """
        Initialize multi-site data loader

        Args:
            json_files: List of JSON file paths to load (optional, auto-detects if None)
            site_name: Single site name to load (e.g., 'serienstream', 'aniworld')
        """
        if json_files is None:
            # Auto-detect all site JSON files
            json_files = self._find_all_json_files(site_name)

        self.json_files = json_files if isinstance(json_files, list) else [json_files]
        self.series_data = []  # Combined data from all sites
        self.redirect_lookup = {}  # redirect_id -> episode info for fast lookup
        self.site_stats = {}  # Per-site statistics

    def _find_all_json_files(self, site_name: str = None) -> List[str]:
        """Auto-detect all site JSON files or specific site"""
        script_dir = Path(__file__).parent
        project_root = script_dir.parent

        # If specific site requested, only load that one
        if site_name:
            site_data_file = project_root / f'sites/{site_name}/data/final_{site_name}_data.json'
            if site_data_file.exists():
                logging.info(f"Found {site_name} data: {site_data_file}")
                return [str(site_data_file)]
            else:
                raise FileNotFoundError(f"Site '{site_name}' data file not found: {site_data_file}")

        # Auto-detect all sites
        sites_dir = project_root / 'sites'
        json_files = []

        if sites_dir.exists():
            # Scan all site directories
            for site_dir in sites_dir.iterdir():
                if site_dir.is_dir():
                    # Look for final_*_data.json in site's data/ folder
                    data_dir = site_dir / 'data'
                    if data_dir.exists():
                        for json_file in data_dir.glob('final_*_data.json'):
                            json_files.append(str(json_file.resolve()))
                            logging.info(f"Found site data: {json_file.name} ({site_dir.name})")

        if not json_files:
            # Fallback: Try old single-file locations for backward compatibility
            legacy_paths = [
                script_dir / '../sites/serienstream/data/final_series_data.json',
                script_dir / '../data/final_series_data.json',
            ]
            for path in legacy_paths:
                if path.exists():
                    json_files.append(str(path.resolve()))
                    logging.info(f"Found legacy data: {path}")
                    break

        if not json_files:
            raise FileNotFoundError(
                f"No site data files found!\n"
                f"Searched in: {sites_dir}\n"
                f"Expected format: sites/<sitename>/data/final_*_data.json"
            )

        return json_files

    def load(self):
        """Load series data from all JSON files and build redirect lookup"""
        try:
            self.series_data = []

            for json_file in self.json_files:
                site_name = self._extract_site_name(json_file)
                logging.info(f"Loading {site_name} data from: {json_file}")

                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    site_series = data.get('series', [])

                    # Tag each series with its source site
                    for series in site_series:
                        series['_source_site'] = site_name

                    self.series_data.extend(site_series)

                    # Track per-site stats
                    self.site_stats[site_name] = {
                        'series_count': len(site_series),
                        'file_path': json_file
                    }

                    logging.info(f"  Loaded {len(site_series)} series from {site_name}")

            # Build fast lookup table
            self._build_redirect_lookup()

            logging.info(f"Total: {len(self.series_data)} series with {len(self.redirect_lookup)} redirect URLs across {len(self.site_stats)} sites")

        except Exception as e:
            logging.error(f"Failed to load data: {str(e)}")
            raise

    def _extract_site_name(self, json_file_path: str) -> str:
        """Extract site name from file path"""
        path = Path(json_file_path)
        # Try to extract from path: sites/<sitename>/data/final_*_data.json
        parts = path.parts
        if 'sites' in parts:
            site_idx = parts.index('sites')
            if site_idx + 1 < len(parts):
                return parts[site_idx + 1]

        # Fallback: extract from filename (final_<sitename>_data.json)
        filename = path.stem  # e.g., "final_series_data"
        if filename.startswith('final_') and filename.endswith('_data'):
            return filename[6:-5]  # Extract "series" from "final_series_data"

        return "unknown"

    def _build_redirect_lookup(self):
        """Build lookup table for redirect_id -> episode info"""
        self.redirect_lookup = {}

        for series_idx, series in enumerate(self.series_data):
            series_name = series.get('jellyfin_name', series.get('name', ''))
            source_site = series.get('_source_site', 'unknown')

            for season_key, season in series.get('seasons', {}).items():
                season_num = season_key.replace('season_', '')

                for episode_key, episode in season.get('episodes', {}).items():
                    episode_num = episode_key.replace('episode_', '')

                    # Extract redirect IDs from streams
                    for language, streams in episode.get('streams_by_language', {}).items():
                        for stream in streams:
                            stream_url = stream.get('stream_url', '')
                            if '/redirect/' in stream_url:
                                redirect_id = stream_url.split('/redirect/')[-1]

                                self.redirect_lookup[redirect_id] = {
                                    'series_idx': series_idx,
                                    'series_name': series_name,
                                    'season_num': season_num,
                                    'episode_num': episode_num,
                                    'language': language,
                                    'provider': stream.get('provider', ''),
                                    'source_site': source_site,
                                    'episode_data': episode
                                }

    def find_episode_by_redirect(self, redirect_id: str) -> Optional[Dict]:
        """Find episode info by redirect ID"""
        return self.redirect_lookup.get(redirect_id)

    def get_season_episodes(self, series_idx: int, season_num: str) -> List[Dict]:
        """Get all episodes in a season that have streams"""
        if series_idx >= len(self.series_data):
            return []

        series = self.series_data[series_idx]
        season_key = f"season_{season_num}"
        season = series.get('seasons', {}).get(season_key, {})

        episodes = []
        for episode_key, episode in season.get('episodes', {}).items():
            episode_num = episode_key.replace('episode_', '')

            # Only include episodes with streams
            if episode.get('total_streams', 0) > 0:
                # Get first available redirect (prefer Deutsch)
                redirect_id = None
                provider = None

                # Try Deutsch first
                german_streams = episode.get('streams_by_language', {}).get('Deutsch', [])
                if german_streams:
                    stream_url = german_streams[0].get('stream_url', '')
                    if '/redirect/' in stream_url:
                        redirect_id = stream_url.split('/redirect/')[-1]
                        provider = german_streams[0].get('provider', '')

                # Fallback to any language
                if not redirect_id:
                    for language, streams in episode.get('streams_by_language', {}).items():
                        if streams:
                            stream_url = streams[0].get('stream_url', '')
                            if '/redirect/' in stream_url:
                                redirect_id = stream_url.split('/redirect/')[-1]
                                provider = streams[0].get('provider', '')
                                break

                if redirect_id:
                    episodes.append({
                        'episode_num': episode_num,
                        'redirect_id': redirect_id,
                        'provider': provider,
                        'url': episode.get('url', '')
                    })

        return episodes

    def get_series_count(self) -> int:
        """Get total number of series"""
        return len(self.series_data)

    def get_redirect_count(self) -> int:
        """Get total number of redirect URLs"""
        return len(self.redirect_lookup)

    def get_stats(self) -> Dict:
        """Get data statistics"""
        provider_counts = {}
        language_counts = {}

        for redirect_info in self.redirect_lookup.values():
            provider = redirect_info.get('provider', 'Unknown')
            language = redirect_info.get('language', 'Unknown')

            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            language_counts[language] = language_counts.get(language, 0) + 1

        return {
            'total_series': len(self.series_data),
            'total_redirects': len(self.redirect_lookup),
            'providers': provider_counts,
            'languages': language_counts,
            'sites': self.site_stats
        }
