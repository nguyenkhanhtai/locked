from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class StudyProject:
    id: int
    name: str
    description: str
    created_at: Optional[int] = None
    parent_project_id: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class StudyProblem:
    id: int
    project_id: int
    title: str
    description: Optional[str] = ""
    created_at: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class StudyColumn:
    id: int
    problem_id: int
    name: str
    order_index: Optional[int] = 0

    def to_dict(self):
        return asdict(self)

@dataclass
class StudyRecord:
    id: int
    title: str
    project_id: Optional[int] = None
    problem_id: Optional[int] = None
    body: Optional[str] = ""
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class StudyProblemCard:
    id: int
    column_id: int
    record_id: int
    order_index: int = 0
    record_title: Optional[str] = None

    def to_dict(self):
        return asdict(self)

