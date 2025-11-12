import requests
import logging
import re
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

class RedirectResolver:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Disable SSL verification for problematic providers
        self.session.verify = False
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def resolve_redirect(self, serienstream_url):
        """
        Resolve serienstream.to redirect URL to final provider URL
        Handles both HTTP redirects and JavaScript redirects
        """
        logger.info(f"Resolving redirect: {serienstream_url}")
        
        try:
            current_url = serienstream_url
            max_redirects = 10
            
            for i in range(max_redirects):
                logger.info(f"Step {i+1}: Requesting {current_url}")
                
                response = self.session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=10
                )
                
                # Handle HTTP redirects
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location')
                    if location:
                        if location.startswith('/'):
                            location = urljoin(current_url, location)
                        current_url = location
                        logger.info(f"HTTP redirect to: {current_url}")
                        continue
                
                # Handle successful response
                elif response.status_code == 200:
                    # Check for JavaScript redirects in the content
                    js_redirect = self._extract_js_redirect(response.text)
                    if js_redirect:
                        logger.info(f"JavaScript redirect found: {js_redirect}")
                        current_url = js_redirect
                        continue
                    else:
                        # No more redirects, this is the final URL
                        logger.info(f"Final URL reached: {current_url}")
                        return current_url
                
                else:
                    logger.warning(f"Unexpected status code: {response.status_code}")
                    break
            
            logger.warning(f"Too many redirects (>{max_redirects})")
            return current_url
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Redirect resolution failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in redirect resolution: {e}")
            return None
    
    def _extract_js_redirect(self, html_content):
        """Extract JavaScript redirect URL from HTML content"""
        # Common JavaScript redirect patterns
        patterns = [
            r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
            r'document\.location\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                # Return the first match (most likely the redirect URL)
                redirect_url = matches[0]
                if redirect_url.startswith('http'):
                    return redirect_url
        
        return None
    
    def _is_valid_provider_url(self, url):
        """Check if URL is from a supported provider"""
        if not url:
            return False
        
        try:
            domain = urlparse(url).netloc.lower()
            
            # Known provider domains
            provider_domains = [
                'voe.sx', 'voe.to', 'voe.cx',
                'jilliandescribecompany.com',  # VOE redirect domain
                'doodstream.com', 'dood.to', 'dood.ws', 'dood.li', 'doply.net',  # Doodstream domains
                'vidoza.net', 'videzz.net',  # Vidoza domains
            ]
            
            return any(provider in domain for provider in provider_domains)
            
        except Exception:
            return False
    
    def get_provider_type(self, url):
        """Determine which provider this URL belongs to"""
        if not url:
            return None
        
        try:
            domain = urlparse(url).netloc.lower()
            
            if any(voe in domain for voe in ['voe.sx', 'voe.to', 'voe.cx', 'jilliandescribecompany.com', 'mikaylaarealike.com']):
                return 'voe'
            elif any(dood in domain for dood in ['doodstream.com', 'dood.to', 'dood.ws', 'dood.li', 'doply.net']):
                return 'doodstream'
            elif any(vidoza in domain for vidoza in ['vidoza.net', 'videzz.net']):
                return 'vidoza'
            else:
                return 'unknown'
                
        except Exception:
            return None

if __name__ == "__main__":
    # Test the redirector
    print("🔄 Testing Redirect Resolver...")
    print("=" * 50)
    
    resolver = RedirectResolver()
    
    # Test URL from your data
    test_url = "https://serienstream.to/redirect/8312502"
    print(f"🔍 Testing URL: {test_url}")
    
    try:
        direct_url = resolver.resolve_redirect(test_url)
        
        if direct_url:
            print(f"✅ Redirect resolved!")
            print(f"🎯 Direct URL: {direct_url}")
            provider_type = resolver.get_provider_type(direct_url)
            print(f"🏷️  Provider: {provider_type}")
        else:
            print("❌ Failed to resolve redirect")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()