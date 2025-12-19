# ThomasNet Scraper - URL Update

## Goal
Fix "Page Not Found" error by using the modern ThomasNet search URL structure.

## Changes
### `thomasnet_scraper.py`
*   Update `base_url` or `search_url` construction.
*   New Pattern: `https://www.thomasnet.com/suppliers/search?cov=NA&searchsource=suppliers&searchterm={product}&searchx=true`
    *   (Derived from the "Suggested Searches" links in the 404 page: `searchterm=Metal+Stamping`)

## Verification
*   Run `test_scraper_manual.py` again.
