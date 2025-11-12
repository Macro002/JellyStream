#!/usr/bin/env python3
"""
Main Orchestrator - Aniworld Database Builder
Runs all scraping scripts in sequence to build complete anime database
Output: data/final_aniworld_data.json
"""

import subprocess
import sys
import time
import logging
import json
import threading
from pathlib import Path
import config
from typing import Optional

# Try to import psutil, fallback if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil not available - resource monitoring disabled")
    print("💡 Install with: pip install psutil")

class AniworldOrchestrator:
    def __init__(self, limit: Optional[int] = None, batch_size: Optional[int] = None):
        self.limit = limit
        self.batch_size = batch_size or self.get_optimal_batch_size()
        self.data_folder = Path(config.DATA_DIR)
        
        # Setup logging and resource monitoring
        self.setup_logging()
        self.setup_resource_monitoring()
        
        # Script paths
        self.scripts = {
            'catalog': '1_catalog_scraper.py',
            'structure': '2_url_season_episode_num.py', 
            'streams': '3_language_streamurl.py',
            'structurer': '4_json_structurer.py'
        }
        
        # Output files to check
        self.output_files = {
            'catalog': self.data_folder / 'tmp_name_url.json',
            'structure': self.data_folder / 'tmp_season_episode_data.json',
            'streams': self.data_folder / 'tmp_episode_streams.json',
            'final': self.data_folder / 'final_series_data.json'
        }
    
    def get_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on available RAM"""
        if not PSUTIL_AVAILABLE:
            return 25  # Safe default without psutil
        
        try:
            # Get total RAM in GB
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
            
            if total_ram_gb >= 8:
                return 50  # High memory system
            elif total_ram_gb >= 4:
                return 25  # Medium memory system (like yours)
            else:
                return 10  # Low memory system
        except:
            return 25  # Safe default
    
    def setup_resource_monitoring(self):
        """Setup resource monitoring"""
        if not PSUTIL_AVAILABLE:
            self.logger.info("Resource monitoring disabled (psutil not available)")
            self.monitoring_active = False
            self.resource_warnings = []
            return
        
        self.monitoring_active = True
        self.resource_warnings = []
        
        # Start resource monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_resources, daemon=True)
        self.monitor_thread.start()
        
        # Log initial system specs
        try:
            cpu_count = psutil.cpu_count()
            ram_gb = psutil.virtual_memory().total / (1024**3)
            self.logger.info(f"System specs: {cpu_count} CPU cores, {ram_gb:.1f}GB RAM")
            self.logger.info(f"Optimal batch size: {self.batch_size}")
        except Exception as e:
            self.logger.warning(f"Could not get system specs: {e}")
    
    def monitor_resources(self):
        """Monitor system resources in background"""
        if not PSUTIL_AVAILABLE:
            return
        
        while self.monitoring_active:
            try:
                # Check every 30 seconds
                time.sleep(30)
                
                # Get current resource usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_available_gb = memory.available / (1024**3)
                
                # Log resource usage every 5 minutes
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    self.logger.info(f"Resources: CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}% ({memory_available_gb:.1f}GB free)")
                
                # Check for resource warnings
                if memory_percent > 85:
                    warning = f"⚠️  HIGH MEMORY USAGE: {memory_percent:.1f}% - Available: {memory_available_gb:.1f}GB"
                    if warning not in self.resource_warnings:
                        self.logger.warning(warning)
                        self.resource_warnings.append(warning)
                
                if cpu_percent > 90:
                    warning = f"⚠️  HIGH CPU USAGE: {cpu_percent:.1f}%"
                    if warning not in self.resource_warnings:
                        self.logger.warning(warning)
                        self.resource_warnings.append(warning)
                
                # Critical memory warning
                if memory_available_gb < 0.5:  # Less than 500MB free
                    self.logger.error(f"🚨 CRITICAL: Only {memory_available_gb:.1f}GB RAM available!")
                
            except Exception as e:
                self.logger.debug(f"Resource monitoring error: {e}")
                continue
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        if hasattr(self, 'monitoring_active'):
            self.monitoring_active = False
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        self.data_folder.mkdir(exist_ok=True)
        logs_folder = Path(config.LOGS_DIR)
        logs_folder.mkdir(exist_ok=True)
        log_file = logs_folder / 'pipeline.log'
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Log startup
        self.logger.info("="*60)
        self.logger.info("Aniworld Pipeline Started")
        self.logger.info(f"Limit: {self.limit if self.limit else 'None (full dataset)'}")
        self.logger.info(f"Batch size: {self.batch_size}")
        self.logger.info("="*60)
    
    def check_prerequisites(self) -> bool:
        """Check if all required scripts exist"""
        self.logger.info("Checking prerequisites...")
        
        missing_scripts = []
        for name, script_path in self.scripts.items():
            if not Path(script_path).exists():
                missing_scripts.append(script_path)
                self.logger.error(f"Missing script: {script_path}")
        
        if missing_scripts:
            self.logger.error(f"Missing scripts: {', '.join(missing_scripts)}")
            return False
        
        # Create data folder if it doesn't exist
        self.data_folder.mkdir(exist_ok=True)
        self.logger.info("All scripts found and data folder ready")
        return True
    
    def validate_json_file(self, file_path: Path) -> dict:
        """Validate and analyze JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Analyze content
            if 'series' in data:
                series_count = len(data['series'])
                self.logger.info(f"JSON validation - {file_path.name}: {series_count} series")
                
                # Check for empty/corrupt series
                empty_series = sum(1 for s in data['series'] if not s.get('name'))
                if empty_series > 0:
                    self.logger.warning(f"Found {empty_series} series with missing names in {file_path.name}")
                
                # Check specific data integrity
                if 'tmp_season_episode' in file_path.name:
                    total_endpoints = sum(len(s.get('endpoints', [])) for s in data['series'])
                    self.logger.info(f"Structure file has {total_endpoints} total endpoints")
                
                elif 'tmp_episode_streams' in file_path.name:
                    total_movies = sum(len(s.get('movies', {})) for s in data['series'])
                    total_episodes = sum(
                        sum(len(season.get('episodes', {})) for season in s.get('seasons', {}).values())
                        for s in data['series']
                    )
                    self.logger.info(f"Streams file has {total_movies} movies, {total_episodes} episodes")
                
                return data
            else:
                self.logger.error(f"No 'series' key found in {file_path.name}")
                return {}
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in {file_path.name}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error reading {file_path.name}: {e}")
            return {}
    
    def run_script(self, script_name: str, script_path: str, description: str) -> bool:
        """Run a single script and check for success"""
        self.logger.info("="*60)
        self.logger.info(f"STEP {list(self.scripts.keys()).index(script_name) + 1}: {description}")
        self.logger.info(f"Script: {script_path}")
        self.logger.info("="*60)
        
        # Build command
        cmd = [sys.executable, script_path]
        
        # Add limit if specified and script supports it (skip catalog scraper)
        if self.limit and script_name in ['structure', 'streams', 'structurer']:
            cmd.extend(['--limit', str(self.limit)])
            self.logger.info(f"Added limit: {self.limit}")
        
        # Add batch processing for structure and streams analyzers
        if script_name in ['structure', 'streams']:
            cmd.extend(['-b', str(self.batch_size)])
            self.logger.info(f"Added batch size: {self.batch_size}")
        
        self.logger.info(f"Running: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # Log resource usage before starting script
            if PSUTIL_AVAILABLE:
                try:
                    memory = psutil.virtual_memory()
                    cpu_percent = psutil.cpu_percent()
                    self.logger.info(f"Pre-script resources: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}% ({memory.available/(1024**3):.1f}GB free)")
                except:
                    pass
            
            # Run the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=14400  # 4 hour timeout for batch processing
            )
            
            duration = time.time() - start_time
            
            # Log resource usage after script
            if PSUTIL_AVAILABLE:
                try:
                    memory = psutil.virtual_memory()
                    cpu_percent = psutil.cpu_percent()
                    self.logger.info(f"Post-script resources: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}% ({memory.available/(1024**3):.1f}GB free)")
                except:
                    pass
            
            # Log all output
            if result.stdout:
                self.logger.info("Script STDOUT:")
                for line in result.stdout.strip().split('\n'):
                    self.logger.info(f"  {line}")
            
            if result.stderr:
                self.logger.warning("Script STDERR:")
                for line in result.stderr.strip().split('\n'):
                    self.logger.warning(f"  {line}")
            
            # Check success
            if result.returncode == 0:
                self.logger.info(f"{description} completed successfully in {duration:.1f}s")
                return True
            else:
                self.logger.error(f"{description} failed with return code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"{description} timed out after 4 hours")
            return False
        except Exception as e:
            self.logger.error(f"Error running {description}: {e}")
            return False
    
    def check_output_file(self, file_path: Path, description: str) -> bool:
        """Check if output file was created successfully"""
        if file_path.exists():
            file_size = file_path.stat().st_size
            self.logger.info(f"{description} created: {file_size / 1024 / 1024:.1f} MB")
            
            # Validate JSON integrity
            data = self.validate_json_file(file_path)
            if not data:
                self.logger.error(f"{description} is corrupted or invalid!")
                return False
            
            return True
        else:
            self.logger.error(f"{description} not found!")
            return False
    
    def run_full_pipeline(self) -> bool:
        """Run the complete scraping pipeline"""
        print("🚀 Aniworld Database Builder")
        print("🎯 Running all scripts in sequence with batch processing")
        if self.limit:
            print(f"📊 Limit: {self.limit} anime (testing mode)")
        else:
            print("📊 Limit: None (full database)")
        print(f"📦 Batch size: {self.batch_size} anime per batch")
        print("=" * 60)
        
        total_start_time = time.time()
        
        try:
            # Step 1: Catalog Scraper (no batching needed - fast anyway)
            if not self.run_script('catalog', self.scripts['catalog'], 'Catalog Scraper (Anime Names & URLs)'):
                return False
            
            if not self.check_output_file(self.output_files['catalog'], 'Catalog data'):
                return False
            
            # Step 2: Structure Analyzer (with batching)
            if not self.run_script('structure', self.scripts['structure'], 'Structure Analyzer (Seasons & Episodes)'):
                return False
            
            if not self.check_output_file(self.output_files['structure'], 'Structure data'):
                return False
            
            # Step 3: Streams Analyzer (with batching)
            if not self.run_script('streams', self.scripts['streams'], 'Streams Analyzer (Languages & URLs)'):
                return False
            
            if not self.check_output_file(self.output_files['streams'], 'Streams data'):
                return False
            
            # Step 4: JSON Structurer (no batching needed)
            if not self.run_script('structurer', self.scripts['structurer'], 'JSON Structurer (Final Database)'):
                return False
            
            if not self.check_output_file(self.output_files['final'], 'Final database'):
                return False
            
            # Success summary
            total_duration = time.time() - total_start_time
            print(f"\n{'='*60}")
            print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
            print(f"⏱️  Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
            print(f"📁 Final database: {self.output_files['final']}")
            
            # Show file sizes
            print(f"\n📊 Generated files:")
            for name, file_path in self.output_files.items():
                if file_path.exists():
                    size_mb = file_path.stat().st_size / 1024 / 1024
                    print(f"   {name}: {file_path.name} ({size_mb:.1f} MB)")
            
            # Show resource warnings if any
            if self.resource_warnings:
                print(f"\n⚠️  Resource warnings during processing:")
                for warning in self.resource_warnings[-5:]:  # Show last 5 warnings
                    print(f"   {warning}")
            
            print(f"\n✅ Database ready for use!")
            print(f"🔗 Access your data at: {self.output_files['final']}")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            return False
        finally:
            # Stop resource monitoring
            self.stop_monitoring()
    
    def run_update_mode(self) -> bool:
        """Run in update mode - same as full pipeline since all scripts auto-update"""
        print("🔄 SerienStream Database Updater")
        print("🎯 All scripts auto-update - running full pipeline")
        print("=" * 60)
        
        # Since all scripts are designed to update, just run the full pipeline
        return self.run_full_pipeline()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Aniworld Database Builder')
    parser.add_argument('--limit', type=int, help='Limit number of anime to process (for testing)')
    parser.add_argument('-b', '--batch', type=int, help='Override default batch size')

    args = parser.parse_args()

    orchestrator = AniworldOrchestrator(limit=args.limit, batch_size=args.batch)
    
    try:
        # Check prerequisites
        if not orchestrator.check_prerequisites():
            print("❌ Prerequisites check failed!")
            sys.exit(1)
        
        # Run pipeline with batch processing
        success = orchestrator.run_full_pipeline()
        
        if success:
            print("🎉 All done! Database is ready.")
            sys.exit(0)
        else:
            print("❌ Pipeline failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Pipeline interrupted by user")
        orchestrator.stop_monitoring()
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        orchestrator.stop_monitoring()
        sys.exit(1)

if __name__ == "__main__":
    main()