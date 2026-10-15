import sqlite3
import time
import logging
from typing import List, Optional, Dict, Any
from core.db import DatabaseManager
from core.events import EventBus
from .models import (
    StudyProject, StudyProblem, StudyColumn,
    StudyRecord, StudyProblemCard
)

logger = logging.getLogger("modules.study")


def init_study_schema(conn: sqlite3.Connection):
    """Schema hook for study module."""
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
    try:
        cursor.execute('ALTER TABLE study_problems ADD COLUMN description TEXT DEFAULT ""')
    except Exception:
        pass

    cursor.execute("PRAGMA table_info(study_records)")
    record_cols = [row[1] for row in cursor.fetchall()]
    if "problem_id" not in record_cols:
        try:
            cursor.execute('ALTER TABLE study_records ADD COLUMN problem_id INTEGER REFERENCES study_problems(id) ON DELETE CASCADE')
            cursor.execute('''
                UPDATE study_records SET problem_id = (
                    SELECT c.problem_id FROM study_problem_columns c
                    JOIN study_problem_cards card ON card.column_id = c.id
                    WHERE card.record_id = study_records.id
                    LIMIT 1
                ) WHERE problem_id IS NULL AND id IN (SELECT record_id FROM study_problem_cards)
            ''')
        except Exception:
            pass

    conn.commit()


# Self-register schema into DatabaseManager
DatabaseManager.register_schema(init_study_schema)


class StudyRepository:
    """Repository handling all database operations for Study Workspace."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        if db_path:
            with DatabaseManager.get_connection(db_path) as conn:
                init_study_schema(conn)

    def _conn(self):
        return DatabaseManager.get_connection(self.db_path)

    # --- Projects ---
    def add_study_project(self, name: str, description: str = "", parent_project_id: Optional[int] = None) -> StudyProject:
        now = int(time.time())
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO study_projects (name, description, created_at, parent_project_id) VALUES (?, ?, ?, ?)",
                (name, description, now, parent_project_id)
            )
            project_id = cursor.lastrowid
            conn.commit()

        project = StudyProject(id=project_id, name=name, description=description, created_at=now, parent_project_id=parent_project_id)
        EventBus.emit("study.project.created", project=project)
        return project

    def get_study_projects(self, parent_project_id: Optional[int] = None) -> List[StudyProject]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                if parent_project_id is None:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id IS NULL ORDER BY id DESC")
                else:
                    cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE parent_project_id = ? ORDER BY id DESC", (parent_project_id,))
                rows = cursor.fetchall()
            return [StudyProject(id=row[0], name=row[1], description=row[2] or "", created_at=row[3] or 0, parent_project_id=row[4]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting study projects: {e}")
            return []

    def get_study_project(self, project_id: int) -> Optional[StudyProject]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE id = ?", (project_id,))
                row = cursor.fetchone()
            if row:
                return StudyProject(id=row[0], name=row[1], description=row[2] or "", created_at=row[3] or 0, parent_project_id=row[4])
            return None
        except Exception as e:
            logger.error(f"Error getting study project {project_id}: {e}")
            return None

    def get_study_project_path(self, project_id: int) -> List[StudyProject]:
        try:
            path = []
            current_id = project_id
            with self._conn() as conn:
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
            logger.error(f"Error getting project path for {project_id}: {e}")
            return []

    def delete_study_project(self, project_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?))", (project_id,))
            cursor.execute("DELETE FROM study_problem_columns WHERE problem_id IN (SELECT id FROM study_problems WHERE project_id = ?)", (project_id,))
            cursor.execute("DELETE FROM study_problems WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM study_records WHERE project_id = ?", (project_id,))
            cursor.execute("UPDATE study_projects SET parent_project_id = NULL WHERE parent_project_id = ?", (project_id,))
            cursor.execute("DELETE FROM study_projects WHERE id = ?", (project_id,))
            conn.commit()

        EventBus.emit("study.project.deleted", project_id=project_id)
        return True

    # --- Problems ---
    def add_study_problem(self, project_id: int, title: str, description: str = "") -> StudyProblem:
        now = int(time.time())
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO study_problems (project_id, title, description, created_at) VALUES (?, ?, ?, ?)",
                (project_id, title, description, now)
            )
            problem_id = cursor.lastrowid
            conn.commit()

        problem = StudyProblem(id=problem_id, project_id=project_id, title=title, description=description, created_at=now)
        EventBus.emit("study.problem.created", problem=problem)
        return problem

    def get_study_problems(self, project_id: int) -> List[StudyProblem]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE project_id = ? ORDER BY id DESC", (project_id,))
                rows = cursor.fetchall()
            return [StudyProblem(id=row[0], project_id=row[1], title=row[2], description=row[3] or "", created_at=row[4] or 0) for row in rows]
        except Exception as e:
            logger.error(f"Error getting study problems for project {project_id}: {e}")
            return []

    def get_study_problem(self, problem_id: int) -> Optional[StudyProblem]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE id = ?", (problem_id,))
                row = cursor.fetchone()
            if row:
                return StudyProblem(id=row[0], project_id=row[1], title=row[2], description=row[3] or "", created_at=row[4] or 0)
            return None
        except Exception as e:
            logger.error(f"Error getting study problem {problem_id}: {e}")
            return None

    def update_study_problem(self, problem_id: int, title: Optional[str] = None, description: Optional[str] = None) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            if title is not None and description is not None:
                cursor.execute("UPDATE study_problems SET title = ?, description = ? WHERE id = ?", (title, description, problem_id))
            elif title is not None:
                cursor.execute("UPDATE study_problems SET title = ? WHERE id = ?", (title, problem_id))
            elif description is not None:
                cursor.execute("UPDATE study_problems SET description = ? WHERE id = ?", (description, problem_id))
            conn.commit()
        return True

    def delete_study_problem(self, problem_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_problem_cards WHERE column_id IN (SELECT id FROM study_problem_columns WHERE problem_id = ?)", (problem_id,))
            cursor.execute("DELETE FROM study_problem_columns WHERE problem_id = ?", (problem_id,))
            cursor.execute("DELETE FROM study_problems WHERE id = ?", (problem_id,))
            conn.commit()

        EventBus.emit("study.problem.deleted", problem_id=problem_id)
        return True

    # --- Columns ---
    def add_study_column(self, problem_id: int, name: str, order_index: int = 0) -> StudyColumn:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO study_problem_columns (problem_id, name, order_index) VALUES (?, ?, ?)", (problem_id, name, order_index))
            col_id = cursor.lastrowid
            conn.commit()
        return StudyColumn(id=col_id, problem_id=problem_id, name=name, order_index=order_index)

    def get_study_columns(self, problem_id: int) -> List[StudyColumn]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, problem_id, name, order_index FROM study_problem_columns WHERE problem_id = ? ORDER BY order_index ASC, id ASC", (problem_id,))
                rows = cursor.fetchall()
            return [StudyColumn(id=row[0], problem_id=row[1], name=row[2], order_index=row[3]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting columns: {e}")
            return []

    def update_study_column(self, column_id: int, name: str) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE study_problem_columns SET name = ? WHERE id = ?", (name, column_id))
            conn.commit()
        return True

    def delete_study_column(self, column_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_problem_cards WHERE column_id = ?", (column_id,))
            cursor.execute("DELETE FROM study_problem_columns WHERE id = ?", (column_id,))
            conn.commit()
        return True

    # --- Records ---
    def add_study_record(self, title: str, body: str = "", project_id: Optional[int] = None, problem_id: Optional[int] = None) -> StudyRecord:
        now = int(time.time())
        with self._conn() as conn:
            cursor = conn.cursor()
            if problem_id is not None and project_id is None:
                cursor.execute("SELECT project_id FROM study_problems WHERE id = ?", (problem_id,))
                p_row = cursor.fetchone()
                if p_row:
                    project_id = p_row[0]

            cursor.execute(
                "INSERT INTO study_records (title, body, created_at, updated_at, project_id, problem_id) VALUES (?, ?, ?, ?, ?, ?)",
                (title, body, now, now, project_id, problem_id)
            )
            rec_id = cursor.lastrowid
            conn.commit()

        record = StudyRecord(id=rec_id, title=title, body=body, created_at=now, updated_at=now, project_id=project_id, problem_id=problem_id)
        EventBus.emit("study.record.created", record=record)
        return record

    def get_study_records(self, limit: int = 100, offset: int = 0, search: str = "", project_id: Optional[int] = None, problem_id: Optional[int] = None, unassigned_only: bool = False) -> List[StudyRecord]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                params: List[Any] = []
                query = "SELECT id, title, body, created_at, updated_at, project_id, problem_id FROM study_records WHERE 1=1"

                if problem_id is not None:
                    query += " AND problem_id = ?"
                    params.append(problem_id)
                elif unassigned_only:
                    query += " AND problem_id IS NULL"

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
                    project_id=row[5], problem_id=row[6] if len(row) > 6 else None
                ) for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting records: {e}")
            return []

    def get_study_record(self, record_id: int) -> Optional[StudyRecord]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, body, created_at, updated_at, project_id, problem_id FROM study_records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
            if row:
                return StudyRecord(
                    id=row[0], title=row[1], body=row[2] or "",
                    created_at=row[3] or 0, updated_at=row[4] or 0,
                    project_id=row[5], problem_id=row[6] if len(row) > 6 else None
                )
            return None
        except Exception as e:
            logger.error(f"Error getting record {record_id}: {e}")
            return None

    def update_study_record(self, record_id: int, title: str, body: str, problem_id: Optional[int] = None) -> bool:
        now = int(time.time())
        with self._conn() as conn:
            cursor = conn.cursor()
            if problem_id is not None:
                cursor.execute(
                    "UPDATE study_records SET title = ?, body = ?, updated_at = ?, problem_id = ? WHERE id = ?",
                    (title, body, now, problem_id, record_id)
                )
            else:
                cursor.execute(
                    "UPDATE study_records SET title = ?, body = ?, updated_at = ? WHERE id = ?",
                    (title, body, now, record_id)
                )
            conn.commit()

        EventBus.emit("study.record.updated", record_id=record_id, title=title)
        return True

    def delete_study_record(self, record_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_problem_cards WHERE record_id = ?", (record_id,))
            cursor.execute("DELETE FROM study_records WHERE id = ?", (record_id,))
            conn.commit()

        EventBus.emit("study.record.deleted", record_id=record_id)
        return True

    def get_project_hierarchy_tree(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        with self._conn() as conn:
            cursor = conn.cursor()
            # 1. Sub-projects
            projects = self.get_study_projects(parent_project_id=project_id)

            current_project = None
            if project_id:
                cursor.execute("SELECT id, name, description, created_at, parent_project_id FROM study_projects WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                if row:
                    current_project = {
                        "id": row[0], "name": row[1], "description": row[2] or "",
                        "created_at": row[3], "parent_project_id": row[4]
                    }

            # 2. Problems under this project with their notes
            problems_data = []
            if project_id:
                cursor.execute("SELECT id, project_id, title, description, created_at FROM study_problems WHERE project_id = ? ORDER BY id DESC", (project_id,))
                prob_rows = cursor.fetchall()
                for p_row in prob_rows:
                    prob_id = p_row[0]
                    cursor.execute(
                        "SELECT id, title, body, created_at, updated_at, project_id, problem_id FROM study_records WHERE problem_id = ? ORDER BY updated_at DESC",
                        (prob_id,)
                    )
                    rec_rows = cursor.fetchall()
                    notes = [
                        {"id": r[0], "title": r[1], "body": r[2] or "", "created_at": r[3], "updated_at": r[4], "project_id": r[5], "problem_id": r[6]}
                        for r in rec_rows
                    ]
                    problems_data.append({
                        "id": p_row[0], "project_id": p_row[1], "title": p_row[2],
                        "description": p_row[3] or "", "created_at": p_row[4],
                        "notes": notes
                    })

            # 3. General project notes (where problem_id is NULL)
            general_notes = []
            if project_id:
                cursor.execute(
                    "SELECT id, title, body, created_at, updated_at, project_id, problem_id FROM study_records WHERE project_id = ? AND problem_id IS NULL ORDER BY updated_at DESC",
                    (project_id,)
                )
                rec_rows = cursor.fetchall()
                general_notes = [
                    {"id": r[0], "title": r[1], "body": r[2] or "", "created_at": r[3], "updated_at": r[4], "project_id": r[5], "problem_id": r[6]}
                    for r in rec_rows
                ]

            return {
                "project": current_project,
                "subprojects": [p.to_dict() for p in projects],
                "problems": problems_data,
                "general_notes": general_notes
            }

    # --- Problem Cards ---
    def add_study_problem_card(self, column_id: int, record_id: int, order_index: int = 0) -> StudyProblemCard:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO study_problem_cards (column_id, record_id, order_index) VALUES (?, ?, ?)",
                (column_id, record_id, order_index)
            )
            card_id = cursor.lastrowid
            conn.commit()
        return StudyProblemCard(id=card_id, column_id=column_id, record_id=record_id, order_index=order_index)

    def get_study_problem_cards(self, column_id: int) -> List[StudyProblemCard]:
        try:
            with self._conn() as conn:
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
            logger.error(f"Error getting problem cards for column {column_id}: {e}")
            return []

    def delete_study_problem_card(self, card_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_problem_cards WHERE id = ?", (card_id,))
            conn.commit()
        return True

    # --- Global Search (for Mentions / Autocomplete) ---
    def search_all_study_items(self, query: str = "") -> List[Dict[str, Any]]:
        try:
            with self._conn() as conn:
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
            logger.error(f"Error searching all study items: {e}")
            return []

