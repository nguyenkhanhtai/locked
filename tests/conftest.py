import os
import sys
import pytest
from starlette.testclient import TestClient

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import TaskDatabase, StudyDatabase
import app as app_module


@pytest.fixture
def task_db(tmp_path):
    """Provides an isolated TaskDatabase instance in a temporary directory."""
    db_file = str(tmp_path / "task_test.db")
    return TaskDatabase(db_path=db_file)


@pytest.fixture
def study_db(tmp_path):
    """Provides an isolated StudyDatabase instance in a temporary directory."""
    db_file = str(tmp_path / "study_test.db")
    return StudyDatabase(db_path=db_file)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Configures Starlette app with temporary isolated databases and settings,
    returning a TestClient for API testing.
    """
    task_db_file = str(tmp_path / "api_task_test.db")
    study_db_file = str(tmp_path / "api_study_test.db")
    settings_file = str(tmp_path / "state_test.json")

    test_task_db = TaskDatabase(db_path=task_db_file)
    test_study_db = StudyDatabase(db_path=study_db_file)

    monkeypatch.setattr(app_module, "event_db", test_task_db)
    monkeypatch.setattr(app_module, "study_db", test_study_db)
    monkeypatch.setattr(app_module.SettingsManager, "get_settings_path", lambda: settings_file)

    with TestClient(app_module.app, raise_server_exceptions=True) as c:
        yield c

