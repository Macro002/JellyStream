#!/usr/bin/env python3
import os
import re
import json
import base64
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class VOEDownloader:
    def __init__(self):
        self.downloads_dir = Path("downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def rot13(self, text):
        """Apply ROT13 cipher to the text (only affects letters)."""
        result = ""
        for char in text:
            code = ord(char)
            if 65 <= code <= 90:  # A-Z
                code = ((code - 65 + 13) % 26) + 65
            elif 97 <= code <= 122:  # a-z
                code = ((code - 97 + 13) % 26) + 97
            result += chr(code)
        return result

    def replace_patterns(self, text):
        """Replace specific patterns with underscores."""
        patterns = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']
        for pattern in patterns:
            text = text.replace(pattern, '')
        return text

    def decode_base64(self, text):
        """Decode base64 encoded string."""
        try:
            return base64.b64decode(text).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return None

    def shift_chars(self, text, shift):
        """Shift character codes by specified amount."""
        return ''.join([chr(ord(char) - shift) for char in text])

    def reverse_string(self, text):
        """Reverse the string."""
        return text[::-1]

    def deobfuscate(self, obfuscated_json):
        """Deobfuscate the JSON data using the new method."""
        try:
            data = json.loads(obfuscated_json)
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                obfuscated_string = data[0]
            else:
                print("Input doesn't match expected format.")
                return None
        except json.JSONDecodeError:
            print("Invalid JSON input.")
            return None
        
        try:
            step1 = self.rot13(obfuscated_string)
            step2 = self.replace_patterns(step1)
            step4 = self.decode_base64(step2)
            if not step4:
                return None
            step5 = self.shift_chars(step4, 3)
            step6 = self.reverse_string(step5)
            step7 = self.decode_base64(step6)
            if not step7:
                return None
            
            result = json.loads(step7)
            return result
        except Exception as e:
            print(f"Error during deobfuscation: {str(e)}")
            return None

    def extract_video_data(self, url):
        """Extract video data from VOE page."""
        print(f"Fetching page: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching page: {e}")
            return None, None

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = self.extract_title(soup, url)
        
        # Look for the new obfuscated data pattern
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
                
            # Look for JSON arrays that might contain obfuscated data
            json_pattern = r'\[\"[^\"]+\"\]'
            matches = re.findall(json_pattern, script.string)
            
            for match in matches:
                print(f"Trying to deobfuscate: {match[:100]}...")
                result = self.deobfuscate(match)
                
                if result and isinstance(result, dict):
                    # Look for m3u8 URL in the result
                    m3u8_url = self.find_m3u8_url(result)
                    if m3u8_url:
                        print(f"Found m3u8 URL: {m3u8_url}")
                        return title, m3u8_url
        
        # Fallback: look for any m3u8 URLs directly in the page
        m3u8_pattern = r'(https?://[^"\']+\.m3u8[^"\'\s]*)'
        m3u8_matches = re.findall(m3u8_pattern, response.text)
        if m3u8_matches:
            print(f"Found direct m3u8 URL: {m3u8_matches[0]}")
            return title, m3u8_matches[0]
        
        print("Could not find m3u8 URL")
        return title, None

    def find_m3u8_url(self, data):
        """Recursively search for m3u8 URL in the data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and '.m3u8' in value:
                    return value
                elif isinstance(value, (dict, list)):
                    result = self.find_m3u8_url(value)
                    if result:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = self.find_m3u8_url(item)
                if result:
                    return result
        elif isinstance(data, str) and '.m3u8' in data:
            return data
        
        return None

    def extract_title(self, soup, url):
        """Extract video title from the page."""
        # Try various methods to get the title
        for selector in ['meta[property="og:title"]', 'meta[name="title"]', 'title']:
            element = soup.select_one(selector)
            if element:
                title = element.get('content') or element.get_text()
                if title:
                    # Clean the title for filename use
                    title = re.sub(r'[<>:"/\\|?*]', '_', title.strip())
                    return title[:100]  # Limit length
        
        # Fallback to URL
        return urlparse(url).path.split('/')[-1] or 'video'

    def download_with_ffmpeg(self, m3u8_url, output_path):
        """Download m3u8 stream using ffmpeg."""
        print(f"Downloading to: {output_path}")
        
        cmd = [
            'ffmpeg',
            '-i', m3u8_url,
            '-c', 'copy',
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("Download completed successfully!")
                return True
            else:
                print(f"FFmpeg error: {result.stderr}")
                return False
        except FileNotFoundError:
            print("FFmpeg not found. Please install ffmpeg to download m3u8 streams.")
            print("On Ubuntu/Debian: sudo apt install ffmpeg")
            print("On Arch: sudo pacman -S ffmpeg")
            return False
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def download_with_yt_dlp(self, m3u8_url, output_path):
        """Alternative download method using yt-dlp."""
        try:
            from yt_dlp import YoutubeDL
            
            ydl_opts = {
                'outtmpl': str(output_path.with_suffix('.%(ext)s')),
                'format': 'best'
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([m3u8_url])
            
            print("Download completed successfully!")
            return True
            
        except ImportError:
            print("yt-dlp not found. Install it with: pip install yt-dlp")
            return False
        except Exception as e:
            print(f"yt-dlp error: {e}")
            return False

    def download(self, url):
        """Main download function."""
        print("=" * 50)
        print("VOE Video Downloader")
        print("=" * 50)
        
        # Extract video data
        title, m3u8_url = self.extract_video_data(url)
        
        if not m3u8_url:
            print("Could not extract m3u8 URL from the page.")
            return False
        
        # Prepare output file
        filename = f"{title}.mp4" if title else "video.mp4"
        output_path = self.downloads_dir / filename
        
        print(f"Title: {title}")
        print(f"M3U8 URL: {m3u8_url}")
        print(f"Output: {output_path}")
        
        # Try ffmpeg first, then yt-dlp as fallback
        success = self.download_with_ffmpeg(m3u8_url, output_path)
        
        if not success:
            print("Trying alternative download method...")
            success = self.download_with_yt_dlp(m3u8_url, output_path)
        
        return success


def main():
    downloader = VOEDownloader()
    
    print("VOE Video Downloader")
    print("=" * 30)
    
    while True:
        url = input("\nEnter VOE video URL (or 'quit' to exit): ").strip()
        
        if url.lower() in ['quit', 'exit', 'q']:
            break
        
        if not url:
            continue
            
        if 'voe.sx' not in url and 'voe.' not in url:
            print("This appears to be a non-VOE URL. Continue anyway? (y/n): ", end='')
            if input().lower() != 'y':
                continue
        
        try:
            success = downloader.download(url)
            if success:
                print("\n✅ Download completed!")
            else:
                print("\n❌ Download failed!")
        except KeyboardInterrupt:
            print("\n\nDownload cancelled by user.")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\nGoodbye!")


if __name__ == "__main__":
    main()