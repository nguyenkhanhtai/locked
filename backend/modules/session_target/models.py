from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
import time
import json

@dataclass
class SessionTodo:
    id: str
    text: str
    done: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class SessionTarget:
    id: Optional[int]
    title: str
    duration_minutes: int
    todos: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending, running, paused, completed, abandoned
    created_at: int = field(default_factory=lambda: int(time.time()))
    started_at: int = 0
    ended_at: int = 0
    elapsed_seconds: int = 0
    last_paused_at: int = 0
    note: str = ""
    scheduled_start_at: int = 0
    scheduled_end_at: int = 0

    def total_duration_seconds(self) -> int:
        return max(1, self.duration_minutes * 60)

    def current_elapsed_seconds(self, current_time: Optional[int] = None) -> int:
        now = current_time if current_time is not None else int(time.time())
        if self.status == "running":
            if self.started_at > 0:
                return self.elapsed_seconds + max(0, now - self.started_at)
            elif self.scheduled_start_at > 0 and self.scheduled_start_at <= now:
                return min(self.total_duration_seconds(), max(0, now - self.scheduled_start_at))
        elif self.status == "scheduled" and self.scheduled_start_at > 0 and self.scheduled_start_at <= now:
            return min(self.total_duration_seconds(), max(0, now - self.scheduled_start_at))
        return self.elapsed_seconds

    def remaining_seconds(self, current_time: Optional[int] = None) -> int:
        total = self.total_duration_seconds()
        elapsed = self.current_elapsed_seconds(current_time)
        return max(0, total - elapsed)

    def formatted_remaining(self, current_time: Optional[int] = None) -> str:
        rem = self.remaining_seconds(current_time)
        hours = rem // 3600
        minutes = (rem % 3600) // 60
        seconds = rem % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def progress_percent(self, current_time: Optional[int] = None) -> float:
        total = self.total_duration_seconds()
        elapsed = self.current_elapsed_seconds(current_time)
        return min(100.0, round((elapsed / total) * 100, 1))

    def is_active_at(self, current_time: Optional[int] = None) -> bool:
        now = current_time if current_time is not None else int(time.time())
        if self.status in ("completed", "abandoned"):
            return False
        if self.status in ("running", "paused"):
            return True
        if self.scheduled_start_at > 0 and self.scheduled_start_at <= now < self.scheduled_end_at:
            return True
        return False

    def todos_stats(self) -> Dict[str, int]:
        total = len(self.todos)
        done = sum(1 for t in self.todos if t.get("done"))
        return {"total": total, "done": done}

    def to_dict(self, current_time: Optional[int] = None) -> Dict[str, Any]:
        data = asdict(self)
        stats = self.todos_stats()
        data["current_elapsed_seconds"] = self.current_elapsed_seconds(current_time)
        data["remaining_seconds"] = self.remaining_seconds(current_time)
        data["formatted_remaining"] = self.formatted_remaining(current_time)
        data["progress_percent"] = self.progress_percent(current_time)
        data["todos_total"] = stats["total"]
        data["todos_done"] = stats["done"]
        data["is_scheduled"] = self.scheduled_start_at > 0
        data["is_active"] = self.is_active_at(current_time)
        data["scheduled_start_formatted"] = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self.scheduled_start_at))
            if self.scheduled_start_at > 0 else ""
        )
        data["scheduled_end_formatted"] = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self.scheduled_end_at))
            if self.scheduled_end_at > 0 else ""
        )
        return data

