import os
import time
import json
import random
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ProxiflyManager:
    """
    Manages fetching, verifying, and formatting free proxies from Proxifly
    (https://github.com/proxifly/free-proxy-list).
    """

    PROXY_SOURCES = {
        'http': 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.json',
        'socks4': 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.json',
        'socks5': 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.json'
    }

    def __init__(self, test_url="https://www.google.com", timeout=5):
        """
        Args:
            test_url: The URL used to verify if a proxy actually works.
            timeout: Timeout in seconds for proxy testing.
        """
        self.test_url = test_url
        self.timeout = timeout
        self._cached_proxies = []
        self._last_fetch_time = 0
        self.cache_ttl = 300  # Proxifly updates every 5 mins

    def fetch_proxies(self, protocols=None):
        """
        Fetches proxies from the Proxifly Github repository.
        """
        if protocols is None:
            protocols = ['http', 'socks4', 'socks5']

        current_time = time.time()
        if self._cached_proxies and (current_time - self._last_fetch_time < self.cache_ttl):
            logger.info("Using cached Proxifly proxies.")
            return self._cached_proxies

        logger.info("Fetching fresh proxies from Proxifly...")
        all_proxies = []

        for protocol in protocols:
            if protocol not in self.PROXY_SOURCES:
                continue

            try:
                url = self.PROXY_SOURCES[protocol]
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Parse the JSON response
                proxy_data = response.json()
                
                # Format into a usable list of dictionaries
                for p in proxy_data:
                    # Each proxy entry in the JSON typically contains: ip, port, protocol, etc.
                    proxy_str = f"{p['protocol']}://{p['ip']}:{p['port']}"
                    all_proxies.append({
                        'protocol': p['protocol'],
                        'ip': p['ip'],
                        'port': p['port'],
                        'full_url': proxy_str,
                        'anonymity': p.get('anonymity', 'unknown'),
                        'country': p.get('geolocation', {}).get('country', 'unknown')
                    })
                    
                logger.info(f"Fetched {len(proxy_data)} {protocol.upper()} proxies.")
            except Exception as e:
                logger.error(f"Failed to fetch {protocol.upper()} proxies: {e}")

        self._cached_proxies = all_proxies
        self._last_fetch_time = current_time
        return all_proxies

    def test_proxy(self, proxy_dict):
        """
        Tests a given proxy to see if it allows access to the test_url.
        """
        proxy_url = proxy_dict['full_url']
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        try:
            # SOCKS proxies might need special requests configuration if pure HTTP requests module is used,
            # but usually requests supports SOCKS if requests[socks] is installed.
            # We'll do a simple GET request.
            response = requests.get(self.test_url, proxies=proxies, timeout=self.timeout)
            if response.status_code == 200:
                logger.debug(f"Proxy {proxy_url} works!")
                return True
        except Exception as e:
            logger.debug(f"Proxy test failed for {proxy_url}: {e}")
            
        return False

    def get_working_proxy(self, protocols=None, max_attempts=15, us_only=False):
        """
        Fetches proxies, shuffles them, and tests them until one works.
        Returns a dictionary suitable for Playwright's proxy configuration, or None.
        
        Args:
            protocols: List of protocols to include ('http', 'socks4', 'socks5').
            max_attempts: Maximum number of proxies to test before giving up.
            us_only: If True, only attempts to use US-based proxies.
        """
        proxies = self.fetch_proxies(protocols)
        
        if not proxies:
            logger.error("No proxies could be fetched from Proxifly.")
            return None

        # Filter if US only is requested
        if us_only:
            # Note: The Proxifly JSON format has a 'country' code field.
            proxies = [p for p in proxies if str(p.get('country', '')).upper() in ['US', 'USA']]
            if not proxies:
                logger.warning("No US proxies found in the fetched list.")
                return None

        # Shuffle to pick randomly
        random.shuffle(proxies)
        
        logger.info(f"Testing up to {max_attempts} proxies to find a working one...")
        attempts = 0
        
        for proxy_dict in proxies:
            if attempts >= max_attempts:
                break
                
            attempts += 1
            logger.info(f"Testing proxy {attempts}/{max_attempts}: {proxy_dict['full_url']} (Country: {proxy_dict.get('country')})")
            
            if self.test_proxy(proxy_dict):
                logger.info(f"Found working proxy: {proxy_dict['full_url']}")
                return {
                    "server": proxy_dict['full_url'],
                    # Optional: "username": "...", "password": "..." (Not needed for free public proxies)
                }

        logger.warning(f"Failed to find a working proxy after {max_attempts} attempts.")
        return None

if __name__ == "__main__":
    # Configure basic logging for the test run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    manager = ProxiflyManager(test_url="https://www.google.com", timeout=5)
    
    # Try to find a working proxy
    working_proxy = manager.get_working_proxy(protocols=['http', 'socks5'], max_attempts=10, us_only=True)
    
    if working_proxy:
        print(f"\nSUCCESS! Found a working US proxy for Playwright: {working_proxy}")
    else:
        print("\nFAILURE to find a working proxy in test.")
