#!/usr/bin/env python3
"""
Batch RFQ Regeneration Script
Re-scrapes sam.gov pages and regenerates RFQ content for all solicitation stubs.
Runs on the GCP VM via: venv/bin/python3 batch_regenerate_rfqs.py [--dry-run] [--limit N]
"""

import os
import sys
import time
import json
import logging
import sqlite3
import argparse
import traceback
from datetime import datetime

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
from database_manager import DatabaseManager
from rfq_validator import validate_rfq, ValidationResult
import re

# Load .env file for API keys
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, 'logs', 'batch_regenerate.log'), mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs dir
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)


def fetch_sam_gov_page(url: str, timeout=30000) -> str:
    """Fetch a sam.gov page using Playwright and return the text content."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            page.wait_for_selector("main", timeout=10000)
            time.sleep(3)
            html = page.content()
            browser.close()
            return html
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            try:
                browser.close()
            except:
                pass
            return ""


def extract_description_from_html(html: str) -> str:
    """Extract solicitation description from sam.gov page HTML using BeautifulSoup."""
    from bs4 import BeautifulSoup
    import re

    if not html:
        return ""

    soup = BeautifulSoup(html, 'html.parser')
    description_parts = []

    # Strategy 1: Look for main description container
    desc_selectors = [
        {'class': re.compile(r'description', re.IGNORECASE)},
        {'id': re.compile(r'description', re.IGNORECASE)},
        {'class': re.compile(r'details', re.IGNORECASE)},
        {'class': re.compile(r'content', re.IGNORECASE)},
    ]

    for selector in desc_selectors:
        desc_elem = soup.find('div', selector)
        if desc_elem:
            text = desc_elem.get_text(separator='\n', strip=True)
            if len(text) > 100:
                description_parts.append(f"=== Main Description ===\n{text}\n")
                break

    # Strategy 2: Extract all section elements with substantial text
    sections = soup.find_all(['section', 'article', 'div'],
                              class_=re.compile(r'section|detail|info', re.IGNORECASE))

    for section in sections:
        section_text = section.get_text(separator='\n', strip=True)
        if len(section_text) > 200:
            if not any(section_text[:100] in part for part in description_parts):
                description_parts.append(f"\n=== Section ===\n{section_text}\n")

    # Strategy 3: Look for key information fields
    key_fields = [
        'Notice ID', 'Solicitation Number', 'Posted Date', 'Response Date',
        'Classification Code', 'NAICS', 'Set Aside', 'Place of Performance'
    ]

    field_data = []
    for field in key_fields:
        label = soup.find(string=re.compile(f'^{field}', re.IGNORECASE))
        if label:
            parent = label.find_parent()
            if parent:
                sibling = parent.find_next_sibling()
                if sibling:
                    value = sibling.get_text(strip=True)
                    field_data.append(f"{field}: {value}")
                else:
                    value = parent.get_text(strip=True)
                    value = value.replace(field, '').strip()
                    if value:
                        field_data.append(f"{field}: {value}")

    if field_data:
        description_parts.insert(0, "=== Solicitation Information ===\n" + "\n".join(field_data) + "\n")

    # Strategy 4: Extract table data
    tables = soup.find_all('table')
    for idx, table in enumerate(tables):
        try:
            rows = table.find_all('tr')
            if len(rows) > 1:
                table_text = f"\n=== Table {idx+1} ===\n"
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    row_text = " | ".join([cell.get_text(strip=True) for cell in cells])
                    if row_text:
                        table_text += row_text + "\n"
                if len(table_text) > 100:
                    description_parts.append(table_text)
        except:
            continue

    # Strategy 5: Fallback to paragraphs
    if not description_parts:
        all_paragraphs = soup.find_all('p')
        para_texts = [p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 50]
        if para_texts:
            description_parts.append("=== Content ===\n" + "\n\n".join(para_texts))

    full_description = "\n".join(description_parts)
    return full_description if full_description.strip() else ""


def extract_notice_id_from_html(html: str) -> str:
    """Extract real Notice ID from HTML."""
    import re
    if not html:
        return None

    patterns = [
        r'Notice\s+ID[:\s]+([A-Z0-9][\w-]+)',
        r'Solicitation\s+Number[:\s]+([A-Z0-9][\w-]+)',
        r'Contract\s+Number[:\s]+([A-Z0-9][\w-]+)',
    ]

    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def generate_rfq_from_description(description_text: str, contract_id: str) -> dict:
    """Generate RFQ content using Groq (free, Llama 3.1 open-source model)."""
    prompt = f"""You are a procurement specialist. Generate a professional RFQ (Request for Quotation) document based on the following government solicitation description.

IMPORTANT RULES:
- Output valid Markdown format
- Use the EXACT solicitation/notice ID in the RFQ header: {contract_id}
- Include all product requirements mentioned
- Set internal deadline 4 days before the response date
- Use organization: Camp Sable, LLC
- Email: bobbysmitty078@gmail.com
- Mark as PRODUCT type unless clearly a SERVICE solicitation

SOLICITATION DESCRIPTION:
{description_text[:8000]}

Generate a complete RFQ document now:"""

    # Detect type
    rfq_type = "SERVICE" if any(w in description_text.lower() for w in [
        "service", "maintenance", "repair", "cleaning", "consulting"
    ]) and "product" not in description_text.lower() else "PRODUCT"

    # Groq (free, open-source Llama 3.1)
    try:
        import os
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key and not groq_key.startswith("your_"):
            from groq import Groq
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3
            )
            return {"rfq_content": response.choices[0].message.content, "rfq_type": rfq_type}
        else:
            logger.warning("No GROQ_API_KEY found")
    except Exception as e:
        logger.error(f"Groq failed: {e}")

    # Fallback: OpenAI-compatible providers
    try:
        import os
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key and not openai_key.startswith("your_"):
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3
            )
            return {"rfq_content": response.choices[0].message.content, "rfq_type": rfq_type}
    except Exception as e:
        logger.error(f"OpenAI fallback failed: {e}")

    logger.error("All LLM providers failed")
    return None


def save_solicitation_data(contract_id: str, description: str, url: str):
    """Save scraped data to solicitation_data/ directory."""
    data_dir = os.path.join(config.SOLICITATION_DATA_DIR, contract_id)
    os.makedirs(data_dir, exist_ok=True)
    desc_path = os.path.join(data_dir, "description.txt")
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(description)


def parse_llm_rfq_output(raw_text: str) -> dict:
    """Extract structured fields from LLM's markdown RFQ output for validation."""
    result = {"body": raw_text or ""}
    if not raw_text:
        return result

    patterns = {
        "scope": r"(?:scope|description|summary|overview)[:\s]+(.+?)(?:\n\n|\n#|\Z)",
        "quantity": r"(?:quantity|qty|amount|units?)[:\s]+(.+?)(?:\n|\Z)",
        "deadline": r"(?:deadline|due\s*date|response\s*date|submission\s*date)[:\s]+(.+?)(?:\n|\Z)",
        "delivery_location": r"(?:delivery|ship\s*to|location|place\s*of\s*performance)[:\s]+(.+?)(?:\n\n|\n#|\Z)",
        "contact": r"(?:contact|email|phone|point\s*of\s*contact)[:\s]+(.+?)(?:\n|\Z)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if match:
            result[field] = match.group(1).strip()[:500]

    return result


def main():
    parser = argparse.ArgumentParser(description='Batch regenerate RFQs')
    parser.add_argument('--dry-run', action='store_true', help='Only fetch and save descriptions, skip RFQ generation')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of solicitations to process (0=all)')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N solicitations')
    parser.add_argument('--skip-fetch', action='store_true', help='Skip fetching, use existing solicitation_data/')
    args = parser.parse_args()

    db = DatabaseManager()
    conn = db._connect_db()
    cursor = conn.cursor()

    # Get all solicitations with URLs
    cursor.execute("SELECT contract_id, url, title FROM solicitations WHERE url IS NOT NULL AND url LIKE '%sam.gov%'")
    solicitations = cursor.fetchall()
    logger.info(f"Found {len(solicitations)} solicitations with sam.gov URLs")

    if args.offset > 0:
        solicitations = solicitations[args.offset:]
        logger.info(f"Skipping first {args.offset} solicitations (offset={args.offset})")

    if args.limit > 0:
        solicitations = solicitations[:args.limit]
        logger.info(f"Limiting to {args.limit} solicitations")

    processed = 0
    skipped = 0
    errors = 0
    rejected = 0
    warnings = 0

    for idx, (contract_id, url, title) in enumerate(solicitations, 1):
        logger.info(f"\n[{idx}/{len(solicitations)}] Processing: {contract_id[:30]}...")
        logger.info(f"  URL: {url}")

        try:
            # Step 1: Fetch page (or use existing data)
            desc_path = os.path.join(config.SOLICITATION_DATA_DIR, contract_id, "description.txt")

            if args.skip_fetch and os.path.exists(desc_path):
                logger.info(f"  Using existing description")
                with open(desc_path, 'r', encoding='utf-8') as f:
                    description = f.read()
                html = ""
            else:
                logger.info(f"  Fetching sam.gov page...")
                html = fetch_sam_gov_page(url)
                if not html:
                    logger.warning(f"  Failed to fetch page, skipping")
                    errors += 1
                    continue

                description = extract_description_from_html(html)
                if not description or len(description) < 50:
                    logger.warning(f"  Description too short ({len(description)} chars), skipping")
                    errors += 1
                    continue

                # Save description
                save_solicitation_data(contract_id, description, url)
                logger.info(f"  Saved description ({len(description)} chars)")

                # Update contract_id if real Notice ID found
                real_notice_id = extract_notice_id_from_html(html)
                if real_notice_id and real_notice_id != contract_id:
                    logger.info(f"  Found real Notice ID: {real_notice_id} (was: {contract_id[:20]}...)")
                    # Update solicitation and RFQ entries
                    try:
                        cursor.execute("UPDATE solicitations SET contract_id = ? WHERE contract_id = ?",
                                       (real_notice_id, contract_id))
                        cursor.execute("UPDATE rfq_outputs SET contract_id = ? WHERE contract_id = ?",
                                       (real_notice_id, contract_id))
                        conn.commit()

                        # Move solicitation_data to new ID
                        old_dir = os.path.join(config.SOLICITATION_DATA_DIR, contract_id)
                        new_dir = os.path.join(config.SOLICITATION_DATA_DIR, real_notice_id)
                        if os.path.exists(old_dir):
                            os.rename(old_dir, new_dir)

                        # Update contract_id for next steps
                        contract_id = real_notice_id
                    except Exception as e:
                        logger.error(f"  Failed to update contract_id: {e}")
                        conn.rollback()

                time.sleep(2)  # Be nice to sam.gov

            if args.dry_run:
                processed += 1
                continue

            # Step 2: Generate RFQ content using LLM
            logger.info(f"  Generating RFQ with LLM...")
            result = generate_rfq_from_description(description, contract_id)

            if not result or not result.get('rfq_content'):
                logger.error(f"  RFQ generation failed, skipping")
                errors += 1
                continue

            rfq_content = result['rfq_content']
            rfq_type = result['rfq_type']
            logger.info(f"  Generated {rfq_type} RFQ ({len(rfq_content)} chars)")

            # Step 2b: Validate RFQ quality
            rfq_dict = parse_llm_rfq_output(rfq_content)
            validation = validate_rfq(rfq_dict)
            review_status = "approved" if validation.severity == "ok" else \
                            "pending_review" if validation.severity == "warning" else \
                            "auto_rejected"
            issues_json = json.dumps(validation.issues) if validation.issues else None
            logger.info(f"  Validation: severity={validation.severity}, issues={len(validation.issues)}")
            if validation.severity == "reject":
                logger.warning(f"  REJECTED: {validation.issues}")
                rejected += 1
            elif validation.severity == "warning":
                logger.warning(f"  WARNING: {validation.issues}")
                warnings += 1

            # Step 3: Save .docx file
            try:
                from utils.doc_converter import convert_md_to_docx
                filename = f"{contract_id}_RFQ_{rfq_type}.docx"
                output_dir = os.path.join("rfq_downloads", datetime.now().strftime("%Y-%m-%d"))
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, filename)
                convert_md_to_docx(rfq_content, output_path)
                logger.info(f"  Saved DOCX: {output_path}")
            except Exception as e:
                logger.warning(f"  DOCX save failed: {e}")

            # Step 4: Update database with validation result
            cursor.execute("""
                UPDATE rfq_outputs
                SET rfq_content = ?, rfq_type = ?, format = 'markdown',
                    review_status = ?, validation_issues = ?
                WHERE contract_id = ?
            """, (rfq_content, rfq_type, review_status, issues_json, contract_id))

            # Also update title if still generic
            if title == 'Solicitation for Product' or title == 'Solicitation for Service':
                # Extract title from description
                title_match = re.search(r'(?:Title|Solicitation)[:\s]+(.+)', description[:500], re.IGNORECASE)
                new_title = title_match.group(1).strip()[:200] if title_match else title
                cursor.execute("UPDATE solicitations SET title = ?, description = ? WHERE contract_id = ?",
                               (new_title, description[:1000], contract_id))

            conn.commit()
            processed += 1
            logger.info(f"  ✓ Done ({processed} processed, {skipped} skipped, {errors} errors)")

        except Exception as e:
            logger.error(f"  Error: {e}")
            logger.error(traceback.format_exc())
            errors += 1
            conn.rollback()

        # Rate limit
        time.sleep(1)

    logger.info(f"\n{'='*80}")
    logger.info(f"BATCH COMPLETE")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Skipped:   {skipped}")
    logger.info(f"  Errors:    {errors}")
    logger.info(f"  Approved:  {processed - rejected - warnings}")
    logger.info(f"  Warnings:  {warnings} (pending review)")
    logger.info(f"  Rejected:  {rejected} (auto-rejected)")
    logger.info(f"{'='*80}")

    db._close_db()


if __name__ == '__main__':
    main()
