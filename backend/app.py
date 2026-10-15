from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
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

from core.db import DatabaseManager
from core.registry import ModuleRegistry
from database import TaskDatabase, StudyDatabase

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


# Backwards compatibility database references
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
# Settings Manager (Core Service)
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
# Core Page Views
# ----------------------------------------------------
async def homepage(request):
    modules = ModuleRegistry.get_modules()
    return templates.TemplateResponse(request, "main/index.html", {"modules": modules})


# ----------------------------------------------------
# Application Factory / Initialization
# ----------------------------------------------------
# Ensure schemas are initialized in primary database
DatabaseManager.init_all()
SettingsManager.init()

core_routes = [
    Route('/', endpoint=homepage, methods=['GET']),
    Route('/api/settings', endpoint=SettingsManager.route_get_settings, methods=['GET']),
    Route('/api/settings', endpoint=SettingsManager.route_save_settings, methods=['POST']),
    Mount('/static', app=StaticFiles(directory=frontend_dir), name="static")
]

middleware = [
    Middleware(RequestLoggingMiddleware)
]

app = Starlette(debug=True, routes=core_routes, middleware=middleware)
app.state.templates = templates

# Dynamically discover and register modules (tasks, study, future plugins)
ModuleRegistry.discover_and_register(app)

if __name__ == '__main__':
    port = int(os.environ.get("LOCKED_PORT", 8765))
    uvicorn.run("app:app", host='127.0.0.1', port=port, reload=True, use_colors=False)
