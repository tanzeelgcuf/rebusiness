import os
import json
import logging
import time
import requests
from twocaptcha import TwoCaptcha
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class DataDomeSolver:
    """
    Solves DataDome slider captchas using 2Captcha or CapSolver.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TWO_CAPTCHA_API_KEY")
        self.cap_key = os.getenv("CAPSOLVER_API_KEY")
        self.solver = TwoCaptcha(self.api_key) if self.api_key else None

    def solve_datadome(self, page_url: str, user_agent: str, proxy: dict = None) -> str:
        """
        Send a DataDome challenge to 2Captcha and return the solved cookie token.

        Args:
            page_url: The URL of the page where the captcha appeared.
            user_agent: The User-Agent string used by the browser.
            proxy: Optional proxy dictionary with 'server', 'username', 'password'.

        Returns:
            The 'datadome' cookie value.
        """
        logger.info(f"Initiating DataDome solver for {page_url}...")

        # Prepare proxy string for 2Captcha format: login:password@ip:port
        proxy_str = None
        if proxy:
            server = proxy.get('server', '')
            parsed = urlparse(server)
            host = parsed.hostname
            port = parsed.port
            user = proxy.get('username')
            pw = proxy.get('password')

            if user and pw:
                proxy_str = f"{user}:{pw}@{host}:{port}"
            else:
                proxy_str = f"{host}:{port}"

        # Try CapSolver first (faster/cheaper for DataDome)
        if self.cap_key and self.cap_key != "your_capsolver_key_here":
            try:
                return self._solve_capsolver(page_url, user_agent, proxy_str)
            except Exception as e:
                logger.warning(f"CapSolver failed, falling back to 2Captcha: {e}")

        # Fallback to 2Captcha
        if not self.solver:
            raise RuntimeError("No solver configured — set TWO_CAPTCHA_API_KEY or CAPSOLVER_API_KEY")

        try:
            result = self.solver.datadome(
                sitekey="NoKeyNeededForDataDome",
                url=page_url,
                userAgent=user_agent,
                proxy={
                    'type': 'HTTP',
                    'uri': proxy_str
                } if proxy_str else None,
            )

            logger.info("Captcha solved successfully by 2Captcha!")
            return result['code']

        except Exception as e:
            logger.error(f"2Captcha solver failed: {e}")
            raise e

    def _solve_capsolver(self, page_url: str, user_agent: str, proxy_str: str = None) -> str:
        """
        Solve DataDome via CapSolver's DatadomeSliderTask.
        Returns the datadome cookie value.
        """
        logger.info("Attempting CapSolver DataDomeSliderTask...")

        payload = {
            "clientKey": self.cap_key,
            "task": {
                "type": "DatadomeSliderTask",
                "websiteURL": page_url,
                "userAgent": user_agent,
            }
        }

        if proxy_str:
            # CapSolver expects proxy in "ip:port:user:pass" or "ip:port" format
            payload["task"]["proxy"] = proxy_str

        # Create task
        resp = requests.post("https://api.capsolver.com/createTask", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errorId") != 0:
            raise RuntimeError(f"CapSolver createTask error: {data.get('errorDescription', data)}")

        task_id = data.get("taskId")
        logger.info(f"CapSolver task created: {task_id}")

        # Poll for result
        for _ in range(60):
            time.sleep(2)
            resp = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": self.cap_key,
                "taskId": task_id
            }, timeout=15)
            resp.raise_for_status()
            result = resp.json()

            if result.get("status") == "ready":
                cookie = result.get("solution", {}).get("cookie", "")
                logger.info("✅ CapSolver solved DataDome successfully!")
                return cookie

            if result.get("status") == "failed":
                raise RuntimeError(f"CapSolver task failed: {result.get('errorDescription', result)}")

        raise TimeoutError("CapSolver DataDome task timed out after 120s")


def detect_datadome(page) -> bool:
    """Check if the page currently has a DataDome captcha."""
    try:
        # 1. Check for characteristic iframe
        if page.frame_locator('iframe[title*="DataDome"]').first.is_visible(timeout=1000):
            return True
        # 2. Check for captcha-delivery.com in page content
        content = page.content()
        if "captcha-delivery.com" in content or "DataDome" in content:
            return True
        # 3. Check for specific JS variables
        if "var dd={'rt':'c'" in content:
            return True
        return False
    except:
        return False
