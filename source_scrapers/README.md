# Procurement Source Scrapers

Pull structured procurement opportunities from official free JSON APIs into a
separate `source_procurement.db`, ready to be merged into the sam.gov
`rebusiness_automation.db` pipeline.

## Sources

| Source | Endpoint | Key |
|--------|----------|-----|
| USAspending | `https://api.usaspending.gov/api/v2/search/spending_by_award/` (POST) | none |
| Federal Register | `https://www.federalregister.gov/api/v1/documents.json` | none |
| Regulations.gov | `https://api.regulations.gov/v4/documents` | `REGULATIONS_GOV_API_KEY` env |
| ~~FPDS~~ | — | **dropped** — redundant with USAspending (same backend), public ezsearch now returns a JS shell requiring sam.gov login |

## Usage

```bash
# all three sources, 20 records each
python -m source_scrapers.cli all --limit 20

# single source
python -m source_scrapers.cli usaspending --limit 50
python -m source_scrapers.cli federal_register --limit 30
REGULATIONS_GOV_API_KEY=your_key python -m source_scrapers.cli regulations --limit 20

# inspect
python -c "from source_scrapers.base import SourceDB; print(SourceDB().summary())"
```

Run from the repo root. Output goes to `source_procurement.db` (never touches
`rebusiness_automation.db`).

## Merge into the main pipeline

Each row maps to `solicitations`:
`source_id → contract_id` (prefix with source when collisions matter),
`title/description/location` direct, `data_json → data`.

```sql
INSERT OR IGNORE INTO solicitations (contract_id, url, title, description, location, data)
SELECT source || '-' || source_id, url, title, description, location, data_json
FROM source_rows;
```

Then the normal pipeline (`batch_regenerate_rfqs.py`, ThomasNet submission)
operates unchanged.

## Notes

- USAspending rows are **award** records (past obligations), not open
  solicitations — use as lead-gen for vendors/NAICS, not as RFQ sources.
- Federal Register / Regulations.gov are notice/docket records — lead-gen and
  early-warning, not RFQs.
- For true RFQ candidates, sam.gov remains the authoritative source.
