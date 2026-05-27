from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import os
import uvicorn
import json
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse
import urllib.error
import asyncio
from database import BlockedDatabase, ConsumptionDatabase, TaskDatabase, StudyDatabase, ChatDatabase
from schema import serialize_to_dict
from model.chatbot import ChatBot
from model.similarity import AIModelFactory, TraditionalSimilarityModel
import webview

# Set up Logger for API requests
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user", "log")
os.makedirs(log_dir, exist_ok=True)

app_logger = logging.getLogger("app_requests")
app_logger.setLevel(logging.INFO)
if not app_logger.handlers:
    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=20*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    app_logger.addHandler(fh)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "Unknown"
        app_logger.info(f"Get request: {request.method} {request.url.path} từ {client_ip}")
        response = await call_next(request)
        app_logger.info(f"State: {request.method} {request.url.path} - Status code: {response.status_code}")
        return response

db = BlockedDatabase()
consumption_db = ConsumptionDatabase()
event_db = TaskDatabase()
study_db = StudyDatabase()
chat_db = ChatDatabase()

import functools

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

# 1. Definition of classes

class Blocker:
    @staticmethod 
    def get_domain(url: str) -> str:
        try:
            # Add default scheme if not present
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
                
            parsed = urlparse(url)
            domain = parsed.netloc
            
            # Remove www. prefix for normalization (e.g., www.youtube.com -> youtube.com)
            if domain.startswith('www.'):
                domain = domain[4:]
                            
            return domain
        except Exception:
            return url

    class TemporaryBlocker:
        @staticmethod
        @api_error_handler
        async def add_sites(data):
            url = data.get("url", "")
            if url:
                url = Blocker.get_domain(url)
                base_domain = url.split(':')[0]
                if base_domain in ["localhost", "127.0.0.1"]:
                    return JSONResponse({
                        "status": "400 <Bad Request>",
                        "message": "You cannot block system pages (localhost/locked)."
                    }, status_code=400)
                
            duration = data.get("duration", {})

            hours = duration.get("hours", 0)
            minutes = duration.get("minutes", 0)
            seconds = duration.get("seconds", 0)

            open_at = int(datetime.now().timestamp()) + hours * 3600 + minutes * 60 + seconds

            db.add_temp_site(url, open_at)

            return JSONResponse({
                "status": "200 <OK>",
                "message": f"Added {url} to temporary blocklists for {hours}:{minutes}:{seconds}"
            })

        @staticmethod
        @api_error_handler
        async def delete_sites(keyword):
            if keyword:
                keyword = Blocker.get_domain(keyword)
                db.delete_temp_sites(keyword)
                
            return JSONResponse({
                "status": "200 <OK>",
                "message": f"Deleted temporary sites containing '{keyword}'"
            })

    class PermanentBlocker:
        @staticmethod
        @api_error_handler
        async def add_sites(data):
            url = data.get("url", "")
            if url:
                url = Blocker.get_domain(url)
                base_domain = url.split(':')[0]
                if base_domain in ["localhost", "127.0.0.1"]:
                    return JSONResponse({
                        "status": "400 <Bad Request>",
                        "message": "You cannot block system pages (localhost/locked)."
                    }, status_code=400)
                
            duration = data.get("duration", {})
            days = duration.get("days", 1)
            hours = duration.get("hours", 0)
            minutes = duration.get("minutes", 0)
            seconds = duration.get("seconds", 0)

            unlock_at = int(datetime.now().timestamp()) + days * 86400 + hours * 3600 + minutes * 60 + seconds
            db.add_perm_site(url, unlock_at)

            return JSONResponse({
                "status": "200 <OK>",
                "message": f"Added {url} to permanent blocklists for {days} days"
            })

        @staticmethod
        @api_error_handler
        async def delete_sites(keyword):
            if keyword:
                keyword = Blocker.get_domain(keyword)
                result = db.delete_perm_sites(keyword)
                
                if result.get("deleted", 0) == 0:
                    return JSONResponse({
                        "status": "400 <Bad Request>",
                        "message": result.get("message", f"Unable to delete '{keyword}'.")
                    }, status_code=400)
                
            return JSONResponse({
                "status": "200 <OK>",
                "message": f"Deleted permanent sites containing '{keyword}'"
            })

    @staticmethod
    @api_error_handler
    async def route_add_block(request):
        data = await request.json()
        mode = data.get("mode", "temporary")
        if mode == "permanent":
            return await Blocker.PermanentBlocker.add_sites(data)
        return await Blocker.TemporaryBlocker.add_sites(data)

    @staticmethod
    @api_error_handler
    async def route_delete_block(request):
        try:
            data = await request.json()
            keyword = data.get("url", "")
            mode = data.get("mode", "temporary")
        except Exception:
            keyword = request.query_params.get("url", "")
            mode = request.query_params.get("mode", "temporary")
            
        if mode == "permanent":
            return await Blocker.PermanentBlocker.delete_sites(keyword)
        return await Blocker.TemporaryBlocker.delete_sites(keyword)

    @staticmethod
    @api_error_handler
    async def route_get_blocks(request):
        data = serialize_to_dict(db.get_all_blocks())
        return JSONResponse({"status": "200 <OK>", "data": data})

    class FocusMode:
        @staticmethod
        @api_error_handler
        async def route_toggle(request):
            data = await request.json()
            is_active = data.get("is_active", False)
            duration = data.get("duration", 0) # seconds
            db.set_focus_mode(is_active, duration)
            return JSONResponse({"status": "200 <OK>", "message": f"Focus mode {'activated' if is_active else 'deactivated'}"})

        @staticmethod
        @api_error_handler
        async def route_get_status(request):
            status = db.get_focus_status()
            return JSONResponse({"status": "200 <OK>", "data": status})

        @staticmethod
        @api_error_handler
        async def route_get_list(request):
            focus_list = db.get_focus_list()
            return JSONResponse({"status": "200 <OK>", "data": focus_list})

        @staticmethod
        @api_error_handler
        async def route_add_url(request):
            data = await request.json()
            url = data.get("url", "")
            if url:
                url = Blocker.get_domain(url)
                db.add_focus_url(url)
            return JSONResponse({"status": "200 <OK>", "message": f"Added {url} to focus list"})

        @staticmethod
        @api_error_handler
        async def route_delete_url(request):
            data = await request.json()
            url = data.get("url", "")
            if url:
                url = Blocker.get_domain(url)
                db.delete_focus_url(url)
            return JSONResponse({"status": "200 <OK>", "message": f"Deleted {url} from focus list"})

    @staticmethod
    @api_error_handler
    async def route_get_top_sites(request):
        data = serialize_to_dict(consumption_db.get_top_sites(limit=5))
        return JSONResponse({"status": "200 <OK>", "data": data})

    @staticmethod
    @api_error_handler
    async def homepage(request):
        frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "page", "index.html")
        return FileResponse(frontend_path)

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
        name = data.get("name", "Untitled")
        description = data.get("description", "")
        
        now = int(datetime.now().timestamp())
        start_date = data.get("start_date", now)
        end_date = data.get("end_date", now + 86400) # Default to 1 day later
        priority = data.get("priority", 1)
        labels = data.get("labels", "")
        done = 1 if data.get("done") else 0
        
        if event_id:
            event_db.update_event(event_id, name, description, start_date, end_date, priority, labels, done)
            return JSONResponse({"status": "200 <OK>", "message": "Task updated"})
        else:
            event_db.add_event(name, description, start_date, end_date, priority, labels, done)
            return JSONResponse({"status": "200 <OK>", "message": "Task added"})
        
    @staticmethod
    @api_error_handler
    async def route_delete_event(request):
        data = await request.json()
        event_id = data.get("id")
        if event_id:
            event_db.delete_event(event_id)
        return JSONResponse({"status": "200 <OK>", "message": "Event deleted"})

class StudyManager:
    class Memorize:
        @staticmethod
        @api_error_handler
        async def route_get_projects(request):
            return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(study_db.get_study_projects())})
            
        @staticmethod
        @api_error_handler
        async def route_add_project(request):
            data = await request.json()
            study_db.add_study_project(data.get("name", "Untitled"), data.get("description", ""))
            return JSONResponse({"status": "200 <OK>", "message": "Project added"})

        @staticmethod
        @api_error_handler
        async def route_delete_project(request):
            data = await request.json()
            project_id = data.get("id")
            if project_id:
                study_db.delete_study_project(project_id)
            return JSONResponse({"status": "200 <OK>", "message": "Project deleted"})

        @staticmethod
        @api_error_handler
        async def route_delete_flashcard(request):
            data = await request.json()
            card_id = data.get("id")
            if card_id:
                study_db.delete_flashcard(card_id)
            return JSONResponse({"status": "200 <OK>", "message": "Flashcard deleted"})

        @staticmethod
        @api_error_handler
        async def route_get_flashcards(request):
            data = serialize_to_dict(study_db.get_flashcards())
            return JSONResponse({"status": "200 <OK>", "data": data})
    
        @staticmethod
        @api_error_handler
        async def route_add_flashcard(request):
            data = await request.json()
            study_db.add_flashcard(
                word=data.get("word", ""),
                meaning=data.get("meaning", ""),
                label=data.get("label", ""),
                other_info=data.get("other_info", ""),
                project_id=data.get("project_id")
            )
            return JSONResponse({"status": "200 <OK>", "message": "Flashcard added"})
    
        @staticmethod
        @api_error_handler
        async def route_check_answer(request):
            data = await request.json()
            req_eval_mode = data.get("eval_mode", "similarity")
            provider, provider_error = ChatbotManager._resolve_provider(data.get("provider"))
            if provider_error:
                return JSONResponse({"status": "400 <Bad Request>", "message": provider_error}, status_code=400)

            api_key, api_key_error = ChatbotManager._resolve_api_key(provider, data.get("api_key"))
            if api_key_error:
                app_logger.warning(f"No valid API key for provider '{provider}'. Falling back to Traditional.")
                model = TraditionalSimilarityModel()
                similarity = await model.calculate_similarity(data.get("ground_truth", ""), data.get("user_answer", ""))
            else:
                eval_model_name = ChatbotManager._resolve_eval_model_name(provider)
                model = AIModelFactory.create(req_eval_mode, provider, api_key, eval_model_name)
                similarity = await model.calculate_similarity(data.get("ground_truth", ""), data.get("user_answer", ""))
                app_logger.info(f"Danh gia bai tap thanh cong bang API cua {provider}")

            return JSONResponse({"status": "200 <OK>", "similarity": float(similarity)})

    class Thinking:
        @staticmethod
        @api_error_handler
        async def route_get_thinking_projects(request):
            return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(study_db.get_thinking_projects())})
    
        @staticmethod
        @api_error_handler
        async def route_add_thinking_project(request):
            data = await request.json()
            app_logger.info(f"Adding/Updating thinking project: {data.get('name')}")
            if "id" in data and "problem_statement" in data and len(data) == 2:
                study_db.update_thinking_project(data["id"], data["problem_statement"])
            else:
                study_db.add_thinking_project(data.get("name", "Untitled"), data.get("problem_statement", ""))
            return JSONResponse({"status": "200 <OK>", "message": "Project saved"})
    
        @staticmethod
        @api_error_handler
        async def route_get_all_knowledge(request):
            return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(study_db.get_all_thinking_knowledge())})
    
        @staticmethod
        @api_error_handler
        async def route_get_thinking_items(request):
            project_id = request.query_params.get("project_id")
            if not project_id:
                return JSONResponse({"status": "400 <Bad Request>", "message": "Missing project_id"}, status_code=400)
            return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(study_db.get_thinking_items(project_id))})
    
        @staticmethod
        @api_error_handler
        async def route_add_thinking_item(request):
            data = await request.json()
            item_id, item_type, project_id = data.get("id"), data.get("type"), data.get("project_id")
            name, description, source_ids = data.get("name", ""), data.get("description", ""), data.get("source_ids")
            is_global = data.get("is_global", 0)

            app_logger.info(f"Request to {'update' if item_id else 'add'} thinking item: {name} (type: {item_type})")
            if description:
                app_logger.info(f"Item Content: {description[:1000]}...")

            if item_id:
                updated_item = study_db.update_thinking_item(item_type, item_id, name, description, source_ids)
                return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(updated_item)})
            else:
                new_item = None
                if item_type == "knowledge": new_item = study_db.add_thinking_knowledge(project_id, name, description, is_global)
                elif item_type == "inference": new_item = study_db.add_thinking_inference(project_id, name, description, source_ids or "", is_global)
                elif item_type == "question": new_item = study_db.add_thinking_question(project_id, name, description, is_global)

                return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(new_item)})

        @staticmethod
        @api_error_handler
        async def route_delete_thinking_project(request):
            data = await request.json()
            project_id = data.get("id")
            if project_id:
                study_db.delete_thinking_project(project_id)
            return JSONResponse({"status": "200 <OK>", "message": "Project deleted"})

        @staticmethod
        @api_error_handler
        async def route_delete_thinking_item(request):
            data = await request.json()
            item_id = data.get("id")
            item_type = data.get("type")
            if item_id and item_type:
                study_db.delete_thinking_item(item_type, item_id)
            return JSONResponse({"status": "200 <OK>", "message": f"{item_type} deleted"})

        @staticmethod
        @api_error_handler
        async def route_toggle_global(request):
            data = await request.json()
            item_id = data.get("id")
            item_type = data.get("type")
            is_global = 1 if data.get("is_global") else 0
            if item_id and item_type:
                study_db.toggle_global_thinking_item(item_type, item_id, is_global)
            return JSONResponse({"status": "200 <OK>", "message": f"Toggled global for {item_type}"})

class ChatbotManager:
    VALID_PROVIDERS = {"gemini", "openai", "openrouter"}

    @staticmethod
    def _load_api_settings():
        try:
            settings_path = SettingsManager.get_settings_path()
            if not os.path.exists(settings_path):
                return {}

            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            api_keys = settings.get("api_keys")
            return api_keys if isinstance(api_keys, dict) else {}
        except Exception as e:
            app_logger.error(f"Error loading API settings: {e}")
            return {}

    @staticmethod
    def _resolve_provider(requested_provider=None):
        provider = (requested_provider or "").strip()
        if provider:
            if provider not in ChatbotManager.VALID_PROVIDERS:
                return None, f"Provider '{provider}' does not exist."
            return provider, None

        settings_provider = ChatbotManager._load_api_settings().get("provider")
        if isinstance(settings_provider, str):
            settings_provider = settings_provider.strip()
            if settings_provider in ChatbotManager.VALID_PROVIDERS:
                return settings_provider, None

        return None, "Provider does not exist."

    @staticmethod
    def _resolve_api_key(provider: str, requested_api_key=None):
        api_key = (requested_api_key or "").strip()
        if api_key:
            return api_key, None

        stored_key = ChatbotManager._load_api_settings().get(provider, "")
        if isinstance(stored_key, str) and stored_key.strip():
            return stored_key.strip(), None

        return None, f"No API key configured for {provider}."

    @staticmethod
    def _resolve_model_name(provider: str, requested_model):
        model_name = (requested_model or "").strip()
        if model_name:
            return model_name, None

        stored_models = ChatbotManager._load_api_settings().get("chat_models", {})
        if isinstance(stored_models, dict):
            stored_model = (stored_models.get(provider) or "").strip()
            if stored_model:
                return stored_model, None

        return None, "Model name does not exist."

    @staticmethod
    def _resolve_eval_model_name(provider: str):
        stored_models = ChatbotManager._load_api_settings().get("eval_models", {})
        if isinstance(stored_models, dict):
            stored_model = (stored_models.get(provider) or "").strip()
            if stored_model:
                return stored_model

        return None

    @staticmethod
    def _resolve_inference_model_name(provider: str):
        stored_models = ChatbotManager._load_api_settings().get("inference_models", {})
        if isinstance(stored_models, dict):
            stored_model = (stored_models.get(provider) or "").strip()
            if stored_model:
                return stored_model

        return None

    @staticmethod
    def _resolve_session_id(raw_session_id):
        if raw_session_id in [None, ""]:
            return None
        try:
            return int(raw_session_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    @api_error_handler
    async def route_get_sessions(request):
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(chat_db.get_sessions())})

    @staticmethod
    @api_error_handler
    async def route_create_session(request):
        data = await request.json()
        session_data = chat_db.create_session(data.get("title"))
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(session_data)})

    @staticmethod
    @api_error_handler
    async def route_get_history(request):
        session_id = ChatbotManager._resolve_session_id(request.query_params.get("session_id"))
        limit = int(request.query_params.get("limit", 10))
        offset = int(request.query_params.get("offset", 0))
        if session_id is None:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Chat session does not exist."}, status_code=400)
        return JSONResponse({"status": "200 <OK>", "data": serialize_to_dict(chat_db.get_messages(session_id, limit=limit, offset=offset))})

    @staticmethod
    @api_error_handler
    async def route_delete_session(request):
        data = await request.json()
        session_id = ChatbotManager._resolve_session_id(data.get("session_id"))
        if session_id is None:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Chat session does not exist."}, status_code=400)
        chat_db.delete_session(session_id)
        return JSONResponse({"status": "200 <OK>", "message": "Chat session deleted"})

    @staticmethod
    @api_error_handler
    async def route_chat(request):
        data = await request.json()
        user_msg = data.get("message", "")
        session_id = ChatbotManager._resolve_session_id(data.get("session_id"))
        if session_id is None:
            return JSONResponse({"status": "400 <Bad Request>", "message": "Chat session does not exist."}, status_code=400)
        provider, provider_error = ChatbotManager._resolve_provider(data.get("provider"))
        if provider_error:
            return JSONResponse({"status": "400 <Bad Request>", "message": provider_error}, status_code=400)

        model_name, model_error = ChatbotManager._resolve_model_name(provider, data.get("model"))
        if model_error:
            return JSONResponse({"status": "400 <Bad Request>", "message": model_error}, status_code=400)

        api_key, api_key_error = ChatbotManager._resolve_api_key(provider)
        if api_key_error:
            return JSONResponse({"status": "400 <Bad Request>", "message": api_key_error}, status_code=400)

        chat_db.add_message(session_id, "user", user_msg)
        history = chat_db.get_messages(session_id, limit=20)

        settings_path = SettingsManager.get_settings_path()
        model_params = {}
        tool_params = {}
        system_prompt = ""
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    s_data = json.load(f)
                    model_params = s_data.get("model_params", {})
                    tool_params = s_data.get("tool_params", {})
                    system_prompt = s_data.get("system_prompt", "")
            except Exception:
                pass

        temperature = float(model_params.get("temperature", 0.7))
        top_k = int(model_params.get("top_k", 40))
        top_p = float(model_params.get("top_p", 0.9))
        max_tool_rounds = int(tool_params.get("max_tool_rounds", 8) or 8)

        chatbot = ChatBot(provider, api_key, model_name, system_prompt, temperature, top_k, top_p, max_tool_rounds=max_tool_rounds)
        try:
            loop = asyncio.get_event_loop()
            reply, tokens_used = await loop.run_in_executor(None, chatbot.send_message, history)

            chat_db.add_message(session_id, "assistant", reply)
            if tokens_used > 0:
                chat_db.add_session_tokens(session_id, tokens_used)
            SettingsManager.save_chat_model(provider, model_name)
            return JSONResponse({"status": "200 <OK>", "reply": reply, "session_id": session_id, "tokens": tokens_used})
        except urllib.error.HTTPError as e:
            return JSONResponse({"status": "500", "message": f"Provider error ({provider}): {e.code} - {e.read().decode()}"}, status_code=500)

class SettingsManager:
    @staticmethod
    def get_settings_path():
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, "state.json")

    @staticmethod
    def init():
        try:
            path = SettingsManager.get_settings_path()
            default_data = {
                "hotkeys": {"block": "ctrl+alt+shift+b", "task": "ctrl+alt+shift+t", "memorize": "ctrl+alt+shift+m"},
                "api_keys": {"provider": "gemini", "gemini": "", "openai": "", "openrouter": "", "chat_models": {"gemini": "", "openai": "", "openrouter": ""}},
                "tool_params": {"max_tool_rounds": 8},
            }

            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            else:
                data = {}

            updated = False
            if "hotkeys" not in data:
                data["hotkeys"] = default_data["hotkeys"]
                updated = True
            else:
                for k, v in default_data["hotkeys"].items():
                    if k not in data["hotkeys"]:
                        data["hotkeys"][k] = v
                        updated = True

            if "api_keys" not in data or not isinstance(data.get("api_keys"), dict):
                data["api_keys"] = default_data["api_keys"]
                updated = True
            else:
                api_keys = data["api_keys"]
                if "provider" not in api_keys:
                    api_keys["provider"] = "gemini"
                    updated = True
                if "eval_mode" not in api_keys:
                    api_keys["eval_mode"] = "similarity"
                    updated = True
                for prov in ["gemini", "openai", "openrouter"]:
                    if prov not in api_keys:
                        api_keys[prov] = ""
                        updated = True
                if "chat_models" not in api_keys or not isinstance(api_keys.get("chat_models"), dict):
                    api_keys["chat_models"] = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini", "openrouter": "google/gemini-2.5-pro"}
                    updated = True
                else:
                    for prov in ["gemini", "openai", "openrouter"]:
                        if prov not in api_keys["chat_models"]:
                            api_keys["chat_models"][prov] = ""
                            updated = True
                            
                if "eval_models" not in api_keys or not isinstance(api_keys.get("eval_models"), dict):
                    api_keys["eval_models"] = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini", "openrouter": "google/gemini-2.5-pro"}
                    updated = True
                else:
                    for prov in ["gemini", "openai", "openrouter"]:
                        if prov not in api_keys["eval_models"]:
                            api_keys["eval_models"][prov] = ""
                            updated = True
                            
                if "inference_models" not in api_keys or not isinstance(api_keys.get("inference_models"), dict):
                    api_keys["inference_models"] = {"gemini": "gemini-2.5-pro", "openai": "gpt-4o", "openrouter": "google/gemini-2.5-pro"}
                    updated = True
                else:
                    for prov in ["gemini", "openai", "openrouter"]:
                        if prov not in api_keys["inference_models"]:
                            api_keys["inference_models"][prov] = ""
                            updated = True

            if "model_params" not in data:
                data["model_params"] = {"temperature": 0.7, "top_k": 40, "top_p": 0.9}
                updated = True
            else:
                params = data["model_params"]
                for k, v in {"temperature": 0.7, "top_k": 40, "top_p": 0.9}.items():
                    if k not in params:
                        params[k] = v
                        updated = True

            if "tool_params" not in data or not isinstance(data.get("tool_params"), dict):
                data["tool_params"] = default_data["tool_params"]
                updated = True
            else:
                tp = data["tool_params"]
                if "max_tool_rounds" not in tp:
                    tp["max_tool_rounds"] = default_data["tool_params"]["max_tool_rounds"]
                    updated = True

            if "system_prompt" not in data:
                data["system_prompt"] = "You are an advanced, helpful AI assistant integrated into the 'Locked' productivity and study application.\nYour primary goals are:\n1. Assist users with their tasks, studying, and technical questions clearly and accurately.\n2. Format your responses using Markdown.\n3. For mathematical equations, use LaTeX. Use single dollar signs ($ ... $) for inline math and double dollar signs ($$ ... $$) for block math. Ensure block math is placed on its own new lines.\n4. When providing code, always use markdown code blocks with the appropriate programming language tag.\n5. When creating flashcards, always use the 'tags' parameter to provide a list of relevant categories/tags to help organize the content.\n6. Be concise but thorough. Ensure your answers are well-structured and easy to read.\n\nUse the provided tools to browse the web or interact with the app's database if the user requests current information, their schedule, or their blocked sites."
                updated = True

            if updated or not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            app_logger.error(f"Settings init error: {e}")

    
    @staticmethod
    def save_chat_model(provider: str, model_name: str):
        try:
            path = SettingsManager.get_settings_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}

            if "api_keys" not in data or not isinstance(data.get("api_keys"), dict):
                data["api_keys"] = {}

            api_keys = data["api_keys"]
            if "chat_models" not in api_keys or not isinstance(api_keys.get("chat_models"), dict):
                api_keys["chat_models"] = {}

            api_keys["chat_models"][provider] = model_name

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            app_logger.error(f"Error saving chat model: {e}")

    @staticmethod
    @api_error_handler
    async def route_get_settings(request):
        path = SettingsManager.get_settings_path()
        data = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        return JSONResponse({"status": "200 <OK>", "data": data})

    @staticmethod
    @api_error_handler
    async def route_save_settings(request):
        data = await request.json()
        path = SettingsManager.get_settings_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return JSONResponse({"status": "200 <OK>", "message": "Settings saved"})


# 2. API Routing
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
os.makedirs(frontend_dir, exist_ok=True) # Äáº£m báº£o thÆ° má»¥c tá»“n táº¡i Ä‘á»ƒ trÃ¡nh lá»—i

routes = [
    Route('/api/block', endpoint=Blocker.route_add_block, methods=['POST']),
    Route('/api/block', endpoint=Blocker.route_delete_block, methods=['DELETE']),
    Route('/api/blocks', endpoint=Blocker.route_get_blocks, methods=['GET']),
    Route('/api/focus/toggle', endpoint=Blocker.FocusMode.route_toggle, methods=['POST']),
    Route('/api/focus/status', endpoint=Blocker.FocusMode.route_get_status, methods=['GET']),
    Route('/api/focus/list', endpoint=Blocker.FocusMode.route_get_list, methods=['GET']),
    Route('/api/focus/list', endpoint=Blocker.FocusMode.route_add_url, methods=['POST']),
    Route('/api/focus/list', endpoint=Blocker.FocusMode.route_delete_url, methods=['DELETE']),
    Route('/api/top-sites', endpoint=Blocker.route_get_top_sites, methods=['GET']),
    Route('/api/events', endpoint=EventManager.route_get_events, methods=['GET']),
    Route('/api/events', endpoint=EventManager.route_add_event, methods=['POST']),
    Route('/api/events', endpoint=EventManager.route_delete_event, methods=['DELETE']),
    Route('/api/study/memorize/projects', endpoint=StudyManager.Memorize.route_get_projects, methods=['GET']),
    Route('/api/study/memorize/projects', endpoint=StudyManager.Memorize.route_add_project, methods=['POST']),
    Route('/api/study/memorize/projects', endpoint=StudyManager.Memorize.route_delete_project, methods=['DELETE']),
    Route('/api/study/memorize/flashcards', endpoint=StudyManager.Memorize.route_get_flashcards, methods=['GET']),
    Route('/api/study/memorize/flashcards', endpoint=StudyManager.Memorize.route_add_flashcard, methods=['POST']),
    Route('/api/study/memorize/flashcards', endpoint=StudyManager.Memorize.route_delete_flashcard, methods=['DELETE']),
    Route('/api/study/memorize/check', endpoint=StudyManager.Memorize.route_check_answer, methods=['POST']),
    Route('/api/study/thinking/projects', endpoint=StudyManager.Thinking.route_get_thinking_projects, methods=['GET']),
    Route('/api/study/thinking/projects', endpoint=StudyManager.Thinking.route_add_thinking_project, methods=['POST']),
    Route('/api/study/thinking/projects', endpoint=StudyManager.Thinking.route_delete_thinking_project, methods=['DELETE']),
    Route('/api/study/thinking/all-knowledge', endpoint=StudyManager.Thinking.route_get_all_knowledge, methods=['GET']),
    Route('/api/study/thinking/items', endpoint=StudyManager.Thinking.route_get_thinking_items, methods=['GET']),
    Route('/api/study/thinking/items', endpoint=StudyManager.Thinking.route_add_thinking_item, methods=['POST']),
    Route('/api/study/thinking/items', endpoint=StudyManager.Thinking.route_delete_thinking_item, methods=['DELETE']),
    Route('/api/study/thinking/global', endpoint=StudyManager.Thinking.route_toggle_global, methods=['POST']),
    Route('/api/settings', endpoint=SettingsManager.route_get_settings, methods=['GET']),
    Route('/api/settings', endpoint=SettingsManager.route_save_settings, methods=['POST']),
    Route('/api/chat/sessions', endpoint=ChatbotManager.route_get_sessions, methods=['GET']),
    Route('/api/chat/sessions', endpoint=ChatbotManager.route_create_session, methods=['POST']),
    Route('/api/chat/sessions', endpoint=ChatbotManager.route_delete_session, methods=['DELETE']),
    Route('/api/chat/history', endpoint=ChatbotManager.route_get_history, methods=['GET']),
    Route('/api/chat', endpoint=ChatbotManager.route_chat, methods=['POST']),
    Route('/', endpoint=Blocker.homepage, methods=['GET']),
    Mount('/static', app=StaticFiles(directory=frontend_dir), name="static")
]

SettingsManager.init()

# 3. Initialize middleware
middleware = [
    Middleware(RequestLoggingMiddleware)
]
app = Starlette(debug=True, routes=routes, middleware=middleware)

# 4. Run server with uvicorn
if __name__ == '__main__':
    uvicorn.run("app:app", host='127.0.0.1', port=8765, reload=True)
