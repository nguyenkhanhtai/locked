from dataclasses import dataclass, asdict

@dataclass
class TaskEvent:
    id: int
    name: str
    description: str
    start_date: int
    end_date: int
    priority: int
    labels: str
    done: bool
    calendar_type: str = "task"

    def to_dict(self):
        return asdict(self)

