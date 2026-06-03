import os
import sys
import json
import time
import random
import anthropic
from playwright.sync_api import sync_playwright
from stealth_browser import ensure_xvfb, get_stealth_browser
from free_datadome_solver import solve_datadome_slider
from auto_login import auto_login_and_save_session, is_session_valid
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = "/Users/apple/Downloads/rebusinessautomationproject"
AUTH_STATE_PATH = f"{PROJECT_ROOT}/ai_monitor_agent/auth_state.json"
LOG_PATH = f"{PROJECT_ROOT}/dashboard/logs/submission.log"
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def log(msg):
    from datetime import datetime
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(entry)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")


def get_pending_rfqs():
    """Get all pending RFQs from the database/filesystem."""
    import glob
    import sqlite3

    rfqs = []

    # Try filesystem discovery
    patterns = [
        f"{PROJECT_ROOT}/rfq_downloads/2*/*_RFQ_PRODUCT.docx",
        f"{PROJECT_ROOT}/rfq_downloads/*.docx",
        f"{PROJECT_ROOT}/uploads/rfqs/**/*.docx"
    ]
    for pattern in patterns:
        rfqs.extend(glob.glob(pattern, recursive=True))

    # Try database
    db_paths = [
        f"{PROJECT_ROOT}/rfq.db",
        f"{PROJECT_ROOT}/dashboard/rfq.db",
        f"{PROJECT_ROOT}/database.db"
    ]
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, product_name, rfq_file_path FROM rfqs WHERE status='pending' OR status='queued'"
                )
                rows = cursor.fetchall()
                for row in rows:
                    rfqs.append({"id": row[0], "product": row[1], "path": row[2]})
                conn.close()
            except Exception as e:
                log(f"DB query error: {e}")

    log(f"Found {len(rfqs)} pending RFQs")
    return rfqs


def submit_rfq_to_thomasnet(rfq, context, page):
    """Submit a single RFQ to ThomasNet with full bot bypass."""
    product = rfq.get("product") or extract_product_from_filename(rfq)
    log(f"Submitting RFQ for product: {product}")

    try:
        # Navigate to ThomasNet supplier search
        search_url = f"https://www.thomasnet.com/search/?searchTerm={product.replace(' ', '+')}&cov=NA"
        page.goto(search_url, wait_until="networkidle", timeout=30000)
        time.sleep(random.uniform(2, 4))

        # Check for DataDome
        if is_datadome_blocking(page):
            log("DataDome detected during search — solving...")
            solved = solve_datadome_slider(page)
            if not solved:
                raise Exception("DataDome solve failed during search")
            page.wait_for_load_state("networkidle")
            time.sleep(2)

        # Find and click "Request Quote" buttons
        quote_buttons = page.locator(
            'button:has-text("Request Quote"), a:has-text("Request Quote"), '
            '[class*="rfq"], [data-action*="rfq"]'
        ).all()

        if not quote_buttons:
            log(f"No quote buttons found for '{product}'")
            return False

        contacted = 0
        for btn in quote_buttons[:5]:  # Contact up to 5 vendors
            try:
                btn.scroll_into_view_if_needed()
                time.sleep(random.uniform(0.5, 1.5))
                btn.click()
                page.wait_for_load_state("networkidle", timeout=10000)
                time.sleep(random.uniform(1, 2))

                # Fill RFQ form if it appears
                fill_rfq_form(page, product)
                contacted += 1
                log(f"✅ Vendor {contacted} contacted for '{product}'")
                page.go_back()
                time.sleep(random.uniform(1, 2))

            except Exception as e:
                log(f"Vendor contact error: {e}")
                continue

        return contacted > 0

    except Exception as e:
        log(f"❌ RFQ submission error for '{product}': {e}")
        page.screenshot(
            path=f"{PROJECT_ROOT}/dashboard/logs/rfq_error_{product[:20]}.png"
        )
        return False


def fill_rfq_form(page, product):
    """Fill out ThomasNet RFQ form fields."""
    email = os.getenv("THOMASNET_EMAIL", "bobbysmitty078@gmail.com")

    field_map = {
        'input[name*="email"], input[type="email"]': email,
        'input[name*="quantity"], input[placeholder*="quantity"]': "100",
        'textarea[name*="description"], textarea[placeholder*="describe"]': f"Request for quote on {product}. Please provide pricing and availability.",
        'input[name*="company"], input[placeholder*="company"]': "SAM Automation"
    }

    for selector, value in field_map.items():
        try:
            field = page.locator(selector).first
            if field.count() > 0 and field.is_visible():
                field.fill(value)
                time.sleep(random.uniform(0.2, 0.5))
        except:
            pass

    # Submit the form
    try:
        submit = page.locator('button[type="submit"]:has-text("Send"), button:has-text("Submit RFQ")').first
        if submit.is_visible():
            time.sleep(random.uniform(0.5, 1))
            submit.click()
            page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as e:
        log(f"Form submit error: {e}")


def is_datadome_blocking(page):
    try:
        content = page.content()
        return "datadome" in content.lower() or "captcha-delivery" in content.lower()
    except:
        return False


def extract_product_from_filename(rfq_path):
    import re
    name = os.path.basename(str(rfq_path))
    name = re.sub(r'[_-]', ' ', name)
    name = re.sub(r'\.(docx|pdf|txt)', '', name, flags=re.IGNORECASE)
    return name.strip()


def update_rfq_status(rfq, status):
    """Update RFQ status in database."""
    import sqlite3
    db_paths = [
        f"{PROJECT_ROOT}/rfq.db",
        f"{PROJECT_ROOT}/dashboard/rfq.db"
    ]
    for db_path in db_paths:
        if os.path.exists(db_path) and isinstance(rfq, dict) and "id" in rfq:
            try:
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "UPDATE rfqs SET status=? WHERE id=?",
                    (status, rfq["id"])
                )
                conn.commit()
                conn.close()
                return
            except Exception as e:
                log(f"DB update error: {e}")


def run_full_pipeline():
    log("=" * 60)
    log("STARTING FULLY AUTOMATED THOMASNET SUBMISSION")
    log("=" * 60)

    # Step 1: Ensure valid session (auto-login if needed)
    if not is_session_valid():
        log("No valid session — attempting auto-login...")
        success = auto_login_and_save_session()
        if not success:
            log("❌ Auto-login failed. Aborting.")
            return

    # Step 2: Get pending RFQs
    rfqs = get_pending_rfqs()
    if not rfqs:
        log("✅ No pending RFQs to process")
        return

    # Step 3: Launch stealth browser with saved session
    ensure_xvfb()

    with sync_playwright() as p:
        browser, context = get_stealth_browser(p)

        # Load saved auth state
        if os.path.exists(AUTH_STATE_PATH):
            with open(AUTH_STATE_PATH) as f:
                auth_data = json.load(f)
            context.add_cookies(auth_data.get("cookies", []))

        page = context.new_page()
        processed = 0
        failed = 0

        for rfq in rfqs:
            try:
                success = submit_rfq_to_thomasnet(rfq, context, page)
                if success:
                    update_rfq_status(rfq, "submitted")
                    processed += 1
                else:
                    update_rfq_status(rfq, "failed")
                    failed += 1
                # Random delay between RFQs to appear human
                time.sleep(random.uniform(5, 15))
            except Exception as e:
                log(f"Pipeline error for RFQ: {e}")
                failed += 1

        browser.close()

    log("=" * 60)
    log(f"SUBMISSION COMPLETE — Processed: {processed}, Failed: {failed}")
    log("=" * 60)


if __name__ == "__main__":
    run_full_pipeline()