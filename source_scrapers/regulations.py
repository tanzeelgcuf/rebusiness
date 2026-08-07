"""Regulations.gov document search agent.

Scrapes https://api.regulations.gov/v4/documents for DOD agency
documents. Requires a REGULATIONS_GOV_API_KEY env var; without it the
API returns API_KEY_MISSING, so fetch() degrades to an empty list
rather than raising.
"""
import os
from .base import SourceAgent, log

ENDPOINT = "https://api.regulations.gov/v4/documents"
MAX_PAGE_SIZE = 250  # API cap for page[size]


class RegulationsAgent(SourceAgent):
    name = "regulations"

    def fetch(self):
        api_key = os.environ.get("REGULATIONS_GOV_API_KEY")
        if not api_key:
            log.warning("regulations: REGULATIONS_GOV_API_KEY not set; "
                        "skipping")
            return []
        params = {
            "api_key": api_key,
            "page[size]": min(self.limit, MAX_PAGE_SIZE),
            "page[number]": 1,
            "filter[agencyId]": "DOD",
        }
        data = self.fetch_json(ENDPOINT, params=params)
        if "error" in data:
            log.warning("regulations: API error: %s", data["error"])
            return []
        return data.get("data", [])

    def to_solicitation(self, record):
        source_id = record.get("id")
        if not source_id:
            return None
        attrs = record.get("attributes") or {}
        links = record.get("links") or {}
        title = attrs.get("title") or ""
        return {
            "source_id": source_id,
            "title": title,
            "description": attrs.get("description") or title,
            "location": None,
            "category": attrs.get("documentType") or "document",
            "url": links.get("self"),
            "data": record,
        }
