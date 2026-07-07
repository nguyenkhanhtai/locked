from dataclasses import dataclass, asdict
from typing import List, Optional

# --- Blocker Models ---
@dataclass
class TempBlockItem:
    url: str
    open_at: int

@dataclass
class PermBlockItem:
    url: str
    created_at: int
    unlock_at: int

@dataclass
class BlockItemsResponse:
    temporary: List[TempBlockItem]
    permanent: List[PermBlockItem]

# --- Consumption Models ---
@dataclass
class TopSiteItem:
    domain: str
    time_spent: int
    formatted_time: str

# --- Task Models ---
@dataclass
class TaskEvent:
    id: int
    name: str
    description: str
    start_date: int
from dataclasses import dataclass, asdict
from typing import List, Optional

# --- Blocker Models ---
@dataclass
class TempBlockItem:
    url: str
    open_at: int

@dataclass
class PermBlockItem:
    url: str
    created_at: int
    unlock_at: int

@dataclass
class BlockItemsResponse:
    temporary: List[TempBlockItem]
    permanent: List[PermBlockItem]

# --- Consumption Models ---
@dataclass
class TopSiteItem:
    domain: str
    time_spent: int
    formatted_time: str

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

# --- Study/Memorize Models ---
@dataclass
class StudyProject:
    id: int
    name: str
    description: str
    created_at: Optional[int] = None
    parent_project_id: Optional[int] = None

@dataclass
class FlashcardItem:
    id: int
    project_id: Optional[int]
    word: str
    meaning: str
    label: str
    other_info: str

# --- Study/Thinking Models ---
@dataclass
class ThinkingProject:
    id: int
    name: str
    problem_statement: str

@dataclass
class ThinkingItem:
    id: int
    project_id: int
    name: str
    description: str
    is_global: bool
    type: str  # 'knowledge', 'inference', or 'question'
    project_name: Optional[str] = None
    source_ids: Optional[str] = None

@dataclass
class ThinkingItemsResponse:
    knowledge: List[ThinkingItem]
    inferences: List[ThinkingItem]
    questions: List[ThinkingItem]

# --- Chat Models ---
@dataclass
class ChatSession:
    id: int
    title: str
    created_at: int
    updated_at: int
    message_count: int
    tokens_used: int

@dataclass
class ChatMessage:
    role: str
    content: str

def serialize_to_dict(obj):
    if isinstance(obj, list):
        return [asdict(item) for item in obj]
    return asdict(obj)

# --- Study/Kanban Models ---
@dataclass
class StudyProblem:
    id: int
    project_id: int
    title: str
    description: Optional[str]
    created_at: Optional[int] = None

@dataclass
class StudyRecord:
    id: int
    project_id: Optional[int]
    title: str
    body: Optional[str]
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

@dataclass
class StudyColumn:
    id: int
    problem_id: int
    name: str
    order_index: Optional[int] = 0

@dataclass
class StudyProblemCard:
    id: int
    column_id: int
    record_id: int
    order_index: int
    record_title: Optional[str] = None
