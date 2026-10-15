from starlette.responses import JSONResponse
from starlette.routing import Route
from datetime import datetime
from typing import List
from dataclasses import asdict

from core.registry import ModuleRegistry, ModuleMetadata
from .repository import TaskRepository

# Register module metadata for dynamic sidebar and discovery
ModuleRegistry.register(ModuleMetadata(
    id="tasks",
    title="Tasks & Schedule",
    icon="tasks",
    url="/tasks",
    order=1,
    description="Organize tasks and track deadlines with algorithmic calendar view"
))

default_task_repo = TaskRepository()

def get_task_repo() -> TaskRepository:
    try:
        import app as app_module
        if hasattr(app_module, "event_db") and app_module.event_db is not None:
            return getattr(app_module.event_db, "repo", default_task_repo)
    except Exception:
        pass
    return default_task_repo

async def route_get_events(request):
    repo = get_task_repo()
    cal_type = request.query_params.get("calendar_type")
    events = repo.get_events(calendar_type=cal_type)
    return JSONResponse({"status": "200 <OK>", "data": [asdict(e) for e in events]})

async def route_add_event(request):
    repo = get_task_repo()
    data = await request.json()
    event_id = data.get("id")
    name = data.get("name", "").strip() or "Untitled Task"
    description = data.get("description", "")

    now = int(datetime.now().timestamp())
    start_date = data.get("start_date", now)
    end_date = data.get("end_date", now + 86400)
    priority = int(data.get("priority", 1))
    labels = data.get("labels", "")
    done = 1 if data.get("done") else 0
    calendar_type = "routine" if data.get("calendar_type") == "routine" else "task"

    if event_id:
        repo.update_event(int(event_id), name, description, start_date, end_date, priority, labels, done, calendar_type)
        return JSONResponse({"status": "200 <OK>", "message": "Task updated"})
    else:
        task = repo.add_event(name, description, start_date, end_date, priority, labels, done, calendar_type)
        return JSONResponse({"status": "200 <OK>", "message": "Task added", "data": asdict(task)})

async def route_delete_event(request):
    repo = get_task_repo()
    try:
        data = await request.json()
        event_id = data.get("id")
    except Exception:
        event_id = request.query_params.get("id")

    if event_id:
        repo.delete_event(int(event_id))
        return JSONResponse({"status": "200 <OK>", "message": "Task deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing task id"}, status_code=400)

async def route_import_ics(request):
    repo = get_task_repo()
    content_type = request.headers.get("content-type", "")
    ics_text = ""
    target_cal = request.query_params.get("calendar_type")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_field = form.get("file")
        if not target_cal and form.get("calendar_type"):
            target_cal = form.get("calendar_type")
        if file_field is not None:
            file_bytes = await file_field.read()
            ics_text = file_bytes.decode("utf-8", errors="replace")
    elif "application/json" in content_type:
        body = await request.json()
        ics_text = body.get("content", "")
        if not target_cal and body.get("calendar_type"):
            target_cal = body.get("calendar_type")
    else:
        raw_body = await request.body()
        ics_text = raw_body.decode("utf-8", errors="replace")

    cal_type = "routine" if target_cal == "routine" else "task"

    if not ics_text.strip():
        return JSONResponse({"status": "400 <Bad Request>", "message": "No ICS content provided"}, status_code=400)

    try:
        from .ics_service import parse_ics
        parsed_events = parse_ics(ics_text)
        if not parsed_events:
            return JSONResponse({"status": "400 <Bad Request>", "message": "No valid VEVENT found in ICS file"}, status_code=400)

        imported_tasks = []
        for e in parsed_events:
            event_cal_type = e.get("calendar_type") or cal_type
            t = repo.add_event(
                name=e["name"],
                description=e["description"],
                start_date=e["start_date"],
                end_date=e["end_date"],
                priority=e["priority"],
                labels=e["labels"],
                done=e["done"],
                calendar_type=event_cal_type
            )
            imported_tasks.append(asdict(t))

        return JSONResponse({
            "status": "200 <OK>",
            "message": f"Successfully imported {len(imported_tasks)} events into {cal_type} calendar",
            "count": len(imported_tasks),
            "calendar_type": cal_type,
            "data": imported_tasks
        })
    except Exception as err:
        return JSONResponse({"status": "500 <Internal Server Error>", "message": f"Failed to parse ICS: {str(err)}"}, status_code=500)

async def route_export_ics(request):
    from starlette.responses import Response
    from .ics_service import generate_ics

    repo = get_task_repo()
    cal_type = request.query_params.get("calendar_type")
    events = repo.get_events(calendar_type=cal_type)
    ics_content = generate_ics(events)
    filename = f"locked_{cal_type}_schedule.ics" if cal_type else "locked_tasks.ics"
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )

async def tasks_page(request):
    templates = request.app.state.templates
    modules = ModuleRegistry.get_modules()
    return templates.TemplateResponse(request, "main/tasks.html", {"modules": modules})

# Exported routes for auto-discovery
routes: List[Route] = [
    Route('/api/events', endpoint=route_get_events, methods=['GET']),
    Route('/api/events', endpoint=route_add_event, methods=['POST']),
    Route('/api/events', endpoint=route_delete_event, methods=['DELETE']),
    Route('/api/events/import-ics', endpoint=route_import_ics, methods=['POST']),
    Route('/api/events/export-ics', endpoint=route_export_ics, methods=['GET']),
    Route('/tasks', endpoint=tasks_page, methods=['GET']),
]


