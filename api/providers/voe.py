import re
import requests
import logging
import base64
import json
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class VOEProvider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        # Disable SSL verification for VOE domains
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
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
        """Replace specific patterns."""
        patterns = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']
        for pattern in patterns:
            text = text.replace(pattern, '')
        return text

    def decode_base64(self, text):
        """Decode base64 encoded string."""
        try:
            return base64.b64decode(text).decode('utf-8', errors='replace')
        except Exception:
            return None

    def shift_chars(self, text, shift):
        """Shift character codes by specified amount."""
        return ''.join([chr(ord(char) - shift) for char in text])

    def reverse_string(self, text):
        """Reverse the string."""
        return text[::-1]

    def deobfuscate(self, obfuscated_json):
        """Deobfuscate the JSON data using VOE's method."""
        try:
            data = json.loads(obfuscated_json)
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], str):
                obfuscated_string = data[0]
            else:
                return None
        except json.JSONDecodeError:
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
        except Exception:
            return None

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

    def extract_m3u8(self, voe_url):
        """
        Extract m3u8 URL from VOE page
        
        Args:
            voe_url: VOE URL (e.g., https://jilliandescribecompany.com/e/9mm6ogyerorg)
        
        Returns:
            m3u8 master playlist URL or None if extraction failed
        """
        logger.info(f"Extracting m3u8 from VOE: {voe_url}")
        
        try:
            # Get the VOE page
            response = self.session.get(voe_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for obfuscated data in script tags
            scripts = soup.find_all('script')
            
            for script in scripts:
                if not script.string:
                    continue
                    
                # Look for JSON arrays that might contain obfuscated data
                json_pattern = r'\[\"[^\"]+\"\]'
                matches = re.findall(json_pattern, script.string)
                
                for match in matches:
                    # Skip short arrays like ["an"], ["cn"]
                    if len(match) < 50:
                        continue
                    
                    result = self.deobfuscate(match)
                    
                    if result and isinstance(result, dict):
                        # Look for m3u8 URL in the result
                        m3u8_url = self.find_m3u8_url(result)
                        if m3u8_url and 'master.m3u8' in m3u8_url:
                            logger.info(f"Successfully extracted master m3u8: {m3u8_url}")
                            return m3u8_url
            
            # Fallback: look for any m3u8 URLs directly in the page
            m3u8_pattern = r'(https?://[^"\']+\.m3u8[^"\'\s]*)'
            m3u8_matches = re.findall(m3u8_pattern, response.text)
            for match in m3u8_matches:
                if 'master.m3u8' in match:
                    logger.info(f"Found direct master m3u8 URL: {match}")
                    return match
            
            logger.warning("Could not find master m3u8 URL in VOE page")
            return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for VOE URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting from VOE: {e}")
            return None
    
    def can_handle(self, url):
        """Check if this provider can handle the URL"""
        voe_domains = ['voe.sx', 'voe.to', 'voe.cx', 'jilliandescribecompany.com', 'mikaylaarealike.com']
        return any(domain in url.lower() for domain in voe_domains)