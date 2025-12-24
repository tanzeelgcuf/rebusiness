
import asyncio
from playwright.async_api import async_playwright
import os

URL = "https://sam.gov/workspace/contract/opp/7f907be6123244a69699a724e35fa83f/view"
DOWNLOAD_DIR = os.path.abspath("downloads")

async def main():
    print(f"Starting deep fetch for: {URL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        try:
            await page.goto(URL, timeout=60000)
            await page.wait_for_load_state('networkidle')
            print("Page loaded.")
            
            # Save screenshot for verifying layout
            await page.screenshot(path="sam_deep_dive.png")
            print("Screenshot saved.")

            # Try to find description
            desc_el = await page.query_selector("#description")
            if desc_el:
                print("Found description element.")
                text = await desc_el.inner_text()
                print(f"Description Length: {len(text)}")
                with open("diatron_desc.txt", "w") as f:
                    f.write(text)
            
            # Try to find attachments
            # Common selectors in SAM
            # Sometimes inside a div id="attachments-links"
            # Or app-attachments component
            
            # Priority 1: "Download All" button
            try:
                print("Looking for 'Download All' button...")
                download_all_btn = await page.query_selector("button:has-text('Download All')")
                if not download_all_btn:
                     # Try searching specifically inside the attachments section if possible or generic
                     download_all_btn = await page.query_selector("#files button") 
                
                if download_all_btn:
                    print("Found 'Download All' button. Clicking...")
                    async with page.expect_download(timeout=30000) as download_info:
                        await download_all_btn.click()
                    download = await download_info.value
                    path = os.path.join(DOWNLOAD_DIR, f"diatron_all_{download.suggested_filename}")
                    await download.save_as(path)
                    print(f"Downloaded ZIP/File: {path}")
                    download_count += 1
                else:
                    print("'Download All' button not found.")
            except Exception as e:
                print(f"Failed to click 'Download All': {e}")

            # Priority 2: Individual Files (if Download All failed or just to be safe)
            if download_count == 0:
                print("Attempting individual file downloads...")
                # often hidden in a div with class 'description' or similar, or just 'a' tags that look like files
                # We will look for anything that looks like a file extension in text
                elements = await page.query_selector_all("div, a, span")
                for el in elements:
                    try:
                        text = await el.inner_text()
                        if any(ext in text.lower() for ext in ['.pdf', '.docx', '.xlsx', 'statement of work', 'sow', 'specs']):
                            # Check if it's clickable
                            if await el.is_visible():
                                print(f"Found potential file element: {text}")
                                try:
                                    async with page.expect_download(timeout=5000) as download_info:
                                        await el.click()
                                    download = await download_info.value
                                    path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
                                    await download.save_as(path)
                                    print(f"Downloaded: {path}")
                                    download_count += 1
                                except:
                                    pass # Might not be a download link
                    except:
                        continue

        except Exception as e:
            print(f"Error during scrape: {e}")
            await page.screenshot(path="error_state.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
