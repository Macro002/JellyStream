#!/usr/bin/env python3
"""
Aniworld Daily Updater - Fresh & Clean Implementation
Scrapes /neue-episoden to find recently added episodes and updates the database

Two modes:
1. Initial sync: Updates all 150 series from /neue-episoden (for first run)
2. Daily update: Only updates series with "Neu!" tag (today's new episodes)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AniworldDailyUpdater:
    def __init__(self, site_dir: Path = None):
        """Initialize updater"""
        if site_dir is None:
            site_dir = Path(__file__).parent

        self.site_dir = site_dir
        self.data_dir = site_dir / "data"
        self.base_url = "https://aniworld.to"
        self.neue_episoden_url = f"{self.base_url}/neue-episoden"

        # File paths
        self.db_file = self.data_dir / "final_series_data.json"
        self.state_file = self.data_dir / "updater_state.json"

        # Session setup
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def scrape_neue_episoden(self) -> List[Dict]:
        """
        Scrape /neue-episoden page to get the 150 most recent episodes

        Returns:
            List of dicts with: series_name, series_url, season, episode, date, is_new, language
        """
        logging.info(f"🔍 Scraping: {self.neue_episoden_url}")

        try:
            response = self.session.get(self.neue_episoden_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            episodes = []

            # Find all episode links in the page
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Episode URLs format: /anime/stream/{slug}/staffel-{S}/episode-{E}
                if '/anime/stream/' in href and '/staffel-' in href and '/episode-' in href:

                    # Extract series name (in <strong> tag)
                    strong = link.find('strong')
                    if not strong:
                        continue

                    series_name = strong.get_text(strip=True)

                    # Extract season/episode from span.listTag (format: "S## E##")
                    list_tag = link.find('span', class_='listTag')
                    if not list_tag:
                        continue

                    se_text = list_tag.get_text(strip=True)  # e.g., "S01 E02"

                    # Parse season and episode
                    try:
                        parts = se_text.split()
                        season = int(parts[0].replace('S', ''))
                        episode = int(parts[1].replace('E', ''))
                    except:
                        logging.warning(f"Could not parse S/E from: {se_text}")
                        continue

                    # Extract date
                    date_span = link.find('span', class_='elementFloatRight')
                    date_str = date_span.get_text(strip=True) if date_span else ''

                    # Check if "Neu!" badge exists (green span)
                    parent = link.parent
                    is_new = parent.find('span', class_='green') is not None if parent else False

                    # Extract language from flag image
                    flag_img = parent.find('img', class_='flag') if parent else None
                    language = 'Unknown'
                    if flag_img:
                        src = flag_img.get('src', '') or flag_img.get('data-src', '')
                        if 'german.svg' in src:
                            language = 'Deutsch'
                        elif 'japanese-german.svg' in src:
                            language = 'mit Untertitel Deutsch'
                        elif 'japanese-english.svg' in src:
                            language = 'mit Untertitel Englisch'

                    # Build series URL from episode URL
                    # /anime/stream/lets-play/staffel-1/episode-4 -> /anime/stream/lets-play
                    url_parts = href.split('/')
                    if len(url_parts) >= 4:
                        series_slug = url_parts[3]
                        series_url = f"{self.base_url}/anime/stream/{series_slug}"

                        episodes.append({
                            'series_name': series_name,
                            'series_url': series_url,
                            'series_slug': series_slug,
                            'season': season,
                            'episode': episode,
                            'date': date_str,
                            'is_new': is_new,
                            'language': language
                        })

            logging.info(f"✅ Found {len(episodes)} recent episodes")

            # Count how many have "Neu!" tag
            new_count = sum(1 for ep in episodes if ep['is_new'])
            logging.info(f"   🆕 {new_count} episodes marked as 'Neu!' (today)")

            return episodes

        except Exception as e:
            logging.error(f"❌ Error scraping neue-episoden: {e}")
            import traceback
            traceback.print_exc()
            return []

    def load_database(self) -> Dict:
        """Load existing database"""
        if not self.db_file.exists():
            logging.error(f"❌ Database not found: {self.db_file}")
            return None

        with open(self.db_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_database(self, data: Dict):
        """Save database"""
        # Create backup first
        if self.db_file.exists():
            backup_path = Path(str(self.db_file) + '.updater_backup')
            import shutil
            shutil.copy(self.db_file, backup_path)
            logging.info(f"💾 Backup created: {backup_path}")

        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logging.info(f"✅ Database saved: {self.db_file}")

    def find_series_in_db(self, db: Dict, series_url: str) -> Tuple[int, Dict]:
        """
        Find series in database by URL
        Returns: (index, series_dict) or (None, None) if not found
        """
        for idx, series in enumerate(db['series']):
            if series['url'] == series_url:
                return idx, series
        return None, None

    def update_series(self, series_url: str, series_name: str) -> Dict:
        """
        Update a single series by running the scraper pipeline
        Uses the same approach as manual_updater
        Returns updated series dict or None on failure
        """
        logging.info(f"📥 Updating: {series_name}")

        try:
            # Import the update function from manual_updater
            sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
            from manual_updater import update_series_simple

            # Get site name from site_dir
            site_name = self.site_dir.name  # e.g., "aniworld"

            # Run the update
            updated_series = update_series_simple(site_name, series_url, series_name)

            if updated_series:
                logging.info(f"  ✅ Updated successfully")
                return updated_series
            else:
                logging.error(f"  ❌ Update failed")
                return None

        except Exception as e:
            logging.error(f"  ❌ Error updating series: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_series_to_update(self, episodes: List[Dict], only_new: bool = False) -> Set[str]:
        """
        Extract unique series URLs that need updating

        Args:
            episodes: List of episode dicts from scrape_neue_episoden()
            only_new: If True, only return series with is_new=True episodes

        Returns:
            Set of series URLs to update
        """
        series_urls = set()

        for ep in episodes:
            if only_new and not ep['is_new']:
                continue
            series_urls.add(ep['series_url'])

        return series_urls

    def save_state(self, state: Dict):
        """Save updater state (last run time, etc.)"""
        state['last_update'] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def load_state(self) -> Dict:
        """Load updater state"""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def run_initial_sync(self):
        """
        Initial sync mode: Update ALL 150 series from /neue-episoden
        This ensures database is fully current before daily updates
        """
        logging.info("="*70)
        logging.info("🔄 INITIAL SYNC MODE")
        logging.info("   Updating all 150 series from /neue-episoden")
        logging.info("="*70)

        start_time = time.time()

        # Scrape neue-episoden
        episodes = self.scrape_neue_episoden()
        if not episodes:
            logging.error("❌ No episodes found")
            return False

        # Get all unique series (not just "Neu!" ones)
        series_urls = self.get_series_to_update(episodes, only_new=False)
        logging.info(f"\n📺 Will update {len(series_urls)} series")

        # Load database
        db = self.load_database()
        if not db:
            return False

        # Update each series
        updated_count = 0
        failed_count = 0

        for i, series_url in enumerate(series_urls, 1):
            # Find series name
            series_name = next((ep['series_name'] for ep in episodes if ep['series_url'] == series_url), 'Unknown')

            logging.info(f"\n[{i}/{len(series_urls)}] {series_name}")

            # Update the series
            updated_series = self.update_series(series_url, series_name)

            if updated_series:
                # Find and replace in database
                idx, old_series = self.find_series_in_db(db, series_url)

                if idx is not None:
                    db['series'][idx] = updated_series
                    updated_count += 1
                else:
                    # New series - add to database
                    db['series'].append(updated_series)
                    updated_count += 1
                    logging.info(f"  ➕ Added new series to database")
            else:
                failed_count += 1

            # Small delay to avoid hammering the server
            time.sleep(2)

        # Save updated database
        self.save_database(db)

        # Save state
        self.save_state({
            'mode': 'initial_sync',
            'series_updated': updated_count,
            'series_failed': failed_count
        })

        duration = time.time() - start_time

        logging.info("\n" + "="*70)
        logging.info("🎉 INITIAL SYNC COMPLETE")
        logging.info(f"   ✅ Updated: {updated_count}")
        logging.info(f"   ❌ Failed: {failed_count}")
        logging.info(f"   ⏱️  Duration: {duration/60:.1f} minutes")
        logging.info("="*70)

        return True

    def run_daily_update(self):
        """
        Daily update mode: Only update series with "Neu!" tag
        Fast updates for today's new episodes
        """
        logging.info("="*70)
        logging.info("🔄 DAILY UPDATE MODE")
        logging.info("   Only updating series with 'Neu!' tag")
        logging.info("="*70)

        start_time = time.time()

        # Scrape neue-episoden
        episodes = self.scrape_neue_episoden()
        if not episodes:
            logging.error("❌ No episodes found")
            return False

        # Get only series with "Neu!" tag
        series_urls = self.get_series_to_update(episodes, only_new=True)

        if not series_urls:
            logging.info("\n✅ No new episodes today - database is current!")
            return True

        logging.info(f"\n📺 Will update {len(series_urls)} series with new episodes")

        # Load database
        db = self.load_database()
        if not db:
            return False

        # Update each series
        updated_count = 0
        failed_count = 0

        for i, series_url in enumerate(series_urls, 1):
            # Find series name
            series_name = next((ep['series_name'] for ep in episodes if ep['series_url'] == series_url), 'Unknown')

            logging.info(f"\n[{i}/{len(series_urls)}] {series_name}")

            # Update the series
            updated_series = self.update_series(series_url, series_name)

            if updated_series:
                # Find and replace in database
                idx, old_series = self.find_series_in_db(db, series_url)

                if idx is not None:
                    db['series'][idx] = updated_series
                    updated_count += 1
                else:
                    # New series - add to database
                    db['series'].append(updated_series)
                    updated_count += 1
                    logging.info(f"  ➕ Added new series to database")
            else:
                failed_count += 1

            # Small delay
            time.sleep(2)

        # Save updated database
        self.save_database(db)

        # Save state
        self.save_state({
            'mode': 'daily_update',
            'series_updated': updated_count,
            'series_failed': failed_count
        })

        duration = time.time() - start_time

        logging.info("\n" + "="*70)
        logging.info("🎉 DAILY UPDATE COMPLETE")
        logging.info(f"   ✅ Updated: {updated_count}")
        logging.info(f"   ❌ Failed: {failed_count}")
        logging.info(f"   ⏱️  Duration: {duration/60:.1f} minutes")
        logging.info("="*70)

        return True

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Aniworld Daily Updater')
    parser.add_argument('--mode', choices=['initial', 'daily'], required=True,
                        help='Update mode: initial (all 150) or daily (only Neu!)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Scrape and show what would be updated without making changes')

    args = parser.parse_args()

    updater = AniworldDailyUpdater()

    try:
        if args.dry_run:
            episodes = updater.scrape_neue_episoden()
            if episodes:
                series_urls = updater.get_series_to_update(episodes, only_new=(args.mode == 'daily'))
                print(f"\n📺 Would update {len(series_urls)} series:")
                for url in list(series_urls)[:20]:
                    name = next((ep['series_name'] for ep in episodes if ep['series_url'] == url), '')
                    print(f"   - {name}")
                if len(series_urls) > 20:
                    print(f"   ... and {len(series_urls) - 20} more")
            return

        if args.mode == 'initial':
            success = updater.run_initial_sync()
        else:
            success = updater.run_daily_update()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logging.info("\n🛑 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
