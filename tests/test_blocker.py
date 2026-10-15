import time
import pytest
from modules.blocker.repository import HardLockActiveError, normalize_target


def test_normalize_target():
    pattern, domain = normalize_target("https://www.youtube.com/shorts?v=123")
    assert domain == "youtube.com"
    assert pattern == "youtube.com/shorts?v=123"

    pattern, domain = normalize_target("facebook.com")
    assert domain == "facebook.com"
    assert pattern == "facebook.com"

    pattern, domain = normalize_target("http://reddit.com/r/dsa/")
    assert domain == "reddit.com"
    assert pattern == "reddit.com/r/dsa"


def test_blocker_repo_add_rule(blocker_repo):
    rule = blocker_repo.add_rule(
        raw_url="https://www.youtube.com/shorts",
        duration_minutes=60,
        match_type="exact",
        reason="Học bài IT003"
    )
    assert rule.id is not None
    assert rule.domain == "youtube.com"
    assert rule.match_type == "exact"
    assert rule.reason == "Học bài IT003"
    assert rule.duration_minutes == 60
    assert rule.blocked_until > rule.created_at
    assert rule.is_active == 1

    active = blocker_repo.get_active_rules()
    assert len(active) == 1
    assert active[0].id == rule.id


def test_blocker_repo_duration_validation(blocker_repo):
    # Over 6 hours (360 mins)
    with pytest.raises(ValueError, match="tối đa là 6 tiếng"):
        blocker_repo.add_rule("tiktok.com", duration_minutes=361)

    # 0 or negative
    with pytest.raises(ValueError, match="tối thiểu là 1 phút"):
        blocker_repo.add_rule("tiktok.com", duration_minutes=0)

    # Max valid duration (360 mins) succeeds
    rule = blocker_repo.add_rule("tiktok.com", duration_minutes=360)
    assert rule.duration_minutes == 360


def test_blocker_repo_hard_lock_active_cannot_delete(blocker_repo):
    rule = blocker_repo.add_rule("facebook.com", duration_minutes=30)
    
    # Attempting to delete an active rule MUST raise HardLockActiveError
    with pytest.raises(HardLockActiveError, match="Khóa cứng đang hoạt động"):
        blocker_repo.delete_rule(rule.id)

    # Rule must still exist in DB
    retrieved = blocker_repo.get_rule_by_id(rule.id)
    assert retrieved is not None
    assert retrieved.id == rule.id


def test_blocker_repo_expired_can_delete(blocker_repo):
    # Create rule and artificially simulate expiration in DB
    rule = blocker_repo.add_rule("reddit.com", duration_minutes=10)
    now = int(time.time())

    with blocker_repo._conn() as conn:
        conn.execute(
            "UPDATE blocker_rules SET blocked_until = ?, is_active = 0 WHERE id = ?",
            (now - 100, rule.id)
        )
        conn.commit()

    # Now deletion of expired rule succeeds
    success = blocker_repo.delete_rule(rule.id)
    assert success is True

    # Rule is no longer in DB
    assert blocker_repo.get_rule_by_id(rule.id) is None


def test_blocker_repo_check_url_blocked(blocker_repo):
    # 1. Domain match rule
    blocker_repo.add_rule("facebook.com", duration_minutes=60, match_type="domain")
    # 2. Exact match rule
    blocker_repo.add_rule("youtube.com/shorts", duration_minutes=60, match_type="exact")

    # Domain checks
    assert blocker_repo.check_url_blocked("https://facebook.com") is not None
    assert blocker_repo.check_url_blocked("https://www.facebook.com/messages") is not None
    assert blocker_repo.check_url_blocked("http://m.facebook.com/feed") is not None
    assert blocker_repo.check_url_blocked("https://google.com") is None

    # Exact checks
    assert blocker_repo.check_url_blocked("https://www.youtube.com/shorts/xyz") is not None
    assert blocker_repo.check_url_blocked("https://www.youtube.com/watch?v=123") is None


def test_api_blocker_flow(client):
    # 1. Page view routes
    res = client.get("/blocker")
    assert res.status_code == 200
    assert "Focus Blocker" in res.text

    res_blocked = client.get("/blocked?target=facebook.com")
    assert res_blocked.status_code == 200
    assert "TRANG WEB NÀY ĐANG BỊ KHÓA" in res_blocked.text

    # 2. Create rule via API
    payload = {
        "url": "x.com",
        "duration_minutes": 120,
        "match_type": "domain",
        "reason": "Luyện đồ thị Graph"
    }
    create_res = client.post("/api/blocker/rules", json=payload)
    assert create_res.status_code == 201
    create_data = create_res.json()
    rule_id = create_data["data"]["id"]
    assert "Đã kích hoạt khóa cứng" in create_data["message"]

    # 3. Get active rules
    get_res = client.get("/api/blocker/rules")
    assert get_res.status_code == 200
    rules = get_res.json()["data"]
    assert len(rules) == 1
    assert rules[0]["id"] == rule_id
    assert rules[0]["is_locked"] is True

    # 4. Attempt to delete active rule -> MUST be 403 Forbidden!
    del_res = client.delete(f"/api/blocker/rules/{rule_id}")
    assert del_res.status_code == 403
    del_data = del_res.json()
    assert del_data["locked"] is True
    assert "Khóa cứng đang hoạt động" in del_data["message"]

    # 5. Invalid duration (> 360) -> 400 Bad Request
    invalid_res = client.post("/api/blocker/rules", json={"url": "reddit.com", "duration_minutes": 500})
    assert invalid_res.status_code == 400
    assert "tối đa là 6 tiếng" in invalid_res.json()["message"]

    # 6. Check URL API
    chk_res = client.get("/api/blocker/check?url=https://x.com/explore")
    assert chk_res.status_code == 200
    assert chk_res.json()["data"]["blocked"] is True

    chk_res2 = client.get("/api/blocker/check?url=https://github.com")
    assert chk_res2.status_code == 200
    assert chk_res2.json()["data"]["blocked"] is False


def test_blocker_security_domain_sanitization_and_protected_domains(blocker_repo):
    # 1. Newline / carriage return injection attempt
    with pytest.raises(ValueError, match="ký tự điều khiển hoặc xuống dòng"):
        normalize_target("facebook.com\n127.0.0.1 malicious.com")

    with pytest.raises(ValueError, match="ký tự điều khiển hoặc xuống dòng"):
        normalize_target("facebook.com\r\nevil.com")

    with pytest.raises(ValueError, match="ký tự điều khiển hoặc xuống dòng"):
        normalize_target("facebook.com\0evil.com")

    # 2. Protected system domains cannot be blocked
    with pytest.raises(ValueError, match="tên miền hệ thống cốt lõi"):
        normalize_target("localhost")

    with pytest.raises(ValueError, match="tên miền hệ thống cốt lõi"):
        normalize_target("127.0.0.1")

    with pytest.raises(ValueError, match="tên miền hệ thống cốt lõi"):
        normalize_target("0.0.0.0")

    # 3. Invalid characters according to RFC 1123
    with pytest.raises(ValueError, match="RFC 1123"):
        normalize_target("invalid@website!.com")

    with pytest.raises(ValueError, match="RFC 1123"):
        normalize_target("bad domain.com")


