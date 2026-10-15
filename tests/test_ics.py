import io
from datetime import datetime, timezone
from modules.tasks.ics_service import (
    parse_ics,
    generate_ics,
    parse_ics_datetime,
    rfc_priority_to_local,
    local_priority_to_rfc,
)
from modules.tasks.models import TaskEvent


def test_parse_ics_datetime_formats():
    # UTC with Z
    dt_utc = parse_ics_datetime("20260921T145500Z")
    assert dt_utc is not None
    assert dt_utc.year == 2026 and dt_utc.month == 9 and dt_utc.day == 21
    assert dt_utc.hour == 14 and dt_utc.minute == 55 and dt_utc.second == 0
    assert dt_utc.tzinfo == timezone.utc

    # Local floating
    dt_local = parse_ics_datetime("20261015T083000")
    assert dt_local is not None
    assert dt_local.year == 2026 and dt_local.month == 10 and dt_local.day == 15
    assert dt_local.hour == 8 and dt_local.minute == 30

    # Date only
    dt_date = parse_ics_datetime("20261231")
    assert dt_date is not None
    assert dt_date.year == 2026 and dt_date.month == 12 and dt_date.day == 31


def test_priority_mapping():
    assert rfc_priority_to_local(1) == 5  # Highest RFC -> P5
    assert rfc_priority_to_local(2) == 5
    assert rfc_priority_to_local(3) == 4  # High RFC -> P4
    assert rfc_priority_to_local(5) == 3  # Medium -> P3
    assert rfc_priority_to_local(7) == 2  # Low -> P2
    assert rfc_priority_to_local(9) == 1  # Lowest -> P1

    assert local_priority_to_rfc(5) == 1
    assert local_priority_to_rfc(4) == 3
    assert local_priority_to_rfc(3) == 5
    assert local_priority_to_rfc(2) == 7
    assert local_priority_to_rfc(1) == 9


def test_parse_ics_single_event():
    ics_text = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:event-123@test
SUMMARY:SQL Query Exam
DESCRIPTION:Final exam in room A-204\\nBring student ID
DTSTART:20260922T080000Z
DTEND:20260922T100000Z
PRIORITY:1
CATEGORIES:dsa,exam
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    events = parse_ics(ics_text)
    assert len(events) == 1
    e = events[0]
    assert e["name"] == "SQL Query Exam"
    assert "Final exam in room A-204" in e["description"]
    assert "Bring student ID" in e["description"]
    assert e["priority"] == 5  # RFC 1 maps to P5
    assert e["labels"] == "dsa,exam"
    assert e["done"] == 0
    assert e["start_date"] < e["end_date"]


def test_parse_ics_rrule_weekly_with_exdate():
    # Starts Mon 2026-09-07, repeats Mon and Wed, 4 times total
    # Wed 2026-09-09 is in EXDATE, so it should skip 2026-09-09
    ics_text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Operating Systems Lecture
DESCRIPTION:Lab 3
DTSTART:20260907T080000Z
DTEND:20260907T100000Z
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4
EXDATE:20260909T080000Z
PRIORITY:3
END:VEVENT
END:VCALENDAR"""

    events = parse_ics(ics_text)
    assert len(events) == 4

    # Check names have session suffixes (#1), (#2), etc.
    assert "Operating Systems Lecture (#1)" in events[0]["name"]
    assert "Operating Systems Lecture (#2)" in events[1]["name"]
    assert "Operating Systems Lecture (#3)" in events[2]["name"]
    assert "Operating Systems Lecture (#4)" in events[3]["name"]

    # Verify dates:
    # #1 is Mon Sep 7
    # (Wed Sep 9 was skipped by EXDATE)
    # #2 is Mon Sep 14
    # #3 is Wed Sep 16
    # #4 is Mon Sep 21
    dt1 = datetime.fromtimestamp(events[0]["start_date"], tz=timezone.utc)
    dt2 = datetime.fromtimestamp(events[1]["start_date"], tz=timezone.utc)
    dt3 = datetime.fromtimestamp(events[2]["start_date"], tz=timezone.utc)
    dt4 = datetime.fromtimestamp(events[3]["start_date"], tz=timezone.utc)

    assert dt1.day == 7 and dt1.weekday() == 0  # Monday
    assert dt2.day == 14 and dt2.weekday() == 0  # Monday
    assert dt3.day == 16 and dt3.weekday() == 2  # Wednesday
    assert dt4.day == 21 and dt4.weekday() == 0  # Monday


def test_generate_ics():
    tasks = [
        TaskEvent(
            id=101,
            name="Complete Algorithms Assignment",
            description="Graphs and Dynamic Programming",
            start_date=1790000000,
            end_date=1790007200,
            priority=5,
            labels="homework,dsa",
            done=False
        ),
        TaskEvent(
            id=102,
            name="Read Chapter 4",
            description="Memory Hierarchy",
            start_date=1790100000,
            end_date=1790103600,
            priority=3,
            labels="reading",
            done=True
        )
    ]

    ics_output = generate_ics(tasks)
    assert "BEGIN:VCALENDAR" in ics_output
    assert "VERSION:2.0" in ics_output
    assert "PRODID:-//Locked//Study Toolkit//EN" in ics_output
    assert "BEGIN:VEVENT" in ics_output
    assert "SUMMARY:Complete Algorithms Assignment" in ics_output
    assert "CATEGORIES:homework,dsa" in ics_output
    assert "PRIORITY:1" in ics_output  # P5 mapped to RFC 1
    assert "STATUS:CONFIRMED" in ics_output

    assert "SUMMARY:Read Chapter 4" in ics_output
    assert "STATUS:COMPLETED" in ics_output
    assert "END:VCALENDAR" in ics_output


def test_api_import_ics_json(client):
    ics_text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Network Security Seminar
DESCRIPTION:Room C301
DTSTART:20261001T090000Z
DTEND:20261001T113000Z
PRIORITY:4
CATEGORIES:seminar
END:VEVENT
END:VCALENDAR"""

    res = client.post("/api/events/import-ics", json={"content": ics_text})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "200 <OK>"
    assert data["count"] == 1
    assert data["data"][0]["name"] == "Network Security Seminar"

    # Verify task appears in GET /api/events
    list_res = client.get("/api/events")
    assert list_res.status_code == 200
    all_events = list_res.json()["data"]
    match = [e for e in all_events if e["name"] == "Network Security Seminar"]
    assert len(match) == 1
    assert match[0]["labels"] == "seminar"


def test_api_import_ics_multipart_file(client):
    ics_text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Artificial Intelligence Lab
DTSTART:20261002T130000Z
DTEND:20261002T160000Z
PRIORITY:2
END:VEVENT
END:VCALENDAR"""

    files = {
        "file": ("schedule.ics", io.BytesIO(ics_text.encode("utf-8")), "text/calendar")
    }
    res = client.post("/api/events/import-ics", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "200 <OK>"
    assert data["count"] == 1
    assert data["data"][0]["name"] == "Artificial Intelligence Lab"


def test_api_import_ics_invalid_payload(client):
    # Empty content
    res1 = client.post("/api/events/import-ics", json={"content": ""})
    assert res1.status_code == 400

    # No VEVENT
    res2 = client.post("/api/events/import-ics", json={"content": "BEGIN:VCALENDAR\nEND:VCALENDAR"})
    assert res2.status_code == 400


def test_api_export_ics(client):
    # Create a task via POST /api/events
    client.post("/api/events", json={
        "name": "Exported Task Verification",
        "description": "Verify export output",
        "start_date": 1790000000,
        "end_date": 1790010000,
        "priority": 4,
        "labels": "export,test",
        "done": False
    })

    res = client.get("/api/events/export-ics")
    assert res.status_code == 200
    assert "text/calendar" in res.headers.get("content-type", "")
    assert "locked_tasks.ics" in res.headers.get("content-disposition", "")
    content = res.text
    assert "BEGIN:VCALENDAR" in content
    assert "Exported Task Verification" in content
    assert "Verify export output" in content
    assert "CATEGORIES:export,test" in content
    assert "END:VCALENDAR" in content


def test_api_import_export_ics_calendar_type(client):
    # 1. Import ICS with ?calendar_type=routine
    ics_routine = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Morning Jogging
DTSTART:20261005T060000Z
DTEND:20261005T070000Z
END:VEVENT
END:VCALENDAR"""

    res_import = client.post(
        "/api/events/import-ics?calendar_type=routine",
        json={"content": ics_routine}
    )
    assert res_import.status_code == 200
    assert res_import.json()["data"][0]["calendar_type"] == "routine"

    # 2. Add a task with calendar_type=task
    client.post("/api/events", json={
        "name": "Math Assignment Submission",
        "start_date": 1790100000,
        "end_date": 1790103600,
        "calendar_type": "task"
    })

    # 3. Export with ?calendar_type=routine
    res_exp_routine = client.get("/api/events/export-ics?calendar_type=routine")
    assert res_exp_routine.status_code == 200
    assert "Morning Jogging" in res_exp_routine.text
    assert "Math Assignment Submission" not in res_exp_routine.text

    # 4. Export with ?calendar_type=task
    res_exp_task = client.get("/api/events/export-ics?calendar_type=task")
    assert res_exp_task.status_code == 200
    assert "Math Assignment Submission" in res_exp_task.text
    assert "Morning Jogging" not in res_exp_task.text


