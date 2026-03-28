import os
import logging
import time
import requests
from twocaptcha import TwoCaptcha
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class DataDomeSolver:
    """
    Solves DataDome slider captchas using 2Captcha.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.solver = TwoCaptcha(api_key)
        
    def solve_datadome(self, page_url: str, user_agent: str, proxy: dict = None) -> str:
        """
        Send a DataDome challenge to 2Captcha and return the solved cookie token.
        
        Args:
            page_url: The URL of the page where the captcha appeared.
            user_agent: The User-Agent string used by the browser.
            proxy: Optional proxy dictionary with 'server', 'username', 'password'.
            
        Returns:
            The 'datadome' cookie value.
        """
        logger.info(f"Initiating DataDome solver for {page_url}...")
        
        # Prepare proxy string for 2Captcha format: login:password@ip:port
        proxy_str = None
        if proxy:
            server = proxy.get('server', '')
            parsed = urlparse(server)
            host = parsed.hostname
            port = parsed.port
            user = proxy.get('username')
            pw = proxy.get('password')
            
            if user and pw:
                proxy_str = f"{user}:{pw}@{host}:{port}"
            else:
                proxy_str = f"{host}:{port}"
                
        try:
            # We use the 'DataDomeTask' via the generic solve method 
            # as the python library might not have a direct wrapper for the latest DataDome params yet
            result = self.solver.datadome(
                sitekey="NoKeyNeededForDataDome", # DataDome doesn't use a traditional sitekey
                url=page_url,
                userAgent=user_agent,
                proxy={
                    'type': 'HTTP',
                    'uri': proxy_str
                } if proxy_str else None,
                # For DataDome, 2Captcha often needs the full URL of the captcha iframe
                # but the library's datadome() method handles the complexity internally
            )
            
            logger.info("Captcha solved successfully by 2Captcha!")
            return result['code'] # This is the datadome cookie value
            
        except Exception as e:
            logger.error(f"2Captcha solver failed: {e}")
            raise e

def detect_datadome(page) -> bool:
    """Check if the page current has a DataDome captcha."""
    try:
        # 1. Check for characteristic iframe
        if page.frame_locator('iframe[title*="DataDome"]').first.is_visible(timeout=1000):
            return True
        # 2. Check for captcha-delivery.com in page content
        content = page.content()
        if "captcha-delivery.com" in content or "DataDome" in content:
            return True
        # 3. Check for specific JS variables
        if "var dd={'rt':'c'" in content:
            return True
        return False
    except:
        return False
