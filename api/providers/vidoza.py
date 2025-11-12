#!/usr/bin/env python3
"""
providers/vidoza.py - Vidoza provider with network request extraction
"""
import re
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class VidozaProvider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://videzz.net/'
        })
        # Disable SSL verification
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def extract_stream(self, vidoza_url):
        """
        Extract MP4 stream URL from Vidoza page
        
        Args:
            vidoza_url: Vidoza URL (e.g., https://videzz.net/embed-4rb4ir9xqfpu.html)
        
        Returns:
            Direct MP4 URL or None if extraction failed
        """
        logger.info(f"Extracting stream from Vidoza: {vidoza_url}")
        
        try:
            # Get the Vidoza page
            response = self.session.get(vidoza_url, timeout=15)
            response.raise_for_status()
            
            # Method 1: Look for direct MP4 URLs in the HTML
            mp4_url = self._extract_from_html(response.text, vidoza_url)
            if mp4_url:
                return mp4_url
            
            # Method 2: Look for JavaScript that loads the video
            js_mp4_url = self._extract_from_javascript(response.text, vidoza_url)
            if js_mp4_url:
                return js_mp4_url
            
            # Method 3: Try to extract from potential API endpoints
            api_mp4_url = self._extract_from_api(response.text, vidoza_url)
            if api_mp4_url:
                return api_mp4_url
            
            logger.warning("Could not find MP4 URL in Vidoza page")
            return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for Vidoza URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting from Vidoza: {e}")
            return None
    
    def _extract_from_html(self, html_content, base_url):
        """Extract MP4 URL directly from HTML"""
        
        # Common patterns for Vidoza MP4 URLs
        mp4_patterns = [
            r'file:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'src:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'source\s+src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'["\']([^"\']*cache\d+\.vidoza\.net[^"\']*\.mp4[^"\']*)["\']',
            r'["\']([^"\']*vidoza[^"\']*\.mp4[^"\']*)["\']',
        ]
        
        for pattern in mp4_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if self._is_valid_mp4_url(match):
                    full_url = urljoin(base_url, match) if not match.startswith('http') else match
                    logger.info(f"Found MP4 URL in HTML: {full_url}")
                    return full_url
        
        return None
    
    def _extract_from_javascript(self, html_content, base_url):
        """Extract MP4 URL from JavaScript code"""
        
        # Look for JavaScript that might construct the video URL
        js_patterns = [
            r'var\s+\w+\s*=\s*["\']([^"\']*cache\d+\.vidoza\.net[^"\']*)["\']',
            r'videoUrl\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'video_url\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if self._is_valid_mp4_url(match):
                    full_url = urljoin(base_url, match) if not match.startswith('http') else match
                    logger.info(f"Found MP4 URL in JavaScript: {full_url}")
                    return full_url
        
        return None
    
    def _extract_from_api(self, html_content, base_url):
        """Extract MP4 URL by finding API endpoints or other sources"""
        
        # Look for potential API calls or AJAX requests
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
            
            # Look for URLs that might be API endpoints
            api_patterns = [
                r'["\']([^"\']*api[^"\']*)["\']',
                r'["\']([^"\']*ajax[^"\']*)["\']',
                r'["\']([^"\']*get[^"\']*video[^"\']*)["\']',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    if 'vidoza' in match or 'videzz' in match:
                        # Try to call this API endpoint
                        api_result = self._try_api_endpoint(match, base_url)
                        if api_result:
                            return api_result
        
        return None
    
    def _try_api_endpoint(self, endpoint, base_url):
        """Try calling a potential API endpoint"""
        try:
            full_url = urljoin(base_url, endpoint) if not endpoint.startswith('http') else endpoint
            
            # Try GET request to the API
            response = self.session.get(full_url, timeout=10)
            if response.status_code == 200:
                # Look for MP4 URLs in the response
                mp4_matches = re.findall(r'["\']([^"\']*\.mp4[^"\']*)["\']', response.text)
                for match in mp4_matches:
                    if self._is_valid_mp4_url(match):
                        logger.info(f"Found MP4 URL via API: {match}")
                        return match
            
        except Exception as e:
            logger.debug(f"API endpoint {endpoint} failed: {e}")
        
        return None
    
    def _is_valid_mp4_url(self, url):
        """Check if URL looks like a valid MP4 stream"""
        if not url or not isinstance(url, str):
            return False
        
        # Must contain .mp4
        if '.mp4' not in url.lower():
            return False
        
        # Should be HTTP(S) URL
        if not (url.startswith('http') or url.startswith('//')):
            return False
        
        # Skip obviously invalid URLs
        invalid_patterns = [
            'javascript:', 'data:', '.jpg', '.png', '.gif', '.css', '.js',
            'logo', 'thumb', 'preview', 'poster'
        ]
        
        url_lower = url.lower()
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        # Should contain vidoza or cache domains
        valid_domains = ['vidoza.net', 'videzz.net', 'cache']
        if not any(domain in url_lower for domain in valid_domains):
            return False
        
        return True
    
    def can_handle(self, url):
        """Check if this provider can handle the URL"""
        vidoza_domains = ['vidoza.net', 'videzz.net', 'vidoza.']
        return any(domain in url.lower() for domain in vidoza_domains)
    
    def validate_stream(self, stream_url):
        """Validate that the stream URL actually works"""
        try:
            # HEAD request to check if the stream is accessible
            response = self.session.head(stream_url, timeout=10)
            
            # Check if it's a valid video response
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                content_length = response.headers.get('content-length', '0')
                
                # Check if it's actually a video file
                is_video = any(video_type in content_type for video_type in ['video/', 'application/octet-stream'])
                has_content = int(content_length) > 1000  # At least 1KB
                
                if is_video and has_content:
                    logger.info(f"✅ Stream validation passed: {stream_url}")
                    return True
                else:
                    logger.warning(f"❌ Stream validation failed - not a video or too small: {stream_url}")
                    return False
            else:
                logger.warning(f"❌ Stream validation failed - HTTP {response.status_code}: {stream_url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Stream validation error: {e}")
            return False