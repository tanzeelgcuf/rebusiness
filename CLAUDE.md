# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RFQ automation system — scrapes government contract opportunities (SAM.gov), analyzes solicitation attachments, generates RFQ documents (.docx), and submits them to ThomasNet vendors. Also handles vendor outreach, email campaigns, and NAICS code mapping.

## Core Architecture

### Data Flow
1. **Scout** (`ContractScoutAgent`) — scrapes SAM.gov for contract opportunities
2. **Extract** (`AttachmentReaderAgent`) — downloads/reads solicitation attachments, generates structured RFQ .docx files matching Claude Vendor/Service List templates
3. **Analyze** (`SolicitationAnalysisAgent`) — analyzes solicitation details
4. **Write** (`ProposalWriterAgent`) — generates proposal documents
5. **Submit** (`ThomasNetAgent`) — logs into ThomasNet, searches vendors, selects them, fills RFQ form, submits via internal RFQ system
6. **Outreach** (`OutreachAgent`) — sends emails, fills web forms for vendor outreach

### Key Modules

| Module | Purpose |
|--------|---------|
| `database_manager.py` | SQLite DB (`rebusiness_automation.db`) — solicitations, vendors, RFQ outputs |
| `config.py` | API keys (Gemini, Google Maps, SMTP, Twilio) |
| `proxy_manager.py` | Free proxy pool from Proxifly/ProxyScrape for ThomasNet |
| `main_workflow.py` | Orchestrates full pipeline (scout → analyze → propose → submit) |

### AI Agents (`ai_agents/`)

- **ThomasNetAgent/** — Most complex agent. 12 `.py` files: `auth.py` (DataDome bypass via `ThomasNetAuth` class), `searcher.py`, `vendor_selector.py`, `form_filler.py`, `captcha_solver.py`, `proxy_manager.py`, `rfq_parser.py`, `cli.py`, `thomasnet_agent.py`, `setup_session.py`, `summarizer.py`, `config.yaml`
- **AttachmentReaderAgent/** — RFQ generation. Reads PDF/.docx attachments, extracts structured data, outputs .docx RFQs matching exact template format. Uses Gemini 2.5 Flash or OpenAI. Key files: `attachment_reader_agent.py`, `rfq_prompts.py`, `rfq_prompts_v2.py`, `government_solicitation_processor.py`
- **SamGovAgent/** / **SAMGovExtractor/** — SAM.gov login and extraction
- **OutreachAgent/** — Email sending (`email_service.py`), web form filling (`form_filler.py`)
- **ProjectManagerAgent/** — High-level `run_workflow()` orchestrator

### Dashboard (`dashboard/`)
Flask web app (port 5000):
- `app.py` — routes and API endpoints
- `templates/` — HTML pages (52 files)
- `utils/` — browser connector, proxy manager, RFQ regenerator, session saver
- `init_db.py` — DB setup

### Key Root Scripts
- `main_workflow.py` — full pipeline runner
- `run_complete_test.sh` — starts dashboard + Chrome + runs automation test
- `prepare_package.sh` — builds deployment zip
- `run_thomasnet_automation.py` — standalone ThomasNet RFQ submission
- `smart_extract.py` — batch extraction of solicitations
- `batch_sourcing.py` / `batch_extraction.py` — batch processing scripts
- `run_email_campaign.py` / `run_continuous_campaign.py` — email campaign management
- `save_thomasnet_session.py` — manual login session saver for DataDome bypass

## Common Commands

### Run
```bash
# Full pipeline
python3 main_workflow.py

# Dashboard
cd dashboard && python3 app.py

# Complete test (dashboard + Chrome + automation)
./run_complete_test.sh

# ThomasNet RFQ submission
python3 run_thomasnet_automation.py

# Batch extraction
python3 smart_extract.py
```

### Development
```bash
# Activate venv
source .venv/bin/activate

# Install deps
pip install -r requirements.txt

# Deploy to Cloud Run
./prepare_package.sh

# Save ThomasNet login session (for DataDome bypass)
python3 save_thomasnet_session.py
```

### Debug
```bash
# Check DB state
python3 check_db_solicitation.py
python3 check_automation_status.py

# Test individual components
python3 test_thomasnet_auth.py
python3 test_rfq_form_filler.py
python3 test_thomasnet_live_search.py
python3 test_thomasnet_e2e_dryrun.py
python3 test_thomasnet_internal_rfq.py

# Test connectivity
python3 test_tor_connection.py
python3 test_iproyal_connection.py
```

### Database
```bash
# DB lives at `rebusiness_automation.db` (SQLite)
python3 cleanup_db.py
python3 update_schema.py
```

## Key Patterns

- **DataDome bypass**: `ThomasNetAgent/auth.py` (`ThomasNetAuth` class) uses CapSolver, residential proxies, stealth playwright. Session saved via `save_thomasnet_session.py` → `auth_state.json`.
- **Proxy rotation**: `proxy_manager.py` fetches fresh free proxies from Proxifly CDN, validates against ThomasNet.
- **RFQ generation**: `AttachmentReaderAgent` reads solicitation descriptions, classifies as product/service, generates .docx matching exact template format from Claude Vendor/Service List.
- **Self-healing QA**: `SelfHealingAgent` validates RFQ output and retries on quality failures.
- **Campaigns**: Email outreach uses `run_email_campaign.py` with lead enrichment pipeline.
