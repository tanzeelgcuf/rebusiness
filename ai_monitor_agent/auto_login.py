import os
import json
import time
import random
from playwright.sync_api import sync_playwright
from stealth_browser import ensure_xvfb, get_stealth_browser
from free_datadome_solver import solve_datadome_slider

AUTH_STATE_PATH = "/Users/apple/Downloads/rebusinessautomationproject/ai_monitor_agent/auth_state.json"
THOMASNET_EMAIL = os.getenv("THOMASNET_EMAIL")
THOMASNET_PASSWORD = os.getenv("THOMASNET_PASSWORD")


def is_session_valid():
    """Check if stored session is still valid."""
    if not os.path.exists(AUTH_STATE_PATH):
        return False
    try:
        with open(AUTH_STATE_PATH) as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        # Check for ThomasNet session cookie
        return any(
            "thomasnet" in c.get("domain", "").lower()
            for c in cookies
        )
    except:
        return False


def auto_login_and_save_session():
    """Fully automated ThomasNet login with DataDome bypass."""
    print("[AutoLogin] Starting automated ThomasNet login...")
    ensure_xvfb()

    with sync_playwright() as p:
        browser, context = get_stealth_browser(p)
        page = context.new_page()

        try:
            # Step 1: Navigate to ThomasNet
            print("[AutoLogin] Navigating to ThomasNet...")
            page.goto("https://www.thomasnet.com/login", wait_until="networkidle", timeout=30000)
            time.sleep(random.uniform(2, 4))

            # Step 2: Check for DataDome challenge immediately
            if is_datadome_present(page):
                print("[AutoLogin] DataDome detected at landing — solving...")
                solved = solve_datadome_slider(page)
                if not solved:
                    raise Exception("Could not solve DataDome at landing page")
                time.sleep(random.uniform(2, 3))

            # Step 3: Fill login form with human-like typing
            print("[AutoLogin] Filling login form...")
            email_field = page.locator('input[type="email"], input[name="email"], #email').first
            email_field.click()
            time.sleep(random.uniform(0.3, 0.8))
            human_type(page, email_field, THOMASNET_EMAIL)
            time.sleep(random.uniform(0.5, 1.2))

            pass_field = page.locator('input[type="password"], input[name="password"], #password').first
            pass_field.click()
            time.sleep(random.uniform(0.3, 0.6))
            human_type(page, pass_field, THOMASNET_PASSWORD)
            time.sleep(random.uniform(0.8, 1.5))

            # Step 4: Submit
            submit = page.locator('button[type="submit"], input[type="submit"], .login-btn').first
            submit.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(random.uniform(2, 4))

            # Step 5: Check for post-login DataDome
            if is_datadome_present(page):
                print("[AutoLogin] DataDome detected after login — solving...")
                solve_datadome_slider(page)
                page.wait_for_load_state("networkidle", timeout=15000)

            # Step 6: Verify login succeeded
            if "login" in page.url or "signin" in page.url:
                raise Exception(f"Login failed — still on login page: {page.url}")

            # Step 7: Save session
            state = context.storage_state()
            with open(AUTH_STATE_PATH, "w") as f:
                json.dump(state, f)

            print(f"[AutoLogin] ✅ Session saved to {AUTH_STATE_PATH}")
            return True

        except Exception as e:
            print(f"[AutoLogin] ❌ Login failed: {e}")
            # Save screenshot for debugging
            page.screenshot(path="/Users/apple/Downloads/rebusinessautomationproject/dashboard/logs/login_error.png")
            return False
        finally:
            browser.close()


def is_datadome_present(page):
    """Detect DataDome challenge on current page."""
    indicators = [
        '[id*="datadome"]',
        '[class*="datadome"]',
        '[id*="slider"]',
        'iframe[src*="geo.captcha-delivery"]',
        'text=Slide to confirm',
        'text=Please verify'
    ]
    for selector in indicators:
        try:
            if page.locator(selector).count() > 0:
                return True
        except:
            pass
    return "datadome" in page.content().lower() or "captcha-delivery" in page.content().lower()


def human_type(page, element, text):
    """Type text with random delays between keystrokes."""
    for char in text:
        element.type(char, delay=random.randint(50, 180))
        if random.random() < 0.05:  # 5% chance of brief pause
            time.sleep(random.uniform(0.3, 0.8))