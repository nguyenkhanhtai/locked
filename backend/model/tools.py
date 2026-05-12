from mcp.server.fastmcp import FastMCP
import sys
import os

# Đưa thư mục backend vào sys.path để có thể import các file database
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print(backend_dir)

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from database import TaskDatabase, BlockedDatabase, ConsumptionDatabase

mcp = FastMCP("LockedApp")

# --- Playwright Browser State ---
_browser_context = {}

def get_playwright_page():
    if "playwright" not in _browser_context:
        from playwright.sync_api import sync_playwright
        _browser_context["playwright"] = sync_playwright().start()
        _browser_context["browser"] = _browser_context["playwright"].chromium.launch(headless=True)
        _browser_context["page"] = _browser_context["browser"].new_page()
    return _browser_context["page"]

@mcp.tool()
def get_tasks() -> str:
    """Get the current list of events/tasks scheduled."""
    db = TaskDatabase()
    tasks = db.get_events()
    return str(tasks)

@mcp.tool()
def get_blocked_sites() -> str:
    """Get the list of currently blocked or locked websites."""
    db = BlockedDatabase()
    blocks = db.get_all_blocks()
    print(str(blocks))
    return str(blocks)

@mcp.tool()
def get_top_sites(limit: int = 5) -> str:
    """Get statistics of the most visited websites and time spent on them."""
    db = ConsumptionDatabase()
    sites = db.get_top_sites(limit)
    return str(sites)

@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return str(results)
    except Exception as e:
        return f"Search failed: {e}"

@mcp.tool()
def read_webpage(url: str) -> str:
    """Navigate to a webpage and read its text content using Playwright."""
    try:
        page = get_playwright_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=10000)
        content = page.evaluate("document.body.innerText")
        return content[:5000] # Giới hạn nội dung tránh bị lỗi độ dài token
    except Exception as e:
        return f"Failed to read page: {e}"

@mcp.tool()
def click_element(selector: str) -> str:
    """Click an element on the current webpage using Playwright. Useful for navigation."""
    try:
        page = get_playwright_page()
        page.click(selector, timeout=10000)
        page.wait_for_load_state("networkidle", timeout=10000)
        content = page.evaluate("document.body.innerText")
        return f"Successfully clicked '{selector}'. New page content preview:\n" + content[:3000]
    except Exception as e:
        return f"Failed to click element: {e}"

@mcp.tool()
def scroll_page(amount: int = 800) -> str:
    """Scroll the current webpage down by the specified amount of pixels (e.g., 800). Use negative for up."""
    try:
        page = get_playwright_page()
        page.evaluate(f"window.scrollBy(0, {amount})")
        return f"Scrolled by {amount} pixels."
    except Exception as e:
        return f"Failed to scroll: {e}"

if __name__ == "__main__":
    mcp.run()
