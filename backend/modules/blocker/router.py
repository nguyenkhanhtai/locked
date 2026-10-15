from starlette.responses import JSONResponse
from starlette.routing import Route
from typing import List, Optional
import logging

from core.registry import ModuleRegistry, ModuleMetadata
from .repository import BlockerRepository, HardLockActiveError, MAX_DURATION_MINUTES

logger = logging.getLogger("modules.blocker.router")

# Register module metadata for dynamic discovery & navigation
ModuleRegistry.register(ModuleMetadata(
    id="blocker",
    title="Focus Blocker",
    icon="shield",
    url="/blocker",
    order=4,
    description="Khóa website và đường link gây xao nhãng với cơ chế khóa cứng không thể xóa (tối đa 6 giờ)"
))

default_blocker_repo = BlockerRepository()


def get_blocker_repo() -> BlockerRepository:
    try:
        from core.db import DatabaseManager
        active_db = DatabaseManager.get_db_path()
        if default_blocker_repo.db_path != active_db:
            return BlockerRepository(active_db)
    except Exception:
        pass
    return default_blocker_repo


async def blocker_page(request):
    repo = get_blocker_repo()
    templates = request.app.state.templates
    modules = ModuleRegistry.get_modules()
    active_rules = [r.to_dict() for r in repo.get_active_rules()]
    all_rules = [r.to_dict() for r in repo.get_all_rules()]
    return templates.TemplateResponse(
        request,
        "main/blocker.html",
        {
            "modules": modules,
            "active_rules": active_rules,
            "all_rules": all_rules,
            "max_duration": MAX_DURATION_MINUTES
        }
    )


async def blocked_intervention_page(request):
    repo = get_blocker_repo()
    templates = request.app.state.templates
    modules = ModuleRegistry.get_modules()
    target_url = request.query_params.get("target") or request.query_params.get("url") or ""
    matched_rule = repo.check_url_blocked(target_url) if target_url else None
    
    # If no specific match was found by URL, fallback to the nearest active rule if any exist
    if not matched_rule:
        active = repo.get_active_rules()
        if active:
            matched_rule = active[0]

    return templates.TemplateResponse(
        request,
        "main/blocked_page.html",
        {
            "modules": modules,
            "target_url": target_url,
            "rule": matched_rule.to_dict() if matched_rule else None
        }
    )


async def route_get_active_rules(request):
    repo = get_blocker_repo()
    rules = [r.to_dict() for r in repo.get_active_rules()]
    return JSONResponse({"status": "200 <OK>", "data": rules})


async def route_get_all_rules(request):
    repo = get_blocker_repo()
    rules = [r.to_dict() for r in repo.get_all_rules()]
    return JSONResponse({"status": "200 <OK>", "data": rules})


async def route_add_rule(request):
    repo = get_blocker_repo()
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Dữ liệu JSON không hợp lệ"}, status_code=400)

    raw_url = data.get("url", "").strip()
    if not raw_url:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Vui lòng nhập đường dẫn hoặc tên miền muốn chặn."}, status_code=400)

    try:
        duration_minutes = int(data.get("duration_minutes", 60))
    except (ValueError, TypeError):
        return JSONResponse({"status": "400 <Bad Request>", "message": "Thời gian khóa không hợp lệ."}, status_code=400)

    match_type = data.get("match_type", "domain")
    reason = data.get("reason", "")

    try:
        rule = repo.add_rule(
            raw_url=raw_url,
            duration_minutes=duration_minutes,
            match_type=match_type,
            reason=reason
        )
        return JSONResponse({
            "status": "201 <Created>",
            "message": f"Đã kích hoạt khóa cứng cho '{rule.url_pattern}' trong {duration_minutes} phút! Đã đặt là không xóa được.",
            "data": rule.to_dict()
        }, status_code=201)
    except ValueError as e:
        return JSONResponse({"status": "400 <Bad Request>", "message": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error adding blocker rule: {e}", exc_info=True)
        return JSONResponse({"status": "500 <Internal Server Error>", "message": f"Lỗi hệ thống: {str(e)}"}, status_code=500)


async def route_delete_rule(request):
    repo = get_blocker_repo()
    rule_id_str = request.path_params.get("id") or request.query_params.get("id")
    if not rule_id_str:
        return JSONResponse({"status": "400 <Bad Request>", "message": "Thiếu ID quy tắc cần xóa."}, status_code=400)

    try:
        rule_id = int(rule_id_str)
    except ValueError:
        return JSONResponse({"status": "400 <Bad Request>", "message": "ID quy tắc không hợp lệ."}, status_code=400)

    try:
        success = repo.delete_rule(rule_id)
        if not success:
            return JSONResponse({"status": "404 <Not Found>", "message": "Không tìm thấy quy tắc này."}, status_code=404)
        return JSONResponse({"status": "200 <OK>", "message": "Đã xóa quy tắc khỏi lịch sử."})
    except HardLockActiveError as e:
        return JSONResponse({
            "status": "403 <Forbidden>",
            "message": str(e),
            "locked": True
        }, status_code=403)
    except Exception as e:
        logger.error(f"Error deleting rule: {e}", exc_info=True)
        return JSONResponse({"status": "500 <Internal Server Error>", "message": str(e)}, status_code=500)


async def route_check_url(request):
    repo = get_blocker_repo()
    url = request.query_params.get("url", "").strip()
    if not url:
        return JSONResponse({"status": "200 <OK>", "data": {"blocked": False, "rule": None}})

    rule = repo.check_url_blocked(url)
    return JSONResponse({
        "status": "200 <OK>",
        "data": {
            "blocked": rule is not None,
            "rule": rule.to_dict() if rule else None
        }
    })


# Exported routes for auto-discovery by ModuleRegistry
routes: List[Route] = [
    Route('/blocker', endpoint=blocker_page, methods=['GET']),
    Route('/blocked', endpoint=blocked_intervention_page, methods=['GET']),
    Route('/api/blocker/rules', endpoint=route_get_active_rules, methods=['GET']),
    Route('/api/blocker/rules', endpoint=route_add_rule, methods=['POST']),
    Route('/api/blocker/rules/{id:int}', endpoint=route_delete_rule, methods=['DELETE']),
    Route('/api/blocker/delete', endpoint=route_delete_rule, methods=['DELETE']),
    Route('/api/blocker/all', endpoint=route_get_all_rules, methods=['GET']),
    Route('/api/blocker/check', endpoint=route_check_url, methods=['GET']),
]
