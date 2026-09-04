"""
SAM.gov API-based fetcher — drop-in replacement for Playwright-based SamGovAgent.

Uses SAM.gov's public Get Opportunities API (https://api.sam.gov/opportunities/v2/search)
instead of browser scraping. No Playwright, no captchas, no selector maintenance.

Get a free API key at https://sam.gov/data-services (Account Details -> API Keys).
Store as SAM_API_KEY environment variable.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sam_api_client import (
    SamApiClient,
    normalize_opportunity,
    fetch_full_description,
    SamApiError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sam_gov_fetcher")

try:
    from database_manager import DatabaseManager
except ImportError:
    DatabaseManager = None


class SamGovFetcher:
    """
    Drop-in replacement for SamGovAgent with the same interface:
    - fetch_opportunities(keywords, max_results) -> List[dict]
    - process_detail_page(url) -> dict (for AttachmentReaderAgent compatibility)
    """

    def __init__(self, api_key: Optional[str] = None, db_manager: Optional[Any] = None):
        self.api_client = SamApiClient(api_key=api_key)
        self.db_manager = db_manager
        self._cache: Dict[str, Dict] = {}  # URL -> solicitation data cache

    def fetch_opportunities(self, keywords: str = "", max_results: int = 100) -> List[Dict]:
        """
        Search SAM.gov for opportunities matching keywords.
        Returns list of dicts with keys: url, title, description, contract_id,
        posted_date, response_deadline, naics_code
        """
        logger.info(f"Fetching opportunities: keywords='{keywords}', max={max_results}")
        try:
            raw_results = self.api_client.fetch_all(
                keywords=keywords,
                max_records=max_results,
            )
            normalized = [normalize_opportunity(r) for r in raw_results]

            # Convert to the format expected by existing pipeline
            results = []
            for opp in normalized:
                contract_id = opp.get("solicitation_id") or opp.get("sam_url", "").split("/")[-1]
                description_url = opp.get("description_url")

                # Pre-fetch description if available
                description = ""
                if description_url:
                    try:
                        description = fetch_full_description(description_url, self.api_client.api_key)
                    except Exception as e:
                        logger.warning(f"Failed to fetch description for {contract_id}: {e}")

                results.append({
                    "url": opp.get("sam_url", ""),
                    "title": opp.get("title", ""),
                    "description": description,
                    "contract_id": contract_id,
                    "posted_date": opp.get("posted_date", ""),
                    "response_deadline": opp.get("response_deadline", ""),
                    "naics_code": opp.get("naics_code", ""),
                    "notice_type": opp.get("notice_type", ""),
                    "agency": opp.get("agency", ""),
                    "place_of_performance": opp.get("place_of_performance", {}),
                    "point_of_contact": opp.get("point_of_contact", []),
                    # Raw normalized data for AttachmentReaderAgent
                    "api_data": opp,
                })

                # Cache for process_detail_page
                self._cache[opp.get("sam_url", "")] = results[-1]

            logger.info(f"Fetched {len(results)} opportunities")
            return results

        except SamApiError as e:
            logger.error(f"SAM.gov API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching opportunities: {e}")
            return []

    def process_detail_page(self, url: str) -> Optional[Dict]:
        """
        Fetch full solicitation details from a SAM.gov opportunity URL.
        Returns dict compatible with AttachmentReaderAgent.create_summary_report()
        """
        logger.info(f"Processing detail page: {url}")

        # Check cache first
        if url in self._cache:
            cached = self._cache[url]
            logger.info(f"  Using cached data for {cached.get('contract_id')}")
            return cached

        # Try to extract notice ID from URL
        # URL format: https://sam.gov/opp/abc123/view
        import re
        notice_id = None
        if "/opp/" in url:
            parts = url.split("/")
            if len(parts) > 4:
                notice_id = parts[4]

        if not notice_id:
            logger.warning(f"Could not extract notice ID from URL: {url}")
            return None

        # Search for this specific opportunity by title/ID
        try:
            # Try searching by the notice ID as keyword
            results = self.api_client.search_opportunities(
                keywords=notice_id,
                limit=10,
            )
            opportunities = results.get("opportunitiesData", [])

            if not opportunities:
                logger.warning(f"No API results for notice ID: {notice_id}")
                return None

            # Find exact match
            matched = None
            for opp in opportunities:
                if opp.get("noticeId") == notice_id or notice_id in opp.get("uiLink", ""):
                    matched = opp
                    break

            if not matched:
                matched = opportunities[0]  # Fallback to first result

            normalized = normalize_opportunity(matched)
            contract_id = normalized.get("solicitation_id") or notice_id
            description_url = normalized.get("description_url")

            description = ""
            if description_url:
                try:
                    description = fetch_full_description(description_url, self.api_client.api_key)
                except Exception as e:
                    logger.warning(f"Failed to fetch description: {e}")

            result = {
                "url": url,
                "title": normalized.get("title", ""),
                "description": description,
                "contract_id": contract_id,
                "posted_date": normalized.get("posted_date", ""),
                "response_deadline": normalized.get("response_deadline", ""),
                "naics_code": normalized.get("naics_code", ""),
                "notice_type": normalized.get("notice_type", ""),
                "agency": normalized.get("agency", ""),
                "place_of_performance": normalized.get("place_of_performance", {}),
                "point_of_contact": normalized.get("point_of_contact", []),
                "api_data": normalized,
            }

            self._cache[url] = result
            logger.info(f"  Fetched detail for {contract_id}")
            return result

        except SamApiError as e:
            logger.error(f"API error fetching detail for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing {url}: {e}")
            return None

    def search_for_links(self, keyword: str, start_page: int = 1, num_pages: int = 10) -> List[str]:
        """
        Compatibility method matching SamGovAgent.search_for_links interface.
        Returns list of SAM.gov opportunity URLs.
        """
        logger.info(f"Searching for links: keyword='{keyword}', pages={num_pages}")
        max_results = num_pages * 10  # Approximate
        opportunities = self.fetch_opportunities(keywords=keyword, max_results=max_results)
        return [o["url"] for o in opportunities if o.get("url")]

    def start_browser(self):
        """No-op for compatibility — API client doesn't need a browser."""
        logger.info("SamGovFetcher.start_browser() called — no browser needed for API client")

    def close(self):
        """No-op for compatibility."""
        pass


def main():
    """CLI test: fetch opportunities and print summary."""
    import argparse

    parser = argparse.ArgumentParser(description="SAM.gov API Fetcher Test")
    parser.add_argument("--keyword", default="industrial equipment", help="Search keyword")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--url", help="Process specific opportunity URL")
    args = parser.parse_args()

    fetcher = SamGovFetcher()

    if args.url:
        result = fetcher.process_detail_page(args.url)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No result")
    else:
        results = fetcher.fetch_opportunities(keywords=args.keyword, max_results=args.limit)
        print(f"Found {len(results)} opportunities:")
        for r in results[:5]:
            print(f"  {r['contract_id']}: {r['title'][:60]}... (deadline: {r['response_deadline']})")


if __name__ == "__main__":
    main()