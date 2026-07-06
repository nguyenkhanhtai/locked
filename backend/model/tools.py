from mcp.server.fastmcp import FastMCP
import sys
import os

# Đưa thư mục backend vào sys.path để có thể import các file database
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print(backend_dir)

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from database import TaskDatabase, BlockedDatabase, ConsumptionDatabase, StudyDatabase

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
    try:
        tasks = db.get_events()
        return str(tasks)
    except Exception as e:
        return f"Error retrieving tasks: {e}"

@mcp.tool()
def get_blocked_sites() -> str:
    """Get the list of currently blocked or locked websites."""
    db = BlockedDatabase()
    try:
        blocks = db.get_all_blocks()
        return str(blocks)
    except Exception as e:
        return f"Error retrieving blocked sites: {e}"

@mcp.tool()
def get_top_sites(limit: int = 5) -> str:
    """Get statistics of the most visited websites and time spent on them."""
    db = ConsumptionDatabase()
    try:
        sites = db.get_top_sites(limit)
        return str(sites)
    except Exception as e:
        return f"Error retrieving top sites: {e}"

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

@mcp.tool()
def get_thinking_projects() -> str:
    """Get the list of all thinking projects (problem statements)."""
    db = StudyDatabase()
    try:
        projects = db.get_thinking_projects()
        return str(projects)
    except Exception as e:
        return f"Error retrieving thinking projects: {e}"

@mcp.tool()
def get_thinking_items(project_id: int) -> str:
    """Get all thinking items (knowledge, inferences, questions) in a specific thinking project."""
    db = StudyDatabase()
    try:
        items = db.get_thinking_items(project_id)
        return str(items)
    except Exception as e:
        return f"Error retrieving thinking items: {e}"

@mcp.tool()
def get_thinking_item(project_id: int, item_type: str, item_id: int) -> str:
    """Get the content of a specific thinking item in a project. item_type must be 'knowledge', 'inference', or 'question'."""
    db = StudyDatabase()
    try:
        items = db.get_thinking_items(project_id)
        
        items_dict = items.__dict__ if hasattr(items, '__dict__') else items
        target_list = []
        
        if item_type == "knowledge":
            target_list = getattr(items, 'knowledge', items_dict.get("knowledge", []))
        elif item_type == "inference":
            target_list = getattr(items, 'inferences', items_dict.get("inferences", []))
        elif item_type == "question":
            target_list = getattr(items, 'questions', items_dict.get("questions", []))

        for item in target_list:
            item_dict = item.__dict__ if hasattr(item, '__dict__') else item
            if item_dict.get("id") == item_id or getattr(item, "id", None) == item_id:
                return str(item_dict)
                
        return f"Item not found with id {item_id} and type {item_type} in project {project_id}."
    except Exception as e:
        return f"Error retrieving thinking item: {e}"

@mcp.tool()
def create_thinking_item(project_id: int, item_type: str, name: str, description: str, source_ids: str = "") -> str:
    """Create a new thinking item in a project. item_type must be 'knowledge', 'inference', or 'question'."""
    db = StudyDatabase()
    try:
        if item_type == "knowledge":
            db.add_thinking_knowledge(project_id, name, description, 0)
        elif item_type == "inference":
            db.add_thinking_inference(project_id, name, description, source_ids, 0)
        elif item_type == "question":
            db.add_thinking_question(project_id, name, description, 0)
        else:
            return f"Invalid item_type '{item_type}'."
        return f"Successfully created {item_type} '{name}' in project {project_id}."
    except Exception as e:
        return f"Failed to create item: {str(e)}"

@mcp.tool()
def update_thinking_item(item_type: str, item_id: int, name: str, description: str, source_ids: str = "") -> str:
    """Update an existing thinking item. item_type must be 'knowledge', 'inference', or 'question'."""
    db = StudyDatabase()
    try:
        db.update_thinking_item(item_type, item_id, name, description, source_ids)
        return f"Successfully updated {item_type} {item_id}."
    except Exception as e:
        return f"Failed to update item: {str(e)}"


# -----------------------------
# Flashcards (Memorize) tools
# -----------------------------

@mcp.tool()
def get_flashcard_projects() -> str:
    """
    Retrieve all flashcard projects/collections.

    Returns:
        str: A stringified list of `StudyProject` objects.

    Notes:
        - Projects live in the `study.db` database (StudyDatabase).
        - This tool is read-only.
    """
    db = StudyDatabase()
    try:
        return str(db.get_study_projects())
    except Exception as e:
        return f"Error retrieving projects: {e}"


@mcp.tool()
def create_flashcard_project(name: str, description: str = "") -> str:
    """
    Create a new flashcard project/collection.

    Args:
        name: Project name (required).
        description: Optional description.

    Returns:
        str: A stringified `StudyProject` of the created project (includes its generated id).
    """
    db = StudyDatabase()
    try:
        project = db.add_study_project(name=name, description=description)
        return str(project)
    except Exception as e:
        return f"Error creating project: {e}"


@mcp.tool()
def delete_flashcard_project(project_id: int) -> str:
    """
    Delete a flashcard project/collection by id.

    Args:
        project_id: The study project id.

    Returns:
        str: Status message.

    Important:
        - This removes the project and its links in `project_flashcards`.
        - Flashcards may still remain in the global `flashcards` table (depending on DB implementation).
    """
    db = StudyDatabase()
    try:
        db.delete_study_project(project_id)
        return f"Deleted flashcard project {project_id}."
    except Exception as e:
        return f"Failed to delete project: {e}"


@mcp.tool()
def get_flashcards(project_id: int = 0) -> str:
    """
    Retrieve flashcards.

    Args:
        project_id:
            - 0 (default): return all flashcards (with optional project_id link).
            - non-zero: return only flashcards linked to that project.

    Returns:
        str: A stringified list of `FlashcardItem` objects.
    """
    db = StudyDatabase()
    try:
        cards = db.get_flashcards()
        if project_id:
            cards = [c for c in cards if getattr(c, "project_id", None) == project_id]
        return str(cards)
    except Exception as e:
        return f"Error retrieving flashcards: {e}"


@mcp.tool()
def create_flashcard(word: str, meaning: str, tags: list[str] = None, other_info: str = "", project_id: int = 0) -> str:
    """
    Create a single flashcard and optionally attach it to a project.

    Args:
        word: The front side text (required).
        meaning: The back side text (required).
        tags: Optional list of tags/categories (e.g. ["OOP", "Design Patterns"]).
        other_info: Optional notes.
        project_id: Optional project id (0 means no project).

    Returns:
        str: A stringified `FlashcardItem` (includes its generated id).
    """
    db = StudyDatabase()
    try:
        pid = project_id or None
        label_str = ", ".join(tags) if tags else ""
        card = db.add_flashcard(word=word, meaning=meaning, label=label_str, other_info=other_info, project_id=pid)
        return str(card)
    except Exception as e:
        return f"Error creating flashcard: {e}"



@mcp.tool()
def create_flashcards_bulk(project_id: int, cards: list[dict], default_tags: list[str] = None, default_other_info: str = "") -> str:
    """
    Create many flashcards in one call (batch insert) and attach them to a project.

    This tool is meant for "generate/import flashcards" workflows where you already have a list of dictionaries.

    Args:
        project_id: Target project id to link all created flashcards (0 means no project).
        cards:
            A list of dictionaries. Each dict must include:
              - "word": str
              - "meaning": str
            Optional keys per item:
              - "tags": list[str] (e.g. ["Fruit", "Red"])
              - "other_info": str

            Example:
                [
                  {"word": "apple", "meaning": "quả táo", "tags": ["Fruit", "Red"]},
                  {"word": "banana", "meaning": "quả chuối", "tags": ["Fruit", "Yellow"]}
                ]

        default_tags: Fallback tags list used when an item does not provide "tags".
        default_other_info: Fallback note used when an item does not provide "other_info".

    Returns:
        str: Status message including how many were created.
    """
    db = StudyDatabase()
    try:
        pid = project_id or None
        
        # Prepare cards for DB (converting tags list to comma-separated label string)
        db_cards = []
        def_label = ", ".join(default_tags) if default_tags else ""
        
        for c in cards:
            tags = c.get("tags")
            label = ", ".join(tags) if isinstance(tags, list) else c.get("label", def_label)
            
            db_cards.append({
                "word": c.get("word"),
                "meaning": c.get("meaning"),
                "label": label,
                "other_info": c.get("other_info", default_other_info)
            })

        created = db.add_flashcards_bulk(
            cards=db_cards,
            project_id=pid,
            default_label=def_label,
            default_other_info=default_other_info,
        )
        return f"Created {len(created)} flashcards in project {project_id}."
    except Exception as e:
        return f"Failed to bulk create flashcards: {e}"


@mcp.tool()
def delete_flashcard_item(card_id: int) -> str:
    """
    Permanently delete a flashcard by id.

    Args:
        card_id: Flashcard id.

    Returns:
        str: Status message.

    Notes:
        - This removes the flashcard and also removes its links from `project_flashcards`.
    """
    db = StudyDatabase()
    try:
        db.delete_flashcard(card_id)
        return f"Deleted flashcard {card_id}."
    except Exception as e:
        return f"Failed to delete flashcard: {e}"

if __name__ == "__main__":
    mcp.run()
