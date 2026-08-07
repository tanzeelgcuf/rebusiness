"""Federal Register procurement source agent.

Scrapes https://www.federalregister.gov/api/v1/documents.json for
documents matching "procurement". Maps each document to the solicitations
shape via `to_solicitation()`.
"""
from .base import SourceAgent

BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
MAX_PER_PAGE = 100  # under the API's 200 cap, keeps page 1 well-shaped


class FederalRegisterAgent(SourceAgent):
    name = "federal_register"

    def fetch(self):
        params = {
            "conditions[term]": "procurement",
            # RULE/PRORULE only — plain "procurement" term returns near-identical
            # AbilityOne "Procurement List" notices (noise, not leads).
            "conditions[type][]": ["RULE", "PRORULE"],
            "per_page": min(self.limit, MAX_PER_PAGE),
            "page": 1,
        }
        data = self.fetch_json(BASE_URL, params=params)
        return data.get("results", [])

    def to_solicitation(self, record):
        if not record.get("document_number"):
            return None
        title = record.get("title") or ""
        abstract = record.get("abstract")
        return {
            "source_id": record["document_number"],
            "title": title,
            "description": abstract if abstract else title,
            "location": None,
            "category": record.get("type"),
            "url": record.get("html_url"),
            "data": record,
        }
