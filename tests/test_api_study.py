def test_study_projects_api(client):
    # 1. Initially empty
    res = client.get("/api/study/projects")
    assert res.status_code == 200
    assert res.json()["data"] == []

    # 2. Create root project
    create_res = client.post("/api/study/projects", json={
        "name": "Machine Learning",
        "description": "Foundations and algorithms"
    })
    assert create_res.status_code == 200
    root_id = create_res.json()["data"]["id"]

    # 3. Create subproject
    sub_res = client.post("/api/study/projects", json={
        "name": "Neural Networks",
        "description": "Backpropagation and MLP",
        "parent_project_id": root_id
    })
    assert sub_res.status_code == 200
    sub_id = sub_res.json()["data"]["id"]

    # 4. Check project path
    path_res = client.get(f"/api/study/projects/path?id={sub_id}")
    assert path_res.status_code == 200
    path = path_res.json()["data"]
    assert len(path) == 2
    assert path[0]["id"] == root_id
    assert path[1]["id"] == sub_id

    # 5. Delete subproject
    del_res = client.request("DELETE", "/api/study/projects", json={"id": sub_id})
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Project deleted"


def test_study_problems_and_columns_api(client):
    # Create project
    proj_res = client.post("/api/study/projects", json={"name": "Algorithm Design"})
    proj_id = proj_res.json()["data"]["id"]

    # Create problem
    prob_res = client.post("/api/study/problems", json={
        "project_id": proj_id,
        "title": "Minimum Spanning Tree",
        "description": "Kruskal vs Prim"
    })
    assert prob_res.status_code == 200
    prob_id = prob_res.json()["data"]["id"]

    # Verify problem was created and default columns exist
    get_probs = client.get(f"/api/study/problems?project_id={proj_id}")
    assert get_probs.status_code == 200
    assert len(get_probs.json()["data"]) == 1
    assert get_probs.json()["data"][0]["title"] == "Minimum Spanning Tree"

    cols_res = client.get(f"/api/study/columns?problem_id={prob_id}")
    assert cols_res.status_code == 200
    cols = cols_res.json()["data"]
    assert len(cols) == 2  # Default "Knowledge" and "Question"
    knowledge_col_id = cols[0]["id"]

    # Add custom column
    add_col_res = client.post("/api/study/columns", json={
        "problem_id": prob_id,
        "name": "Greedy Choice Property",
        "order_index": 2
    })
    assert add_col_res.status_code == 200
    new_col_id = add_col_res.json()["data"]["id"]

    # Update column
    update_col_res = client.put("/api/study/columns", json={
        "id": new_col_id,
        "name": "Cut Property"
    })
    assert update_col_res.status_code == 200

    # Update problem
    update_prob = client.put("/api/study/problems", json={
        "id": prob_id,
        "title": "Minimum Spanning Tree (MST)",
        "description": "Detailed analysis"
    })
    assert update_prob.status_code == 200

    # Delete column
    del_col = client.request("DELETE", "/api/study/columns", json={"id": new_col_id})
    assert del_col.status_code == 200

    # Delete problem
    del_prob = client.request("DELETE", "/api/study/problems", json={"id": prob_id})
    assert del_prob.status_code == 200


def test_study_records_and_cards_api(client):
    proj_res = client.post("/api/study/projects", json={"name": "DSA Notes"})
    proj_id = proj_res.json()["data"]["id"]

    prob_res = client.post("/api/study/problems", json={"project_id": proj_id, "title": "Graph Traversal"})
    prob_id = prob_res.json()["data"]["id"]
    col_id = client.get(f"/api/study/columns?problem_id={prob_id}").json()["data"][0]["id"]

    # Create record
    rec_res = client.post("/api/study/records", json={
        "title": "Breadth-First Search (BFS)",
        "body": "Uses a FIFO Queue to traverse level by level.",
        "project_id": proj_id
    })
    assert rec_res.status_code == 200
    rec_id = rec_res.json()["data"]["id"]

    # Get single record
    get_rec = client.get(f"/api/study/records/single?id={rec_id}")
    assert get_rec.status_code == 200
    assert get_rec.json()["data"]["title"] == "Breadth-First Search (BFS)"

    # Update record
    update_rec = client.put("/api/study/records", json={
        "id": rec_id,
        "title": "Breadth-First Search (BFS) Algorithm",
        "body": "Uses a Queue, time complexity O(V + E)."
    })
    assert update_rec.status_code == 200

    # Add problem card linking column and record
    card_res = client.post("/api/study/problem_cards", json={
        "column_id": col_id,
        "record_id": rec_id,
        "order_index": 0
    })
    assert card_res.status_code == 200
    card_id = card_res.json()["data"]["id"]

    # Get problem cards
    cards_res = client.get(f"/api/study/problem_cards?column_id={col_id}")
    assert cards_res.status_code == 200
    cards = cards_res.json()["data"]
    assert len(cards) == 1
    assert cards[0]["record_title"] == "Breadth-First Search (BFS) Algorithm"

    # Search items
    search_res = client.get("/api/study/search?q=Queue")
    assert search_res.status_code == 200
    # or search by title
    search_res2 = client.get("/api/study/search?q=BFS")
    assert search_res2.status_code == 200
    results = search_res2.json()["data"]
    assert any(item["name"] == "Breadth-First Search (BFS) Algorithm" for item in results)

    # Delete card
    del_card = client.request("DELETE", "/api/study/problem_cards", json={"id": card_id})
    assert del_card.status_code == 200

    # Delete record
    del_rec = client.request("DELETE", "/api/study/records", json={"id": rec_id})
    assert del_rec.status_code == 200

