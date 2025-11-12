#!/usr/bin/env python3
"""
Manual Series Updater
Allows manual updating of series data in the database
"""
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path to import scrapers
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_database(site: str) -> tuple:
    """Load database for a site"""
    project_root = Path(__file__).parent.parent
    db_path = project_root / f"sites/{site}/data/final_series_data.json"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return None, None
    
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data['series'])} series from {site}")
        return data, db_path
    except Exception as e:
        print(f"❌ Error loading database: {e}")
        return None, None

def search_series(data: Dict, query: str) -> List[tuple]:
    """Search for series by name"""
    query = query.lower()
    results = []
    
    for idx, series in enumerate(data['series']):
        if query in series['name'].lower():
            results.append((idx, series))
    
    return results

def display_series_info(series: Dict):
    """Display detailed series information"""
    print("\n" + "="*70)
    print(f"📺 {series['name']}")
    print(f"🔗 URL: {series['url']}")
    print(f"📅 Start Date: {series.get('start_date', 'N/A')}")
    
    # Count content
    season_count = len(series.get('seasons', {}))
    episode_count = sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
    movie_count = len(series.get('movies', {}))
    
    print(f"📊 Seasons: {season_count} | Episodes: {episode_count} | Movies: {movie_count}")
    print("="*70)

def update_series_simple(site: str, series_url: str, series_name: str = "Manual Update") -> Optional[Dict]:
    """Update a series by running the scrapers directly"""
    import subprocess

    site_dir = Path(__file__).parent.parent / f"sites/{site}"
    data_dir = site_dir / "data"

    print(f"\n🔄 Updating series from {site}...")
    print(f"📥 Fetching latest data for: {series_url}")

    # Create a minimal catalog file with just this series
    import tempfile
    import shutil

    # Backup existing tmp files
    tmp_files = ['tmp_name_url.json', 'tmp_season_episode_data.json', 'tmp_episode_streams.json']
    backups = {}
    for tmp_file in tmp_files:
        tmp_path = data_dir / tmp_file
        if tmp_path.exists():
            backup_path = data_dir / f"{tmp_file}.backup"
            shutil.copy(tmp_path, backup_path)
            backups[tmp_file] = backup_path

    try:
        # Create minimal catalog
        catalog_data = {
            "script": "manual_updater",
            "total_series": 1,
            "series": [{"name": series_name, "url": series_url}]
        }
        
        catalog_path = data_dir / "tmp_name_url.json"
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(catalog_data, f, indent=2)
        
        # Run structure analyzer (script 2)
        print("🔍 Step 1/3: Analyzing structure...")
        result = subprocess.run(
            ["python3", "2_url_season_episode_num.py", "--limit", "1"],
            cwd=site_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            print(f"❌ Structure analysis failed")
            print(result.stderr)
            return None
        
        # Run streams analyzer (script 3)
        print("🔍 Step 2/3: Analyzing streams...")
        result = subprocess.run(
            ["python3", "3_language_streamurl.py", "--limit", "1"],
            cwd=site_dir,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            print(f"❌ Stream analysis failed")
            print(result.stderr)
            return None
        
        # Run JSON structurer (script 4)
        print("🔍 Step 3/3: Structuring data...")
        result = subprocess.run(
            ["python3", "4_json_structurer.py"],
            cwd=site_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"❌ JSON structuring failed")
            print(result.stderr)
            return None
        
        # Load the final structured data
        final_path = data_dir / "final_series_data.json"
        if final_path.exists():
            with open(final_path, 'r', encoding='utf-8') as f:
                final_data = json.load(f)
                if final_data['series']:
                    print("✅ Series data updated successfully")
                    return final_data['series'][0]
        
        print("❌ No updated data found")
        return None
        
    except subprocess.TimeoutExpired:
        print("❌ Update timed out")
        return None
    except Exception as e:
        print(f"❌ Update failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Restore backups
        for tmp_file, backup_path in backups.items():
            if backup_path.exists():
                shutil.copy(backup_path, data_dir / tmp_file)
                backup_path.unlink()

def save_database(data: Dict, db_path: Path, create_backup: bool = True):
    """Save updated database"""
    try:
        # Ask about backup if not specified
        backup_path = db_path.with_suffix('.json.backup')

        if create_backup:
            # Create backup
            with open(db_path, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(backup_data)

        # Save updated data
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Database saved to: {db_path}")
        if create_backup:
            print(f"💾 Backup created: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False

def update_jellyfin_folder(site: str, series_data: Dict) -> bool:
    """Update a single series folder structure on Jellyfin server"""
    try:
        import subprocess

        jellyfin_name = series_data.get('jellyfin_name', series_data['name'])
        print(f"📁 Updating Jellyfin folder for {jellyfin_name}...")

        # Remove old folder if exists
        result = subprocess.run(
            ["ssh", "jellyfin", f"rm -rf '/media/jellyfin/{site}/{jellyfin_name}'"],
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            print(f"🗑️  Removed old: {jellyfin_name}")

        # Create base series directory
        subprocess.run(
            ["ssh", "jellyfin", f"mkdir -p '/media/jellyfin/{site}/{jellyfin_name}'"],
            capture_output=True,
            timeout=10
        )
        print(f"📁 Creating: {jellyfin_name}")

        # Process each season
        for season_key, season_data in series_data.get('seasons', {}).items():
            season_num = season_key.replace('season_', '')
            season_dir = f"/media/jellyfin/{site}/{jellyfin_name}/Season {season_num}"

            # Create season directory
            subprocess.run(
                ["ssh", "jellyfin", f"mkdir -p '{season_dir}'"],
                capture_output=True,
                timeout=10
            )

            # Process each episode
            for ep_key, ep_data in season_data.get('episodes', {}).items():
                ep_num = ep_key.replace('episode_', '')

                # Get best redirect (Deutsch preferred)
                streams = ep_data.get('streams_by_language', {})
                redirect_url = None

                if 'Deutsch' in streams and streams['Deutsch']:
                    redirect_url = streams['Deutsch'][0].get('stream_url')
                elif streams:
                    # Use first available language
                    first_lang = list(streams.keys())[0]
                    if streams[first_lang]:
                        redirect_url = streams[first_lang][0].get('stream_url')

                if redirect_url and '/redirect/' in redirect_url:
                    redirect_id = redirect_url.split('/redirect/')[-1]
                    api_url = f"http://localhost:3000/stream/redirect/{redirect_id}"

                    strm_file = f"{season_dir}/S{int(season_num):02d}E{int(ep_num):02d}.strm"

                    # Create .strm file remotely
                    subprocess.run(
                        ["ssh", "jellyfin", f"echo '{api_url}' > '{strm_file}'"],
                        capture_output=True,
                        timeout=10
                    )

        print(f"✅ Created {jellyfin_name} with all episodes")
        return True

    except Exception as e:
        print(f"❌ Error updating folder: {e}")
        return False

def push_to_jellyfin(site: str, db_path: Path, series_data: Dict = None) -> bool:
    """Push updated database to Jellyfin server and update folder structure"""
    try:
        import subprocess

        jellyfin_path = f"/opt/jellyfin-streaming-platform/sites/{site}/data/final_series_data.json"

        print(f"📤 Pushing to Jellyfin server...")
        result = subprocess.run(
            ["scp", str(db_path), f"jellyfin:{jellyfin_path}"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("✅ Database pushed to Jellyfin server")

            # Update folder structure if series data provided
            if series_data:
                update_jellyfin_folder(site, series_data)

            # Restart API
            print("🔄 Restarting API...")
            subprocess.run(
                ["ssh", "jellyfin", "systemctl restart streaming-api"],
                capture_output=True,
                timeout=10
            )
            print("✅ API restarted")
            return True
        else:
            print(f"❌ Push failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error pushing to Jellyfin: {e}")
        return False

def main():
    """Main interactive loop"""
    print("="*70)
    print("🔧 Manual Series Updater")
    print("="*70)
    
    # Load both databases
    print("\n📚 Loading databases...")
    serienstream_data, serienstream_path = load_database("serienstream")
    aniworld_data, aniworld_path = load_database("aniworld")
    
    if not serienstream_data and not aniworld_data:
        print("❌ No databases could be loaded!")
        return
    
    while True:
        print("\n" + "="*70)
        print("Select site to update:")
        if serienstream_data:
            print("  1. SerienStream")
        if aniworld_data:
            print("  2. Aniworld")
        print("  0. Exit")
        print("="*70)
        
        choice = input("Choice: ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice == "1" and serienstream_data:
            site_name = "serienstream"
            data = serienstream_data
            db_path = serienstream_path
        elif choice == "2" and aniworld_data:
            site_name = "aniworld"
            data = aniworld_data
            db_path = aniworld_path
        else:
            print("❌ Invalid choice")
            continue
        
        # Search for series
        query = input("\n🔍 Search for series: ").strip()
        if not query:
            continue
        
        results = search_series(data, query)
        
        if not results:
            print(f"❌ No series found matching '{query}'")
            continue
        
        print(f"\n✅ Found {len(results)} result(s):")
        for i, (idx, series) in enumerate(results[:20], 1):  # Limit to 20 results
            print(f"  {i}. {series['name']}")
        
        if len(results) > 20:
            print(f"  ... and {len(results)-20} more")
        
        # Select series
        try:
            series_num = int(input("\nSelect series number (0 to cancel): ").strip())
            if series_num == 0:
                continue
            if series_num < 1 or series_num > len(results):
                print("❌ Invalid selection")
                continue
            
            series_idx, series = results[series_num - 1]
        except ValueError:
            print("❌ Invalid input")
            continue
        
        # Display series info
        display_series_info(series)
        
        # Confirm update
        confirm = input("\n⚠️  Update this series? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Update cancelled")
            continue

        # Update series
        updated_series = update_series_simple(site_name, series['url'], series['name'])
        
        if updated_series:
            # Replace in database
            data['series'][series_idx] = updated_series
            print("✅ Series updated in database")
            
            # Display updated info
            display_series_info(updated_series)

            # Ask about backup
            backup = input("\n💾 Create backup before saving? (y/n): ").strip().lower()
            create_backup = backup == 'y'

            # Save locally
            if save_database(data, db_path, create_backup):
                # Ask about pushing to Jellyfin
                push = input("\n📤 Push to Jellyfin server? (y/n): ").strip().lower()
                if push == 'y':
                    push_to_jellyfin(site_name, db_path, updated_series)
                else:
                    print("💡 Run this script on Jellyfin server or manually copy the database")
            else:
                print("❌ Failed to save database")
        else:
            print("❌ Update failed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
