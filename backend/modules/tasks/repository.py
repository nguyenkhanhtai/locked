import sqlite3
import os
import logging
from typing import List, Optional
from core.db import DatabaseManager
from core.events import EventBus
from .models import TaskEvent

logger = logging.getLogger("modules.tasks")

def init_task_schema(conn: sqlite3.Connection):
    """Schema hook for tasks module with auto-migration."""
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
            done INTEGER DEFAULT 0,
            calendar_type TEXT DEFAULT 'task'
        )
    ''')
    cursor.execute("PRAGMA table_info(events)")
    columns = [row[1] for row in cursor.fetchall()]
    if "calendar_type" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN calendar_type TEXT DEFAULT 'task'")
    conn.commit()

# Self-register schema into DatabaseManager
DatabaseManager.register_schema(init_task_schema)


class TaskRepository:
    """Repository handling all database operations for Tasks & Schedule."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        # Ensure schema is initialized
        if db_path:
            with DatabaseManager.get_connection(db_path) as conn:
                init_task_schema(conn)

    def _conn(self):
        return DatabaseManager.get_connection(self.db_path)

    def add_event(self, name: str, description: str = "", start_date: int = 0, end_date: int = 0, priority: int = 1, labels: str = "", done: int = 0, calendar_type: str = "task") -> TaskEvent:
        cal_type = "routine" if calendar_type == "routine" else "task"
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (name, description, start_date, end_date, priority, labels, done, calendar_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, description, start_date, end_date, priority, labels, done, cal_type)
            )
            event_id = cursor.lastrowid
            conn.commit()

        task = TaskEvent(
            id=event_id, name=name, description=description,
            start_date=start_date, end_date=end_date,
            priority=priority, labels=labels, done=bool(done),
            calendar_type=cal_type
        )
        EventBus.emit("task.created", task=task)
        return task

    def update_event(self, event_id: int, name: str, description: str = "", start_date: int = 0, end_date: int = 0, priority: int = 1, labels: str = "", done: int = 0, calendar_type: str = "task") -> bool:
        cal_type = "routine" if calendar_type == "routine" else "task"
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE events SET name = ?, description = ?, start_date = ?, end_date = ?, priority = ?, labels = ?, done = ?, calendar_type = ? WHERE id = ?",
                (name, description, start_date, end_date, priority, labels, done, cal_type, event_id)
            )
            conn.commit()

        EventBus.emit("task.updated", task_id=event_id, name=name, done=bool(done), calendar_type=cal_type)
        return True

    def delete_event(self, event_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()

        EventBus.emit("task.deleted", task_id=event_id)
        return True

    def get_events(self, calendar_type: Optional[str] = None) -> List[TaskEvent]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                if calendar_type and calendar_type != "all":
                    cursor.execute(
                        "SELECT id, name, description, start_date, end_date, priority, labels, done, calendar_type FROM events WHERE calendar_type = ? ORDER BY end_date ASC",
                        (calendar_type,)
                    )
                else:
                    cursor.execute(
                        "SELECT id, name, description, start_date, end_date, priority, labels, done, calendar_type FROM events ORDER BY end_date ASC"
                    )
                rows = cursor.fetchall()
            return [
                TaskEvent(
                    id=row[0], name=row[1], description=row[2] or "",
                    start_date=row[3], end_date=row[4],
                    priority=row[5], labels=row[6] or "", done=bool(row[7]),
                    calendar_type=row[8] if len(row) > 8 and row[8] else "task"
                ) for row in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            return []

    def get_event(self, event_id: int) -> Optional[TaskEvent]:
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description, start_date, end_date, priority, labels, done, calendar_type FROM events WHERE id = ?", (event_id,))
                row = cursor.fetchone()
            if row:
                return TaskEvent(
                    id=row[0], name=row[1], description=row[2] or "",
                    start_date=row[3], end_date=row[4],
                    priority=row[5], labels=row[6] or "", done=bool(row[7]),
                    calendar_type=row[8] if len(row) > 8 and row[8] else "task"
                )
            return None
        except Exception as e:
            logger.error(f"Error fetching task {event_id}: {e}")
            return None

