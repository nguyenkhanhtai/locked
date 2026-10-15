from dataclasses import dataclass, asdict
from typing import Optional
import time

@dataclass
class BlockRule:
    id: Optional[int]
    url_pattern: str
    domain: str
    match_type: str          # 'domain' or 'exact'
    reason: str
    duration_minutes: int    # 1 to 360 (max 6 hours)
    created_at: int          # unix timestamp
    blocked_until: int       # unix timestamp
    is_active: int           # 1 if active, 0 if expired

    def remaining_seconds(self, current_time: Optional[int] = None) -> int:
        now = current_time if current_time is not None else int(time.time())
        return max(0, self.blocked_until - now)

    def formatted_remaining(self, current_time: Optional[int] = None) -> str:
        secs = self.remaining_seconds(current_time)
        if secs <= 0:
            return "00:00:00"
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def to_dict(self, current_time: Optional[int] = None):
        data = asdict(self)
        data["remaining_seconds"] = self.remaining_seconds(current_time)
        data["formatted_remaining"] = self.formatted_remaining(current_time)
        data["is_locked"] = self.remaining_seconds(current_time) > 0
        return data

