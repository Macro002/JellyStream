#!/usr/bin/env python3
"""
New Episodes Updater
Scrapes the neue-episoden page to find recently updated series
Only re-processes series that have new content
Input: data/final_series_data.json (existing DB)
Output: data/final_series_data.json (updated)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Set
from urllib.parse import urljoin
from datetime import datetime

class NewEpisodesUpdater:
    def __init__(self):
        self.base_url = "https://serienstream.to"
        self.neue_episoden_url = "https://s.to/neue-episoden"
        self.data_folder = Path("data")

        # File paths
        self.catalog_file = self.data_folder / "tmp_name_url.json"
        self.structure_file = self.data_folder / "tmp_season_episode_data.json"
        self.streams_file = self.data_folder / "tmp_episode_streams.json"
        self.final_file = self.data_folder / "final_series_data.json"

        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def scrape_neue_episoden(self) -> List[Dict]:
        """
        Scrape the neue-episoden page to get recently updated series
        Returns list of dicts with series info
        """
        print(f"🔍 Scraping neue-episoden page...")

        try:
            response = self.session.get(self.neue_episoden_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the newEpisodeList container
            episode_list = soup.find('div', class_='newEpisodeList')
            if not episode_list:
                print("❌ Could not find newEpisodeList container")
                return []

            # Find all episode entries
            episodes = []
            rows_container = episode_list.find('div', class_='rows')
            if not rows_container:
                print("❌ Could not find rows container")
                return []

            # Find all col-md-12 divs that contain episode info
            for col in rows_container.find_all('div', class_='col-md-12', recursive=False):
                # Each col has a .row, and inside that is another .col-md-12 with the actual data
                inner_row = col.find('div', class_='row')
                if not inner_row:
                    continue

                episode_div = inner_row.find('div', class_='col-md-12')
                if not episode_div:
                    continue

                # Extract episode data
                link = episode_div.find('a')
                if not link:
                    continue

                episode_url = link.get('href', '')
                if not episode_url:
                    continue

                # Extract series name
                strong = link.find('strong')
                series_name = strong.get_text(strip=True) if strong else 'Unknown'

                # Extract season/episode tag
                season_episode_tag = link.find('span', class_='listTag')
                season_episode = season_episode_tag.get_text(strip=True) if season_episode_tag else ''

                # Extract date
                date_span = link.find('span', class_='elementFloatRight')
                date_added = date_span.get_text(strip=True) if date_span else ''

                # Check if it's marked as "Neu!"
                is_new = episode_div.find('span', class_='green') is not None

                # Extract language from flag image (check both src and data-src for lazy loading)
                flag_img = episode_div.find('img', class_='flag')
                language = 'Unknown'
                if flag_img:
                    lang_src = flag_img.get('data-src', '') or flag_img.get('src', '')
                    if 'german' in lang_src.lower():
                        language = 'Deutsch'
                    elif 'english' in lang_src.lower():
                        language = 'Englisch'
                    elif 'subtitle' in lang_src.lower():
                        language = 'mit deutschen Untertiteln'

                # Parse series URL from episode URL
                # Format: /serie/stream/{series-slug}/staffel-{S}/episode-{E}
                parts = episode_url.split('/')
                if len(parts) >= 4 and parts[1] == 'serie' and parts[2] == 'stream':
                    series_slug = parts[3]
                    series_url = f"{self.base_url}/serie/stream/{series_slug}"

                    episodes.append({
                        'series_name': series_name,
                        'series_slug': series_slug,
                        'series_url': series_url,
                        'season_episode': season_episode,
                        'date_added': date_added,
                        'is_new': is_new,
                        'language': language,
                        'episode_url': urljoin(self.base_url, episode_url)
                    })

            print(f"✅ Found {len(episodes)} recent episodes")
            return episodes

        except Exception as e:
            print(f"❌ Error scraping neue-episoden: {e}")
            return []

    def get_unique_series(self, episodes: List[Dict]) -> Set[str]:
        """Extract unique series URLs from episode list"""
        series_urls = set()
        for ep in episodes:
            series_urls.add(ep['series_url'])
        return series_urls

    def load_existing_catalog(self) -> Dict:
        """Load existing catalog data"""
        if self.catalog_file.exists():
            try:
                with open(self.catalog_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {'series': []}

    def update_catalog_with_series(self, series_urls: Set[str], episodes: List[Dict]):
        """Add new series to catalog if they don't exist"""
        catalog = self.load_existing_catalog()
        existing_urls = {s['url'] for s in catalog['series']}

        added = 0
        for series_url in series_urls:
            if series_url not in existing_urls:
                # Find series name from episodes
                series_name = next((ep['series_name'] for ep in episodes if ep['series_url'] == series_url), 'Unknown')

                catalog['series'].append({
                    'name': series_name,
                    'url': series_url,
                    'genre': 'Unknown'
                })
                added += 1

        if added > 0:
            catalog['total_series'] = len(catalog['series'])
            catalog['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

            with open(self.catalog_file, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)

            print(f"✅ Added {added} new series to catalog")

    def remove_series_from_temp_files(self, series_urls: Set[str]):
        """Remove series from temp files so they can be re-processed"""
        # Remove from structure file
        if self.structure_file.exists():
            with open(self.structure_file, 'r', encoding='utf-8') as f:
                structure_data = json.load(f)

            original_count = len(structure_data.get('series', []))
            structure_data['series'] = [
                s for s in structure_data.get('series', [])
                if s['url'] not in series_urls
            ]
            removed = original_count - len(structure_data['series'])

            if removed > 0:
                with open(self.structure_file, 'w', encoding='utf-8') as f:
                    json.dump(structure_data, f, indent=2, ensure_ascii=False)
                print(f"🗑️  Removed {removed} series from structure file for re-processing")

        # Remove from streams file
        if self.streams_file.exists():
            with open(self.streams_file, 'r', encoding='utf-8') as f:
                streams_data = json.load(f)

            original_count = len(streams_data.get('series', []))
            streams_data['series'] = [
                s for s in streams_data.get('series', [])
                if s['url'] not in series_urls
            ]
            removed = original_count - len(streams_data['series'])

            if removed > 0:
                with open(self.streams_file, 'w', encoding='utf-8') as f:
                    json.dump(streams_data, f, indent=2, ensure_ascii=False)
                print(f"🗑️  Removed {removed} series from streams file for re-processing")

    def run_pipeline_for_updates(self, series_count: int):
        """Run pipeline scripts to process the updated series"""
        print("\n" + "="*60)
        print(f"🔄 Running pipeline for {series_count} updated series...")
        print("="*60)

        # Run script 2: Structure analyzer
        print("\n📊 Step 1: Analyzing structure...")
        result = subprocess.run(
            [sys.executable, '2_url_season_episode_num.py', '-b', '25'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ Structure analyzer failed: {result.stderr}")
            return False

        # Run script 3: Streams analyzer
        print("\n🎬 Step 2: Extracting streams...")
        result = subprocess.run(
            [sys.executable, '3_language_streamurl.py', '-b', '10'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ Streams analyzer failed: {result.stderr}")
            return False

        # Run script 4: JSON structurer
        print("\n📦 Step 3: Building final database...")
        result = subprocess.run(
            [sys.executable, '4_json_structurer.py'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ JSON structurer failed: {result.stderr}")
            return False

        print("\n✅ Pipeline completed successfully!")
        return True

    def run(self, dry_run: bool = False):
        """Run the updater"""
        start_time = time.time()

        print("🚀 New Episodes Updater")
        print("=" * 60)
        print(f"📅 Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Source: {self.neue_episoden_url}")
        print("=" * 60)

        # Step 1: Scrape neue-episoden page
        episodes = self.scrape_neue_episoden()
        if not episodes:
            print("❌ No episodes found, exiting")
            return False

        # Step 2: Extract unique series
        series_urls = self.get_unique_series(episodes)
        print(f"\n📺 Found {len(series_urls)} unique series with updates:")

        # Show what will be updated
        for i, ep in enumerate(episodes[:10], 1):
            new_tag = "🆕" if ep['is_new'] else "  "
            print(f"   {new_tag} {ep['series_name']} - {ep['season_episode']} ({ep['language']})")

        if len(episodes) > 10:
            print(f"   ... and {len(episodes) - 10} more")

        if dry_run:
            print("\n🔍 DRY RUN - No changes made")
            return True

        # Step 3: Update catalog with any new series
        self.update_catalog_with_series(series_urls, episodes)

        # Step 4: Remove series from temp files for re-processing
        self.remove_series_from_temp_files(series_urls)

        # Step 5: Run pipeline to re-process these series
        success = self.run_pipeline_for_updates(len(series_urls))

        duration = time.time() - start_time
        print("\n" + "="*60)
        if success:
            print("🎉 Update completed successfully!")
            print(f"⏱️  Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
            print(f"📊 Updated {len(series_urls)} series")
            print(f"📁 Database: {self.final_file}")
        else:
            print("❌ Update failed!")
        print("="*60)

        return success

def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Update database with new episodes')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    args = parser.parse_args()

    updater = NewEpisodesUpdater()

    try:
        success = updater.run(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
