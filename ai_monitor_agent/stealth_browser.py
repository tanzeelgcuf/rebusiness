import os
import subprocess
import time
from playwright.sync_api import sync_playwright

def ensure_xvfb():
    """Make sure Xvfb is running before launching browser."""
    result = subprocess.run(["pgrep", "Xvfb"], capture_output=True)
    if result.returncode != 0:
        print("[Xvfb] Not running — starting...")
        subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    os.environ["DISPLAY"] = ":99"
    print("[Xvfb] ✅ Display :99 ready")


def get_stealth_browser(playwright):
    """Launch a maximally stealthy Chromium browser with IPRoyal proxy."""
    proxy_user = os.getenv("IPROYAL_USER")
    proxy_pass = os.getenv("IPROYAL_PASS")
    proxy_host = os.getenv("IPROYAL_HOST")
    proxy_port = os.getenv("IPROYAL_PORT")

    # Debug: Print proxy info (without password)
    print(f"[Proxy] User: {proxy_user}, Host: {proxy_host}:{proxy_port}")

    browser = playwright.chromium.launch(
        headless=False,  # MUST be False to bypass DataDome
        proxy={
            "server": f"http://{proxy_host}:{proxy_port}",
            "username": proxy_user,
            "password": proxy_pass
        },
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            f"--display={os.environ.get('DISPLAY', ':99')}"
        ]
    )

    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="en-US",
        timezone_id="America/New_York",
        permissions=["geolocation"],
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        }
    )

    # Inject stealth JS to mask automation signals
    context.add_init_script("""
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

        // Fake plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Fake languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // Override chrome runtime
        window.chrome = {runtime: {}};

        // Fake notification permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)

    return browser, context