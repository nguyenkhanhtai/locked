import os
import logging
from logging.handlers import RotatingFileHandler
from core.db import DatabaseManager
from modules.tasks.repository import TaskRepository
from modules.study.repository import StudyRepository
from modules.blocker.repository import BlockerRepository
from schema import (
    TaskEvent, StudyProject, StudyProblem,
    StudyColumn, StudyRecord, StudyProblemCard,
    BlockRule
)

# Initialize logger for database operations
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

db_logger = logging.getLogger("database_ops")
db_logger.setLevel(logging.INFO)
if not db_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "database.log"), maxBytes=10*1024*1024, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    db_logger.addHandler(fh)


class TaskDatabase:
    """Backwards-compatible adapter for TaskRepository."""
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_file = DatabaseManager.get_db_path()
        else:
            self.db_file = db_path
            dir_name = os.path.dirname(os.path.abspath(self.db_file))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        self.repo = TaskRepository(self.db_file)

    def init_db(self):
        pass

    def add_event(self, name: str, description: str = "", start_date: int = 0, end_date: int = 0, priority: int = 1, labels: str = "", done: int = 0, calendar_type: str = "task"):
        return self.repo.add_event(name, description, start_date, end_date, priority, labels, done, calendar_type)

    def update_event(self, event_id: int, name: str, description: str = "", start_date: int = 0, end_date: int = 0, priority: int = 1, labels: str = "", done: int = 0, calendar_type: str = "task"):
        return self.repo.update_event(event_id, name, description, start_date, end_date, priority, labels, done, calendar_type)

    def delete_event(self, event_id: int):
        return self.repo.delete_event(event_id)

    def get_events(self, calendar_type: str = None):
        return self.repo.get_events(calendar_type)

    def get_event(self, event_id: int):
        return self.repo.get_event(event_id)


class StudyDatabase:
    """Backwards-compatible adapter for StudyRepository."""
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_file = DatabaseManager.get_db_path()
        else:
            self.db_file = db_path
            dir_name = os.path.dirname(os.path.abspath(self.db_file))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        self.repo = StudyRepository(self.db_file)

    def init_db(self):
        pass

    def add_study_project(self, name: str, description: str = "", parent_project_id: int = None):
        return self.repo.add_study_project(name, description, parent_project_id)

    def get_study_projects(self, parent_project_id=None):
        return self.repo.get_study_projects(parent_project_id)

    def get_study_project(self, project_id: int):
        return self.repo.get_study_project(project_id)

    def get_study_project_path(self, project_id: int):
        return self.repo.get_study_project_path(project_id)

    def delete_study_project(self, project_id: int):
        return self.repo.delete_study_project(project_id)

    def add_study_problem(self, project_id: int, title: str, description: str = ""):
        return self.repo.add_study_problem(project_id, title, description)

    def get_study_problems(self, project_id: int):
        return self.repo.get_study_problems(project_id)

    def get_study_problem(self, problem_id: int):
        return self.repo.get_study_problem(problem_id)

    def update_study_problem(self, problem_id: int, title: str = None, description: str = None):
        return self.repo.update_study_problem(problem_id, title, description)

    def delete_study_problem(self, problem_id: int):
        return self.repo.delete_study_problem(problem_id)

    def add_study_column(self, problem_id: int, name: str, order_index: int = 0):
        return self.repo.add_study_column(problem_id, name, order_index)

    def get_study_columns(self, problem_id: int):
        return self.repo.get_study_columns(problem_id)

    def update_study_column(self, column_id: int, name: str):
        return self.repo.update_study_column(column_id, name)

    def delete_study_column(self, column_id: int):
        return self.repo.delete_study_column(column_id)

    def add_study_record(self, title: str, body: str = "", project_id: int = None):
        return self.repo.add_study_record(title, body, project_id)

    def get_study_records(self, limit: int = 50, offset: int = 0, search: str = "", project_id: int = None):
        return self.repo.get_study_records(limit, offset, search, project_id)

    def get_study_record(self, record_id: int):
        return self.repo.get_study_record(record_id)

    def update_study_record(self, record_id: int, title: str, body: str):
        return self.repo.update_study_record(record_id, title, body)

    def delete_study_record(self, record_id: int):
        return self.repo.delete_study_record(record_id)

    def add_study_problem_card(self, column_id: int, record_id: int, order_index: int = 0):
        return self.repo.add_study_problem_card(column_id, record_id, order_index)

    def get_study_problem_cards(self, column_id: int):
        return self.repo.get_study_problem_cards(column_id)

    def delete_study_problem_card(self, card_id: int):
        return self.repo.delete_study_problem_card(card_id)

    def search_all_study_items(self, query: str = ""):
        return self.repo.search_all_study_items(query)


class BlockerDatabase:
    """Backwards-compatible adapter for BlockerRepository."""
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_file = DatabaseManager.get_db_path()
        else:
            self.db_file = db_path
            dir_name = os.path.dirname(os.path.abspath(self.db_file))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        self.repo = BlockerRepository(self.db_file)

    def add_rule(self, raw_url: str, duration_minutes: int, match_type: str = "domain", reason: str = ""):
        return self.repo.add_rule(raw_url, duration_minutes, match_type, reason)

    def get_active_rules(self):
        return self.repo.get_active_rules()

    def get_all_rules(self):
        return self.repo.get_all_rules()

    def delete_rule(self, rule_id: int):
        return self.repo.delete_rule(rule_id)

    def check_url_blocked(self, url: str):
        return self.repo.check_url_blocked(url)

