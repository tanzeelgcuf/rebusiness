"""
SAM.gov Get Opportunities API client.

Replaces the Playwright-based scraper. Uses SAM.gov's public API:
https://open.gsa.gov/api/get-opportunities-public-api/

Get a free API key at https://sam.gov/data-services (Account Details -> API Keys).
Store it as an environment variable, never hardcode it.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sam_api_client")

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3


class SamApiError(Exception):
    pass


class SamApiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SAM_API_KEY")
        if not self.api_key:
            raise SamApiError(
                "SAM_API_KEY not set. Get a free key at https://sam.gov/data-services "
                "and export it as an environment variable."
            )

    def search_opportunities(
        self,
        keywords: str = "",
        naics_code: Optional[str] = None,
        posted_from: Optional[str] = None,  # MM/dd/yyyy
        posted_to: Optional[str] = None,    # MM/dd/yyyy
        notice_type: Optional[str] = None,  # e.g. "Solicitation", "Combined Synopsis/Solicitation"
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Query SAM.gov opportunities. Date range is required by the API and
        capped at 1 year per request, so default to the last 30 days if not given.
        """
        if not posted_from or not posted_to:
            today = datetime.utcnow()
            posted_to = today.strftime("%m/%d/%Y")
            posted_from = (today - timedelta(days=30)).strftime("%m/%d/%Y")

        params = {
            "api_key": self.api_key,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "limit": limit,
            "offset": offset,
        }
        if keywords:
            params["title"] = keywords
        if naics_code:
            params["ncode"] = naics_code
        if notice_type:
            params["ptype"] = notice_type

        return self._get_with_retry(SAM_API_BASE, params)

    def _get_with_retry(self, url: str, params: dict) -> dict:
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited by SAM.gov, backing off {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                last_exc = e
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                time.sleep(2 ** attempt)
        raise SamApiError(f"SAM.gov API request failed after {MAX_RETRIES} attempts: {last_exc}")

    def fetch_all(self, keywords: str = "", naics_code: Optional[str] = None,
                   max_records: int = 500) -> list[dict]:
        """Paginate through results up to max_records."""
        results = []
        offset = 0
        page_size = 100
        while len(results) < max_records:
            data = self.search_opportunities(
                keywords=keywords, naics_code=naics_code,
                limit=page_size, offset=offset,
            )
            batch = data.get("opportunitiesData", [])
            if not batch:
                break
            results.extend(batch)
            offset += page_size
            if len(batch) < page_size:
                break
            time.sleep(0.5)  # be polite even to an API with generous limits
        return results[:max_records]


def normalize_opportunity(raw: dict) -> dict:
    """Map SAM.gov API fields to the schema your existing pipeline expects."""
    return {
        "solicitation_id": raw.get("noticeId"),
        "title": raw.get("title"),
        "description_url": raw.get("description"),  # API returns a link to fetch full description text
        "naics_code": raw.get("naicsCode"),
        "notice_type": raw.get("type"),
        "posted_date": raw.get("postedDate"),
        "response_deadline": raw.get("responseDeadLine"),
        "agency": raw.get("fullParentPathName"),
        "place_of_performance": raw.get("placeOfPerformance", {}),
        "point_of_contact": raw.get("pointOfContact", []),
        "sam_url": raw.get("uiLink"),
    }


def fetch_full_description(description_url: str, api_key: str) -> str:
    """SAM.gov returns description as a fetchable link, not inline text — resolve it."""
    resp = requests.get(description_url, params={"api_key": api_key}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    # API returns JSON with a 'description' field containing HTML/text
    data = resp.json()
    return data.get("description", "")


if __name__ == "__main__":
    client = SamApiClient()
    raw_results = client.fetch_all(keywords="industrial equipment", max_records=50)
    normalized = [normalize_opportunity(r) for r in raw_results]
    logger.info(f"Fetched {len(normalized)} opportunities")
    for opp in normalized[:5]:
        print(opp["title"], "-", opp["response_deadline"])