import requests
import random
import logging
import time
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proxifly CDN URLs (jsdelivr is faster than raw.githubusercontent.com)
PROXIFLY_SOURCES = [
    # (url, protocol_prefix)
    ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt", "http"),
    ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt", "socks5"),
    ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt", "http"),
    ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt", "http"),
]

PROXYSCRAPE_URL = (
    "https://api.proxyscrape.com/v2/?request=getproxies"
    "&protocol=http&timeout=5000&country=US&ssl=all&anonymity=elite"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


class ProxyManager:
    """
    Manages a pool of free proxies from Proxifly (GitHub) and ProxyScrape.
    Validates them against ThomasNet and rotates working IPs.
    """

    def __init__(self):
        self.proxies: List[str] = []   # list of "protocol://ip:port"
        self.working_proxy: Optional[str] = None
        self.last_fetch_time: float = 0
        self.CACHE_DURATION: int = 600  # 10 minutes

    def fetch_proxies(self):
        """Fetch fresh proxy lists from all configured sources."""
        if self.proxies and (time.time() - self.last_fetch_time < self.CACHE_DURATION):
            return

        logger.info("🔄 Fetching fresh proxy list...")
        collected: List[str] = []

        # ── Source 1: ProxyScrape ────────────────────────────────────────────
        try:
            resp = requests.get(PROXYSCRAPE_URL, timeout=10)
            if resp.status_code == 200:
                for line in resp.text.strip().splitlines():
                    line = line.strip()
                    if line:
                        collected.append(f"http://{line}")
                logger.info(f"   + ProxyScrape: {len(collected)} proxies")
        except Exception as e:
            logger.error(f"❌ ProxyScrape error: {e}")

        # ── Source 2: Proxifly (via jsDelivr CDN) ───────────────────────────
        logger.info("🔄 Fetching from Proxifly (jsDelivr CDN)...")
        for url, proto in PROXIFLY_SOURCES:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    batch: List[str] = []
                    for line in resp.text.strip().splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        # Lines may already have a protocol prefix or just be IP:PORT
                        if "://" in line:
                            batch.append(line)
                        else:
                            batch.append(f"{proto}://{line}")
                    collected.extend(batch)
                    logger.info(f"   + Proxifly ({proto}): {len(batch)} proxies")
            except Exception as e:
                logger.error(f"❌ Proxifly fetch error ({url}): {e}")

        # Deduplicate and shuffle
        self.proxies = list(set(collected))
        random.shuffle(self.proxies)
        self.last_fetch_time = time.time()
        logger.info(f"✅ Total Candidates: {len(self.proxies)}")

    def validate_proxy(self, proxy_url: str) -> bool:
        """
        Checks if a proxy is alive and can reach ThomasNet without a DataDome block.
        """
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            resp = requests.get(
                "https://www.thomasnet.com",
                proxies=proxies,
                headers=HEADERS,
                timeout=8,
            )
            if resp.status_code == 200:
                if "DataDome" in resp.text or "captcha" in resp.text.lower():
                    return False
                logger.info(f"   [GOOD] {proxy_url} ({resp.elapsed.total_seconds():.2f}s)")
                return True
        except Exception:
            pass
        return False

    def get_working_proxy(self) -> Optional[str]:
        """
        Returns a validated proxy URL string, or None if none found.
        Tests up to 50 candidates per call, rotating through the list.
        """
        if self.working_proxy:
            return self.working_proxy

        self.fetch_proxies()

        if not self.proxies:
            logger.error("⚠️ No proxies available.")
            return None

        logger.info("🕵️ Validating proxies (batch of 50)...")
        # Take next 50 candidates and rotate list
        batch_size = 50
        candidates = self.proxies[:batch_size]
        self.proxies = self.proxies[batch_size:] + self.proxies[:batch_size]

        for proxy in candidates:
            if self.validate_proxy(proxy):
                self.working_proxy = proxy
                logger.info(f"🎯 Selected Proxy: {self.working_proxy}")
                return self.working_proxy

        logger.warning("⚠️ Could not find a working proxy in this batch.")
        return None

    def mark_proxy_bad(self):
        """Discard current proxy and force re-selection next time."""
        if self.working_proxy:
            logger.info(f"🗑️ Discarding bad proxy: {self.working_proxy}")
            self.working_proxy = None


# Global singleton
proxy_manager = ProxyManager()
