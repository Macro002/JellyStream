#!/usr/bin/env python3
"""
Aniworld Episode Updater
Scrapes /neue-episoden to find new episodes and updates only those episodes in the database

Default: Updates only episodes with "Neu!" tag (today's new episodes)
--all: Updates all 150 episodes from /neue-episoden list

Smart deduplication: Same episode with different languages = 1 update
Auto-regenerates .strm files for updated series
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
import logging
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AniworldEpisodeUpdater:
    def __init__(self):
        """Initialize updater"""
        self.base_url = config.BASE_URL
        self.neue_episoden_url = f"{self.base_url}/neue-episoden"
        self.data_dir = Path(config.DATA_DIR)
        self.db_file = self.data_dir / "final_series_data.json"
        self.jellyfin_dir = Path(config.JELLYFIN_OUTPUT_DIR)
        self.api_base_url = "http://localhost:3000/api/stream/redirect"

        # Language priority for .strm files
        self.LANGUAGE_PRIORITY = [
            "Deutsch",
            "mit Untertitel Deutsch",
            "mit Untertitel Englisch"
        ]

        # Session setup
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Track updated series for structure regeneration
        self.updated_series = set()

    def scrape_neue_episoden(self, only_new: bool = True) -> List[Dict]:
        """
        Scrape /neue-episoden page to get recent episodes

        Args:
            only_new: If True, only return episodes with "Neu!" tag

        Returns:
            List of episode dicts with: series_name, series_slug, season, episode, episode_url, is_new
        """
        try:
            response = self.session.get(self.neue_episoden_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            episodes = []

            # Find all episode links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Episode URLs format: /anime/stream/{slug}/staffel-{S}/episode-{E}
                if '/anime/stream/' not in href or '/staffel-' not in href or '/episode-' not in href:
                    continue

                # Extract series name from <strong>
                strong = link.find('strong')
                if not strong:
                    continue

                series_name = strong.get_text(strip=True)

                # Extract S/E from span.listTag (format: "S## E##")
                list_tag = link.find('span', class_='listTag')
                if not list_tag:
                    continue

                se_text = list_tag.get_text(strip=True)

                # Parse season and episode
                try:
                    parts = se_text.split()
                    season = int(parts[0].replace('S', ''))
                    episode = int(parts[1].replace('E', ''))
                except:
                    continue

                # Check if "Neu!" badge exists
                parent = link.parent
                is_new = parent.find('span', class_='green') is not None if parent else False

                # Skip if only_new and this episode doesn't have "Neu!" tag
                if only_new and not is_new:
                    continue

                # Extract series slug from URL
                url_parts = href.split('/')
                if len(url_parts) >= 4:
                    series_slug = url_parts[3]
                    series_url = f"{self.base_url}/anime/stream/{series_slug}"
                    episode_url = f"{self.base_url}{href}"

                    episodes.append({
                        'series_name': series_name,
                        'series_slug': series_slug,
                        'series_url': series_url,
                        'season': season,
                        'episode': episode,
                        'episode_url': episode_url,
                        'is_new': is_new
                    })

            logging.info(f"✅ Found {len(episodes)} episodes" + (" with 'Neu!' tag" if only_new else ""))
            return episodes

        except Exception as e:
            logging.error(f"❌ Error scraping neue-episoden: {e}")
            import traceback
            traceback.print_exc()
            return []

    def deduplicate_episodes(self, episodes: List[Dict]) -> List[Dict]:
        """
        Deduplicate episodes - same series+season+episode but different languages = 1 entry

        Args:
            episodes: List of episode dicts

        Returns:
            Deduplicated list of episodes
        """
        seen = set()
        unique_episodes = []

        for ep in episodes:
            # Create unique key: series_slug + season + episode
            key = (ep['series_slug'], ep['season'], ep['episode'])

            if key not in seen:
                seen.add(key)
                unique_episodes.append(ep)

        return unique_episodes

    def scrape_episode_streams(self, episode_url: str) -> Dict:
        """
        Scrape a single episode page to get all available streams (all languages)
        Uses the same approach as 3_language_streamurl.py

        Args:
            episode_url: Full URL to episode page

        Returns:
            Dict with streams_by_language: {'Deutsch': [...], 'mit Untertitel Deutsch': [...]}
        """
        try:
            response = self.session.get(episode_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Step 1: Extract language mappings (data-lang-key -> title)
            languages = {}
            lang_box = soup.find('div', class_='changeLanguageBox')
            if lang_box:
                lang_elements = lang_box.find_all(attrs={'data-lang-key': True, 'title': True})
                for element in lang_elements:
                    lang_key = element.get('data-lang-key')
                    lang_title = element.get('title')
                    if lang_key and lang_title:
                        languages[lang_key] = lang_title

            # Step 2: Extract streams from hosterSiteVideo
            streams_by_language = {}
            video_section = soup.find('div', class_='hosterSiteVideo')

            if video_section:
                row_ul = video_section.find('ul', class_='row')
                if row_ul:
                    stream_items = row_ul.find_all('li', attrs={'data-lang-key': True, 'data-link-target': True})

                    for item in stream_items:
                        lang_key = item.get('data-lang-key')
                        link_target = item.get('data-link-target')

                        # Get language name from mapping
                        language = languages.get(lang_key, f'Unknown_{lang_key}')

                        # Extract provider name
                        h4_element = item.find('h4')
                        provider = h4_element.get_text(strip=True) if h4_element else 'Unknown'

                        # Build full URL
                        if not link_target.startswith('http'):
                            stream_url = f"{self.base_url}{link_target}"
                        else:
                            stream_url = link_target

                        # Add to streams_by_language dict
                        if language not in streams_by_language:
                            streams_by_language[language] = []

                        streams_by_language[language].append({
                            'hoster': provider,
                            'stream_url': stream_url
                        })

            return {
                'streams_by_language': streams_by_language,
                'total_streams': sum(len(s) for s in streams_by_language.values())
            }

        except Exception as e:
            return {'streams_by_language': {}, 'total_streams': 0}

    def load_database(self) -> Dict:
        """Load existing database"""
        if not self.db_file.exists():
            logging.error(f"❌ Database not found: {self.db_file}")
            return None

        with open(self.db_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_database(self, data: Dict):
        """Save database with backup - replaces old backup"""
        # Delete old backup if exists
        backup_path = Path(str(self.db_file) + '.updater_backup')
        if backup_path.exists():
            backup_path.unlink()

        # Create new backup from current database
        if self.db_file.exists():
            import shutil
            shutil.copy(self.db_file, backup_path)

        # Save updated database
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def find_series_in_db(self, db: Dict, series_url: str) -> Tuple[int, Dict]:
        """
        Find series in database by URL
        Returns: (index, series_dict) or (None, None) if not found
        """
        for idx, series in enumerate(db['series']):
            if series['url'] == series_url:
                return idx, series
        return None, None

    def scrape_new_series(self, series_url: str, series_name: str) -> Dict:
        """
        Scrape a completely new series that doesn't exist in database yet

        Args:
            series_url: Full URL to series page
            series_name: Name of the series

        Returns:
            New series dict with basic structure
        """
        try:
            response = self.session.get(series_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract series info from page
            series_data = {
                'name': series_name,
                'url': series_url,
                'seasons': {},
                'movies': {},
                'total_episodes': 0,
                'season_count': 0,
                'episode_counts': [],
                'jellyfin_name': series_name
            }

            logging.info(f"➕ Adding new series to database: {series_name}")
            return series_data

        except Exception as e:
            logging.error(f"❌ Error scraping new series {series_url}: {e}")
            return None

    def update_episode_in_db(self, db: Dict, episode_info: Dict, streams_data: Dict) -> Tuple[bool, bool]:
        """
        Update or add a single episode in the database with new stream data

        Args:
            db: Database dict
            episode_info: Episode info from scrape_neue_episoden()
            streams_data: Streams data from scrape_episode_streams()

        Returns:
            (success, is_new_episode): True if updated/added, True if new episode was added
        """
        # Find series
        series_idx, series = self.find_series_in_db(db, episode_info['series_url'])

        # If series doesn't exist, add it
        if series_idx is None:
            new_series = self.scrape_new_series(episode_info['series_url'], episode_info['series_name'])
            if not new_series:
                return False, False

            # Add to database
            db['series'].append(new_series)
            series_idx = len(db['series']) - 1
            series = new_series
            logging.info(f"✅ Added new series: {episode_info['series_name']}")

        # Track this series for structure regeneration
        self.updated_series.add(episode_info['series_url'])

        # Find or create season
        season_key = f"season_{episode_info['season']}"
        if season_key not in series.get('seasons', {}):
            # Create new season
            series['seasons'][season_key] = {
                'episode_count': 0,
                'episodes': {}
            }

        season = series['seasons'][season_key]

        # Find or create episode
        episode_key = f"episode_{episode_info['episode']}"
        is_new = episode_key not in season.get('episodes', {})

        if is_new:
            # Create new episode
            season['episodes'][episode_key] = {
                'url': episode_info['episode_url'],
                'streams_by_language': {},
                'total_streams': 0
            }
            # Update episode count
            season['episode_count'] = len(season['episodes'])
            # Update series episode_counts array
            if 'episode_counts' in series and episode_info['season'] <= len(series['episode_counts']):
                series['episode_counts'][episode_info['season'] - 1] = season['episode_count']

        # Update episode streams
        episode = season['episodes'][episode_key]
        episode['streams_by_language'] = streams_data['streams_by_language']
        episode['total_streams'] = streams_data['total_streams']

        return True, is_new

    def sanitize_filename(self, filename: str) -> str:
        """Clean filename for filesystem"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        return filename.strip(' .')[:200] or "Unknown"

    def get_best_redirect(self, content_data: Dict) -> Tuple[str, str]:
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
                    if stream.get('hoster') == provider:
                        stream_url = stream.get('stream_url', '')
                        if '/redirect/' in stream_url:
                            redirect_id = stream_url.split('/redirect/')[-1]
                            return redirect_id, language

            # If no preferred provider, use any redirect from this language
            for stream in language_streams:
                stream_url = stream.get('stream_url', '')
                if '/redirect/' in stream_url:
                    redirect_id = stream_url.split('/redirect/')[-1]
                    return redirect_id, language

        return None, None

    def create_strm_file(self, strm_path: Path, redirect_id: str) -> bool:
        """Create a .strm file"""
        try:
            stream_url = f"{self.api_base_url}/{redirect_id}"
            with open(strm_path, 'w', encoding='utf-8') as f:
                f.write(stream_url)
            return True
        except Exception as e:
            logging.error(f"Error creating {strm_path}: {e}")
            return False

    def regenerate_series_structure(self, db: Dict):
        """Regenerate .strm file structure for updated series"""
        if not self.updated_series:
            return 0

        logging.info(f"\n🔄 Regenerating .strm structure for {len(self.updated_series)} series...")

        regenerated_count = 0
        strm_files_created = 0

        for series_url in self.updated_series:
            # Find series in database
            _, series = self.find_series_in_db(db, series_url)
            if not series:
                continue

            series_name = series.get('jellyfin_name', series.get('name', 'Unknown'))
            safe_name = self.sanitize_filename(series_name)
            series_dir = self.jellyfin_dir / safe_name

            # Remove old series directory
            if series_dir.exists():
                import shutil
                shutil.rmtree(series_dir)

            # Recreate series directory
            series_dir.mkdir(parents=True, exist_ok=True)

            # Process seasons
            for season_key, season_data in series.get('seasons', {}).items():
                season_num = season_key.replace('season_', '')
                season_dir = series_dir / f"Season {season_num.zfill(2)}"
                season_dir.mkdir(parents=True, exist_ok=True)

                # Process episodes
                for episode_key, episode_data in season_data.get('episodes', {}).items():
                    episode_num = episode_key.replace('episode_', '')

                    if episode_data.get('total_streams', 0) == 0:
                        continue

                    redirect_id, _ = self.get_best_redirect(episode_data)
                    if not redirect_id:
                        continue

                    strm_path = season_dir / f"S{season_num.zfill(2)}E{episode_num.zfill(2)}.strm"
                    if self.create_strm_file(strm_path, redirect_id):
                        strm_files_created += 1

            regenerated_count += 1

        logging.info(f"✅ Regenerated {regenerated_count} series ({strm_files_created} .strm files)")
        return regenerated_count

    def run(self, update_all: bool = False):
        """
        Run the updater

        Args:
            update_all: If True, update all 150 episodes. If False, only "Neu!" episodes
        """
        start_time = time.time()

        mode = "ALL 150 EPISODES" if update_all else "NEW EPISODES ONLY"
        logging.info("="*70)
        logging.info(f"🔄 ANIWORLD EPISODE UPDATER - {mode}")
        logging.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("="*70)

        # Step 1: Scrape /neue-episoden
        episodes = self.scrape_neue_episoden(only_new=not update_all)

        if not episodes:
            logging.info("✅ No episodes to update")
            return True

        # Step 2: Deduplicate episodes
        unique_episodes = self.deduplicate_episodes(episodes)
        logging.info(f"📺 Will update {len(unique_episodes)} unique episodes (deduplicated from {len(episodes)} entries)")

        # Step 3: Load database
        db = self.load_database()
        if not db:
            return False

        # Step 4: Update each episode
        updated_count = 0
        new_episode_count = 0
        new_series_count = 0
        failed_count = 0

        # Track series count before updates
        initial_series_count = len(db['series'])

        print(f"\nProcessing {len(unique_episodes)} episodes...", flush=True)

        for i, ep in enumerate(unique_episodes, 1):
            series_name = ep['series_name']
            s = ep['season']
            e = ep['episode']

            # Show progress every 10 episodes or on new episodes
            if i % 10 == 0 or i == len(unique_episodes):
                print(f"Progress: {i}/{len(unique_episodes)}", end='\r', flush=True)

            # Scrape episode streams
            streams_data = self.scrape_episode_streams(ep['episode_url'])

            if streams_data['total_streams'] == 0:
                failed_count += 1
            else:
                # Update in database
                success, is_new = self.update_episode_in_db(db, ep, streams_data)
                if success:
                    updated_count += 1
                    if is_new:
                        new_episode_count += 1
                        print(f"\n➕ New episode: {series_name} S{s:02d}E{e:02d} ({streams_data['total_streams']} streams)", flush=True)
                else:
                    failed_count += 1

            # Small delay to avoid hammering the server
            time.sleep(2)

        # Calculate how many new series were added
        new_series_count = len(db['series']) - initial_series_count

        print()  # New line after progress

        # Step 5: Save database
        if updated_count > 0:
            self.save_database(db)

            # Step 6: Regenerate .strm structure for updated series
            regenerated_series = self.regenerate_series_structure(db)

        duration = time.time() - start_time

        logging.info("\n" + "="*70)
        logging.info("🎉 UPDATE COMPLETE")
        logging.info(f"   ✅ Updated: {updated_count} episodes ({new_episode_count} new)")
        if new_series_count > 0:
            logging.info(f"   📺 New series added: {new_series_count}")
        if updated_count > 0:
            logging.info(f"   📁 Regenerated: {regenerated_series} series structures")
        if failed_count > 0:
            logging.info(f"   ❌ Failed (no streams): {failed_count} episodes")
        logging.info(f"   ⏱️  Duration: {duration/60:.1f} minutes")
        logging.info("="*70)

        return True

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Aniworld Episode Updater')
    parser.add_argument('--all', action='store_true',
                        help='Update all 150 episodes (default: only episodes with "Neu!" tag)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be updated without making changes')

    args = parser.parse_args()

    updater = AniworldEpisodeUpdater()

    try:
        if args.dry_run:
            episodes = updater.scrape_neue_episoden(only_new=not args.all)
            if episodes:
                unique = updater.deduplicate_episodes(episodes)
                print(f"\n📺 Would update {len(unique)} unique episodes:")
                for ep in unique[:20]:
                    print(f"   - {ep['series_name']} S{ep['season']:02d}E{ep['episode']:02d}")
                if len(unique) > 20:
                    print(f"   ... and {len(unique) - 20} more")
            return

        success = updater.run(update_all=args.all)
        import sys
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logging.info("\n🛑 Interrupted by user")
        import sys
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
