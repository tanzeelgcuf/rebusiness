import os
import time
import random
import math
from PIL import Image
from io import BytesIO
import base64

def solve_datadome_slider_free(page, max_attempts=5):
    """
    Free DataDome slider solver without external APIs.
    Attempts to solve slider by detecting element and trying various strategies.
    """
    print("[FreeSolver] Attempting to solve DataDome slider without external APIs...")

    for attempt in range(max_attempts):
        try:
            print(f"[FreeSolver] Attempt {attempt + 1}/{max_attempts}")

            # Step 1: Detect slider element
            slider_selectors = [
                '[id*="slider"]',
                '[class*="slider"]',
                '[class*="captcha"]',
                '[id*="captcha"]',
                '[data-action*="slider"]',
                '.datadome-slider',
                '#datadome-slider'
            ]

            slider_element = None
            slider_box = None

            for selector in slider_selectors:
                try:
                    element = page.locator(selector).first
                    if element.count() > 0 and element.is_visible(timeout=2000):
                        slider_element = element
                        slider_box = element.bounding_box()
                        if slider_box:
                            print(f"[FreeSolver] Found slider with selector: {selector}")
                            break
                except Exception as e:
                    continue

            if not slider_element or not slider_box:
                print("[FreeSolver] No slider element found")
                # Try to take screenshot and look for visual cues
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                else:
                    return False

            # Step 2: Get slider properties
            slider_width = slider_box["width"]
            slider_height = slider_box["height"]

            print(f"[FreeSolver] Slider dimensions: {slider_width}x{slider_height}")

            # Step 3: Try different solving strategies
            strategies = [
                ("Fixed offset (80%)", lambda: int(slider_width * 0.8)),
                ("Fixed offset (75%)", lambda: int(slider_width * 0.75)),
                ("Fixed offset (70%)", lambda: int(slider_width * 0.7)),
                ("Calculate from gap", lambda: calculate_gap_offset(page, slider_element, slider_box)),
                ("Brute force small", lambda: brute_force_offset(page, slider_element, slider_box, 50, 100)),
                ("Brute force medium", lambda: brute_force_offset(page, slider_element, slider_box, 100, 150)),
                ("Brute force large", lambda: brute_force_offset(page, slider_element, slider_box, 150, 250)),
            ]

            for strategy_name, offset_func in strategies:
                try:
                    print(f"[FreeSolver] Trying strategy: {strategy_name}")
                    offset = offset_func()

                    if offset is None or offset <= 0 or offset > slider_width * 1.5:
                        continue

                    print(f"[FreeSolver] Using offset: {offset}")

                    # Execute the drag
                    success = execute_slider_drag(page, slider_box, offset)

                    if success:
                        # Wait to see if challenge passes
                        page.wait_for_timeout(3000)

                        # Check if DataDome is still present
                        if not is_datadome_present(page):
                            print(f"[FreeSolver] ✅ Slider solved successfully with {strategy_name}")
                            return True
                        else:
                            print(f"[FreeSolver] ❌ Slider still present after {strategy_name}")

                except Exception as e:
                    print(f"[FreeSolver] Strategy {strategy_name} failed: {e}")
                    continue

            # If we get here, all strategies failed for this attempt
            if attempt < max_attempts - 1:
                print("[FreeSolver] All strategies failed, waiting before retry...")
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"[FreeSolver] Attempt {attempt + 1} failed with error: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)

    print("[FreeSolver] ❌ All attempts failed to solve slider")
    return False

def calculate_gap_offset(page, slider_element, slider_box):
    """
    Try to calculate offset by analyzing the slider gap visually.
    This is a simplified approach - in reality, this would need image analysis.
    """
    # For now, return a reasonable default based on common DataDome implementations
    # Most sliders require moving ~70-80% of the width
    return int(slider_box["width"] * 0.75)

def brute_force_offset(page, slider_element, slider_box, min_offset, max_offset):
    """
    Try a range of offsets to find the correct one.
    """
    # Try a few values in the range
    for offset in range(min_offset, min(max_offset, int(slider_box["width"])), 10):
        # Execute drag with this offset
        success = execute_slider_drag(page, slider_box, offset, release_only=False)

        if success:
            # Check if it worked
            page.wait_for_timeout(2000)
            if not is_datadome_present(page):
                return offset

            # If not successful, reset and try next
            # Reset slider position by refreshing or clicking reset if available
            try:
                reset_btn = page.locator('[class*="reset"], [id*="reset"], button:has-text("Reset")').first
                if reset_btn.count() > 0:
                    reset_btn.click()
                    page.wait_for_timeout(1000)
            except:
                pass  # Continue anyway

    return None

def execute_slider_drag(page, slider_box, offset_x, release_only=True):
    """
    Execute the slider drag with human-like movement.
    """
    try:
        start_x = slider_box["x"] + 10
        start_y = slider_box["y"] + slider_box["height"] / 2
        end_x = start_x + offset_x

        # Move to start position
        page.mouse.move(start_x, start_y)
        page.wait_for_timeout(random.randint(100, 300))

        if not release_only:
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

        if not release_only:
            page.wait_for_timeout(random.randint(100, 200))
            page.mouse.up()

        print(f"[FreeSolver] Drag executed to offset {offset_x}")
        return True

    except Exception as e:
        print(f"[FreeSolver] Drag execution failed: {e}")
        return False

def is_datadome_present(page):
    """
    Detect if DataDome challenge is still present on the page.
    """
    try:
        indicators = [
            '[id*="datadome"]',
            '[class*="datadome"]',
            '[id*="slider"]',
            'iframe[src*="geo.captcha-delivery"]',
            'text=Slide to confirm',
            'text=Please verify',
            'text=Please slide to verify'
        ]

        for selector in indicators:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except:
                pass

        # Also check page content
        content = page.content()
        return "datadome" in content.lower() or "captcha-delivery" in content.lower()
    except:
        return False

def build_proxy_string():
    """Build proxy string from environment variables."""
    user = os.getenv("IPROYAL_USER")
    pwd = os.getenv("IPROYAL_PASS")
    host = os.getenv("IPROYAL_HOST")
    port = os.getenv("IPROYAL_PORT")
    if user and pwd and host and port:
        return f"http://{user}:{pwd}@{host}:{port}"
    return None