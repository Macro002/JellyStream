#!/usr/bin/env python3
"""
JSON Structurer
Combines all temp JSON files into final structured data
Input: data/tmp_name_url.json, data/tmp_season_episode_data.json, data/tmp_episode_streams.json
Output: data/final_series_data.json
set limit with [--limit] [num] flag.
"""

import json
import time
import re
from typing import Dict, List, Optional
from pathlib import Path
import config

class JSONStructurer:
    def __init__(self, limit: Optional[int] = None):
        self.limit = limit
        
        self.data_folder = Path(config.DATA_DIR)
        self.name_url_file = self.data_folder / "tmp_name_url.json"
        self.structure_file = self.data_folder / "tmp_season_episode_data.json"
        self.streams_file = self.data_folder / "tmp_episode_streams.json"
        self.output_file = self.data_folder / "final_series_data.json"
    
    def generate_jellyfin_name(self, series_name: str, start_date: str) -> str:
        """Generate a clean Jellyfin-compatible name with year"""
        clean_name = series_name.strip()
        
        # Extract year from start_date
        year = ""
        if start_date:
            year_match = re.search(r'(19|20)\d{2}', start_date)
            if year_match:
                year = year_match.group()
        
        # Check if name already has year in parentheses at end
        if re.search(r'\(\d{4}\)$', clean_name):
            # Already has year, check if we need to update it
            if year:
                existing_match = re.search(r'\((\d{4})\)$', clean_name)
                if existing_match and existing_match.group(1) != year:
                    # Replace with correct year
                    clean_name = re.sub(r'\s*\(\d{4}\)$', f' ({year})', clean_name)
            return clean_name.strip()
        else:
            # Add year if we have one
            if year:
                return f"{clean_name} ({year})"
            return clean_name
    
    def load_json_file(self, file_path: Path) -> Dict:
        """Load a JSON file safely"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return {}
    
    def structure_final_data(self, name_url_data: Dict, structure_data: Dict, streams_data: Dict) -> Dict:
        """Structure the final combined data"""
        print("🔧 Structuring final data...")
        
        # Create series lookup from streams data
        streams_lookup = {}
        for series in streams_data.get('series', []):
            series_name = series['name']
            streams_lookup[series_name] = series
        
        # Start with structure data as base
        final_series = []
        structure_series = structure_data.get('series', [])
        
        # Apply limit if set
        if self.limit:
            structure_series = structure_series[:self.limit]
            print(f"📊 Processing {len(structure_series)} series (limit applied)")
        else:
            print(f"📊 Processing {len(structure_series)} series (no limit)")
        
        for series in structure_series:
            series_name = series['name']
            series_url = series['url']
            
            # Get streams data for this series
            series_streams = streams_lookup.get(series_name, {})
            start_date = series_streams.get('start_date', '')
            
            # Generate Jellyfin-compatible name
            jellyfin_name = self.generate_jellyfin_name(series_name, start_date)
            
            # Build final series structure
            final_series_data = {
                'name': series_name,
                'jellyfin_name': jellyfin_name,
                'url': series_url,
                'genre': series.get('genre', 'Unknown'),
                'start_date': start_date,
                'has_movies': series.get('has_filme', False),
                'movie_count': series.get('movie_count', 0),
                'season_count': series.get('season_count', 0),
                'episode_counts': series.get('episode_counts', []),
                'total_episodes': series.get('total_episodes', 0),
                'total_content': series.get('total_content', 0),
                'movies': {},
                'seasons': {}
            }
            
            # Process movies if they exist
            if series.get('has_filme', False) and series_streams:
                series_movies = series_streams.get('movies', {})
                for movie_key, movie_data in series_movies.items():
                    final_series_data['movies'][movie_key] = {
                        'url': movie_data.get('url', ''),
                        'languages': movie_data.get('languages', {}),
                        'streams_by_language': movie_data.get('streams_by_language', {}),
                        'total_streams': movie_data.get('total_streams', 0)
                    }
            
            # Process seasons
            if series_streams:
                series_seasons = series_streams.get('seasons', {})
                for season_key, season_data in series_seasons.items():
                    final_season_data = {
                        'episode_count': season_data.get('episode_count', 0),
                        'episodes': {}
                    }
                    
                    # Process episodes
                    for episode_key, episode_data in season_data.get('episodes', {}).items():
                        final_season_data['episodes'][episode_key] = {
                            'url': episode_data.get('url', ''),
                            'languages': episode_data.get('languages', {}),
                            'streams_by_language': episode_data.get('streams_by_language', {}),
                            'total_streams': episode_data.get('total_streams', 0)
                        }
                    
                    final_series_data['seasons'][season_key] = final_season_data
            
            final_series.append(final_series_data)
        
        return final_series
    
    def run(self):
        """Run the JSON structuring process"""
        print("🚀 JSON Structurer")
        print(f"📂 Inputs: {self.name_url_file.name}, {self.structure_file.name}, {self.streams_file.name}")
        print(f"📂 Output: {self.output_file}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Load all input files
        print("📥 Loading input files...")
        name_url_data = self.load_json_file(self.name_url_file)
        structure_data = self.load_json_file(self.structure_file)
        streams_data = self.load_json_file(self.streams_file)
        
        if not all([name_url_data, structure_data, streams_data]):
            print("❌ Failed to load required input files!")
            return False
        
        print(f"✅ Catalog data: {len(name_url_data.get('series', []))} series")
        print(f"✅ Structure data: {len(structure_data.get('series', []))} series")
        print(f"✅ Streams data: {len(streams_data.get('series', []))} series")
        
        # Structure final data
        final_series = self.structure_final_data(name_url_data, structure_data, streams_data)
        
        # Calculate comprehensive statistics
        total_movies = sum(len(series.get('movies', {})) for series in final_series)
        total_episodes = sum(
            sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
            for series in final_series
        )
        total_streams = sum(
            # Count episode streams
            sum(
                sum(len(streams) for streams in episode.get('streams_by_language', {}).values())
                for season in series.get('seasons', {}).values()
                for episode in season.get('episodes', {}).values()
            ) + 
            # Count movie streams
            sum(
                sum(len(streams) for streams in movie.get('streams_by_language', {}).values())
                for movie in series.get('movies', {}).values()
            )
            for series in final_series
        )
        
        # Count languages and providers
        all_languages = set()
        all_providers = set()
        series_with_movies = sum(1 for series in final_series if series.get('has_movies', False))
        
        for series in final_series:
            # From movies
            for movie in series.get('movies', {}).values():
                for lang_name, streams in movie.get('streams_by_language', {}).items():
                    all_languages.add(lang_name)
                    for stream in streams:
                        all_providers.add(stream.get('provider', 'Unknown'))
            
            # From episodes
            for season in series.get('seasons', {}).values():
                for episode in season.get('episodes', {}).values():
                    for lang_name, streams in episode.get('streams_by_language', {}).items():
                        all_languages.add(lang_name)
                        for stream in streams:
                            all_providers.add(stream.get('provider', 'Unknown'))
        
        # Prepare comprehensive final output
        output_data = {
            # Script metadata
            'script': 'json_structurer',
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            
            # Source data metadata
            'source_data': {
                'catalog_script': name_url_data.get('script', 'unknown'),
                'catalog_scraped_at': name_url_data.get('scraped_at', ''),
                'structure_script': structure_data.get('script', 'unknown'),
                'structure_analyzed_at': structure_data.get('analyzed_at', ''),
                'streams_script': streams_data.get('script', 'unknown'),
                'streams_analyzed_at': streams_data.get('analyzed_at', '')
            },
            
            # Comprehensive statistics
            'statistics': {
                'total_series': len(final_series),
                'series_with_movies': series_with_movies,
                'total_movies': total_movies,
                'total_episodes': total_episodes,
                'total_content_items': total_movies + total_episodes,
                'total_streams': total_streams,
                'unique_languages': len(all_languages),
                'unique_providers': len(all_providers),
                'available_languages': sorted(list(all_languages)),
                'available_providers': sorted(list(all_providers))
            },
            
            # Original catalog metadata
            'catalog_metadata': {
                'total_genres': name_url_data.get('total_genres', 0),
                'genre_breakdown': name_url_data.get('genre_breakdown', {}),
                'series_added': name_url_data.get('series_added', 0)
            },
            
            # Structure metadata
            'structure_metadata': {
                'processing_errors': structure_data.get('processing_errors', 0),
                'total_content_analyzed': structure_data.get('total_content', 0)
            },
            
            # Streams metadata  
            'streams_metadata': {
                'total_endpoints_processed': streams_data.get('total_endpoints_processed', 0),
                'processing_errors': streams_data.get('processing_errors', 0)
            },
            
            # Main data
            'series': final_series
        }
        
        # Save final data
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            duration = time.time() - start_time
            file_size = self.output_file.stat().st_size / (1024 * 1024)
            
            print(f"\n⚡ {duration:.1f}s | {len(final_series)} series structured")
            print(f"🎬 {total_movies} movies | 📺 {total_episodes} episodes | 🔗 {total_streams} streams")
            print(f"🌍 {len(all_languages)} languages | 🎥 {len(all_providers)} providers")
            print(f"💾 Saved {file_size:.1f} MB to: {self.output_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving final data: {e}")
            return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='JSON Structurer')
    parser.add_argument('--limit', type=int, help='Limit number of series to process')
    args = parser.parse_args()
    
    # Use limit only if specified
    limit = args.limit
    
    structurer = JSONStructurer(limit=limit)
    
    try:
        success = structurer.run()
        print("✅ Structuring complete!" if success else "❌ Structuring failed!")
    except KeyboardInterrupt:
        print("🛑 Interrupted")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    main()