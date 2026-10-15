import pytest
from core.events import EventBus
from core.registry import ModuleRegistry, ModuleMetadata
from core.db import DatabaseManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def test_event_bus_pub_sub():
    received_events = []

    def handler(task):
        received_events.append(task)

    # Subscribe
    EventBus.subscribe("test.created", handler)

    # Emit
    EventBus.emit("test.created", task={"id": 1, "title": "Test Task"})
    assert len(received_events) == 1
    assert received_events[0]["id"] == 1

    # Unsubscribe
    EventBus.unsubscribe("test.created", handler)
    EventBus.emit("test.created", task={"id": 2, "title": "Second Task"})
    assert len(received_events) == 1  # No new event received


def test_event_bus_error_isolation():
    def failing_handler(**kwargs):
        raise ValueError("Intentional subscriber error")

    passed_events = []
    def passing_handler(**kwargs):
        passed_events.append(True)

    EventBus.subscribe("fault.test", failing_handler)
    EventBus.subscribe("fault.test", passing_handler)

    # Emit should not throw exception even if one subscriber fails
    EventBus.emit("fault.test")
    assert len(passed_events) == 1

    EventBus.unsubscribe("fault.test", failing_handler)
    EventBus.unsubscribe("fault.test", passing_handler)


def test_module_registry():
    # Verify built-in modules are registered
    modules = ModuleRegistry.get_modules()
    module_ids = [m.id for m in modules]
    assert "tasks" in module_ids
    assert "study" in module_ids

    # Verify order sorting
    tasks_mod = ModuleRegistry.get_module("tasks")
    study_mod = ModuleRegistry.get_module("study")
    assert tasks_mod.order < study_mod.order


def test_database_manager_schema_hooks(tmp_path):
    test_db = str(tmp_path / "test_schema_hooks.db")

    executed_tables = []
    def custom_schema(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS mock_plugin (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        executed_tables.append("mock_plugin")

    DatabaseManager.register_schema(custom_schema)
    DatabaseManager.init_all(test_db)

    with DatabaseManager.get_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mock_plugin'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "mock_plugin"


def test_dynamic_plugin_registration(tmp_path):
    test_app = Starlette()

    # Simulate a third-party or custom plugin
    mock_meta = ModuleMetadata(
        id="flashcards",
        title="Flashcards Plugin",
        icon="🗂️",
        url="/flashcards",
        order=3,
        description="Spaced repetition flashcards"
    )
    ModuleRegistry.register(mock_meta)

    async def mock_endpoint(request):
        return JSONResponse({"status": "200 <OK>", "plugin": "flashcards"})

    test_app.router.routes.append(Route('/api/flashcards', endpoint=mock_endpoint, methods=['GET']))

    # Verify discovery in registry
    registered = ModuleRegistry.get_module("flashcards")
    assert registered is not None
    assert registered.title == "Flashcards Plugin"
    assert registered.icon == "🗂️"
