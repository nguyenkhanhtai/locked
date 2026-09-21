import time

def test_get_events_empty(client):
    res = client.get("/api/events")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "200 <OK>"
    assert data["data"] == []


def test_add_and_update_task(client):
    now = int(time.time())
    payload = {
        "name": "Complete DSA Homework",
        "description": "Exercise on Dijkstra's Algorithm",
        "start_date": now,
        "end_date": now + 86400,
        "priority": 4,
        "labels": "homework,graph",
        "done": False
    }

    # 1. Create task
    res = client.post("/api/events", json=payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["message"] == "Task added"
    created_id = res_data["data"]["id"]
    assert created_id > 0

    # 2. Get events
    get_res = client.get("/api/events")
    assert get_res.status_code == 200
    tasks = get_res.json()["data"]
    assert len(tasks) == 1
    assert tasks[0]["id"] == created_id
    assert tasks[0]["name"] == "Complete DSA Homework"
    assert tasks[0]["done"] is False

    # 3. Update task
    update_payload = {
        "id": created_id,
        "name": "Complete DSA Homework (Done)",
        "description": "Finished and submitted to portal",
        "start_date": now,
        "end_date": now + 86400,
        "priority": 5,
        "labels": "homework,graph,submitted",
        "done": True
    }
    update_res = client.post("/api/events", json=update_payload)
    assert update_res.status_code == 200
    assert update_res.json()["message"] == "Task updated"

    # Verify updated
    get_res2 = client.get("/api/events")
    tasks2 = get_res2.json()["data"]
    assert len(tasks2) == 1
    assert tasks2[0]["name"] == "Complete DSA Homework (Done)"
    assert tasks2[0]["done"] is True


def test_delete_task(client):
    now = int(time.time())
    add_res = client.post("/api/events", json={
        "name": "Temporary Task",
        "start_date": now,
        "end_date": now + 1000
    })
    task_id = add_res.json()["data"]["id"]

    # Delete with JSON body
    del_res = client.request("DELETE", "/api/events", json={"id": task_id})
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Task deleted"

    # Verify empty
    get_res = client.get("/api/events")
    assert get_res.json()["data"] == []

