import pytest
import time
from modules.session_target.models import SessionTarget
from modules.session_target.repository import SessionTargetRepository

def test_session_target_models():
    now = int(time.time())
    st = SessionTarget(
        id=1,
        title="DSA Trees & Graphs",
        duration_minutes=25,
        todos=[
            {"id": "1", "text": "Solve LC 102", "done": True},
            {"id": "2", "text": "Solve LC 200", "done": False}
        ],
        status="running",
        created_at=now,
        started_at=now - 300,  # 5 minutes ago
        elapsed_seconds=0
    )

    assert st.total_duration_seconds() == 1500
    current_elapsed = st.current_elapsed_seconds(now)
    assert current_elapsed == 300
    assert st.remaining_seconds(now) == 1200
    assert st.formatted_remaining(now) == "20:00"
    assert st.progress_percent(now) == 20.0
    stats = st.todos_stats()
    assert stats["total"] == 2
    assert stats["done"] == 1


def test_session_target_repo_crud(tmp_path):
    db_file = str(tmp_path / "test_session_repo.db")
    repo = SessionTargetRepository(db_path=db_file)

    # 1. Create session
    todos = [
        {"id": "1", "text": "Review Binary Search", "done": False},
        {"id": "2", "text": "Edge Cases with Duplicates", "done": False}
    ]
    session = repo.create_session("Binary Search Focus", 30, todos, start_immediately=False)
    assert session.id is not None
    assert session.title == "Binary Search Focus"
    assert session.duration_minutes == 30
    assert session.status == "pending"
    assert len(session.todos) == 2

    # 2. Get session
    fetched = repo.get_session(session.id)
    assert fetched is not None
    assert fetched.title == "Binary Search Focus"

    # 3. Update todos
    todos[0]["done"] = True
    repo.update_todos(session.id, todos)
    updated = repo.get_session(session.id)
    assert updated.todos[0]["done"] is True
    assert updated.todos[1]["done"] is False

    # 4. List sessions
    all_sessions = repo.get_sessions()
    assert len(all_sessions) == 1

    # 5. Delete session
    assert repo.delete_session(session.id) is True
    assert repo.get_session(session.id) is None


def test_session_target_start_pause_resume_complete(tmp_path):
    db_file = str(tmp_path / "test_session_flow.db")
    repo = SessionTargetRepository(db_path=db_file)

    session = repo.create_session("DP Knapsack", 45, start_immediately=False)
    assert session.status == "pending"

    # 1. Start session
    started = repo.start_session(session.id)
    assert started.status == "running"
    assert started.started_at > 0

    active = repo.get_active_session()
    assert active is not None
    assert active.id == session.id

    # 2. Pause session
    paused = repo.pause_session(session.id)
    assert paused.status == "paused"
    assert paused.last_paused_at > 0

    # 3. Resume session
    resumed = repo.resume_session(session.id)
    assert resumed.status == "running"
    assert resumed.last_paused_at == 0

    # 4. Complete session
    completed = repo.complete_session(session.id, note="Solved all problems successfully!")
    assert completed.status == "completed"
    assert completed.ended_at > 0
    assert completed.note == "Solved all problems successfully!"

    # Active session should now be None
    assert repo.get_active_session() is None

    # Stats
    stats = repo.get_stats()
    assert stats["total_sessions"] == 1
    assert stats["completed_sessions"] == 1


def test_api_session_target_flow(client):
    # 1. Initially no active session
    res_active = client.get("/api/sessions/active")
    assert res_active.status_code == 200
    assert res_active.json()["data"] is None

    # 2. Create session via POST /api/sessions
    create_res = client.post("/api/sessions", json={
        "title": "Evening Algorithm Study",
        "duration_minutes": 50,
        "todos": [
            {"id": "t1", "text": "LeetCode 33", "done": False},
            {"id": "t2", "text": "LeetCode 81", "done": False}
        ],
        "start_immediately": True
    })
    assert create_res.status_code == 200
    session_data = create_res.json()["data"]
    s_id = session_data["id"]
    assert session_data["status"] == "running"

    # 3. Check active session
    res_active2 = client.get("/api/sessions/active")
    assert res_active2.status_code == 200
    assert res_active2.json()["data"]["id"] == s_id
    assert res_active2.json()["data"]["status"] == "running"

    # 4. Pause session
    pause_res = client.post("/api/sessions/pause", json={"id": s_id})
    assert pause_res.status_code == 200
    assert pause_res.json()["data"]["status"] == "paused"

    # 5. Resume session
    resume_res = client.post("/api/sessions/resume", json={"id": s_id})
    assert resume_res.status_code == 200
    assert resume_res.json()["data"]["status"] == "running"

    # 6. Update todos
    new_todos = [
        {"id": "t1", "text": "LeetCode 33", "done": True},
        {"id": "t2", "text": "LeetCode 81", "done": True}
    ]
    todos_res = client.put("/api/sessions/todos", json={"id": s_id, "todos": new_todos})
    assert todos_res.status_code == 200
    assert todos_res.json()["data"]["todos_done"] == 2

    # 7. Complete session
    complete_res = client.post("/api/sessions/complete", json={"id": s_id, "note": "Finished fast"})
    assert complete_res.status_code == 200
    assert complete_res.json()["data"]["status"] == "completed"

    # 8. Check stats
    stats_res = client.get("/api/sessions/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()["data"]
    assert stats["completed_sessions"] == 1
    assert stats["done_todos"] == 2
    assert stats["todo_completion_rate"] == 100.0

    # 9. View page responds 200 OK
    page_res = client.get("/session-target")
    assert page_res.status_code == 200
    assert "Session Target" in page_res.text


def test_scheduled_session_flow(tmp_path):
    db_file = str(tmp_path / "test_scheduled.db")
    repo = SessionTargetRepository(db_path=db_file)

    now = int(time.time())
    future_start = now + 3600  # 1 hour in future
    session = repo.create_session(
        title="Future DP Session",
        duration_minutes=45,
        todos=[{"id": "1", "text": "LIS Problem", "done": False}],
        scheduled_start_at=future_start
    )
    assert session.status == "scheduled"
    assert session.scheduled_start_at == future_start
    assert session.scheduled_end_at == future_start + 45 * 60
    assert not session.is_active_at(now)
    # Becomes active at scheduled start
    assert session.is_active_at(future_start + 60)
    # Not active after scheduled end
    assert not session.is_active_at(future_start + 45 * 60 + 1)


def test_concurrent_sessions_merged_targets(tmp_path):
    db_file = str(tmp_path / "test_merged.db")
    repo = SessionTargetRepository(db_path=db_file)

    now = int(time.time())
    # Session 1: Running
    s1 = repo.create_session(
        title="Session 1 - Trees",
        duration_minutes=30,
        todos=[
            {"id": "s1_t1", "text": "LC 102", "done": True},
            {"id": "s1_t2", "text": "LC 104", "done": False}
        ],
        start_immediately=True
    )

    # Session 2: Concurrent running
    s2 = repo.create_session(
        title="Session 2 - Math",
        duration_minutes=20,
        todos=[
            {"id": "s2_t1", "text": "Combinatorics", "done": False}
        ],
        start_immediately=True,
        pause_others=False
    )

    active_sessions = repo.get_active_sessions(now)
    assert len(active_sessions) == 2

    merged = repo.get_merged_active_targets(now)
    assert merged is not None
    assert merged["is_merged"] is True
    assert merged["active_count"] == 2
    assert len(merged["merged_todos"]) == 3
    assert merged["done_todos"] == 1
    assert merged["total_todos"] == 3

    # Toggle a todo in Session 2
    repo.toggle_todo(s2.id, "s2_t1", done=True)
    merged_after = repo.get_merged_active_targets(now)
    assert merged_after["done_todos"] == 2


def test_api_merged_sessions_and_toggle(client):
    # 1. Create two concurrent running sessions
    res1 = client.post("/api/sessions", json={
        "title": "Module A",
        "duration_minutes": 25,
        "todos": [{"id": "a1", "text": "Task A1", "done": False}],
        "start_immediately": True
    })
    s1_id = res1.json()["data"]["id"]

    res2 = client.post("/api/sessions", json={
        "title": "Module B",
        "duration_minutes": 30,
        "todos": [{"id": "b1", "text": "Task B1", "done": False}],
        "start_immediately": True,
        "pause_others": False
    })
    s2_id = res2.json()["data"]["id"]

    # 2. Check active merged endpoint
    active_res = client.get("/api/sessions/active")
    assert active_res.status_code == 200
    active_data = active_res.json()["data"]
    assert active_data["is_merged"] is True
    assert active_data["active_count"] == 2
    assert len(active_data["todos"]) == 2
    assert active_data["started_at"] > 0
    assert "elapsed_seconds" in active_data
    assert "current_elapsed_seconds" in active_data
    assert "remaining_seconds" in active_data

    # 3. Toggle todo via API
    toggle_res = client.post("/api/sessions/todo/toggle", json={
        "session_id": s2_id,
        "todo_id": "b1",
        "done": True
    })
    assert toggle_res.status_code == 200
    updated_merged = toggle_res.json()["data"]
    assert updated_merged["done_todos"] == 1
    assert updated_merged["started_at"] > 0

    # 4. Abandon all active merged sessions
    abandon_res = client.post("/api/sessions/abandon", json={"abandon_all": True})
    assert abandon_res.status_code == 200
    assert abandon_res.json()["message"] == "All active sessions abandoned"

    # Verify no more active sessions
    res_after = client.get("/api/sessions/active")
    assert res_after.status_code == 200
    assert res_after.json()["data"] is None


def test_api_session_abandon_single(client):
    res = client.post("/api/sessions", json={
        "title": "Single session to abandon",
        "duration_minutes": 25,
        "start_immediately": True
    })
    s_id = res.json()["data"]["id"]

    abandon_res = client.post("/api/sessions/abandon", json={"id": s_id})
    assert abandon_res.status_code == 200
    assert abandon_res.json()["data"]["status"] == "abandoned"


