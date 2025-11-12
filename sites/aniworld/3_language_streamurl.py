#!/usr/bin/env python3
"""
Episode Streams Analyzer
Extracts available languages and streaming URLs for each episode
Input: data/tmp_season_episode_data.json
Output: data/tmp_episode_streams.json
set limit with [--limit] [num] flag.
set batch processing with [-b] [num] flag.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
import config
from urllib.parse import urljoin

class EpisodeStreamsAnalyzer:
    def __init__(self, limit: Optional[int] = None, batch_size: Optional[int] = None):
        self.limit = limit
        self.batch_size = batch_size
        self.base_url = config.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.data_folder = Path(config.DATA_DIR)
        self.input_file = self.data_folder / "tmp_season_episode_data.json"
        self.output_file = self.data_folder / "tmp_episode_streams.json"
    
    def load_series_data(self) -> List[Dict]:
        """Load series data from input file"""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('series', [])
        except Exception as e:
            print(f"❌ Error loading {self.input_file}: {e}")
            return []
    
    def load_existing_data(self) -> Dict:
        """Load existing analyzed data if file exists"""
        if self.output_file.exists():
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"📂 Found existing data: {data.get('total_series', 0)} series")
                return data
            except Exception as e:
                print(f"⚠️  Error loading existing data: {e}")
        return None
    
    def get_existing_names(self, existing_data: Dict) -> set:
        """Get set of existing series names to avoid duplicates"""
        if not existing_data or 'series' not in existing_data:
            return set()
        
        existing_names = {series['name'] for series in existing_data['series']}
        print(f"🔍 Found {len(existing_names)} existing series")
        return existing_names
    
    def save_batch_data(self, new_series: List[Dict], existing_data: Dict = None) -> Dict:
        """Save batch data by merging with existing data"""
        if existing_data:
            # Merge with existing data
            all_series = existing_data.get('series', []) + new_series
        else:
            # First batch
            all_series = new_series
        
        # Calculate statistics
        total_movies = sum(len(series.get('movies', {})) for series in all_series)
        total_episodes = sum(
            sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
            for series in all_series
        )
        total_endpoints = sum(
            len(series.get('movies', {})) + 
            sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
            for series in all_series
        )
        
        output_data = {
            'script': 'episode_streams_analyzer',
            'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_series': len(all_series),
            'total_endpoints_processed': total_endpoints,
            'total_movies': total_movies,
            'total_episodes': total_episodes,
            'processing_errors': existing_data.get('processing_errors', 0) if existing_data else 0,
            'series': all_series
        }
        
        # Save to file
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"   💾 Saved {len(all_series)} total series to database")
            return output_data
        except Exception as e:
            print(f"   ❌ Error saving data: {e}")
            return existing_data or {}
    
    def get_start_date(self, series_url: str) -> str:
        """Get start date from series page"""
        try:
            response = self.session.get(series_url, timeout=15)
            if response.status_code != 200:
                return ""
            
            soup = BeautifulSoup(response.content, 'html.parser')
            start_date_element = soup.find('span', itemprop='startDate')
            
            return start_date_element.get_text(strip=True) if start_date_element else ""
        except:
            return ""
    
    def extract_languages(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract available languages from changeLanguageBox"""
        languages = {}
        
        try:
            lang_box = soup.find('div', class_='changeLanguageBox')
            if not lang_box:
                return languages
            
            lang_elements = lang_box.find_all(attrs={'data-lang-key': True, 'title': True})
            
            for element in lang_elements:
                lang_key = element.get('data-lang-key')
                lang_title = element.get('title')
                
                if lang_key and lang_title:
                    languages[lang_key] = lang_title
            
            return languages
        except:
            return languages
    
    def extract_streams(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract streaming URLs and providers from hosterSiteVideo"""
        streams = []
        
        try:
            video_section = soup.find('div', class_='hosterSiteVideo')
            if not video_section:
                return streams
            
            row_ul = video_section.find('ul', class_='row')
            if not row_ul:
                return streams
            
            stream_items = row_ul.find_all('li', attrs={'data-lang-key': True, 'data-link-target': True})
            
            for item in stream_items:
                try:
                    lang_key = item.get('data-lang-key')
                    link_target = item.get('data-link-target')
                    
                    h4_element = item.find('h4')
                    provider_name = h4_element.get_text(strip=True) if h4_element else 'Unknown'
                    
                    stream_url = urljoin(self.base_url, link_target)
                    
                    streams.append({
                        'language_key': lang_key,
                        'provider': provider_name,
                        'stream_url': stream_url
                    })
                except:
                    continue
            
            return streams
        except:
            return streams
    
    def analyze_episode(self, episode_url: str) -> tuple[Dict[str, str], List[Dict]]:
        """Analyze a single episode for languages and streams"""
        try:
            response = self.session.get(episode_url, timeout=15)
            if response.status_code != 200:
                return {}, []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            languages = self.extract_languages(soup)
            streams = self.extract_streams(soup)
            
            return languages, streams
        except:
            return {}, []
    
    def parse_endpoint(self, endpoint: str, movie_count: int) -> Dict:
        """Parse endpoint to determine if it's a movie or episode"""
        if '/filme/' in endpoint:
            # Movie endpoint
            film_num = endpoint.split('/film-')[-1]
            return {
                'type': 'movie',
                'movie_number': int(film_num),
                'season': None,
                'episode': None
            }
        elif '/staffel-' in endpoint and '/episode-' in endpoint:
            # Episode endpoint
            parts = endpoint.split('/')
            season_part = [p for p in parts if p.startswith('staffel-')][0]
            episode_part = [p for p in parts if p.startswith('episode-')][0]
            
            season_num = int(season_part.split('-')[1])
            episode_num = int(episode_part.split('-')[1])
            
            return {
                'type': 'episode',
                'movie_number': None,
                'season': season_num,
                'episode': episode_num
            }
        
        return {'type': 'unknown'}
    
    def analyze_series(self, series: Dict) -> Dict:
        """Analyze a complete series by processing each endpoint"""
        series_name = series['name']
        series_url = series['url']
        movie_count = series.get('movie_count', 0)
        season_count = series.get('season_count', 0)
        episode_counts = series.get('episode_counts', [])
        endpoints = series.get('endpoints', [])
        
        # Get start date
        start_date = self.get_start_date(series_url)
        
        # Structure to organize results
        result = {
            'name': series_name,
            'url': series_url,
            'start_date': start_date,
            'movies': {},
            'seasons': {}
        }
        
        # Initialize seasons structure
        for season_num in range(1, season_count + 1):
            episode_count = episode_counts[season_num - 1] if season_num - 1 < len(episode_counts) else 0
            result['seasons'][f'season_{season_num}'] = {
                'episode_count': episode_count,
                'episodes': {}
            }
        
        # Process each endpoint
        for endpoint in endpoints:
            try:
                endpoint_info = self.parse_endpoint(endpoint, movie_count)
                languages, streams = self.analyze_episode(endpoint)
                
                # Group streams by language
                streams_by_language = {}
                for stream in streams:
                    lang_key = stream['language_key']
                    lang_name = languages.get(lang_key, f"Language_{lang_key}")
                    
                    if lang_name not in streams_by_language:
                        streams_by_language[lang_name] = []
                    
                    streams_by_language[lang_name].append({
                        'provider': stream['provider'],
                        'stream_url': stream['stream_url']
                    })
                
                episode_data = {
                    'url': endpoint,
                    'languages': languages,
                    'streams_by_language': streams_by_language,
                    'total_streams': len(streams)
                }
                
                # Store in appropriate structure
                if endpoint_info['type'] == 'movie':
                    movie_num = endpoint_info['movie_number']
                    result['movies'][f'movie_{movie_num}'] = episode_data
                elif endpoint_info['type'] == 'episode':
                    season_num = endpoint_info['season']
                    episode_num = endpoint_info['episode']
                    season_key = f'season_{season_num}'
                    
                    if season_key in result['seasons']:
                        result['seasons'][season_key]['episodes'][f'episode_{episode_num}'] = episode_data
                
            except Exception as e:
                continue
        
        return result
    
    def run(self):
        """Run the episode streams analysis"""
        # Check if batch processing is enabled
        if self.batch_size:
            print("🚀 Episode Streams Analyzer (Batch Mode)")
            print(f"📂 Input: {self.input_file}")
            print(f"📂 Output: {self.output_file}")
            print(f"📊 Batch size: {self.batch_size}")
            if self.limit:
                print(f"📊 Total limit: {self.limit}")
            print("=" * 50)
            
            start_time = time.time()
            
            # Load series data
            series_list = self.load_series_data()
            if not series_list:
                print("❌ No series data found!")
                return False
            
            # Apply total limit if set
            if self.limit:
                series_list = series_list[:self.limit]
                print(f"📊 Limited to first {len(series_list)} series")
            
            # Load existing data to avoid duplicates
            existing_data = self.load_existing_data()
            existing_names = self.get_existing_names(existing_data)
            
            # Filter out already processed series
            remaining_series = [s for s in series_list if s['name'] not in existing_names]
            
            if not remaining_series:
                print("✅ All series already processed!")
                return True
            
            print(f"📺 Processing {len(remaining_series)} remaining series in batches of {self.batch_size}")
            
            total_processed = 0
            errors = 0
            total_endpoints = 0
            
            # Process in batches
            for batch_start in range(0, len(remaining_series), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(remaining_series))
                batch = remaining_series[batch_start:batch_end]
                batch_num = (batch_start // self.batch_size) + 1
                total_batches = (len(remaining_series) + self.batch_size - 1) // self.batch_size
                
                print(f"\n🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} series)")
                batch_start_time = time.time()
                
                analyzed_batch = []
                
                for i, series in enumerate(batch):
                    series_name = series.get('name', 'Unknown')
                    endpoints_count = len(series.get('endpoints', []))
                    print(f"   📺 [{i+1}/{len(batch)}] Processing: {series_name} ({endpoints_count} endpoints)")
                    
                    try:
                        result = self.analyze_series(series)
                        analyzed_batch.append(result)
                        total_processed += 1
                        total_endpoints += endpoints_count
                        
                        # Count results
                        movies = len(result.get('movies', {}))
                        episodes = sum(len(season.get('episodes', {})) for season in result.get('seasons', {}).values())
                        print(f"      ✅ Completed: {movies} movies, {episodes} episodes processed")
                            
                    except Exception as e:
                        errors += 1
                        print(f"      ❌ Error: {e}")
                        continue
                
                # Save batch results
                print(f"   💾 Saving batch {batch_num} results...")
                existing_data = self.save_batch_data(analyzed_batch, existing_data)
                
                batch_duration = time.time() - batch_start_time
                print(f"   ✅ Batch {batch_num} complete: {len(analyzed_batch)} series processed in {batch_duration:.1f}s")
                print(f"   📊 Progress: {total_processed}/{len(remaining_series)} series ({total_processed/len(remaining_series)*100:.1f}%)")
                
                # Show current totals
                current_total = existing_data.get('total_series', 0)
                print(f"   📈 Database now contains: {current_total} total series")
            
            total_duration = time.time() - start_time
            print(f"\n⚡ BATCH PROCESSING COMPLETE!")
            print(f"⏱️  Total time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
            print(f"📊 Processed: {total_processed} series | Errors: {errors}")
            print(f"🎬 Final stats: {existing_data.get('total_movies', 0)} movies")
            print(f"📺 Final episodes: {existing_data.get('total_episodes', 0)} episodes")
            
            return True
        
        else:
            # Original single-run processing
            print("🚀 Episode Streams Analyzer")
            print(f"📂 Input: {self.input_file}")
            print(f"📂 Output: {self.output_file}")
            print("=" * 50)
            
            start_time = time.time()
            
            # Load series data
            series_list = self.load_series_data()
            if not series_list:
                print("❌ No series data found!")
                return False
            
            # Apply limit if set
            if self.limit:
                series_list = series_list[:self.limit]
                print(f"📺 Analyzing {len(series_list)} series (limit: {self.limit})...")
            else:
                print(f"📺 Analyzing {len(series_list)} series (no limit)...")
            
            analyzed_series = []
            processed = 0
            errors = 0
            total_endpoints = 0
            
            for series in series_list:
                try:
                    print(f"📺 Analyzing: {series['name']} ({len(series.get('endpoints', []))} endpoints)")
                    result = self.analyze_series(series)
                    analyzed_series.append(result)
                    processed += 1
                    total_endpoints += len(series.get('endpoints', []))
                    
                    if processed % 5 == 0:
                        print(f"📊 {processed}/{len(series_list)}")
                    
                except Exception as e:
                    errors += 1
                    continue
            
            # Calculate statistics
            total_movies = sum(len(series.get('movies', {})) for series in analyzed_series)
            total_episodes = sum(
                sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
                for series in analyzed_series
            )
            
            # Prepare output data
            output_data = {
                'script': 'episode_streams_analyzer',
                'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_series': len(analyzed_series),
                'total_endpoints_processed': total_endpoints,
                'total_movies': total_movies,
                'total_episodes': total_episodes,
                'processing_errors': errors,
                'series': analyzed_series
            }
            
            # Save results
            try:
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                duration = time.time() - start_time
                print(f"\n⚡ {duration:.1f}s | {len(analyzed_series)} series | {total_endpoints} endpoints")
                print(f"🎬 {total_movies} movies | 📺 {total_episodes} episodes")
                
                return True
                
            except Exception as e:
                print(f"❌ Error saving results: {e}")
                return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Episode Streams Analyzer')
    parser.add_argument('--limit', type=int, help='Limit number of series to process')
    parser.add_argument('-b', '--batch', type=int, help='Batch processing size (e.g., -b 10)')
    args = parser.parse_args()
    
    print(f"DEBUG: limit={args.limit}, batch={args.batch}")
    
    analyzer = EpisodeStreamsAnalyzer(limit=args.limit, batch_size=args.batch)
    
    try:
        success = analyzer.run()
        print("✅ Analysis complete!" if success else "❌ Analysis failed!")
    except KeyboardInterrupt:
        print("🛑 Interrupted")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    main()