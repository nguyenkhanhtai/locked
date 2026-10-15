from starlette.responses import JSONResponse
from starlette.routing import Route
from typing import List, Optional
import logging

from core.registry import ModuleRegistry, ModuleMetadata
from .repository import SessionTargetRepository

logger = logging.getLogger("modules.session_target.router")

# Register module metadata for dynamic discovery & navigation
ModuleRegistry.register(ModuleMetadata(
    id="session_target",
    title="Session Target",
    icon="target",
    url="/session-target",
    order=2,
    description="Thiết lập phiên làm việc có mục tiêu cụ thể và đồng hồ đếm ngược nổi"
))

default_session_repo = SessionTargetRepository()

def get_session_repo() -> SessionTargetRepository:
    try:
        from core.db import DatabaseManager
        active_db = DatabaseManager.get_db_path()
        if default_session_repo.db_path != active_db:
            return SessionTargetRepository(active_db)
    except Exception:
        pass
    return default_session_repo


# --- Route Handlers ---

async def route_get_sessions(request):
    repo = get_session_repo()
    status = request.query_params.get("status")
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    sessions = repo.get_sessions(status=status, limit=limit, offset=offset)
    return JSONResponse({"status": "200 <OK>", "data": [s.to_dict() for s in sessions]})


async def route_get_active_session(request):
    repo = get_session_repo()
    merged = repo.get_merged_active_targets()
    return JSONResponse({"status": "200 <OK>", "data": merged})


async def route_get_merged_sessions(request):
    repo = get_session_repo()
    merged = repo.get_merged_active_targets()
    return JSONResponse({"status": "200 <OK>", "data": merged})


async def route_get_stats(request):
    repo = get_session_repo()
    stats = repo.get_stats()
    return JSONResponse({"status": "200 <OK>", "data": stats})


async def route_create_session(request):
    repo = get_session_repo()
    data = await request.json()
    title = data.get("title", "").strip() or "Untitled Session"
    duration = int(data.get("duration_minutes", 25))
    todos = data.get("todos", [])
    start_immediately = bool(data.get("start_immediately", False))
    scheduled_start_at = int(data.get("scheduled_start_at", 0))
    pause_others = bool(data.get("pause_others", False))

    session = repo.create_session(
        title=title,
        duration_minutes=duration,
        todos=todos,
        start_immediately=start_immediately,
        scheduled_start_at=scheduled_start_at,
        pause_others=pause_others
    )
    return JSONResponse({
        "status": "200 <OK>",
        "message": "Session created",
        "data": session.to_dict()
    })


async def route_start_session(request):
    repo = get_session_repo()
    data = await request.json()
    session_id = data.get("id")
    pause_others = bool(data.get("pause_others", False))
    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing session id"}, status_code=400)

    session = repo.start_session(int(session_id), pause_others=pause_others)
    if not session:
        return JSONResponse({"status": "404 <Not Found>", "message": "Session not found"}, status_code=404)
    return JSONResponse({"status": "200 <OK>", "message": "Session started", "data": session.to_dict()})


async def route_pause_session(request):
    repo = get_session_repo()
    try:
        data = await request.json()
        session_id = data.get("id")
    except Exception:
        session_id = None

    if not session_id:
        active = repo.get_active_session()
        if active and active.status == "running":
            session_id = active.id

    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "No active running session"}, status_code=400)

    session = repo.pause_session(int(session_id))
    return JSONResponse({"status": "200 <OK>", "message": "Session paused", "data": session.to_dict() if session else None})


async def route_resume_session(request):
    repo = get_session_repo()
    try:
        data = await request.json()
        session_id = data.get("id")
        pause_others = bool(data.get("pause_others", False))
    except Exception:
        session_id = None
        pause_others = False

    if not session_id:
        active = repo.get_active_session()
        if active and active.status == "paused":
            session_id = active.id

    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "No active paused session"}, status_code=400)

    session = repo.resume_session(int(session_id), pause_others=pause_others)
    return JSONResponse({"status": "200 <OK>", "message": "Session resumed", "data": session.to_dict() if session else None})


async def route_complete_session(request):
    repo = get_session_repo()
    data = await request.json()
    session_id = data.get("id")
    complete_all = bool(data.get("complete_all", False))
    note = data.get("note", "")

    if complete_all:
        actives = repo.get_active_sessions()
        for s in actives:
            repo.complete_session(s.id, note=note)
        return JSONResponse({"status": "200 <OK>", "message": "All active sessions completed", "data": None})

    if not session_id:
        active = repo.get_active_session()
        if active:
            session_id = active.id

    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "No session specified"}, status_code=400)

    session = repo.complete_session(int(session_id), note=note)
    return JSONResponse({"status": "200 <OK>", "message": "Session completed", "data": session.to_dict() if session else None})


async def route_abandon_session(request):
    repo = get_session_repo()
    data = await request.json()
    session_id = data.get("id")
    abandon_all = bool(data.get("abandon_all", False))

    if abandon_all:
        actives = repo.get_active_sessions()
        for s in actives:
            repo.abandon_session(s.id)
        return JSONResponse({"status": "200 <OK>", "message": "All active sessions abandoned", "data": None})

    if not session_id:
        active = repo.get_active_session()
        if active:
            session_id = active.id

    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "No session specified"}, status_code=400)

    session = repo.abandon_session(int(session_id))
    return JSONResponse({"status": "200 <OK>", "message": "Session abandoned", "data": session.to_dict() if session else None})


async def route_update_todos(request):
    repo = get_session_repo()
    data = await request.json()
    session_id = data.get("id") or data.get("session_id")
    todos = data.get("todos", [])

    if not session_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing session id"}, status_code=400)

    session = repo.update_todos(int(session_id), todos)
    return JSONResponse({"status": "200 <OK>", "message": "Todos updated", "data": session.to_dict() if session else None})


async def route_toggle_todo(request):
    repo = get_session_repo()
    data = await request.json()
    session_id = data.get("session_id") or data.get("id")
    todo_id = str(data.get("todo_id", ""))
    done = data.get("done")

    if not session_id or not todo_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing session_id or todo_id"}, status_code=400)

    session = repo.toggle_todo(int(session_id), todo_id, done)
    if not session:
        return JSONResponse({"status": "404 <Not Found>", "message": "Session not found"}, status_code=404)
    return JSONResponse({"status": "200 <OK>", "message": "Todo toggled", "data": repo.get_merged_active_targets()})


async def route_delete_session(request):
    repo = get_session_repo()
    try:
        data = await request.json()
        session_id = data.get("id")
    except Exception:
        session_id = request.query_params.get("id")

    if session_id:
        repo.delete_session(int(session_id))
        return JSONResponse({"status": "200 <OK>", "message": "Session deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing session id"}, status_code=400)


async def session_target_page(request):
    templates = request.app.state.templates
    modules = ModuleRegistry.get_modules()
    return templates.TemplateResponse(request, "main/session_target.html", {"modules": modules})


async def session_popout_page(request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "main/session_popout.html", {})


routes: List[Route] = [
    Route('/api/sessions', endpoint=route_get_sessions, methods=['GET']),
    Route('/api/sessions', endpoint=route_create_session, methods=['POST']),
    Route('/api/sessions', endpoint=route_delete_session, methods=['DELETE']),
    Route('/api/sessions/active', endpoint=route_get_active_session, methods=['GET']),
    Route('/api/sessions/merged', endpoint=route_get_merged_sessions, methods=['GET']),
    Route('/api/sessions/stats', endpoint=route_get_stats, methods=['GET']),
    Route('/api/sessions/start', endpoint=route_start_session, methods=['POST']),
    Route('/api/sessions/pause', endpoint=route_pause_session, methods=['POST']),
    Route('/api/sessions/resume', endpoint=route_resume_session, methods=['POST']),
    Route('/api/sessions/complete', endpoint=route_complete_session, methods=['POST']),
    Route('/api/sessions/abandon', endpoint=route_abandon_session, methods=['POST']),
    Route('/api/sessions/todos', endpoint=route_update_todos, methods=['PUT']),
    Route('/api/sessions/todo/toggle', endpoint=route_toggle_todo, methods=['POST', 'PUT']),
    Route('/session-target', endpoint=session_target_page, methods=['GET']),
    Route('/session-widget-popout', endpoint=session_popout_page, methods=['GET']),
]

