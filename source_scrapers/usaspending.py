"""USAspending.gov award search agent.

Pulls contract award records via the public spending_by_award API and maps
them to the solicitations shape with category "contract_award".
"""
from .base import SourceAgent

ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
MAX_LIMIT = 100  # API caps results per request

# Keywords plus default contract award type codes (A, B, C, D).
FILTERS = {
    "keywords": ["office supplies", "janitorial", "equipment"],
    "award_type_codes": ["A", "B", "C", "D"],
    "time_period": [
        {"start_date": "2025-01-01", "end_date": "2026-08-07"}
    ],
}


class USAspendingAgent(SourceAgent):
    """Fetch and map contract awards from USAspending.gov."""
    name = "usaspending"

    def fetch(self):
        limit = min(self.limit, MAX_LIMIT)
        payload = {
            "filters": FILTERS,
            "limit": limit,
            "order": "desc",
            "sort": "Last Modified Date",
            "fields": ["Award ID", "Description", "Recipient Name",
                       "Awarding Agency", "Place of Performance City Code",
                       "Last Modified Date"],
        }
        data = self.fetch_json(ENDPOINT, method="POST", payload=payload,
                               headers={"Content-Type": "application/json"})
        return data.get("results", [])

    def to_solicitation(self, record):
        source_id = record.get("Award ID")
        if not source_id:
            return None
        description = record.get("Description") or ""
        title = description or record.get("Recipient Name") or ""
        if len(title) > 200:
            title = title[:200]
        return {
            "source_id": source_id,
            "title": title,
            "description": description,
            "location": record.get("Place of Performance City Code") or None,
            "category": "contract_award",
            "url": None,
            "data": record,
        }
