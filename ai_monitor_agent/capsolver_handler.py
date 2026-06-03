import capsolver
import base64
import os
import time
import requests
from PIL import Image
from io import BytesIO

capsolver.api_key = os.getenv("CAPSOLVER_API_KEY")

def solve_datadome_slider(page, max_attempts=3):
    """Fully automated DataDome slider solver using CapSolver."""
    for attempt in range(max_attempts):
        try:
            print(f"[CapSolver] Attempt {attempt + 1} to solve slider...")

            # Take screenshot of the full page
            screenshot = page.screenshot()
            img_b64 = base64.b64encode(screenshot).decode()

            # Get the slider element bounds
            slider = page.locator('[id*="slider"], [class*="slider"], [class*="captcha"]').first
            box = slider.bounding_box()

            if not box:
                print("[CapSolver] No slider element found on page")
                return False

            # Crop the captcha area from screenshot
            img = Image.open(BytesIO(screenshot))
            captcha_img = img.crop((
                int(box["x"]),
                int(box["y"]),
                int(box["x"] + box["width"]),
                int(box["y"] + box["height"])
            ))
            captcha_b64 = base64.b64encode(
                captcha_img.tobytes()
            ).decode()

            # Send to CapSolver
            solution = capsolver.solve({
                "type": "DataDomeSliderTask",
                "websiteURL": page.url,
                "captchaUrl": page.url,
                "proxy": build_proxy_string(),
                "userAgent": page.evaluate("navigator.userAgent")
            })

            if solution and solution.get("token"):
                # Inject the solution token
                page.evaluate(f"""
                    (token) => {{
                        window.datadome = window.datadome || {{}};
                        window.datadome.captchaToken = token;
                        // Trigger any datadome callback
                        if (window.ddjskey) {{
                            document.dispatchEvent(new CustomEvent('datadome_solved', {{detail: token}}));
                        }}
                    }}
                """, solution["token"])
                print(f"[CapSolver] ✅ Token injected successfully")
                page.wait_for_timeout(2000)
                return True

            # Fallback: use offset from CapSolver for manual drag
            if solution and solution.get("offset"):
                offset = solution["offset"]
                await_human_drag(page, box, offset)
                return True

        except Exception as e:
            print(f"[CapSolver] Attempt {attempt + 1} failed: {e}")
            time.sleep(3)

    return False


def await_human_drag(page, slider_box, offset_x):
    """Simulate human-like slider drag with natural mouse movement."""
    import random
    import math

    start_x = slider_box["x"] + 10
    start_y = slider_box["y"] + slider_box["height"] / 2
    end_x = start_x + offset_x

    # Move to start position
    page.mouse.move(start_x, start_y)
    page.wait_for_timeout(random.randint(100, 300))
    page.mouse.down()
    page.wait_for_timeout(random.randint(50, 150))

    # Simulate natural acceleration curve (ease-in-out)
    steps = 35
    for i in range(steps + 1):
        t = i / steps
        # Ease-in-out cubic
        if t < 0.5:
            eased = 4 * t * t * t
        else:
            eased = 1 - pow(-2 * t + 2, 3) / 2

        # Add subtle vertical jitter (humans don't drag perfectly horizontal)
        jitter_y = random.uniform(-1.5, 1.5)
        current_x = start_x + (end_x - start_x) * eased
        current_y = start_y + jitter_y

        page.mouse.move(current_x, current_y)
        # Variable speed — slower at start and end
        delay = random.randint(8, 25) if 0.2 < t < 0.8 else random.randint(20, 50)
        page.wait_for_timeout(delay)

    page.wait_for_timeout(random.randint(100, 200))
    page.mouse.up()
    print(f"[CapSolver] Human drag completed to offset {offset_x}")


def build_proxy_string():
    user = os.getenv("IPROYAL_USER")
    pwd = os.getenv("IPROYAL_PASS")
    host = os.getenv("IPROYAL_HOST")
    port = os.getenv("IPROYAL_PORT")
    return f"http://{user}:{pwd}@{host}:{port}"