from dataclasses import dataclass, asdict
from typing import List, Optional

# --- Task Models ---
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

# --- Study/Workspace Models ---
@dataclass
class StudyProject:
    id: int
    name: str
    description: str
    created_at: Optional[int] = None
    parent_project_id: Optional[int] = None

@dataclass
class StudyProblem:
    id: int
    project_id: int
    title: str
    description: Optional[str] = ""
    created_at: Optional[int] = None

@dataclass
class StudyColumn:
    id: int
    problem_id: int
    name: str
    order_index: Optional[int] = 0

@dataclass
class StudyRecord:
    id: int
    title: str
    project_id: Optional[int] = None
    body: Optional[str] = ""
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

@dataclass
class StudyProblemCard:
    id: int
    column_id: int
    record_id: int
    order_index: int = 0
    record_title: Optional[str] = None

def serialize_to_dict(obj):
    if isinstance(obj, list):
        return [asdict(item) for item in obj]
    if obj is None:
        return None
    return asdict(obj)
