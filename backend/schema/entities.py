from dataclasses import asdict
from typing import Any
from modules.tasks.models import TaskEvent
from modules.study.models import (
    StudyProject, StudyProblem, StudyColumn,
    StudyRecord, StudyProblemCard
)
from modules.blocker.models import BlockRule


def serialize_to_dict(obj: Any):
    if isinstance(obj, list):
        return [asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in obj]
    if obj is None:
        return None
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return obj
