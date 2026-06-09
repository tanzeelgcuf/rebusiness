#!/usr/bin/env python3
"""
ThomasNet Submission Diagnostic Agent
Connects to your logged-in Chrome, walks through the ENTIRE submission flow,
screenshots every step, and reports exactly where it fails.

Usage:
  python3 diagnose_thomasnet.py
  python3 diagnose_thomasnet.py --product "Fasteners"
  python3 diagnose_thomasnet.py --rfq-path /path/to/RFQ_PRODUCT.docx
"""

import os, sys, time, json, logging
from pathlib import Path
from datetime import datetime

# Ensure we can import project modules
sys.path.insert(0, str(Path(__file__).parent))

from dashboard.utils.browser_connector import connect_to_browser

# Setup logging
log_path = Path("logs/diagnose.log")
log_path.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_path)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DiagnoseAgent")

class DiagnoseAgent:
    """Walks through ThomasNet RFQ submission and reports exactly where it fails."""

    def __init__(self, cdp_url="http://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.browser = None
        self.page = None
        self.connector = None
        self.screenshot_dir = Path("logs/diagnose_screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.step = 0
        self.report = {"passed": [], "failed": [], "warnings": []}

    def _screenshot(self, label):
        self.step += 1
        path = self.screenshot_dir / f"{self.step:02d}_{label}.png"
        try:
            self.page.screenshot(path=str(path), full_page=True)
            logger.info(f"  Screenshot: {path.name}")
        except Exception as e:
            logger.warning(f"  Screenshot failed: {e}")
        return path

    def _dump_html(self, label):
        path = self.screenshot_dir / f"{self.step:02d}_{label}.html"
        try:
            with open(path, "w") as f:
                f.write(self.page.content())
            logger.info(f"  HTML saved: {path.name}")
        except Exception as e:
            logger.warning(f"  HTML dump failed: {e}")

    def _check_datadome(self):
        try:
            has_dd = self.page.frame_locator('iframe[title*="DataDome"]').first.is_visible(timeout=2000)
            if has_dd:
                logger.warning("  DATADOME DETECTED!")
                return True
            has_slider = self.page.frame_locator('iframe[src*="datadome"]').first.is_visible(timeout=1000)
            if has_slider:
                logger.warning("  DATADOME SLIDER DETECTED!")
                return True
            content = self.page.content().lower()
            if "access denied" in content or "captcha" in content or "blocked" in content:
                if "datadome" in content or "cdn" in content:
                    logger.warning("  DATADOME IN PAGE CONTENT!")
                    return True
        except:
            pass
        return False

    def connect(self):
        logger.info("=" * 70)
        logger.info("STEP 0: Connecting to Chrome browser...")
        logger.info("=" * 70)
        try:
            self.browser, self.page, self.connector = connect_to_browser(
                self.cdp_url, validate_login=False
            )
            logger.info("  Connected to browser!")
            current_url = self.page.url
            logger.info(f"  Current URL: {current_url}")
            if "thomasnet" in current_url.lower():
                logger.info("  Already on ThomasNet!")
            self._screenshot("00_connected")
            self.report["passed"].append("Browser connection")
            return True
        except Exception as e:
            logger.error(f"  Failed to connect: {e}")
            self.report["failed"].append(f"Browser connection: {e}")
            return False

    def check_login(self):
        logger.info("\n" + "=" * 70)
        logger.info("STEP 1: Checking ThomasNet login status...")
        logger.info("=" * 70)
        try:
            self.page.goto("https://www.thomasnet.com", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"  Navigation issue: {e}")
        if self._check_datadome():
            self._screenshot("01_datadome_blocked")
            self._dump_html("01_datadome_blocked")
            self.report["failed"].append("DataDome blocking homepage - solve captcha first")
            return False
        self._screenshot("01_homepage")
        page_text = self.page.content().lower()
        logging.info(f"  Page seen: {page_text[:500]}")
        # Check for DataDome in raw HTML (iframe approach)
        if 'datadome' in page_text or 'captcha-delivery.com' in page_text or 'geo.captcha-delivery.com' in page_text:
            logger.warning("  DataDome detected in page HTML!")
            self._dump_html("01_datadome_html")
            self._screenshot("01_datadome_screenshot")
            self.report["failed"].append("DataDome CAPTCHA blocking page access")
            return False
        logged_in = False
        for indicator in ["sign out", "logout", "my account", "account", "hi,", "welcome"]:
            if indicator in page_text:
                logger.info(f"  Login indicator found: '{indicator}'")
                logged_in = True
        for indicator in ["sign in", "log in", "register"]:
            if indicator in page_text:
                try:
                    if self.page.locator(f'a:has-text("{indicator.title()}"), button:has-text("{indicator.title()}")').first.is_visible(timeout=1000):
                        logger.warning(f"  Login button visible: '{indicator}' - NOT LOGGED IN!")
                        self._screenshot("01_not_logged_in")
                        self.report["failed"].append("Not logged in to ThomasNet")
                        return False
                except:
                    pass
        if logged_in:
            logger.info("  ThomasNet login confirmed!")
            self._screenshot("01_logged_in")
            self.report["passed"].append("ThomasNet login")
            return True
        else:
            logger.warning("  Cannot determine login status - proceeding anyway")
            self._screenshot("01_login_unknown")
            self.report["warnings"].append("Login status unclear - proceeding anyway")
            return True

    def test_search(self, query="Fasteners"):
        logger.info("\n" + "=" * 70)
        logger.info(f"STEP 2: Testing search for '{query}'...")
        logger.info("=" * 70)
        try:
            self.page.goto("https://www.thomasnet.com", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except:
            pass
        search_selectors = [
            'input[data-ref="srp.DiscoverBox.input"]',
            'input[placeholder*="Discover suppliers"]',
            'input[placeholder*="Search"]',
            '#search-input',
            'input[name="term"]',
            'input[type="text"]',
        ]
        found = False
        for sel in search_selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=2000):
                    logger.info(f"  Search box found: {sel}")
                    el.click()
                    time.sleep(0.5)
                    el.fill(query)
                    time.sleep(0.5)
                    self.page.keyboard.press("Enter")
                    found = True
                    break
            except:
                continue
        if not found:
            logger.warning("  Search box not found with any selector!")
            self._dump_html("02_search_box_missing")
            self._screenshot("02_search_box_missing")
            self.report["failed"].append("Search box not found")
            return False
        time.sleep(5)
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        time.sleep(2)
        if self._check_datadome():
            self._screenshot("02_datadome_after_search")
            self._dump_html("02_datadome_after_search")
            logger.warning("  DataDome triggered by search!")
            self.report["failed"].append("DataDome triggered during search")
            return False
        self._screenshot("02_search_results")
        self._dump_html("02_search_results")
        page_text = self.page.content().lower()
        if "no results" in page_text or "no suppliers" in page_text:
            logger.warning("  No search results found")
            self.report["failed"].append(f"No results for '{query}'")
            return False
        card_count = 0
        for card_sel in [
            'li[data-sentry-component="SearchResultSupplier"]',
            'li[data-sentry-component*="SearchResult"]',
            'li:has(h2 button)',
            'li[class*="supplier"]',
        ]:
            try:
                card_count = self.page.locator(card_sel).count()
                if card_count > 0:
                    logger.info(f"  Found {card_count} vendor cards (selector: {card_sel})")
                    break
            except:
                continue
        if card_count == 0:
            logger.warning(f"  No vendor cards detected (text length: {len(page_text)})")
            self.report["warnings"].append("No vendor cards detected in search results")
        else:
            self.report["passed"].append(f"Search returned {card_count} vendors")
        vendor_names = []
        try:
            h2_buttons = self.page.locator('li[data-sentry-component="SearchResultSupplier"] h2 button, li:has(h2) h2 button').all()
            for btn in h2_buttons[:10]:
                try:
                    name = btn.inner_text().strip()
                    if name:
                        vendor_names.append(name)
                except:
                    pass
        except:
            pass
        if vendor_names:
            logger.info(f"  Vendor names ({len(vendor_names)}):")
            for i, n in enumerate(vendor_names[:5], 1):
                logger.info(f"    {i}. {n}")
            self.report["passed"].append(f"Vendor names extracted: {len(vendor_names)}")
        else:
            logger.warning("  Could not extract vendor names")
            self.report["warnings"].append("Could not extract vendor names from cards")
        return True

    def test_clear_cart(self):
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Testing Clear Supplier Cart...")
        logger.info("=" * 70)
        remove_selectors = [
            'button[slot="close"][aria-label="Remove supplier"]',
            'button[aria-label="Remove supplier"]',
            'l-chip button[slot="close"]',
        ]
        found_any = False
        for sel in remove_selectors:
            try:
                count = self.page.locator(sel).count()
                if count > 0:
                    logger.info(f"  Found {count} remove buttons (selector: {sel})")
                    found_any = True
                    for i in range(count - 1, -1, -1):
                        try:
                            btn = self.page.locator(sel).nth(i)
                            if btn.is_visible():
                                btn.click()
                                time.sleep(0.5)
                                logger.info(f"  Cleared vendor {i+1}")
                        except:
                            pass
            except:
                continue
        if not found_any:
            logger.info("  No vendors in cart - already clean")
        self._screenshot("03_after_clear_cart")
        self.report["passed"].append("Cart cleared or already empty")
        return True

    def test_select_vendors(self, count=3):
        logger.info("\n" + "=" * 70)
        logger.info(f"STEP 4: Selecting {count} vendors...")
        logger.info("=" * 70)
        select_btn_selectors = [
            'button:has-text("Select")',
            'button[aria-label*="Select"]',
            'button[data-ref*="select"]',
        ]
        select_btns = None
        used_sel = ""
        for sel in select_btn_selectors:
            try:
                btns = self.page.locator(sel)
                if btns.count() > 0:
                    select_btns = btns
                    used_sel = sel
                    logger.info(f"  Found {btns.count()} Select buttons (selector: {sel})")
                    break
            except:
                continue
        if not select_btns or select_btns.count() == 0:
            logger.warning("  No Select buttons found!")
            self._dump_html("04_no_select_buttons")
            self._screenshot("04_no_select_buttons")
            # Try alternate approach: look for buttons in vendor cards
            try:
                # Maybe it's an "Add to list" or similar button
                all_btns = self.page.locator('li[data-sentry-component="SearchResultSupplier"] button, li:has(h2) button').all()
                btn_texts = []
                for btn in all_btns[:10]:
                    try:
                        t = btn.inner_text().strip()
                        if t: btn_texts.append(t)
                    except: pass
                if btn_texts:
                    logger.warning(f"  Buttons in vendor cards: {btn_texts}")
            except:
                pass
            self.report["failed"].append("No Select buttons on vendor cards")
            return False
        selected = 0
        for i in range(min(count, select_btns.count())):
            try:
                btn = select_btns.nth(i)
                if btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    btn.click()
                    selected += 1
                    logger.info(f"  Selected vendor {i+1}")
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"  Failed vendor {i+1}: {e}")
        logger.info(f"  Selected {selected}/{count} vendors")
        time.sleep(3)
        self._screenshot("04_after_selection")
        if selected == 0:
            self.report["failed"].append("Could not click any Select buttons")
            return False
        self.report["passed"].append(f"Selected {selected} vendors")
        return selected

    def test_request_quote_button(self):
        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: Finding Request Quote / Send Request button...")
        logger.info("=" * 70)
        self._screenshot("05_before_request_quote")
        self._dump_html("05_before_request_quote")
        try:
            all_buttons = self.page.locator('button').all()
            button_texts = []
            for btn in all_buttons:
                try:
                    if btn.is_visible():
                        txt = btn.inner_text().strip()
                        if txt:
                            button_texts.append(txt)
                except:
                    pass
            if button_texts:
                logger.info(f"  Visible buttons: {button_texts}")
        except:
            pass
        quote_selectors = [
            ('button:has-text("Request Quote")', "Request Quote button"),
            ('button:has-text("Send Request")', "Send Request button"),
            ('a:has-text("Request Quote")', "Request Quote link"),
            ('a:has-text("Request a Quote")', "Request a Quote link"),
            ('button:has-text("Request a Quote")', "Request a Quote button"),
            ('[data-testid="request-quote-button"]', "data-testid button"),
            ('button.batch-rfq-trigger', "batch-rfq-trigger"),
            ('button:has-text("Get Quotes")', "Get Quotes button"),
        ]
        for sel, desc in quote_selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=2000):
                    logger.info(f"  Found: {desc}")
                    logger.info(f"    Selector: {sel}")
                    el.scroll_into_view_if_needed()
                    time.sleep(1)
                    self._screenshot("05_found_request_quote")
                    el.click()
                    time.sleep(3)
                    self._screenshot("05_after_click_quote")
                    logger.info(f"  Clicked '{desc}'")
                    self.report["passed"].append(f"Clicked {desc}")
                    return True
            except:
                continue
        logger.warning("  No Request Quote / Send Request button found!")
        self._screenshot("05_missing_quote_button")
        self.report["failed"].append("Request Quote / Send Request button not found after vendor selection")
        return False

    def test_fill_and_send_form(self):
        logger.info("\n" + "=" * 70)
        logger.info("STEP 6: Testing form fill + submit...")
        logger.info("=" * 70)
        time.sleep(3)
        self._screenshot("06_form_state")
        self._dump_html("06_form_state")
        form_count = self.page.locator('form').count()
        input_count = self.page.locator('input, textarea').count()
        logger.info(f"  Forms: {form_count}, Inputs: {input_count}")
        if form_count == 0 and input_count == 0:
            logger.warning("  No form found on page!")
            self.report["failed"].append("No form appeared after clicking Request Quote")
            logger.info(f"  Current URL: {self.page.url}")
            try:
                modal = self.page.locator('[class*="modal"], [class*="dialog"], [class*="overlay"]').first
                if modal.is_visible(timeout=2000):
                    logger.info(f"  Modal detected: {modal.inner_text()[:100]}")
                    self._screenshot("06_modal_detected")
            except:
                pass
            return False
        fields_filled = 0
        try:
            subject = self.page.locator('input[name*="subject"], input[id*="subject"], input[placeholder*="Subject"]').first
            if subject.is_visible(timeout=2000):
                subject.fill("Request for Quote")
                fields_filled += 1
                logger.info("  Filled subject")
        except:
            logger.warning("  Subject field not found")
        try:
            details = self.page.locator('textarea').first
            if details.is_visible(timeout=2000):
                details.fill("Please provide pricing and lead time for the product listed in the attached RFQ document.")
                fields_filled += 1
                logger.info("  Filled details/message")
        except:
            logger.warning("  Textarea not found")
        try:
            checkbox = self.page.locator('input[type="checkbox"]').first
            if checkbox.is_visible(timeout=2000):
                checkbox.check()
                logger.info("  Checked verification checkbox")
        except:
            logger.warning("  Checkbox not found")
        self._screenshot("06_form_filled")
        send_selectors = [
            'button:has-text("Send Request")',
            'button:has-text("Submit")',
            'button:has-text("Send")',
            'button[type="submit"]',
            'input[type="submit"]',
        ]
        for sel in send_selectors:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn_text = btn.inner_text().strip()
                    logger.info(f"  Send button found: '{btn_text}'")
                    logger.info(f"  Selector: {sel}")
                    self._screenshot("06_before_send")
                    self.report["passed"].append(f"Form fillable, send button found: '{btn_text}'")
                    return True
            except:
                continue
        logger.warning("  No send/submit button found!")
        self._screenshot("06_missing_send_button")
        self.report["failed"].append("Send Request button not found in form")
        return False

    def close(self):
        if self.connector:
            try:
                self.connector.close()
                logger.info("  Disconnected from browser")
            except:
                pass

    def print_report(self):
        logger.info("\n" + "=" * 70)
        logger.info("DIAGNOSTIC REPORT")
        logger.info("=" * 70)
        logger.info(f"\nPassed ({len(self.report['passed'])}):")
        for item in self.report["passed"]:
            logger.info(f"  {item}")
        logger.info(f"\nFailed ({len(self.report['failed'])}):")
        for item in self.report["failed"]:
            logger.info(f"  FAIL: {item}")
        logger.info(f"\nWarnings ({len(self.report['warnings'])}):")
        for item in self.report["warnings"]:
            logger.info(f"  WARN: {item}")
        logger.info(f"\nScreenshots: {self.screenshot_dir}")
        logger.info("=" * 70)
        if not self.report["failed"]:
            logger.info("\nALL CHECKS PASSED - submission should work!")
        else:
            logger.info(f"\n{len(self.report['failed'])} blocking issue(s)")
            for i, fail in enumerate(self.report["failed"], 1):
                if "DataDome" in fail:
                    logger.info(f"  {i}. Solve DataDome captcha/slider in Chrome, then re-run")
                elif "Search box" in fail:
                    logger.info(f"  {i}. Search box selector outdated - check HTML dump")
                elif "Select buttons" in fail:
                    logger.info(f"  {i}. Select button selector needs updating")
                elif "Request Quote" in fail:
                    logger.info(f"  {i}. After selecting vendors, no Request Quote button - ThomasNet changed flow?")
                elif "Send Request" in fail:
                    logger.info(f"  {i}. Send Request button not found in form")
                elif "Not logged in" in fail:
                    logger.info(f"  {i}. Log into ThomasNet in Chrome first")
                elif "No results" in fail:
                    logger.info(f"  {i}. Search returned no vendors - try different product name")
                else:
                    logger.info(f"  {i}. {fail}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose ThomasNet submission issues")
    parser.add_argument("--product", default="Fasteners")
    parser.add_argument("--rfq-path", default=None)
    parser.add_argument("--cdp", default="http://127.0.0.1:9222")
    args = parser.parse_args()
    agent = DiagnoseAgent(cdp_url=args.cdp)
    if not agent.connect():
        agent.print_report()
        return 1
    if not agent.check_login():
        agent.print_report()
        return 1
    products_to_try = [args.product]
    if args.rfq_path:
        try:
            from dashboard.utils.dashboard_thomasnet import extract_product_name
            name = extract_product_name(args.rfq_path)
            if name and name not in products_to_try:
                products_to_try.insert(0, name)
        except Exception as e:
            logger.info(f"(could not extract product name: {e})")
    search_ok = False
    for prod in products_to_try:
        if agent.test_search(prod):
            search_ok = True
            break
        else:
            logger.info(f"Retrying with: '{prod}'...")
    if not search_ok:
        if agent.test_search("Industrial"):
            search_ok = True
    if not search_ok:
        agent.print_report()
        agent.close()
        return 1
    agent.test_clear_cart()
    selected = agent.test_select_vendors(count=3)
    if selected:
        agent.test_request_quote_button()
        agent.test_fill_and_send_form()
    agent.print_report()
    agent.close()
    logger.info(f"\nAll diagnostics saved to: {agent.screenshot_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
