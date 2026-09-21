def test_page_routes(client):
    # Test Homepage
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert "LOCKED" in home_res.text

    # Test Tasks page
    tasks_res = client.get("/tasks")
    assert tasks_res.status_code == 200
    assert "Task" in tasks_res.text

    # Test Study page
    study_res = client.get("/study")
    assert study_res.status_code == 200
    assert "Study" in study_res.text


def test_removed_features_not_found(client):
    # Blocklist page should not be found or return 404
    block_page = client.get("/blocklist")
    assert block_page.status_code == 404

    # Chat page should not be found or return 404
    chat_page = client.get("/chat")
    assert chat_page.status_code == 404

    # Block API should not exist
    block_api = client.get("/api/blocks")
    assert block_api.status_code == 404

    # Chat API should not exist
    chat_api = client.get("/api/chat/sessions")
    assert chat_api.status_code == 404


def test_settings_api(client):
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200

    save_res = client.post("/api/settings", json={"theme": {"primary": "#3b82f6"}})
    assert save_res.status_code == 200

    verify_res = client.get("/api/settings")
    assert verify_res.json()["data"]["theme"]["primary"] == "#3b82f6"


def test_static_files(client):
    static_res = client.get("/static/style/variables.css")
    assert static_res.status_code == 200

