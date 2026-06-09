#!/usr/bin/env python3
"""
Advanced Proxy Manager for ThomasNet Automation
Handles multi-source proxy fetching, rotation, health monitoring, and failure tracking.
Prevents IP blocking through intelligent proxy rotation between vendor submissions.
"""

import os
import time
import json
import logging
import random
import requests
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class AdvancedProxyManager:
    """
    Manages proxy rotation with health monitoring, failure tracking, and multi-source support.
    Designed for high-volume vendor submission automation on ThomasNet.
    """

    # Proxy sources - all free/public
    PROXIFLY_SOURCES = [
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt",
    ]

    PROXYSCRAPE_URL = (
        "https://api.proxyscrape.com/v2/?request=getproxies"
        "&protocol=http&timeout=5000&country=US&ssl=all&anonymity=elite"
    )

    def __init__(
        self,
        min_pool_size: int = 10,
        failure_cooldown: int = 600,
        cache_ttl: int = 300,
        test_url: str = "https://www.thomasnet.com",
        timeout: int = 5,
    ):
        """
        Initialize advanced proxy manager.

        Args:
            min_pool_size: Minimum working proxies to maintain
            failure_cooldown: Cooldown period for failed proxies (seconds)
            cache_ttl: Time to live for cached proxies (seconds)
            test_url: URL to test proxy connectivity
            timeout: Timeout for proxy tests (seconds)
        """
        self.min_pool_size = min_pool_size
        self.failure_cooldown = failure_cooldown
        self.cache_ttl = cache_ttl
        self.test_url = test_url
        self.timeout = timeout

        self.proxy_pool: List[Dict] = []
        self.failed_proxies: Dict[str, float] = {}  # {proxy_url: timestamp}
        self.rotation_index = 0
        self.last_fetch_time = 0
        self.last_health_check = 0

        logger.info(
            f"Initialized AdvancedProxyManager (min_pool={min_pool_size}, "
            f"failure_cooldown={failure_cooldown}s, cache_ttl={cache_ttl}s)"
        )

    def fetch_proxies_from_proxifly(self) -> List[Dict]:
        """Fetch proxies from Proxifly sources."""
        proxies = []
        for source_url in self.PROXIFLY_SOURCES:
            try:
                logger.debug(f"Fetching proxies from Proxifly: {source_url}")
                response = requests.get(source_url, timeout=10)
                response.raise_for_status()

                # Parse proxy list (format: ip:port or protocol://ip:port)
                lines = response.text.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Normalize to http://ip:port format if needed
                    if "://" not in line:
                        line = f"http://{line}"

                    proxies.append(
                        {
                            "url": line,
                            "source": "proxifly",
                            "protocol": urlparse(line).scheme or "http",
                            "timestamp": time.time(),
                        }
                    )

                logger.info(f"✓ Fetched {len(lines)} proxies from Proxifly")
            except Exception as e:
                logger.warning(f"Failed to fetch from Proxifly ({source_url}): {e}")

        return proxies

    def fetch_proxies_from_proxyscrape(self) -> List[Dict]:
        """Fetch proxies from ProxyScrape API."""
        try:
            logger.debug(f"Fetching proxies from ProxyScrape API")
            response = requests.get(self.PROXYSCRAPE_URL, timeout=10)
            response.raise_for_status()

            proxies = []
            lines = response.text.strip().split("\r\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # ProxyScrape returns ip:port format
                proxy_url = f"http://{line}"
                proxies.append(
                    {
                        "url": proxy_url,
                        "source": "proxyscrape",
                        "protocol": "http",
                        "timestamp": time.time(),
                    }
                )

            logger.info(f"✓ Fetched {len(proxies)} proxies from ProxyScrape")
            return proxies

        except Exception as e:
            logger.warning(f"Failed to fetch from ProxyScrape: {e}")
            return []

    def test_proxy(self, proxy_dict: Dict) -> bool:
        """
        Test if a proxy works by making a simple HTTP request.

        Args:
            proxy_dict: Proxy dictionary with 'url' key

        Returns:
            True if proxy works, False otherwise
        """
        proxy_url = proxy_dict["url"]
        proxies = {"http": proxy_url, "https": proxy_url}

        try:
            response = requests.get(
                self.test_url, proxies=proxies, timeout=self.timeout
            )
            if response.status_code < 400:  # Accept 2xx and 3xx
                logger.debug(f"✓ Proxy {proxy_url} is working")
                return True
        except Exception as e:
            logger.debug(f"✗ Proxy {proxy_url} failed: {type(e).__name__}")

        return False

    def refill_proxy_pool(self) -> None:
        """Fetch fresh proxies from all sources and validate."""
        logger.info("Refilling proxy pool from sources...")
        current_time = time.time()

        # Check cache
        if (
            self.proxy_pool
            and current_time - self.last_fetch_time < self.cache_ttl
        ):
            logger.info(
                f"Using cached proxies ({len(self.proxy_pool)} in pool, "
                f"TTL: {self.cache_ttl}s)"
            )
            return

        # Fetch from all sources
        all_proxies = []
        all_proxies.extend(self.fetch_proxies_from_proxifly())
        all_proxies.extend(self.fetch_proxies_from_proxyscrape())

        if not all_proxies:
            logger.warning("⚠ No proxies fetched from any source!")
            return

        logger.info(f"Testing {len(all_proxies)} proxies for viability...")

        # Test and keep working proxies
        working = []
        for i, proxy in enumerate(all_proxies):
            if i % 10 == 0:
                logger.debug(f"Testing proxy {i}/{len(all_proxies)}...")

            if self.test_proxy(proxy):
                working.append(proxy)

            if len(working) >= self.min_pool_size * 2:
                break  # Got enough, stop testing

        if working:
            self.proxy_pool = working
            self.last_fetch_time = current_time
            logger.info(f"✓ Pool refilled: {len(self.proxy_pool)} working proxies")
        else:
            logger.warning("✗ No working proxies found after testing!")

    def health_check(self) -> Dict:
        """
        Check health of proxy pool. Returns status metrics.

        Returns:
            Dict with pool_size, working_count, failed_count, etc.
        """
        current_time = time.time()

        # Clean up expired failed proxies
        expired_failures = [
            proxy
            for proxy, fail_time in self.failed_proxies.items()
            if current_time - fail_time > self.failure_cooldown
        ]
        for proxy in expired_failures:
            del self.failed_proxies[proxy]

        # Get active proxies (not in cooldown)
        active = [
            p
            for p in self.proxy_pool
            if p["url"] not in self.failed_proxies
        ]

        health = {
            "total_in_pool": len(self.proxy_pool),
            "active_proxies": len(active),
            "failed_proxies": len(self.failed_proxies),
            "pool_health_percent": (
                100 * len(active) / len(self.proxy_pool)
                if self.proxy_pool
                else 0
            ),
            "timestamp": datetime.now().isoformat(),
        }

        # Warn if pool is low
        if len(active) < self.min_pool_size:
            logger.warning(
                f"⚠ Proxy pool low: {len(active)}/{self.min_pool_size} working. "
                f"Refilling..."
            )
            self.refill_proxy_pool()

        return health

    def get_next_proxy(self) -> Optional[Dict]:
        """
        Get next working proxy from pool, rotating through available proxies.

        Returns:
            Dict with 'url' and 'source' keys, or None if no proxies available
        """
        # Ensure pool is healthy
        if len(self.proxy_pool) < self.min_pool_size:
            self.refill_proxy_pool()

        # Filter out failed proxies
        active = [
            p
            for p in self.proxy_pool
            if p["url"] not in self.failed_proxies
        ]

        if not active:
            logger.warning("✗ No active proxies available, refilling...")
            self.refill_proxy_pool()
            active = [
                p
                for p in self.proxy_pool
                if p["url"] not in self.failed_proxies
            ]

        if not active:
            logger.error("✗ Exhausted proxy pool - no working proxies!")
            return None

        # Select next proxy in rotation
        proxy = active[self.rotation_index % len(active)]
        self.rotation_index += 1

        logger.debug(
            f"Selected proxy: {proxy['url']} "
            f"(active: {len(active)}/{len(self.proxy_pool)})"
        )

        return proxy

    def mark_proxy_failed(self, proxy_url: str) -> None:
        """
        Mark a proxy as failed, add to cooldown.

        Args:
            proxy_url: URL of the failed proxy
        """
        self.failed_proxies[proxy_url] = time.time()
        logger.warning(
            f"Marked proxy as failed: {proxy_url} "
            f"(cooldown: {self.failure_cooldown}s)"
        )

    def mark_proxy_success(self, proxy_url: str) -> None:
        """
        Mark a proxy as successful (remove from failed list).

        Args:
            proxy_url: URL of the successful proxy
        """
        if proxy_url in self.failed_proxies:
            del self.failed_proxies[proxy_url]
            logger.debug(f"Proxy recovered: {proxy_url}")

    def get_proxy_for_playwright(self) -> Optional[Dict]:
        """
        Get proxy formatted for Playwright browser configuration.

        Returns:
            Dict with 'server' key for Playwright, or None
        """
        proxy = self.get_next_proxy()
        if proxy:
            return {"server": proxy["url"]}
        return None

    def stats(self) -> Dict:
        """Get current pool statistics."""
        active = [
            p
            for p in self.proxy_pool
            if p["url"] not in self.failed_proxies
        ]

        return {
            "total_pool_size": len(self.proxy_pool),
            "active_proxies": len(active),
            "failed_proxies": len(self.failed_proxies),
            "health_percent": (
                100 * len(active) / len(self.proxy_pool)
                if self.proxy_pool
                else 0
            ),
            "sources_configured": ["proxifly", "proxyscrape"],
            "rotation_index": self.rotation_index,
            "failure_cooldown_seconds": self.failure_cooldown,
            "min_pool_size": self.min_pool_size,
        }


# Global instance
_proxy_manager = None


def get_proxy_manager() -> AdvancedProxyManager:
    """Get or create global proxy manager instance."""
    global _proxy_manager
    if _proxy_manager is None:
        # Load config from environment
        min_pool = int(os.getenv("MIN_PROXY_POOL_SIZE", "10"))
        cooldown = int(os.getenv("PROXY_FAILURE_COOLDOWN", "600"))
        cache_ttl = int(os.getenv("PROXY_CACHE_TTL", "300"))

        _proxy_manager = AdvancedProxyManager(
            min_pool_size=min_pool,
            failure_cooldown=cooldown,
            cache_ttl=cache_ttl,
        )

    return _proxy_manager


if __name__ == "__main__":
    # Test the proxy manager
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n🧪 Testing AdvancedProxyManager...\n")

    manager = AdvancedProxyManager(min_pool_size=5, failure_cooldown=60)

    # Refill and test
    print("Refilling proxy pool...")
    manager.refill_proxy_pool()

    print("\nPool stats:")
    print(json.dumps(manager.stats(), indent=2))

    print("\nHealth check:")
    print(json.dumps(manager.health_check(), indent=2))

    print("\nGetting 5 proxies in rotation:")
    for i in range(5):
        proxy = manager.get_next_proxy()
        if proxy:
            print(f"  {i+1}. {proxy['url']} (source: {proxy['source']})")
        else:
            print(f"  {i+1}. No proxy available")

    print("\n✓ Test complete\n")
