import sqlite3
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from schema import (
    TaskEvent, StudyProject, StudyProblem,
    StudyColumn, StudyRecord, StudyProblemCard
)

# Initialize logger for database
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

db_logger = logging.getLogger("database_ops")
db_logger.setLevel(logging.INFO)
if not db_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "database.log"), maxBytes=10*1024*1024, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    db_logger.addHandler(fh)


class TaskDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for managing Tasks and Events."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_dir = os.path.join(base_dir, "db")
            os.makedirs(db_dir, exist_ok=True)
            self.db_file = os.path.join(db_dir, "task.db")
        else:
            self.db_file = db_path
            db_dir = os.path.dirname(os.path.abspath(self.db_file))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in TaskDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        start_date INTEGER NOT NULL,
                        end_date INTEGER NOT NULL,
                        priority INTEGER DEFAULT 1,
                        labels TEXT DEFAULT '',
                        done INTEGER DEFAULT 0
                    )
                ''')
                conn.commit()
            db_logger.info("Initialized TaskDatabase successfully.")
        except Exception as e:
            db_logger.error(f"Failed to initialize TaskDatabase: {e}")

    def add_event(self, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO events (name, description, start_date, end_date, priority, labels, done) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, description, start_date, end_date, priority, labels, done)
                )
                event_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added task: '{name}' (ID: {event_id}, priority: {priority}, done: {done})")
            return TaskEvent(
                id=event_id, name=name, description=description,
                start_date=start_date, end_date=end_date,
                priority=priority, labels=labels, done=bool(done)
            )
        except Exception as e:
            db_logger.error(f"Error adding event {name}: {e}")
            raise

    def update_event(self, event_id: int, name: str, description: str, start_date: int, end_date: int, priority: int, labels: str, done: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE events SET name = ?, description = ?, start_date = ?, end_date = ?, priority = ?, labels = ?, done = ? WHERE id = ?",
                    (name, description, start_date, end_date, priority, labels, done, event_id)
                )
                conn.commit()
            db_logger.info(f"Updated task ID {event_id}: '{name}'")
            return True
        except Exception as e:
            db_logger.error(f"Error updating event {event_id}: {e}")
            raise

    def delete_event(self, event_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()
            db_logger.info(f"Deleted task ID {event_id}")
            return True
        except Exception as e:
            db_logger.error(f"Error deleting event {event_id}: {e}")
            raise

    def get_events(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, start_date, end_date, priority, labels, done FROM events ORDER BY end_date ASC")
                rows = cursor.fetchall()
            return [
                TaskEvent(
                    id=row[0], name=row[1], description=row[2] or "",
                    start_date=row[3], end_date=row[4],
                    priority=row[5], labels=row[6] or "", done=bool(row[7])
                ) for row in rows
            ]
        except Exception as e:
            db_logger.error(f"Error getting events: {e}")
            return []

    def get_event(self, event_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, start_date, end_date, priority, labels, done FROM events WHERE id = ?", (event_id,))
                row = cursor.fetchone()
            if row:
                return TaskEvent(
                    id=row[0], name=row[1], description=row[2] or "",
                    start_date=row[3], end_date=row[4],
                    priority=row[5], labels=row[6] or "", done=bool(row[7])
                )
            return None
        except Exception as e:
            db_logger.error(f"Error getting event {event_id}: {e}")
            return None


class StudyDatabase:
    def __init__(self, db_path=None):
        """Initializes the database for study workspace: projects, problems, columns, records, cards."""
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_dir = os.path.join(base_dir, "db")
            os.makedirs(db_dir, exist_ok=True)
            self.db_file = os.path.join(db_dir, "study.db")
        else:
            self.db_file = db_path
            db_dir = os.path.dirname(os.path.abspath(self.db_file))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        except sqlite3.Error as e:
            db_logger.error(f"SQLite error in StudyDatabase: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        created_at INTEGER,
                        parent_project_id INTEGER,
                        FOREIGN KEY (parent_project_id) REFERENCES study_projects(id) ON DELETE SET NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problems (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        created_at INTEGER,
                        FOREIGN KEY (project_id) REFERENCES study_projects(id) ON DELETE CASCADE
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problem_columns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        order_index INTEGER DEFAULT 0,
                        FOREIGN KEY (problem_id) REFERENCES study_problems(id) ON DELETE CASCADE
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        title TEXT NOT NULL,
                        body TEXT DEFAULT '',
                        created_at INTEGER,
                        updated_at INTEGER,
                        FOREIGN KEY (project_id) REFERENCES study_projects(id) ON DELETE SET NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS study_problem_cards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        column_id INTEGER NOT NULL,
                        record_id INTEGER NOT NULL,
                        order_index INTEGER DEFAULT 0,
                        FOREIGN KEY (column_id) REFERENCES study_problem_columns(id) ON DELETE CASCADE,
                        FOREIGN KEY (record_id) REFERENCES study_records(id) ON DELETE CASCADE
                    )
                ''')
                # Optional migrations if tables already exist with older schema
                try: cursor.execute('ALTER TABLE study_problems ADD COLUMN description TEXT DEFAULT ""')
                except Exception: pass
                conn.commit()
            db_logger.info("Initialized StudyDatabase successfully.")
        except Exception as e:
            db_logger.error(f"Failed to initialize StudyDatabase: {e}")

    # --- Projects ---
    def add_study_project(self, name: str, description: str = "", parent_project_id: int = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute(
                    "INSERT INTO study_projects (name, description, created_at, parent_project_id) VALUES (?, ?, ?, ?)",
                    (name, description, now, parent_project_id)
                )
                project_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added study project: '{name}' (ID: {project_id})")
            return StudyProject(id=project_id, name=name, description=description, created_at=now, parent_project_id=parent_project_id)
        except Exception as e:
            db_logger.error(f"Error adding study project {name}: {e}")
            raise

    def get_study_projects(self, parent_project_id=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if parent_project_id is None:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id IS NULL ORDER BY id DESC")
                else:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id = ? ORDER BY id DESC", (parent_project_id,))
                rows = cursor.fetchall()
            return [StudyProject(id=row[0], name=row[1], description=row[2] or "", created_at=row[3] or 0, parent_project_id=row[4]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting study projects: {e}")
            return []

    def get_study_project(self, project_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE id = ?", (project_id,))
                row = cursor.fetchone()
            if row:
                return StudyProject(id=row[0], name=row[1], description=row[2] or "", created_at=row[3] or 0, parent_project_id=row[4])
            return None
        except Exception as e:
            db_logger.error(f"Error getting study project {project_id}: {e}")
            return None

    def get_study_project_path(self, project_id: int):
        try:
            path = []
            current_id = project_id
            with self._get_connection() as conn:
                cursor = conn.cursor()
                visited = set()
                while current_id and current_id not in visited:
                    visited.add(current_id)
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE id = ?", (current_id,))
                    row = cursor.fetchone()
                    if not row:
                        break
                    proj = StudyProject(id=row[0], name=row[1], description=row[2] or "", created_at=row[3] or 0, parent_project_id=row[4])
                    path.insert(0, proj)
                    current_id = row[4]
            return path
        except Exception as e:
            db_logger.error(f"Error getting project path for {project_id}: {e}")
            return []

    def delete_study_project(self, project_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Manual recursive cascade cleanup for child records/cards/problems
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?))", (project_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?)", (project_id,))
                cursor.execute("DELETE FROM study_problems WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM study_records WHERE project_id = ?", (project_id,))
                cursor.execute("UPDATE study_projects SET parent_project_id = NULL WHERE parent_project_id = ?", (project_id,))
                cursor.execute("DELETE FROM study_projects WHERE id = ?", (project_id,))
                conn.commit()
            db_logger.info(f"Deleted study project ID {project_id}")
            return True
        except Exception as e:
            db_logger.error(f"Error deleting study project {project_id}: {e}")
            raise

    # --- Problems ---
    def add_study_problem(self, project_id: int, title: str, description: str = ""):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute(
                    "INSERT INTO study_problems (project_id, title, description, created_at) VALUES (?, ?, ?, ?)",
                    (project_id, title, description, now)
                )
                problem_id = cursor.lastrowid
                conn.commit()
            db_logger.info(f"Added study problem: '{title}' (ID: {problem_id})")
            return StudyProblem(id=problem_id, project_id=project_id, title=title, description=description, created_at=now)
        except Exception as e:
            db_logger.error(f"Error adding study problem {title}: {e}")
            raise

    def get_study_problems(self, project_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE project_id = ? ORDER BY id DESC", (project_id,))
                rows = cursor.fetchall()
            return [StudyProblem(id=row[0], project_id=row[1], title=row[2], description=row[3] or "", created_at=row[4] or 0) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting study problems for project {project_id}: {e}")
            return []

    def get_study_problem(self, problem_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE id = ?", (problem_id,))
                row = cursor.fetchone()
            if row:
                return StudyProblem(id=row[0], project_id=row[1], title=row[2], description=row[3] or "", created_at=row[4] or 0)
            return None
        except Exception as e:
            db_logger.error(f"Error getting study problem {problem_id}: {e}")
            return None

    def update_study_problem(self, problem_id: int, title: str = None, description: str = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if title is not None and description is not None:
                    cursor.execute("UPDATE study_problems SET title = ?, description = ? WHERE id = ?", (title, description, problem_id))
                elif title is not None:
                    cursor.execute("UPDATE study_problems SET title = ? WHERE id = ?", (title, problem_id))
                elif description is not None:
                    cursor.execute("UPDATE study_problems SET description = ? WHERE id = ?", (description, problem_id))
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error updating study problem {problem_id}: {e}")
            raise

    def delete_study_problem(self, problem_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id = ?)", (problem_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE problem_id = ?", (problem_id,))
                cursor.execute("DELETE FROM study_problems WHERE id = ?", (problem_id,))
                conn.commit()
            db_logger.info(f"Deleted study problem ID {problem_id}")
            return True
        except Exception as e:
            db_logger.error(f"Error deleting study problem {problem_id}: {e}")
            raise

    # --- Columns ---
    def add_study_column(self, problem_id: int, name: str, order_index: int = 0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO study_problem_columns (problem_id, name, order_index) VALUES (?, ?, ?)", (problem_id, name, order_index))
                col_id = cursor.lastrowid
                conn.commit()
            return StudyColumn(id=col_id, problem_id=problem_id, name=name, order_index=order_index)
        except Exception as e:
            db_logger.error(f"Error adding study column: {e}")
            raise

    def get_study_columns(self, problem_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, problem_id, name, order_index FROM study_problem_columns WHERE problem_id = ? ORDER BY order_index ASC, id ASC", (problem_id,))
                rows = cursor.fetchall()
            return [StudyColumn(id=row[0], problem_id=row[1], name=row[2], order_index=row[3]) for row in rows]
        except Exception as e:
            db_logger.error(f"Error getting columns: {e}")
            return []

    def update_study_column(self, column_id: int, name: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE study_problem_columns SET name = ? WHERE id = ?", (name, column_id))
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error updating column {column_id}: {e}")
            raise

    def delete_study_column(self, column_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE column_id = ?", (column_id,))
                cursor.execute("DELETE FROM study_problem_columns WHERE id = ?", (column_id,))
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error deleting column {column_id}: {e}")
            raise

    # --- Records ---
    def add_study_record(self, title: str, body: str = "", project_id: int = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute(
                    "INSERT INTO study_records (title, body, created_at, updated_at, project_id) VALUES (?, ?, ?, ?, ?)",
                    (title, body, now, now, project_id)
                )
                rec_id = cursor.lastrowid
                conn.commit()
            return StudyRecord(id=rec_id, title=title, body=body, created_at=now, updated_at=now, project_id=project_id)
        except Exception as e:
            db_logger.error(f"Error adding record: {e}")
            raise

    def get_study_records(self, limit: int = 50, offset: int = 0, search: str = "", project_id: int = None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                params = []
                query = "SELECT id, title, body, created_at, updated_at, project_id FROM study_records WHERE 1=1"

                if project_id is not None:
                    query += " AND project_id = ?"
                    params.append(project_id)

                if search:
                    like = f"%{search}%"
                    query += " AND (title LIKE ? OR body LIKE ?)"
                    params.extend([like, like])

                query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [
                StudyRecord(
                    id=row[0], title=row[1], body=row[2] or "",
                    created_at=row[3] or 0, updated_at=row[4] or 0,
                    project_id=row[5]
                ) for row in rows
            ]
        except Exception as e:
            db_logger.error(f"Error getting records: {e}")
            return []

    def get_study_record(self, record_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, body, created_at, updated_at, project_id FROM study_records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
            if row:
                return StudyRecord(
                    id=row[0], title=row[1], body=row[2] or "",
                    created_at=row[3] or 0, updated_at=row[4] or 0,
                    project_id=row[5]
                )
            return None
        except Exception as e:
            db_logger.error(f"Error getting record {record_id}: {e}")
            return None

    def update_study_record(self, record_id: int, title: str, body: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute(
                    "UPDATE study_records SET title = ?, body = ?, updated_at = ? WHERE id = ?",
                    (title, body, now, record_id)
                )
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error updating record {record_id}: {e}")
            raise

    def delete_study_record(self, record_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE record_id = ?", (record_id,))
                cursor.execute("DELETE FROM study_records WHERE id = ?", (record_id,))
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error deleting record {record_id}: {e}")
            raise

    # --- Problem Cards ---
    def add_study_problem_card(self, column_id: int, record_id: int, order_index: int = 0):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO study_problem_cards (column_id, record_id, order_index) VALUES (?, ?, ?)",
                    (column_id, record_id, order_index)
                )
                card_id = cursor.lastrowid
                conn.commit()
            return StudyProblemCard(id=card_id, column_id=column_id, record_id=record_id, order_index=order_index)
        except Exception as e:
            db_logger.error(f"Error adding problem card: {e}")
            raise

    def get_study_problem_cards(self, column_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT c.id, c.column_id, c.record_id, c.order_index, r.title
                    FROM study_problem_cards c
                    LEFT JOIN study_records r ON c.record_id = r.id
                    WHERE c.column_id = ?
                    ORDER BY c.order_index ASC, c.id ASC
                    """,
                    (column_id,)
                )
                rows = cursor.fetchall()
            return [
                StudyProblemCard(
                    id=row[0], column_id=row[1], record_id=row[2],
                    order_index=row[3], record_title=row[4] or "Untitled Record"
                ) for row in rows
            ]
        except Exception as e:
            db_logger.error(f"Error getting problem cards for column {column_id}: {e}")
            return []

    def delete_study_problem_card(self, card_id: int):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM study_problem_cards WHERE id = ?", (card_id,))
                conn.commit()
            return True
        except Exception as e:
            db_logger.error(f"Error deleting problem card {card_id}: {e}")
            raise

    # --- Global Search (for Mentions / Autocomplete) ---
    def search_all_study_items(self, query: str = ""):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                results = []
                like_query = f"%{query}%"

                # Search Projects
                cursor.execute("SELECT id, name, parent_project_id FROM study_projects WHERE name LIKE ? LIMIT 10", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "project", "id": row[0], "name": row[1], "project_id": row[2] or row[0]})

                # Search Problems
                cursor.execute("SELECT id, title, project_id FROM study_problems WHERE title LIKE ? LIMIT 10", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "problem", "id": row[0], "name": row[1], "project_id": row[2]})

                # Search Records
                cursor.execute("SELECT id, title, project_id FROM study_records WHERE title LIKE ? LIMIT 10", (like_query,))
                for row in cursor.fetchall():
                    results.append({"type": "record", "id": row[0], "name": row[1], "project_id": row[2]})

                return results
        except Exception as e:
            db_logger.error(f"Error searching all study items: {e}")
            return []
