from duckduckgo_search import DDGS
import time

print("Testing DuckDuckGo Search...")
try:
    results = DDGS().text("test query", max_results=3)
    print(f"Results found: {len(results)}")
    for r in results:
        print(r)
except Exception as e:
    print(f"Search failed: {e}")
