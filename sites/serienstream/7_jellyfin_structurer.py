#!/usr/bin/env python3
"""
structure_generator.py - Creates Jellyfin folder structure with .strm files

Usage:
    python structure_generator.py                    # Process all remaining series
    python structure_generator.py --limit 500        # Process next 500 series
    python structure_generator.py -b 250             # Use batch size of 250
    python structure_generator.py --wait 3           # Wait 3 minutes between series
    python structure_generator.py --clear-progress   # Start fresh

Flags:
    --limit [num]       Set limit of series to process from remaining unprocessed
    -b [num]           Set batch processing size (default: 1000)
    --wait [num]       Wait time in minutes between series for Jellyfin metadata
    --clear-progress   Clear previous progress and start from beginning
    --api-url [url]    Set custom API URL (default: http://localhost:3000/api/stream/redirect)

Features:
    - Automatically resumes where it left off (no manual start-from needed)
    - Creates movies in Season 00 folders
    - Monitors disk space and aborts at 90% to prevent disk full
    - Single language selection (set in code)
    - Progress tracking with crash recovery
"""

import os
import json
import logging
import time
import shutil
from pathlib import Path
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class JellyfinStructureGenerator:
    def __init__(self, output_dir=None, api_base_url="http://localhost:3000/api/stream/redirect"):
        self.output_dir = Path(output_dir) if output_dir else Path(config.JELLYFIN_OUTPUT_DIR)
        self.api_base_url = api_base_url
        self.series_data = []
        
        # === LANGUAGE SETTING (CHANGE HERE) ===
        # Priority system: German first, then English, then German Subtitles
        self.LANGUAGE_PRIORITY = [
            "Deutsch",                    # 1st priority: German audio
            "Englisch",                   # 2nd priority: English audio  
            "mit deutschen Untertiteln"   # 3rd priority: German subtitles
        ]
        
        # Alternative: Single language only (uncomment to use)
        # self.GERMAN_ONLY = True
        # self.ENGLISH_ONLY = False  
        # self.GERMAN_SUB_ONLY = False
        
        # Progress tracking
        self.progress_file = self.output_dir / '.structure_progress.json'
        self.processed_series = set()
        
        # Statistics with language breakdown
        self.stats = {
            'series_processed': 0,
            'series_created': 0,
            'seasons_created': 0,
            'episodes_created': 0,
            'movies_created': 0,
            'episodes_skipped_no_streams': 0,
            'episodes_skipped_no_language': 0,
            'movies_skipped_no_streams': 0,
            'movies_skipped_no_language': 0,
            'episodes_by_language': {'Deutsch': 0, 'Englisch': 0, 'mit deutschen Untertiteln': 0},
            'movies_by_language': {'Deutsch': 0, 'Englisch': 0, 'mit deutschen Untertiteln': 0},
            'errors': 0,
            'last_disk_check': 0
        }
    
    def find_json_file(self):
        """Find the series data JSON file"""
        script_dir = Path(__file__).parent
        possible_paths = [
            script_dir / 'data/final_series_data.json',
            Path('data/final_series_data.json'),
            Path('./final_series_data.json'),
            Path.cwd() / 'data/final_series_data.json'
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path.resolve())
        
        raise FileNotFoundError(f"Could not find final_series_data.json. Tried: {[str(p) for p in possible_paths]}")
    
    def load_data(self):
        """Load series data from JSON"""
        json_file = self.find_json_file()
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.series_data = data.get('series', [])
        
        logging.info(f"Loaded {len(self.series_data)} series from {json_file}")
    
    def load_progress(self):
        """Load previous progress"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    self.processed_series = set(progress.get('processed_series', []))
                return True
            except Exception as e:
                logging.warning(f"Could not load progress: {e}")
        return False
    
    def save_progress(self, series_name):
        """Save progress after each series"""
        self.processed_series.add(series_name)
        
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            progress = {
                'processed_series': list(self.processed_series),
                'total_processed': len(self.processed_series)
            }
            with open(self.progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save progress: {e}")
    
    def clear_progress(self):
        """Clear progress file"""
        if self.progress_file.exists():
            self.progress_file.unlink()
            print("🗑️  Progress cleared")
    
    def check_disk_space(self):
        """Check disk space and warn if > 90%"""
        try:
            total, used, free = shutil.disk_usage(self.output_dir)
            usage_percent = (used / total) * 100
            
            # Show disk status periodically
            current_time = time.time()
            if (current_time - self.stats['last_disk_check'] > 600) or usage_percent > 85:
                print(f"💾 Disk usage: {usage_percent:.1f}% ({used//1024//1024//1024}GB / {total//1024//1024//1024}GB)")
                self.stats['last_disk_check'] = current_time
            
            if usage_percent > 90:
                print(f"🚨 DISK CRITICAL: {usage_percent:.1f}% full! Aborting.")
                return False
        except Exception as e:
            logging.warning(f"Could not check disk space: {e}")
        
        return True
    
    def sanitize_filename(self, filename):
        """Clean filename for filesystem"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename.strip(' .')[:200] or "Unknown"
    
    def get_best_redirect(self, content_data):
        """Get best redirect URL with language priority fallback"""
        streams_by_language = content_data.get('streams_by_language', {})
        
        # Try languages in priority order
        for language in self.LANGUAGE_PRIORITY:
            language_streams = streams_by_language.get(language, [])
            if not language_streams:
                continue
            
            # Found streams in this language - try providers in order
            for provider in ['VOE', 'Vidoza', 'Doodstream']:
                for stream in language_streams:
                    if stream.get('provider') == provider:
                        stream_url = stream.get('stream_url', '')
                        if '/redirect/' in stream_url:
                            redirect_id = stream_url.split('/redirect/')[-1]
                            return redirect_id, language  # Return both redirect and which language was used
            
            # If no preferred provider, use any redirect from this language
            for stream in language_streams:
                stream_url = stream.get('stream_url', '')
                if '/redirect/' in stream_url:
                    redirect_id = stream_url.split('/redirect/')[-1]
                    return redirect_id, language
        
        # No streams found in any priority language
        available_languages = list(streams_by_language.keys())
        return None, available_languages
    
    def create_strm_file(self, strm_path, redirect_id):
        """Create a .strm file"""
        try:
            stream_url = f"{self.api_base_url}/{redirect_id}"
            with open(strm_path, 'w', encoding='utf-8') as f:
                f.write(stream_url)
            return True
        except Exception as e:
            logging.error(f"Error creating {strm_path}: {e}")
            self.stats['errors'] += 1
            return False
    
    def process_movies(self, series_dir, movies_data):
        """Process movies (Season 00)"""
        if not movies_data:
            return
        
        season_dir = series_dir / "Season 00"
        season_dir.mkdir(parents=True, exist_ok=True)
        
        movies_created = 0
        for movie_key, movie_data in movies_data.items():
            movie_num = movie_key.replace('movie_', '')
            
            # Check if movie has streams
            if movie_data.get('total_streams', 0) == 0:
                self.stats['movies_skipped_no_streams'] += 1
                continue
            
            # Get redirect for priority languages
            redirect_id, used_language = self.get_best_redirect(movie_data)
            if not redirect_id:
                self.stats['movies_skipped_no_language'] += 1
                continue
            
            # Track which language was used
            if isinstance(used_language, str):
                self.stats['movies_by_language'][used_language] += 1
            
            # Create .strm file
            strm_path = season_dir / f"S00E{movie_num.zfill(2)}.strm"
            if self.create_strm_file(strm_path, redirect_id):
                self.stats['movies_created'] += 1
                movies_created += 1
        
        if movies_created > 0:
            self.stats['seasons_created'] += 1
    
    def process_episodes(self, series_dir, seasons_data):
        """Process regular episodes"""
        if not seasons_data:
            return
        
        for season_key, season_data in seasons_data.items():
            season_num = season_key.replace('season_', '')
            season_dir = series_dir / f"Season {season_num.zfill(2)}"
            season_dir.mkdir(parents=True, exist_ok=True)
            
            episodes_data = season_data.get('episodes', {})
            if not episodes_data:
                continue
            
            episodes_created = 0
            for episode_key, episode_data in episodes_data.items():
                episode_num = episode_key.replace('episode_', '')
                
                # Check if episode has streams
                if episode_data.get('total_streams', 0) == 0:
                    self.stats['episodes_skipped_no_streams'] += 1
                    continue
                
                # Get redirect for priority languages
                redirect_id, used_language = self.get_best_redirect(episode_data)
                if not redirect_id:
                    self.stats['episodes_skipped_no_language'] += 1
                    continue
                
                # Track which language was used
                if isinstance(used_language, str):
                    self.stats['episodes_by_language'][used_language] += 1
                
                # Create .strm file
                strm_path = season_dir / f"S{season_num.zfill(2)}E{episode_num.zfill(2)}.strm"
                if self.create_strm_file(strm_path, redirect_id):
                    self.stats['episodes_created'] += 1
                    episodes_created += 1
            
            if episodes_created > 0:
                self.stats['seasons_created'] += 1
    
    def process_series(self, series_data, series_idx, total_series):
        """Process a single series"""
        series_name = series_data.get('jellyfin_name', series_data.get('name', 'Unknown'))
        safe_name = self.sanitize_filename(series_name)
        series_dir = self.output_dir / safe_name
        
        # Progress display
        if series_idx % 100 == 0 or series_idx <= 10:
            print(f"📺 [{series_idx}/{total_series}] {safe_name}")
        
        # Create series directory
        series_dir.mkdir(parents=True, exist_ok=True)
        
        # Process movies (Season 00)
        movies_data = series_data.get('movies', {})
        self.process_movies(series_dir, movies_data)
        
        # Process regular episodes
        seasons_data = series_data.get('seasons', {})
        self.process_episodes(series_dir, seasons_data)
        
        # Count as processed
        self.stats['series_processed'] += 1
        if movies_data or seasons_data:
            self.stats['series_created'] += 1
    
    def generate_structure(self, limit=None, batch_size=1000, wait_minutes=0):
        """Main generation function"""
        print("🚀 Starting Jellyfin structure generation...")
        print("🌍 Language Priority: German → English → German Subtitles")
        
        # Load data and progress
        self.load_data()
        self.load_progress()
        
        # Find remaining series to process
        remaining_series = []
        for series in self.series_data:
            series_name = series.get('jellyfin_name', series.get('name', ''))
            if series_name not in self.processed_series:
                remaining_series.append(series)
        
        if limit:
            remaining_series = remaining_series[:limit]
        
        total_series = len(self.series_data)
        already_processed = len(self.processed_series)
        remaining_count = len(remaining_series)
        
        print(f"📊 Total series: {total_series:,}")
        print(f"✅ Already processed: {already_processed:,}")
        print(f"⏳ Remaining: {remaining_count:,}")
        
        if remaining_count == 0:
            print("🎉 All series already processed!")
            return
        
        # Create output directory and check disk
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if not self.check_disk_space():
            return
        
        # Process series
        wait_seconds = wait_minutes * 60
        for idx, series in enumerate(remaining_series, 1):
            try:
                # Check disk space periodically
                if idx % 50 == 0 and not self.check_disk_space():
                    print(f"🛑 Stopped due to disk space at {already_processed + idx}")
                    return
                
                series_name = series.get('jellyfin_name', series.get('name', ''))
                current_total = already_processed + idx
                
                self.process_series(series, current_total, total_series)
                self.save_progress(series_name)
                
                # Wait if specified
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                
                # Batch checkpoint
                if idx % batch_size == 0:
                    print(f"✅ Batch {idx}: {self.stats['episodes_created']} episodes, {self.stats['movies_created']} movies created")
                    progress_pct = ((already_processed + idx) / total_series) * 100
                    print(f"📊 Total progress: {already_processed + idx}/{total_series} ({progress_pct:.1f}%)")
                    
            except Exception as e:
                logging.error(f"Error processing series {current_total}: {e}")
                self.stats['errors'] += 1
        
        self.print_final_stats()
    
    def print_final_stats(self):
        """Print final statistics"""
        print("\n" + "="*60)
        print("📊 JELLYFIN STRUCTURE GENERATION COMPLETE")
        print("="*60)
        print("🌍 Language Priority: German → English → German Subtitles")
        print(f"✅ Series processed: {self.stats['series_processed']:,}")
        print(f"✅ Series created: {self.stats['series_created']:,}")
        print(f"✅ Seasons created: {self.stats['seasons_created']:,}")
        print(f"✅ Episodes created: {self.stats['episodes_created']:,}")
        print(f"🎬 Movies created: {self.stats['movies_created']:,}")
        print()
        print("📺 Episodes by language:")
        for lang, count in self.stats['episodes_by_language'].items():
            if count > 0:
                print(f"   {lang}: {count:,}")
        print("🎬 Movies by language:")
        for lang, count in self.stats['movies_by_language'].items():
            if count > 0:
                print(f"   {lang}: {count:,}")
        print()
        print(f"⏭️  Episodes skipped (no streams): {self.stats['episodes_skipped_no_streams']:,}")
        print(f"⏭️  Episodes skipped (no supported language): {self.stats['episodes_skipped_no_language']:,}")
        print(f"⏭️  Movies skipped (no streams): {self.stats['movies_skipped_no_streams']:,}")
        print(f"⏭️  Movies skipped (no supported language): {self.stats['movies_skipped_no_language']:,}")
        print(f"❌ Errors: {self.stats['errors']:,}")
        print(f"📁 Output: {self.output_dir}")
        print("="*60)
        
        total_content = self.stats['episodes_created'] + self.stats['movies_created']
        if total_content > 0:
            print("🎯 Ready for Jellyfin!")
            print("   1. Scan library in Jellyfin")
            print("   2. Disable image downloads (recommended)")
            print("   3. Movies are in Season 00")

    def detect_changes(self):
        """Detect which series need to be updated or removed"""
        print("\n🔍 Detecting changes...")

        # Load database series
        db_series = {s.get('jellyfin_name', s.get('name', '')): s for s in self.series_data}

        # Get existing folders
        existing_folders = set()
        if self.output_dir.exists():
            for item in self.output_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    existing_folders.add(item.name)

        # Find series to update (in DB but outdated in folders)
        # Find series to remove (in folders but not in DB)
        # Find series to add (in DB but not in folders)

        to_update = []
        to_remove = existing_folders - set(db_series.keys())
        to_add = set(db_series.keys()) - existing_folders

        # Check for content changes in existing series
        for series_name in existing_folders & set(db_series.keys()):
            series_dir = self.output_dir / series_name
            series = db_series[series_name]

            # Count expected episodes/movies from DB
            expected_episodes = 0
            expected_movies = 0

            seasons_data = series.get('seasons', {})
            movies_data = series.get('movies', {})

            for season_data in seasons_data.values():
                for episode_data in season_data.get('episodes', {}).values():
                    if episode_data.get('total_streams', 0) > 0:
                        redirect_id, _ = self.get_best_redirect(episode_data)
                        if redirect_id:
                            expected_episodes += 1

            for movie_data in movies_data.values():
                if movie_data.get('total_streams', 0) > 0:
                    redirect_id, _ = self.get_best_redirect(movie_data)
                    if redirect_id:
                        expected_movies += 1

            # Count actual .strm files
            actual_strm_count = len(list(series_dir.rglob('*.strm')))
            expected_total = expected_episodes + expected_movies

            # If counts don't match, needs update
            if actual_strm_count != expected_total:
                to_update.append(series_name)

        print(f"📝 Series to add: {len(to_add)}")
        print(f"🔄 Series to update: {len(to_update)}")
        print(f"🗑️  Series to remove: {len(to_remove)}")

        return to_add, to_update, to_remove

    def update_structure(self):
        """Update only changed series"""
        to_add, to_update, to_remove = self.detect_changes()

        # Remove outdated series
        for series_name in to_remove:
            series_dir = self.output_dir / series_name
            print(f"🗑️  Removing: {series_name}")
            shutil.rmtree(series_dir)

        # Update changed series (remove and recreate)
        for series_name in to_update:
            series_dir = self.output_dir / series_name
            print(f"🔄 Updating: {series_name}")
            shutil.rmtree(series_dir)
            # Find series in database and process
            for series in self.series_data:
                if series.get('jellyfin_name', series.get('name', '')) == series_name:
                    self.process_series(series, 0, len(self.series_data))
                    break

        # Add new series
        print(f"\n📥 Adding {len(to_add)} new series...")
        for idx, series_name in enumerate(to_add, 1):
            # Find series in database and process
            for series in self.series_data:
                if series.get('jellyfin_name', series.get('name', '')) == series_name:
                    print(f"📺 [{idx}/{len(to_add)}] Adding: {series_name}")
                    self.process_series(series, 0, len(self.series_data))
                    break

        self.print_final_stats()

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate Jellyfin structure for serienstream data')
    parser.add_argument('--api-url', default='http://localhost:3000/stream/redirect')
    parser.add_argument('--limit', type=int, help='Limit series to process')
    parser.add_argument('-b', type=int, default=1000, help='Batch size (default: 1000)')
    parser.add_argument('--wait', type=int, default=0, help='Wait minutes between series')
    parser.add_argument('--clear-progress', action='store_true', help='Clear progress and start fresh')
    parser.add_argument('--update', action='store_true', help='Only update changed series')

    args = parser.parse_args()

    generator = JellyfinStructureGenerator(api_base_url=args.api_url)

    if args.clear_progress:
        generator.clear_progress()

    if args.update:
        generator.update_structure()
    else:
        generator.generate_structure(
            limit=args.limit,
            batch_size=args.b,
            wait_minutes=args.wait
        )

if __name__ == '__main__':
    main()