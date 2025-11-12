#!/usr/bin/env python3
"""
Aniworld Catalog Scraper - Performance Optimized
Scrapes anime names and URLs from all genres
Creates: data/tmp_name_url.json
Fetch all links new with flag [--fresh]
blacklist certain anime with [--blacklist] [url]
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from typing import List, Dict, Set
from urllib.parse import urljoin
from pathlib import Path
import config

class CatalogScraper:
    def __init__(self, use_blacklist: bool = False):
        self.base_url = config.BASE_URL
        self.catalog_url = f"{config.BASE_URL}/animes"
        self.use_blacklist = use_blacklist
        
        # Create data folder
        self.data_folder = Path(config.DATA_DIR)
        self.data_folder.mkdir(exist_ok=True)
        self.output_file = self.data_folder / "tmp_name_url.json"
        
        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        })
    
    def load_existing_data(self) -> Dict:
        """Load existing data if file exists"""
        if self.output_file.exists():
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def get_existing_urls(self, existing_data: Dict) -> Set[str]:
        """Get set of existing URLs for duplicate checking"""
        if not existing_data or 'series' not in existing_data:
            return set()
        return {series['url'] for series in existing_data['series']}
    
    def scrape_all_genres(self, existing_urls: Set[str] = None) -> List[Dict]:
        """Scrape ALL genres from Aniworld catalog"""
        if existing_urls is None:
            existing_urls = set()
        
        try:
            response = self.session.get(self.catalog_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            series_container = soup.find('div', {'id': 'seriesContainer', 'class': 'seriesList'})
            if not series_container:
                return []
            
            genre_sections = series_container.find_all('div', class_='genre')
            all_series = []
            
            for genre_section in genre_sections:
                # Get genre name
                genre_name = "Unknown"
                genre_list = genre_section.find('div', class_='seriesGenreList')
                if genre_list:
                    genre_title = genre_list.find('h3')
                    if genre_title:
                        genre_name = genre_title.get_text(strip=True)
                
                # Find series list
                series_ul = genre_section.find('ul')
                if not series_ul:
                    continue
                
                # Extract all series links
                for li in series_ul.find_all('li'):
                    link = li.find('a')
                    if not link:
                        continue
                    
                    series_name = link.get_text(strip=True)
                    series_endpoint = link.get('href')
                    
                    if not series_name or not series_endpoint:
                        continue
                    
                    series_url = urljoin(self.base_url, series_endpoint)
                    
                    # Skip if already exists
                    if series_url in existing_urls:
                        continue
                    
                    all_series.append({
                        'name': series_name,
                        'url': series_url,
                        'genre': genre_name
                    })
            
            return all_series
            
        except:
            return []
    
    def merge_with_existing(self, series_to_add: List[Dict], existing_data: Dict = None) -> Dict:
        """Merge new series with existing data"""
        # Handle blacklist if enabled
        if self.use_blacklist and existing_data:
            deleted_urls = set(existing_data.get('deleted_urls', []))
            series_to_add = [s for s in series_to_add if s['url'] not in deleted_urls]
        
        # Merge data
        if existing_data:
            all_series = existing_data.get('series', []) + series_to_add
        else:
            all_series = series_to_add
        
        # Quick genre count
        genre_stats = {}
        for series in all_series:
            genre = series['genre']
            genre_stats[genre] = genre_stats.get(genre, 0) + 1
        
        result = {
            'script': 'catalog_scraper',
            'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_series': len(all_series),
            'series_added': len(series_to_add),
            'total_genres': len(genre_stats),
            'genre_breakdown': dict(sorted(genre_stats.items(), key=lambda x: x[1], reverse=True)),
            'series': all_series
        }
        
        # Add blacklist data if enabled
        if self.use_blacklist:
            result['deleted_urls'] = list(existing_data.get('deleted_urls', [])) if existing_data else []
        
        return result
    
    def save_data(self, data: Dict) -> bool:
        """Save data to JSON file"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False
    
    def run(self, update_mode: bool = True) -> bool:
        """Run the catalog scraper"""
        start_time = time.time()
        
        # Load existing data if update mode
        existing_data = None
        existing_urls = set()
        
        if update_mode:
            existing_data = self.load_existing_data()
            if existing_data:
                existing_urls = self.get_existing_urls(existing_data)
        
        # Scrape series
        series_to_add = self.scrape_all_genres(existing_urls)
        
        if not series_to_add and not existing_data:
            return False
        
        # Merge and save
        final_data = self.merge_with_existing(series_to_add, existing_data)
        success = self.save_data(final_data)
        
        # Quick results
        duration = time.time() - start_time
        print(f"⚡ {duration:.1f}s | {final_data['total_series']} total | +{len(series_to_add)} new")
        
        return success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SerienStream Catalog Scraper')
    parser.add_argument('--fresh', action='store_true', help='Force fresh scrape')
    parser.add_argument('--blacklist', action='store_true', help='Enable blacklist feature')
    args = parser.parse_args()
    
    scraper = CatalogScraper(use_blacklist=args.blacklist)
    
    try:
        success = scraper.run(update_mode=not args.fresh)
        print("✅ Done" if success else "❌ Failed")
    except KeyboardInterrupt:
        print("🛑 Stopped")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    main()