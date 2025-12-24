
import asyncio
from playwright.async_api import async_playwright

URL = "https://sam.gov/workspace/contract/opp/1a5c9c24027047688641b4a08412ea45/view"

async def main():
    print(f"Debugging URL: {URL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(URL, timeout=90000)
            await page.wait_for_load_state("domcontentloaded")
            print("DOM Loaded. Waiting 5s for dynamic content...")
            await asyncio.sleep(5)
            
            print(f"Page Title: {await page.title()}")
            
            # Screenshot to visualize what the bot sees
            await page.screenshot(path="nexxt_debug.png", full_page=True)
            print("Screenshot saved: nexxt_debug.png")
            
            # List all links
            links = await page.query_selector_all("a")
            print(f"Found {len(links)} links on page.")
            
            for i, link in enumerate(links):
                text = (await link.inner_text()).strip().replace('\n', ' ')
                href = await link.get_attribute("href")
                if href and ("http" in href or "download" in href or "file" in href):
                    print(f"  [{i}] TEXT: '{text}' | URL: {href}")

            # Specific HTML dump
            content = await page.content()
            with open("nexxt_full_page.html", "w") as f:
                f.write(content)
            print("Saved full HTML to nexxt_full_page.html")


        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
