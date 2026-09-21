import os
import time
from database import TaskDatabase, StudyDatabase


# ==========================================
# TaskDatabase Unit Tests
# ==========================================
def test_task_db_initialization(tmp_path):
    sub_dir = tmp_path / "deep" / "nested" / "dir"
    db_file = str(sub_dir / "tasks.db")
    assert not os.path.exists(db_file)
    db = TaskDatabase(db_path=db_file)
    assert os.path.exists(db_file)
    events = db.get_events()
    assert events == []


def test_task_db_crud(task_db):
    now = int(time.time())
    # 1. Add event
    task = task_db.add_event(
        name="Study DSA",
        description="Review AVL Trees and Min-Heap",
        start_date=now,
        end_date=now + 3600,
        priority=4,
        labels="study,dsa",
        done=0
    )
    assert task.id is not None
    assert task.name == "Study DSA"
    assert task.priority == 4
    assert task.done is False

    # 2. Get event
    fetched = task_db.get_event(task.id)
    assert fetched is not None
    assert fetched.name == "Study DSA"
    assert fetched.description == "Review AVL Trees and Min-Heap"

    # 3. Update event
    task_db.update_event(
        event_id=task.id,
        name="Master DSA",
        description="AVL Trees, Graphs, Greedy",
        start_date=now,
        end_date=now + 7200,
        priority=5,
        labels="study,dsa,urgent",
        done=1
    )
    updated = task_db.get_event(task.id)
    assert updated.name == "Master DSA"
    assert updated.priority == 5
    assert updated.done is True

    # 4. Get all events
    events = task_db.get_events()
    assert len(events) == 1
    assert events[0].id == task.id

    # 5. Delete event
    task_db.delete_event(task.id)
    assert task_db.get_event(task.id) is None
    assert len(task_db.get_events()) == 0


def test_task_db_sorting(task_db):
    now = int(time.time())
    task_db.add_event("Task 3 (Later)", "", now, now + 5000, 1, "", 0)
    task_db.add_event("Task 1 (Soonest)", "", now, now + 1000, 1, "", 0)
    task_db.add_event("Task 2 (Middle)", "", now, now + 3000, 1, "", 0)

    events = task_db.get_events()
    assert len(events) == 3
    assert events[0].name == "Task 1 (Soonest)"
    assert events[1].name == "Task 2 (Middle)"
    assert events[2].name == "Task 3 (Later)"


# ==========================================
# StudyDatabase Unit Tests
# ==========================================
def test_study_db_initialization(tmp_path):
    sub_dir = tmp_path / "custom" / "path"
    db_file = str(sub_dir / "study.db")
    assert not os.path.exists(db_file)
    db = StudyDatabase(db_path=db_file)
    assert os.path.exists(db_file)
    assert db.get_study_projects() == []


def test_study_db_project_hierarchy_and_path(study_db):
    # Root project
    root = study_db.add_study_project(name="Computer Science", description="Degree studies")
    assert root.id is not None
    assert root.parent_project_id is None

    # Sub-project level 1
    sub1 = study_db.add_study_project(name="DSA", description="Algorithms", parent_project_id=root.id)
    assert sub1.parent_project_id == root.id

    # Sub-project level 2
    sub2 = study_db.add_study_project(name="Trees", description="Binary Trees", parent_project_id=sub1.id)
    assert sub2.parent_project_id == sub1.id

    # Test get_study_project_path
    path = study_db.get_study_project_path(sub2.id)
    assert len(path) == 3
    assert path[0].id == root.id
    assert path[0].name == "Computer Science"
    assert path[1].id == sub1.id
    assert path[1].name == "DSA"
    assert path[2].id == sub2.id
    assert path[2].name == "Trees"

    # Test filtering by parent_project_id
    root_projects = study_db.get_study_projects(parent_project_id=None)
    assert len(root_projects) == 1
    assert root_projects[0].id == root.id

    sub_projects = study_db.get_study_projects(parent_project_id=root.id)
    assert len(sub_projects) == 1
    assert sub_projects[0].id == sub1.id


def test_study_db_problem_and_columns(study_db):
    proj = study_db.add_study_project(name="Algorithms")

    # Add problem
    prob = study_db.add_study_problem(proj.id, "Interval Partitioning", "Schedule rooms using min-heap")
    assert prob.id is not None
    assert prob.title == "Interval Partitioning"

    # Add columns
    col1 = study_db.add_study_column(prob.id, "Knowledge", order_index=0)
    col2 = study_db.add_study_column(prob.id, "Inference", order_index=1)
    col3 = study_db.add_study_column(prob.id, "Questions", order_index=2)

    cols = study_db.get_study_columns(prob.id)
    assert len(cols) == 3
    assert [c.name for c in cols] == ["Knowledge", "Inference", "Questions"]

    # Update column
    study_db.update_study_column(col2.id, "Deductions")
    updated_cols = study_db.get_study_columns(prob.id)
    assert updated_cols[1].name == "Deductions"

    # Delete column
    study_db.delete_study_column(col3.id)
    assert len(study_db.get_study_columns(prob.id)) == 2


def test_study_db_records_and_cards(study_db):
    proj = study_db.add_study_project(name="Math")
    prob = study_db.add_study_problem(proj.id, "Calculus Problem")
    col = study_db.add_study_column(prob.id, "Theorems", 0)

    # 1. Add record
    rec = study_db.add_study_record(title="Taylor Series", body="f(x) = sum f^(n)(a)/n! (x-a)^n", project_id=proj.id)
    assert rec.id is not None
    assert rec.title == "Taylor Series"

    # 2. Get records
    records = study_db.get_study_records(project_id=proj.id)
    assert len(records) == 1
    assert records[0].id == rec.id

    # 3. Add problem card linking column and record
    card = study_db.add_study_problem_card(column_id=col.id, record_id=rec.id, order_index=0)
    assert card.id is not None
    assert card.column_id == col.id
    assert card.record_id == rec.id

    # 4. Get problem cards (hydrated with record title)
    cards = study_db.get_study_problem_cards(col.id)
    assert len(cards) == 1
    assert cards[0].record_title == "Taylor Series"

    # 5. Global search
    search_results = study_db.search_all_study_items("Taylor")
    assert len(search_results) >= 1
    assert search_results[0]["type"] == "record"
    assert search_results[0]["name"] == "Taylor Series"

    # 6. Delete card
    study_db.delete_study_problem_card(card.id)
    assert len(study_db.get_study_problem_cards(col.id)) == 0

    # Record still exists
    assert study_db.get_study_record(rec.id) is not None

    # Delete record
    study_db.delete_study_record(rec.id)
    assert study_db.get_study_record(rec.id) is None


def test_study_db_cascade_deletion(study_db):
    proj = study_db.add_study_project(name="Cascade Test")
    prob = study_db.add_study_problem(proj.id, "Cascade Problem")
    col = study_db.add_study_column(prob.id, "Cascade Column")
    rec = study_db.add_study_record("Cascade Record", "desc", project_id=proj.id)
    study_db.add_study_problem_card(col.id, rec.id)

    # Delete project
    study_db.delete_study_project(proj.id)

    # Check that child problem, column, card, and record were deleted
    assert study_db.get_study_project(proj.id) is None
    assert len(study_db.get_study_problems(proj.id)) == 0
    assert len(study_db.get_study_columns(prob.id)) == 0
    assert len(study_db.get_study_problem_cards(col.id)) == 0
    assert study_db.get_study_record(rec.id) is None

