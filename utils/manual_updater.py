#!/usr/bin/env python3
"""
Manual Series Updater
Allows manual updating of series data in the database
Works on both code server and Jellyfin server
"""
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import shutil

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
    print(f"📅 Jellyfin Name: {series.get('jellyfin_name', 'N/A')}")

    # Count content
    season_count = len(series.get('seasons', {}))
    episode_count = sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
    movie_count = len(series.get('movies', {}))

    print(f"📊 Seasons: {season_count} | Episodes: {episode_count} | Movies: {movie_count}")
    print("="*70)

def update_series_simple(site: str, series_url: str, series_name: str = "Manual Update") -> Optional[Dict]:
    """Update a series by running the scrapers directly"""

    site_dir = Path(__file__).parent.parent / f"sites/{site}"
    data_dir = site_dir / "data"

    print(f"\n🔄 Updating series from {site}...")
    print(f"📥 Fetching latest data for: {series_url}")

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
        backup_path = db_path.with_suffix('.json.backup')

        if create_backup:
            # Create backup
            with open(db_path, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(backup_data)
            print(f"💾 Backup created: {backup_path}")

        # Save updated data
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Database saved to: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False

def update_jellyfin_structure(site: str, series_name: str) -> bool:
    """
    Regenerate Jellyfin folder structure for a specific series
    Uses the 7_jellyfin_structurer.py script with series name filter
    """
    try:
        print(f"\n📁 Regenerating Jellyfin structure for: {series_name}")

        # Create temp JSON with just this series for structurer
        site_dir = Path(__file__).parent.parent / f"sites/{site}"
        data_dir = site_dir / "data"

        # Load full database
        with open(data_dir / "final_series_data.json", 'r', encoding='utf-8') as f:
            full_data = json.load(f)

        # Find the series
        target_series = None
        for series in full_data['series']:
            if series.get('jellyfin_name') == series_name or series['name'] == series_name:
                target_series = series
                break

        if not target_series:
            print(f"❌ Series not found in database: {series_name}")
            return False

        jellyfin_name = target_series.get('jellyfin_name', target_series['name'])

        # Remove old folder on Jellyfin server
        print(f"🗑️  Removing old folder: {jellyfin_name}")
        result = subprocess.run(
            ["ssh", "jellyfin", f"rm -rf '/media/jellyfin/{site}/{jellyfin_name}'"],
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            print(f"✅ Old folder removed")

        # Create temp database with just this series
        temp_data = {
            "series": [target_series],
            "script": "manual_updater_structure"
        }

        temp_db_path = data_dir / "temp_single_series.json"
        with open(temp_db_path, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, indent=2, ensure_ascii=False)

        # Run structurer script with the temp database
        print(f"📝 Generating new structure...")

        # Import and run structurer directly
        import sys
        sys.path.insert(0, str(site_dir))

        # Backup original final file
        final_file = data_dir / "final_series_data.json"
        final_backup = data_dir / "final_series_data.json.temp_backup"
        shutil.copy(final_file, final_backup)

        # Temporarily replace with single series
        shutil.copy(temp_db_path, final_file)

        try:
            # Check if we're on Jellyfin or code server
            location = check_location()

            if location == "jellyfin":
                # Run locally on Jellyfin server
                result = subprocess.run(
                    ["python3", "7_jellyfin_structurer.py", "--api-url", "http://localhost:3000/stream/redirect", "--clear-progress"],
                    cwd=site_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            else:
                # Push temp database to Jellyfin first
                temp_jellyfin_path = f"/opt/JellyStream/sites/{site}/data/temp_single_series.json"
                result = subprocess.run(
                    ["scp", str(temp_db_path), f"jellyfin:{temp_jellyfin_path}"],
                    capture_output=True,
                    timeout=30
                )

                if result.returncode != 0:
                    print(f"❌ Failed to copy temp database to Jellyfin")
                    return False

                # Run structurer on Jellyfin server via SSH
                result = subprocess.run(
                    ["ssh", "jellyfin",
                     f"cd /opt/JellyStream/sites/{site} && "
                     f"cp data/final_series_data.json data/final_series_data.json.temp_backup && "
                     f"cp data/temp_single_series.json data/final_series_data.json && "
                     f"python3 7_jellyfin_structurer.py --api-url http://localhost:3000/stream/redirect --clear-progress && "
                     f"cp data/final_series_data.json.temp_backup data/final_series_data.json && "
                     f"rm data/final_series_data.json.temp_backup data/temp_single_series.json"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            if result.returncode == 0:
                print(f"✅ Structure generated successfully")
                return True
            else:
                print(f"❌ Structure generation failed:")
                print(result.stderr)
                return False

        finally:
            # Restore original database (only on code server)
            if check_location() == "codeserver":
                shutil.copy(final_backup, final_file)
                final_backup.unlink()
                temp_db_path.unlink()
            else:
                # Clean up temp files on Jellyfin
                shutil.copy(final_backup, final_file)
                final_backup.unlink()
                temp_db_path.unlink()

    except Exception as e:
        print(f"❌ Error updating structure: {e}")
        import traceback
        traceback.print_exc()
        return False

def push_to_jellyfin(site: str, db_path: Path) -> bool:
    """Push updated database to Jellyfin server"""
    try:
        # Fixed path
        jellyfin_path = f"/opt/JellyStream/sites/{site}/data/final_series_data.json"

        print(f"\n📤 Pushing database to Jellyfin server...")
        result = subprocess.run(
            ["scp", str(db_path), f"jellyfin:{jellyfin_path}"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("✅ Database pushed to Jellyfin server")

            # Restart API with correct service name
            print("🔄 Restarting API...")
            subprocess.run(
                ["ssh", "jellyfin", "systemctl restart jellystream-api"],
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

def check_location():
    """Check if we're running on code server or Jellyfin server"""
    try:
        hostname = subprocess.run(
            ["hostname"],
            capture_output=True,
            text=True,
            timeout=5
        ).stdout.strip()

        if "jellyfin" in hostname.lower():
            return "jellyfin"
        else:
            return "codeserver"
    except:
        return "unknown"

def main():
    """Main interactive loop"""
    print("="*70)
    print("🔧 Manual Series Updater")
    print("="*70)

    # Detect location
    location = check_location()
    print(f"\n📍 Running on: {location}")

    # Load both databases
    print("\n📚 Loading databases...")
    serienstream_data, serienstream_path = load_database("serienstream")
    aniworld_data, aniworld_path = load_database("aniworld")

    if not serienstream_data and not aniworld_data:
        print("❌ No databases could be loaded!")
        return

    # Collect series to update
    series_to_update = []  # List of (site_name, data, db_path, series_idx, series)

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

        # Ask to add to list
        add = input("\n➕ Add this series to update list? (y/n): ").strip().lower()
        if add == 'y':
            series_to_update.append((site_name, data, db_path, series_idx, series))
            print(f"✅ Added to list ({len(series_to_update)} series total)")

            # Show all series in list
            print("\n📋 Series to update:")
            for i, (s_site, s_data, s_path, s_idx, s_series) in enumerate(series_to_update, 1):
                print(f"  {i}. [{s_site}] {s_series['name']}")

        # Ask to add another
        another = input("\n➕ Add another series? (y/n): ").strip().lower()
        if another != 'y':
            break

    # Exit if no series selected
    if not series_to_update:
        print("👋 No series selected. Goodbye!")
        return

    # Show final list
    print("\n" + "="*70)
    print(f"📋 FINAL UPDATE LIST ({len(series_to_update)} series):")
    print("="*70)
    for i, (s_site, s_data, s_path, s_idx, s_series) in enumerate(series_to_update, 1):
        print(f"\n{i}. [{s_site.upper()}]")
        display_series_info(s_series)

    # Confirm batch update
    confirm = input("\n⚠️  Update all these series? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Update cancelled")
        return

    # Ask about backup BEFORE updating
    backup = input("\n💾 Create backup before updating? (Y/n): ").strip().lower()
    create_backup = backup != 'n'

    # Create backups NOW (before any changes) - one per database
    backups_created = {}
    if create_backup:
        for site_name, data, db_path, _, _ in series_to_update:
            if db_path not in backups_created:
                backup_path = Path(str(db_path) + '.backup')
                try:
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    backups_created[db_path] = backup_path
                    print(f"💾 Backup created: {backup_path}")
                except Exception as e:
                    print(f"❌ Backup failed: {e}")
                    retry = input("⚠️  Continue without backup? (y/n): ").strip().lower()
                    if retry != 'y':
                        print("❌ Update cancelled")
                        return

    # Process each series
    print("\n" + "="*70)
    print("🔄 Starting batch update...")
    print("="*70)

    updated_series_list = []
    for i, (site_name, data, db_path, series_idx, series) in enumerate(series_to_update, 1):
        print(f"\n[{i}/{len(series_to_update)}] Updating: {series['name']}")

        # Update series data
        updated_series = update_series_simple(site_name, series['url'], series['name'])

        if not updated_series:
            print(f"❌ Update failed for: {series['name']}")
            continue

        # Replace in database
        data['series'][series_idx] = updated_series
        print(f"✅ Updated: {series['name']}")
        updated_series_list.append((site_name, data, db_path, updated_series))

    # Save all databases
    print("\n" + "="*70)
    print("💾 Saving databases...")
    print("="*70)

    saved_dbs = {}
    for site_name, data, db_path, updated_series in updated_series_list:
        if db_path not in saved_dbs:
            if save_database(data, db_path, create_backup=False):
                saved_dbs[db_path] = (site_name, data, db_path)

    # Ask about pushing to Jellyfin (only if on code server)
    if location == "codeserver" and saved_dbs:
        push = input("\n📤 Push databases to Jellyfin server? (y/n): ").strip().lower()
        if push == 'y':
            for db_path, (site_name, data, path) in saved_dbs.items():
                push_to_jellyfin(site_name, path)
    elif saved_dbs:
        print("💡 Already on Jellyfin server - databases updated locally")

    # Ask about structure update
    structure = input("\n📁 Update Jellyfin folder structures? (y/n): ").strip().lower()
    if structure == 'y':
        print("\n🔄 Updating Jellyfin structures...")
        for site_name, data, db_path, updated_series in updated_series_list:
            jellyfin_name = updated_series.get('jellyfin_name', updated_series['name'])
            print(f"\n📁 {jellyfin_name}...")
            update_jellyfin_structure(site_name, jellyfin_name)

    print("\n" + "="*70)
    print(f"✅ Batch update complete! ({len(updated_series_list)}/{len(series_to_update)} succeeded)")
    print("="*70)

def plugin_mode():
    """Plugin mode - accepts command line arguments for non-interactive use"""
    import argparse

    parser = argparse.ArgumentParser(description='Manual Series Updater - Plugin Mode')
    parser.add_argument('--plugin', action='store_true', help='Enable plugin mode (non-interactive)')
    parser.add_argument('--site', choices=['aniworld', 'serienstream'], required=True, help='Site name')
    parser.add_argument('--series-name', required=True, help='Series jellyfin_name or name to update')
    parser.add_argument('--list-series', action='store_true', help='List all series as JSON')
    parser.add_argument('--search', help='Search for series (returns JSON)')
    parser.add_argument('--json', action='store_true', help='Output as JSON for plugin consumption')

    args = parser.parse_args()

    if not args.plugin:
        # Not in plugin mode, run interactive
        main()
        return

    # Plugin mode - handle commands
    try:
        # Load database
        data, db_path = load_database(args.site)
        if not data:
            if args.json:
                print(json.dumps({"success": False, "error": "Database not found"}))
            else:
                print(f"❌ Database not found for {args.site}")
            sys.exit(1)

        # Handle list command
        if args.list_series:
            series_list = []
            for idx, series in enumerate(data['series']):
                series_list.append({
                    "name": series['name'],
                    "jellyfin_name": series.get('jellyfin_name', series['name']),
                    "url": series['url'],
                    "season_count": len(series.get('seasons', {})),
                    "episode_count": sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
                })
            print(json.dumps({"success": True, "series": series_list}))
            return

        # Handle search command
        if args.search:
            results = search_series(data, args.search)
            series_list = []
            for idx, series in results[:50]:  # Limit to 50 results
                series_list.append({
                    "name": series['name'],
                    "jellyfin_name": series.get('jellyfin_name', series['name']),
                    "url": series['url'],
                    "season_count": len(series.get('seasons', {})),
                    "episode_count": sum(len(season.get('episodes', {})) for season in series.get('seasons', {}).values())
                })
            print(json.dumps({"success": True, "count": len(results), "series": series_list}))
            return

        # Handle update command
        # Find series
        target_series = None
        series_idx = -1
        for idx, series in enumerate(data['series']):
            jellyfin_name = series.get('jellyfin_name', series['name'])
            if jellyfin_name == args.series_name or series['name'] == args.series_name:
                target_series = series
                series_idx = idx
                break

        if not target_series:
            if args.json:
                print(json.dumps({"success": False, "error": f"Series not found: {args.series_name}"}))
            else:
                print(f"❌ Series not found: {args.series_name}")
            sys.exit(1)

        # Update the series
        if args.json:
            print(json.dumps({"success": True, "message": f"Starting update for {args.series_name}"}))

        updated_series = update_series_simple(args.site, target_series['url'], target_series['name'])

        if not updated_series:
            if args.json:
                print(json.dumps({"success": False, "error": "Update failed"}))
            sys.exit(1)

        # Replace in database
        data['series'][series_idx] = updated_series

        # Save database
        if not save_database(data, db_path, create_backup=True):
            if args.json:
                print(json.dumps({"success": False, "error": "Failed to save database"}))
            sys.exit(1)

        # Update Jellyfin structure
        jellyfin_name = updated_series.get('jellyfin_name', updated_series['name'])
        if not update_jellyfin_structure(args.site, jellyfin_name):
            if args.json:
                print(json.dumps({"success": False, "error": "Failed to regenerate .strm files"}))
            sys.exit(1)

        # Success
        if args.json:
            episode_count = sum(len(season.get('episodes', {})) for season in updated_series.get('seasons', {}).values())
            print(json.dumps({
                "success": True,
                "series": args.series_name,
                "episodes": episode_count,
                "message": f"Successfully updated {args.series_name}"
            }))
        else:
            print(f"✅ Successfully updated {args.series_name}")

    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        plugin_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
