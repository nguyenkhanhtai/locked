import sqlite3
import time
import json
import logging
from typing import List, Optional, Dict, Any

from core.db import DatabaseManager
from core.events import EventBus
from .models import SessionTarget

logger = logging.getLogger("modules.session_target")

def init_session_target_schema(conn: sqlite3.Connection):
    """Schema hook for Session Target module with auto-migration."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            todos TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            started_at INTEGER DEFAULT 0,
            ended_at INTEGER DEFAULT 0,
            elapsed_seconds INTEGER DEFAULT 0,
            last_paused_at INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            scheduled_start_at INTEGER DEFAULT 0,
            scheduled_end_at INTEGER DEFAULT 0
        )
    ''')
    # Auto-migration check
    cursor.execute("PRAGMA table_info(session_targets)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if "scheduled_start_at" not in existing_cols:
        cursor.execute("ALTER TABLE session_targets ADD COLUMN scheduled_start_at INTEGER DEFAULT 0")
    if "scheduled_end_at" not in existing_cols:
        cursor.execute("ALTER TABLE session_targets ADD COLUMN scheduled_end_at INTEGER DEFAULT 0")
    conn.commit()

# Self-register schema into DatabaseManager
DatabaseManager.register_schema(init_session_target_schema)


class SessionTargetRepository:
    """Repository handling database operations for Session Targets."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        if db_path:
            with DatabaseManager.get_connection(db_path) as conn:
                init_session_target_schema(conn)

    def _conn(self):
        return DatabaseManager.get_connection(self.db_path)

    def _row_to_model(self, row) -> SessionTarget:
        try:
            todos_list = json.loads(row[3]) if row[3] else []
        except Exception:
            todos_list = []

        return SessionTarget(
            id=row[0],
            title=row[1],
            duration_minutes=row[2],
            todos=todos_list,
            status=row[4],
            created_at=row[5],
            started_at=row[6] or 0,
            ended_at=row[7] or 0,
            elapsed_seconds=row[8] or 0,
            last_paused_at=row[9] or 0,
            note=row[10] or "",
            scheduled_start_at=row[11] if len(row) > 11 and row[11] is not None else 0,
            scheduled_end_at=row[12] if len(row) > 12 and row[12] is not None else 0
        )

    def create_session(
        self,
        title: str,
        duration_minutes: int,
        todos: Optional[List[Dict[str, Any]]] = None,
        start_immediately: bool = False,
        scheduled_start_at: int = 0,
        pause_others: bool = False
    ) -> SessionTarget:
        now = int(time.time())
        duration_mins = max(1, min(720, int(duration_minutes)))  # between 1 min and 12 hours
        todos_data = todos if todos is not None else []
        todos_json = json.dumps(todos_data, ensure_ascii=False)

        sched_start = int(scheduled_start_at) if scheduled_start_at else 0
        sched_end = 0

        if sched_start > 0:
            sched_end = sched_start + duration_mins * 60
            if sched_start <= now < sched_end:
                status = "running"
                started_at = sched_start
            elif sched_start > now:
                status = "scheduled"
                started_at = 0
            else:
                status = "pending"
                started_at = 0
        else:
            status = "running" if start_immediately else "pending"
            started_at = now if start_immediately else 0

        # If requested to pause others when starting immediately
        if (start_immediately or status == "running") and pause_others:
            self._pause_all_running(now)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO session_targets 
                (title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, '', ?, ?)
                ''',
                (title, duration_mins, todos_json, status, now, started_at, sched_start, sched_end)
            )
            session_id = cursor.lastrowid
            conn.commit()

        session = SessionTarget(
            id=session_id,
            title=title,
            duration_minutes=duration_mins,
            todos=todos_data,
            status=status,
            created_at=now,
            started_at=started_at,
            scheduled_start_at=sched_start,
            scheduled_end_at=sched_end
        )
        EventBus.emit("session.created", session=session)
        if status == "running":
            EventBus.emit("session.started", session=session)
        return session

    def _pause_all_running(self, current_time: int):
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, started_at, elapsed_seconds FROM session_targets WHERE status = 'running'")
            running_sessions = cursor.fetchall()
            for s_id, s_started, s_elapsed in running_sessions:
                additional_elapsed = max(0, current_time - s_started)
                total_elapsed = s_elapsed + additional_elapsed
                cursor.execute(
                    "UPDATE session_targets SET status = 'paused', elapsed_seconds = ?, last_paused_at = ? WHERE id = ?",
                    (total_elapsed, current_time, s_id)
                )
            conn.commit()

    def get_session(self, session_id: int) -> Optional[SessionTarget]:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at
                FROM session_targets WHERE id = ?
                ''',
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_active_sessions(self, current_time: Optional[int] = None) -> List[SessionTarget]:
        """Returns all sessions that are currently active (running, paused, or scheduled sessions within their window)."""
        now = current_time if current_time is not None else int(time.time())
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at
                FROM session_targets 
                WHERE status IN ('running', 'paused')
                   OR (scheduled_start_at > 0 AND scheduled_start_at <= ? AND scheduled_end_at > ? AND status NOT IN ('completed', 'abandoned'))
                ORDER BY CASE WHEN status = 'running' THEN 0 WHEN status = 'scheduled' THEN 1 ELSE 2 END, started_at DESC, id DESC
                ''',
                (now, now)
            )
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    def get_active_session(self) -> Optional[SessionTarget]:
        """Returns the primary active session (running, scheduled in progress, or paused)."""
        actives = self.get_active_sessions()
        return actives[0] if actives else None

    def get_merged_active_targets(self, current_time: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Merges all currently active sessions and their goals/todos into a unified structure.
        Provides both multi-session metadata and top-level backward-compatible fields.
        """
        now = current_time if current_time is not None else int(time.time())
        active_sessions = self.get_active_sessions(now)
        if not active_sessions:
            return None

        # Prioritize running sessions, else first active
        running = [s for s in active_sessions if s.status == "running"]
        primary = running[0] if running else active_sessions[0]

        merged_todos: List[Dict[str, Any]] = []
        for s in active_sessions:
            for idx, t in enumerate(s.todos):
                todo_id = str(t.get("id") or idx)
                merged_todos.append({
                    "id": todo_id,
                    "session_id": s.id,
                    "session_title": s.title,
                    "text": t.get("text", ""),
                    "done": bool(t.get("done", False))
                })

        total_todos = len(merged_todos)
        done_todos = sum(1 for t in merged_todos if t["done"])

        # Determine overall status
        if any(s.status == "running" for s in active_sessions):
            overall_status = "running"
        elif any(s.status == "paused" for s in active_sessions):
            overall_status = "paused"
        else:
            overall_status = primary.status

        is_merged = len(active_sessions) > 1

        title_display = (
            f"Merged: {primary.title} (+{len(active_sessions)-1} more)"
            if is_merged else primary.title
        )

        effective_started_at = primary.started_at if primary.started_at > 0 else (
            primary.scheduled_start_at if primary.scheduled_start_at > 0 and primary.scheduled_start_at <= now else 0
        )

        return {
            "is_merged": is_merged,
            "active_count": len(active_sessions),
            "primary_session": primary.to_dict(now),
            "active_sessions": [s.to_dict(now) for s in active_sessions],
            "merged_todos": merged_todos,
            "total_todos": total_todos,
            "done_todos": done_todos,
            "overall_status": overall_status,
            # Top-level fields compatible with SessionTarget.to_dict()
            "id": primary.id,
            "title": title_display,
            "duration_minutes": primary.duration_minutes,
            "status": overall_status,
            "started_at": effective_started_at,
            "last_paused_at": primary.last_paused_at,
            "elapsed_seconds": primary.elapsed_seconds,
            "current_elapsed_seconds": primary.current_elapsed_seconds(now),
            "remaining_seconds": primary.remaining_seconds(now),
            "formatted_remaining": primary.formatted_remaining(now),
            "progress_percent": primary.progress_percent(now),
            "todos": merged_todos,
            "todos_total": total_todos,
            "todos_done": done_todos,
            "scheduled_start_at": primary.scheduled_start_at,
            "scheduled_end_at": primary.scheduled_end_at,
            "is_scheduled": primary.scheduled_start_at > 0,
            "scheduled_start_formatted": primary.to_dict(now).get("scheduled_start_formatted", ""),
            "scheduled_end_formatted": primary.to_dict(now).get("scheduled_end_formatted", "")
        }

    def get_sessions(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[SessionTarget]:
        with self._conn() as conn:
            cursor = conn.cursor()
            if status == "pending":
                # Return both pending and scheduled in the planned view
                cursor.execute(
                    '''
                    SELECT id, title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at
                    FROM session_targets WHERE status IN ('pending', 'scheduled') ORDER BY CASE WHEN scheduled_start_at > 0 THEN scheduled_start_at ELSE 9999999999 END ASC, id DESC LIMIT ? OFFSET ?
                    ''',
                    (limit, offset)
                )
            elif status:
                cursor.execute(
                    '''
                    SELECT id, title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at
                    FROM session_targets WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?
                    ''',
                    (status, limit, offset)
                )
            else:
                cursor.execute(
                    '''
                    SELECT id, title, duration_minutes, todos, status, created_at, started_at, ended_at, elapsed_seconds, last_paused_at, note, scheduled_start_at, scheduled_end_at
                    FROM session_targets ORDER BY id DESC LIMIT ? OFFSET ?
                    ''',
                    (limit, offset)
                )
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    def start_session(self, session_id: int, pause_others: bool = False) -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session:
            return None

        now = int(time.time())
        if pause_others:
            self._pause_all_running(now)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET status = 'running', started_at = ?, last_paused_at = 0 WHERE id = ?",
                (now, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.started", session=updated)
        return updated

    def pause_session(self, session_id: int) -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session or session.status != "running":
            return session

        now = int(time.time())
        add_elapsed = max(0, now - session.started_at)
        total_elapsed = session.elapsed_seconds + add_elapsed

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET status = 'paused', elapsed_seconds = ?, last_paused_at = ? WHERE id = ?",
                (total_elapsed, now, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.paused", session=updated)
        return updated

    def resume_session(self, session_id: int, pause_others: bool = False) -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session or session.status != "paused":
            return session

        now = int(time.time())
        if pause_others:
            self._pause_all_running(now)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET status = 'running', started_at = ?, last_paused_at = 0 WHERE id = ?",
                (now, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.resumed", session=updated)
        return updated

    def toggle_todo(self, session_id: int, todo_id: str, done: Optional[bool] = None) -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session:
            return None
        todos = list(session.todos)
        updated_any = False
        for t in todos:
            if str(t.get("id")) == str(todo_id):
                t["done"] = not t.get("done", False) if done is None else bool(done)
                updated_any = True
                break
        if updated_any:
            return self.update_todos(session_id, todos)
        return session

    def complete_session(self, session_id: int, note: str = "") -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session:
            return None

        now = int(time.time())
        total_elapsed = session.current_elapsed_seconds(now)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET status = 'completed', ended_at = ?, elapsed_seconds = ?, note = ? WHERE id = ?",
                (now, total_elapsed, note, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.completed", session=updated)
        return updated

    def abandon_session(self, session_id: int) -> Optional[SessionTarget]:
        session = self.get_session(session_id)
        if not session:
            return None

        now = int(time.time())
        total_elapsed = session.current_elapsed_seconds(now)

        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET status = 'abandoned', ended_at = ?, elapsed_seconds = ? WHERE id = ?",
                (now, total_elapsed, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.abandoned", session=updated)
        return updated

    def update_todos(self, session_id: int, todos: List[Dict[str, Any]]) -> Optional[SessionTarget]:
        todos_json = json.dumps(todos, ensure_ascii=False)
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session_targets SET todos = ? WHERE id = ?",
                (todos_json, session_id)
            )
            conn.commit()

        updated = self.get_session(session_id)
        EventBus.emit("session.todos.updated", session=updated)
        return updated

    def delete_session(self, session_id: int) -> bool:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_targets WHERE id = ?", (session_id,))
            conn.commit()

        EventBus.emit("session.deleted", session_id=session_id)
        return True

    def get_stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(elapsed_seconds) FROM session_targets WHERE status = 'completed'")
            row = cursor.fetchone()
            completed_count = row[0] or 0
            total_focus_seconds = row[1] or 0

            cursor.execute("SELECT COUNT(*) FROM session_targets")
            total_count = cursor.fetchone()[0] or 0

            # Calculate todos done across all sessions
            cursor.execute("SELECT todos FROM session_targets")
            all_todos_rows = cursor.fetchall()
            total_todos = 0
            done_todos = 0
            for r in all_todos_rows:
                if r[0]:
                    try:
                        tds = json.loads(r[0])
                        for t in tds:
                            total_todos += 1
                            if t.get("done"):
                                done_todos += 1
                    except Exception:
                        pass

            # Today's focus time
            now = int(time.time())
            start_of_today = now - (now % 86400)
            cursor.execute(
                "SELECT SUM(elapsed_seconds), COUNT(*) FROM session_targets WHERE status = 'completed' AND ended_at >= ?",
                (start_of_today,)
            )
            today_row = cursor.fetchone()
            today_focus_seconds = today_row[0] or 0
            today_completed_count = today_row[1] or 0

        todo_rate = round((done_todos / total_todos * 100), 1) if total_todos > 0 else 100.0

        return {
            "total_sessions": total_count,
            "completed_sessions": completed_count,
            "total_focus_seconds": total_focus_seconds,
            "total_focus_formatted": self._format_seconds(total_focus_seconds),
            "today_focus_seconds": today_focus_seconds,
            "today_focus_formatted": self._format_seconds(today_focus_seconds),
            "today_completed_sessions": today_completed_count,
            "total_todos": total_todos,
            "done_todos": done_todos,
            "todo_completion_rate": todo_rate
        }

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

