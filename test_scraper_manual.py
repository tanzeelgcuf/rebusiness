from thomasnet_scraper import ThomasNetScraper
from database_manager import DatabaseManager

db = DatabaseManager()
scraper = ThomasNetScraper(db)

# Manual test with a good keyword
scraper.scrape_suppliers("Industrial Bolts")
