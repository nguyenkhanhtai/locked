from starlette.responses import JSONResponse
from starlette.routing import Route
from dataclasses import asdict
from typing import List, Any
import logging

from core.registry import ModuleRegistry, ModuleMetadata
from .repository import StudyRepository

logger = logging.getLogger("modules.study.router")

# Register module metadata for dynamic discovery
ModuleRegistry.register(ModuleMetadata(
    id="study",
    title="Study Workspace",
    icon="study",
    url="/study",
    order=3,
    description="Organize DSA topics, problems, and study notes"
))

default_study_repo = StudyRepository()


def get_study_repo() -> StudyRepository:
    try:
        import app as app_module
        if hasattr(app_module, "study_db") and app_module.study_db is not None:
            return getattr(app_module.study_db, "repo", default_study_repo)
    except Exception:
        pass
    return default_study_repo


def serialize(obj: Any):
    if isinstance(obj, list):
        return [asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in obj]
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return obj


# --- Projects ---
async def route_get_projects(request):
    repo = get_study_repo()
    parent_id_str = request.query_params.get("parent_project_id")
    parent_id = int(parent_id_str) if parent_id_str and parent_id_str != 'null' else None
    projects = repo.get_study_projects(parent_id)
    return JSONResponse({"status": "200 <OK>", "data": serialize(projects)})


async def route_add_project(request):
    repo = get_study_repo()
    data = await request.json()
    parent_id = data.get("parent_project_id")
    name = data.get("name", "").strip() or "Untitled Project"
    description = data.get("description", "")
    project = repo.add_study_project(name, description, parent_id)
    return JSONResponse({"status": "200 <OK>", "message": "Project added", "data": serialize(project)})


async def route_delete_project(request):
    repo = get_study_repo()
    try:
        data = await request.json()
        project_id = data.get("id")
    except Exception:
        project_id = request.query_params.get("id")

    if project_id:
        repo.delete_study_project(int(project_id))
        return JSONResponse({"status": "200 <OK>", "message": "Project deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project id"}, status_code=400)


async def route_get_project_path(request):
    repo = get_study_repo()
    project_id_str = request.query_params.get("id")
    if not project_id_str:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
    project_id = int(project_id_str)
    path = repo.get_study_project_path(project_id)
    return JSONResponse({"status": "200 <OK>", "data": serialize(path)})


# --- Problems ---
async def route_get_problems(request):
    repo = get_study_repo()
    project_id = request.query_params.get("project_id")
    if not project_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project_id"}, status_code=400)
    problems = repo.get_study_problems(int(project_id))
    return JSONResponse({"status": "200 <OK>", "data": serialize(problems)})


async def route_add_problem(request):
    repo = get_study_repo()
    data = await request.json()
    project_id = data.get("project_id")
    title = data.get("title", "").strip() or "Untitled Problem"
    description = data.get("description", "")
    if not project_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project_id"}, status_code=400)

    problem = repo.add_study_problem(int(project_id), title, description)
    # Create default columns: Knowledge and Question
    repo.add_study_column(problem.id, "Knowledge", 0)
    repo.add_study_column(problem.id, "Question", 1)
    return JSONResponse({"status": "200 <OK>", "message": "Problem added", "data": serialize(problem)})


async def route_update_problem(request):
    repo = get_study_repo()
    data = await request.json()
    problem_id = data.get("id")
    if not problem_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
    title = data.get("title")
    description = data.get("description")
    repo.update_study_problem(int(problem_id), title, description)
    return JSONResponse({"status": "200 <OK>", "message": "Problem updated"})


async def route_delete_problem(request):
    repo = get_study_repo()
    try:
        data = await request.json()
        problem_id = data.get("id")
    except Exception:
        problem_id = request.query_params.get("id")

    if problem_id:
        repo.delete_study_problem(int(problem_id))
        return JSONResponse({"status": "200 <OK>", "message": "Problem deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem id"}, status_code=400)


# --- Columns ---
async def route_get_columns(request):
    repo = get_study_repo()
    problem_id = request.query_params.get("problem_id")
    if not problem_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem_id"}, status_code=400)
    columns = repo.get_study_columns(int(problem_id))
    return JSONResponse({"status": "200 <OK>", "data": serialize(columns)})


async def route_add_column(request):
    repo = get_study_repo()
    data = await request.json()
    problem_id = data.get("problem_id")
    name = data.get("name", "").strip() or "New Column"
    order_index = int(data.get("order_index", 0))
    if not problem_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem_id"}, status_code=400)
    col = repo.add_study_column(int(problem_id), name, order_index)
    return JSONResponse({"status": "200 <OK>", "message": "Column added", "data": serialize(col)})


async def route_update_column(request):
    repo = get_study_repo()
    data = await request.json()
    column_id = data.get("id")
    name = data.get("name")
    if column_id and name:
        repo.update_study_column(int(column_id), name.strip())
        return JSONResponse({"status": "200 <OK>", "message": "Column updated"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id or name"}, status_code=400)


async def route_delete_column(request):
    repo = get_study_repo()
    try:
        data = await request.json()
        column_id = data.get("id")
    except Exception:
        column_id = request.query_params.get("id")

    if column_id:
        repo.delete_study_column(int(column_id))
        return JSONResponse({"status": "200 <OK>", "message": "Column deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column id"}, status_code=400)


# --- Hierarchy Tree ---
async def route_get_project_tree(request):
    repo = get_study_repo()
    project_id_str = request.query_params.get("project_id")
    project_id = int(project_id_str) if project_id_str and project_id_str != 'null' else None
    tree = repo.get_project_hierarchy_tree(project_id)
    return JSONResponse({"status": "200 <OK>", "data": tree})


# --- Records ---
async def route_get_records(request):
    repo = get_study_repo()
    limit = int(request.query_params.get("limit", 100))
    offset = int(request.query_params.get("offset", 0))
    search = request.query_params.get("search", "")
    project_id_str = request.query_params.get("project_id")
    project_id = int(project_id_str) if project_id_str and project_id_str != 'null' else None
    problem_id_str = request.query_params.get("problem_id")
    problem_id = int(problem_id_str) if problem_id_str and problem_id_str != 'null' else None
    unassigned = request.query_params.get("unassigned", "").lower() in ("true", "1")
    records = repo.get_study_records(limit, offset, search, project_id, problem_id, unassigned)
    return JSONResponse({"status": "200 <OK>", "data": serialize(records)})


async def route_get_record(request):
    repo = get_study_repo()
    record_id = request.query_params.get("id")
    if not record_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
    data = repo.get_study_record(int(record_id))
    if not data:
        return JSONResponse({"status": "404 <Not Found>", "message": "Record not found"}, status_code=404)
    return JSONResponse({"status": "200 <OK>", "data": serialize(data)})


async def route_add_record(request):
    repo = get_study_repo()
    data = await request.json()
    title = data.get("title", "").strip() or "Untitled Record"
    body = data.get("body", "")
    project_id = data.get("project_id")
    if project_id is not None:
        project_id = int(project_id)
    problem_id = data.get("problem_id")
    if problem_id is not None:
        problem_id = int(problem_id)
    record = repo.add_study_record(title, body, project_id, problem_id)
    return JSONResponse({"status": "200 <OK>", "message": "Record added", "data": serialize(record)})


async def route_update_record(request):
    repo = get_study_repo()
    data = await request.json()
    record_id = data.get("id")
    title = data.get("title", "").strip() or "Untitled Record"
    body = data.get("body", "")
    problem_id = data.get("problem_id")
    if problem_id is not None:
        problem_id = int(problem_id)
    if record_id:
        repo.update_study_record(int(record_id), title, body, problem_id)
        return JSONResponse({"status": "200 <OK>", "message": "Record updated"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing record id"}, status_code=400)


async def route_delete_record(request):
    repo = get_study_repo()
    try:
        data = await request.json()
        record_id = data.get("id")
    except Exception:
        record_id = request.query_params.get("id")

    if record_id:
        repo.delete_study_record(int(record_id))
        return JSONResponse({"status": "200 <OK>", "message": "Record deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing record id"}, status_code=400)


# --- Problem Cards ---
async def route_get_problem_cards(request):
    repo = get_study_repo()
    column_id = request.query_params.get("column_id")
    if not column_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id"}, status_code=400)
    cards = repo.get_study_problem_cards(int(column_id))
    return JSONResponse({"status": "200 <OK>", "data": serialize(cards)})


async def route_add_problem_card(request):
    repo = get_study_repo()
    data = await request.json()
    column_id = data.get("column_id")
    record_id = data.get("record_id")
    order_index = int(data.get("order_index", 0))

    if not record_id and "title" in data:
        rec = repo.add_study_record(data.get("title"), data.get("body", ""), data.get("project_id"))
        record_id = rec.id

    if not column_id or not record_id:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id or record_id"}, status_code=400)

    card = repo.add_study_problem_card(int(column_id), int(record_id), order_index)
    return JSONResponse({"status": "200 <OK>", "data": serialize(card)})


async def route_delete_problem_card(request):
    repo = get_study_repo()
    try:
        data = await request.json()
        card_id = data.get("id")
    except Exception:
        card_id = request.query_params.get("id")

    if card_id:
        repo.delete_study_problem_card(int(card_id))
        return JSONResponse({"status": "200 <OK>", "message": "Problem card deleted"})
    return JSONResponse({"status": "400 <Bad Request>", "message": "Missing card id"}, status_code=400)


# --- Search ---
async def route_search(request):
    repo = get_study_repo()
    query = request.query_params.get("q", "")
    results = repo.search_all_study_items(query)
    return JSONResponse({"status": "200 <OK>", "data": results})


# --- Page ---
async def study_page(request):
    templates = request.app.state.templates
    modules = ModuleRegistry.get_modules()
    return templates.TemplateResponse(request, "main/study.html", {"modules": modules})


# Exported routes for auto-discovery
routes: List[Route] = [
    # Projects
    Route('/api/study/projects', endpoint=route_get_projects, methods=['GET']),
    Route('/api/study/projects/path', endpoint=route_get_project_path, methods=['GET']),
    Route('/api/study/projects', endpoint=route_add_project, methods=['POST']),
    Route('/api/study/projects', endpoint=route_delete_project, methods=['DELETE']),
    Route('/api/study/tree', endpoint=route_get_project_tree, methods=['GET']),

    # Problems
    Route('/api/study/problems', endpoint=route_get_problems, methods=['GET']),
    Route('/api/study/problems', endpoint=route_add_problem, methods=['POST']),
    Route('/api/study/problems', endpoint=route_update_problem, methods=['PUT']),
    Route('/api/study/problems', endpoint=route_delete_problem, methods=['DELETE']),

    # Columns
    Route('/api/study/columns', endpoint=route_get_columns, methods=['GET']),
    Route('/api/study/columns', endpoint=route_add_column, methods=['POST']),
    Route('/api/study/columns', endpoint=route_update_column, methods=['PUT']),
    Route('/api/study/columns', endpoint=route_delete_column, methods=['DELETE']),

    # Records
    Route('/api/study/records', endpoint=route_get_records, methods=['GET']),
    Route('/api/study/records/single', endpoint=route_get_record, methods=['GET']),
    Route('/api/study/records', endpoint=route_add_record, methods=['POST']),
    Route('/api/study/records', endpoint=route_update_record, methods=['PUT']),
    Route('/api/study/records', endpoint=route_delete_record, methods=['DELETE']),

    # Problem Cards
    Route('/api/study/problem_cards', endpoint=route_get_problem_cards, methods=['GET']),
    Route('/api/study/problem_cards', endpoint=route_add_problem_card, methods=['POST']),
    Route('/api/study/problem_cards', endpoint=route_delete_problem_card, methods=['DELETE']),

    # Search
    Route('/api/study/search', endpoint=route_search, methods=['GET']),

    # Page
    Route('/study', endpoint=study_page, methods=['GET']),
]

