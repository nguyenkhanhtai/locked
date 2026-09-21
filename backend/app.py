from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import os
import sys
import uvicorn
import json
import logging
from logging.handlers import RotatingFileHandler
import functools

# Add backend directory to sys.path if not present
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import TaskDatabase, StudyDatabase
from schema import serialize_to_dict

# Templates & Static configuration
frontend_dir = os.path.join(backend_dir, "..", "frontend")
templates_dir = os.path.join(frontend_dir, "page")
os.makedirs(frontend_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Set up Logger for API requests
log_dir = os.path.join(backend_dir, "user", "log")
os.makedirs(log_dir, exist_ok=True)

app_logger = logging.getLogger("app_requests")
app_logger.setLevel(logging.INFO)
if not app_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=10*1024*1024, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    app_logger.addHandler(fh)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "Unknown"
        app_logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
        response = await call_next(request)
        app_logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code}")
        return response


# Initialize Databases
event_db = TaskDatabase()
study_db = StudyDatabase()


def api_error_handler(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            app_logger.error(f"API Error in {func.__name__}: {str(e)}", exc_info=True)
            return JSONResponse({
                "status": "500 <Internal Server Error>",
                "message": f"An unexpected error occurred: {str(e)}"
            }, status_code=500)
    return wrapper


# ----------------------------------------------------
# 1. Event / Task Manager
# ----------------------------------------------------
class EventManager:
    @staticmethod
    @api_error_handler
    async def route_get_events(request):
        data = serialize_to_dict(event_db.get_events())
        return JSONResponse({"status": "200 <OK>", "data": data})

    @staticmethod
    @api_error_handler
    async def route_add_event(request):
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

        if event_id:
            event_db.update_event(int(event_id), name, description, start_date, end_date, priority, labels, done)
            return JSONResponse({"status": "200 <OK>", "message": "Task updated"})
        else:
            task = event_db.add_event(name, description, start_date, end_date, priority, labels, done)
            return JSONResponse({"status": "200 <OK>", "message": "Task added", "data": serialize_to_dict(task)})

    @staticmethod
    @api_error_handler
    async def route_delete_event(request):
        try:
            data = await request.json()
            event_id = data.get("id")
        except Exception:
            event_id = request.query_params.get("id")

        if event_id:
            event_db.delete_event(int(event_id))
            return JSONResponse({"status": "200 <OK>", "message": "Task deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing task id"}, status_code=400)


# ----------------------------------------------------
# 2. Study Workspace Manager
# ----------------------------------------------------
class StudyManager:
    # --- Projects ---
    @staticmethod
    @api_error_handler
    async def route_get_projects(request):
        parent_id_str = request.query_params.get("parent_project_id")
        parent_id = int(parent_id_str) if parent_id_str and parent_id_str != 'null' else None
        projects = study_db.get_study_projects(parent_id)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(projects)})

    @staticmethod
    @api_error_handler
    async def route_add_project(request):
        data = await request.json()
        parent_id = data.get("parent_project_id")
        name = data.get("name", "").strip() or "Untitled Project"
        description = data.get("description", "")
        project = study_db.add_study_project(name, description, parent_id)
        return JSONResponse({"status": "200 <OK>", "message": "Project added", "data": serialize_to_dict(project)})

    @staticmethod
    @api_error_handler
    async def route_delete_project(request):
        try:
            data = await request.json()
            project_id = data.get("id")
        except Exception:
            project_id = request.query_params.get("id")

        if project_id:
            study_db.delete_study_project(int(project_id))
            return JSONResponse({"status": "200 <OK>", "message": "Project deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project id"}, status_code=400)

    @staticmethod
    @api_error_handler
    async def route_get_project_path(request):
        project_id_str = request.query_params.get("id")
        if not project_id_str:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
        project_id = int(project_id_str)
        path = study_db.get_study_project_path(project_id)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(path)})

    # --- Problems ---
    @staticmethod
    @api_error_handler
    async def route_get_problems(request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project_id"}, status_code=400)
        problems = study_db.get_study_problems(int(project_id))
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(problems)})

    @staticmethod
    @api_error_handler
    async def route_add_problem(request):
        data = await request.json()
        project_id = data.get("project_id")
        title = data.get("title", "").strip() or "Untitled Problem"
        description = data.get("description", "")
        if not project_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project_id"}, status_code=400)

        problem = study_db.add_study_problem(int(project_id), title, description)
        # Create default columns: Knowledge and Question
        study_db.add_study_column(problem.id, "Knowledge", 0)
        study_db.add_study_column(problem.id, "Question", 1)
        return JSONResponse({"status": "200 <OK>", "message": "Problem added", "data": serialize_to_dict(problem)})

    @staticmethod
    @api_error_handler
    async def route_delete_problem(request):
        try:
            data = await request.json()
            problem_id = data.get("id")
        except Exception:
            problem_id = request.query_params.get("id")

        if problem_id:
            study_db.delete_study_problem(int(problem_id))
            return JSONResponse({"status": "200 <OK>", "message": "Problem deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem id"}, status_code=400)

    @staticmethod
    @api_error_handler
    async def route_update_problem(request):
        data = await request.json()
        problem_id = data.get("id")
        if not problem_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
        title = data.get("title")
        description = data.get("description")
        study_db.update_study_problem(int(problem_id), title, description)
        return JSONResponse({"status": "200 <OK>", "message": "Problem updated"})

    # --- Columns ---
    @staticmethod
    @api_error_handler
    async def route_get_columns(request):
        problem_id = request.query_params.get("problem_id")
        if not problem_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem_id"}, status_code=400)
        columns = study_db.get_study_columns(int(problem_id))
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(columns)})

    @staticmethod
    @api_error_handler
    async def route_add_column(request):
        data = await request.json()
        problem_id = data.get("problem_id")
        name = data.get("name", "").strip() or "New Column"
        order_index = int(data.get("order_index", 0))
        if not problem_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing problem_id"}, status_code=400)
        col = study_db.add_study_column(int(problem_id), name, order_index)
        return JSONResponse({"status": "200 <OK>", "message": "Column added", "data": serialize_to_dict(col)})

    @staticmethod
    @api_error_handler
    async def route_update_column(request):
        data = await request.json()
        column_id = data.get("id")
        name = data.get("name")
        if column_id and name:
            study_db.update_study_column(int(column_id), name.strip())
            return JSONResponse({"status": "200 <OK>", "message": "Column updated"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id or name"}, status_code=400)

    @staticmethod
    @api_error_handler
    async def route_delete_column(request):
        try:
            data = await request.json()
            column_id = data.get("id")
        except Exception:
            column_id = request.query_params.get("id")

        if column_id:
            study_db.delete_study_column(int(column_id))
            return JSONResponse({"status": "200 <OK>", "message": "Column deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column id"}, status_code=400)

    # --- Records ---
    @staticmethod
    @api_error_handler
    async def route_get_records(request):
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        search = request.query_params.get("search", "")
        project_id_str = request.query_params.get("project_id")
        project_id = int(project_id_str) if project_id_str and project_id_str != 'null' else None
        records = study_db.get_study_records(limit, offset, search, project_id)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(records)})

    @staticmethod
    @api_error_handler
    async def route_get_record(request):
        record_id = request.query_params.get("id")
        if not record_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing id"}, status_code=400)
        data = study_db.get_study_record(int(record_id))
        if not data:
            return JSONResponse({"status": "404 <Not Found>", "message": "Record not found"}, status_code=404)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(data)})

    @staticmethod
    @api_error_handler
    async def route_add_record(request):
        data = await request.json()
        title = data.get("title", "").strip() or "Untitled Record"
        body = data.get("body", "")
        project_id = data.get("project_id")
        if project_id is not None:
            project_id = int(project_id)
        record = study_db.add_study_record(title, body, project_id)
        return JSONResponse({"status": "200 <OK>", "message": "Record added", "data": serialize_to_dict(record)})

    @staticmethod
    @api_error_handler
    async def route_update_record(request):
        data = await request.json()
        record_id = data.get("id")
        title = data.get("title", "").strip() or "Untitled Record"
        body = data.get("body", "")
        if record_id:
            study_db.update_study_record(int(record_id), title, body)
            return JSONResponse({"status": "200 <OK>", "message": "Record updated"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing record id"}, status_code=400)

    @staticmethod
    @api_error_handler
    async def route_delete_record(request):
        try:
            data = await request.json()
            record_id = data.get("id")
        except Exception:
            record_id = request.query_params.get("id")

        if record_id:
            study_db.delete_study_record(int(record_id))
            return JSONResponse({"status": "200 <OK>", "message": "Record deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing record id"}, status_code=400)

    # --- Problem Cards ---
    @staticmethod
    @api_error_handler
    async def route_get_problem_cards(request):
        column_id = request.query_params.get("column_id")
        if not column_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id"}, status_code=400)
        cards = study_db.get_study_problem_cards(int(column_id))
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(cards)})

    @staticmethod
    @api_error_handler
    async def route_add_problem_card(request):
        data = await request.json()
        column_id = data.get("column_id")
        record_id = data.get("record_id")
        order_index = int(data.get("order_index", 0))

        # If record_id is not provided but title/body are, create a new record first
        if not record_id and "title" in data:
            rec = study_db.add_study_record(data.get("title"), data.get("body", ""), data.get("project_id"))
            record_id = rec.id

        if not column_id or not record_id:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Missing column_id or record_id"}, status_code=400)

        card = study_db.add_study_problem_card(int(column_id), int(record_id), order_index)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(card)})

    @staticmethod
    @api_error_handler
    async def route_delete_problem_card(request):
        try:
            data = await request.json()
            card_id = data.get("id")
        except Exception:
            card_id = request.query_params.get("id")

        if card_id:
            study_db.delete_study_problem_card(int(card_id))
            return JSONResponse({"status": "200 <OK>", "message": "Problem card deleted"})
        return JSONResponse({"status": "400 <Bad Request>", "message": "Missing card id"}, status_code=400)

    # --- Search ---
    @staticmethod
    @api_error_handler
    async def route_search(request):
        query = request.query_params.get("q", "")
        results = study_db.search_all_study_items(query)
        return JSONResponse({"status": "200 <OK>", "data": results})


# ----------------------------------------------------
# 3. Settings Manager
# ----------------------------------------------------
class SettingsManager:
    @staticmethod
    def get_settings_path():
        dir_path = os.path.join(backend_dir, "user")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, "state.json")

    @staticmethod
    def init():
        try:
            path = SettingsManager.get_settings_path()
            if not os.path.exists(path):
                default_data = {
                    "theme": {"primary": "#4f46e5"},
                    "ui": {"compact_mode": False}
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app_logger.error(f"Settings init error: {e}")

    @staticmethod
    @api_error_handler
    async def route_get_settings(request):
        path = SettingsManager.get_settings_path()
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        return JSONResponse({"status": "200 <OK>", "data": data})

    @staticmethod
    @api_error_handler
    async def route_save_settings(request):
        data = await request.json()
        path = SettingsManager.get_settings_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return JSONResponse({"status": "200 <OK>", "message": "Settings saved"})


# ----------------------------------------------------
# 4. Page Views
# ----------------------------------------------------
async def homepage(request):
    return templates.TemplateResponse(request, "main/index.html")

async def tasks_page(request):
    return templates.TemplateResponse(request, "main/tasks.html")

async def study_page(request):
    return templates.TemplateResponse(request, "main/study.html")


# ----------------------------------------------------
# 5. Routing Definitions
# ----------------------------------------------------
routes = [
    # Task Routes
    Route('/api/events', endpoint=EventManager.route_get_events, methods=['GET']),
    Route('/api/events', endpoint=EventManager.route_add_event, methods=['POST']),
    Route('/api/events', endpoint=EventManager.route_delete_event, methods=['DELETE']),

    # Study Project Routes
    Route('/api/study/projects', endpoint=StudyManager.route_get_projects, methods=['GET']),
    Route('/api/study/projects/path', endpoint=StudyManager.route_get_project_path, methods=['GET']),
    Route('/api/study/projects', endpoint=StudyManager.route_add_project, methods=['POST']),
    Route('/api/study/projects', endpoint=StudyManager.route_delete_project, methods=['DELETE']),

    # Study Problem Routes
    Route('/api/study/problems', endpoint=StudyManager.route_get_problems, methods=['GET']),
    Route('/api/study/problems', endpoint=StudyManager.route_add_problem, methods=['POST']),
    Route('/api/study/problems', endpoint=StudyManager.route_update_problem, methods=['PUT']),
    Route('/api/study/problems', endpoint=StudyManager.route_delete_problem, methods=['DELETE']),

    # Study Column Routes
    Route('/api/study/columns', endpoint=StudyManager.route_get_columns, methods=['GET']),
    Route('/api/study/columns', endpoint=StudyManager.route_add_column, methods=['POST']),
    Route('/api/study/columns', endpoint=StudyManager.route_update_column, methods=['PUT']),
    Route('/api/study/columns', endpoint=StudyManager.route_delete_column, methods=['DELETE']),

    # Study Record Routes
    Route('/api/study/records', endpoint=StudyManager.route_get_records, methods=['GET']),
    Route('/api/study/records/single', endpoint=StudyManager.route_get_record, methods=['GET']),
    Route('/api/study/records', endpoint=StudyManager.route_add_record, methods=['POST']),
    Route('/api/study/records', endpoint=StudyManager.route_update_record, methods=['PUT']),
    Route('/api/study/records', endpoint=StudyManager.route_delete_record, methods=['DELETE']),

    # Study Problem Cards Routes
    Route('/api/study/problem_cards', endpoint=StudyManager.route_get_problem_cards, methods=['GET']),
    Route('/api/study/problem_cards', endpoint=StudyManager.route_add_problem_card, methods=['POST']),
    Route('/api/study/problem_cards', endpoint=StudyManager.route_delete_problem_card, methods=['DELETE']),

    # Study Search Route
    Route('/api/study/search', endpoint=StudyManager.route_search, methods=['GET']),

    # Settings Routes
    Route('/api/settings', endpoint=SettingsManager.route_get_settings, methods=['GET']),
    Route('/api/settings', endpoint=SettingsManager.route_save_settings, methods=['POST']),

    # Page Routes
    Route('/', endpoint=homepage, methods=['GET']),
    Route('/tasks', endpoint=tasks_page, methods=['GET']),
    Route('/study', endpoint=study_page, methods=['GET']),

    # Static Files
    Mount('/static', app=StaticFiles(directory=frontend_dir), name="static")
]

SettingsManager.init()

middleware = [
    Middleware(RequestLoggingMiddleware)
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == '__main__':
    uvicorn.run("app:app", host='127.0.0.1', port=8765, reload=True, use_colors=False)
