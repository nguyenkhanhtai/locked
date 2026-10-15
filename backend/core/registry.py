import os
import sys
import importlib
import pkgutil
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger("core.registry")

@dataclass
class ModuleMetadata:
    id: str
    title: str
    icon: str
    url: str
    order: int = 100
    description: str = ""

class ModuleRegistry:
    """
    Central registry for feature modules and plugin auto-discovery.
    Handles route discovery from `modules/*/router.py` and provides navigation
    metadata to the frontend sidebar dynamically.
    """
    _modules: Dict[str, ModuleMetadata] = {}

    @classmethod
    def register(cls, meta: ModuleMetadata):
        """Registers metadata for a feature module."""
        cls._modules[meta.id] = meta
        logger.info(f"Registered module: '{meta.title}' ({meta.id}) -> {meta.url}")

    @classmethod
    def get_modules(cls) -> List[ModuleMetadata]:
        """Returns all registered modules sorted by their display order."""
        return sorted(cls._modules.values(), key=lambda m: (m.order, m.title))

    @classmethod
    def get_module(cls, module_id: str) -> Optional[ModuleMetadata]:
        return cls._modules.get(module_id)

    @classmethod
    def discover_and_register(cls, app, modules_package="modules"):
        """
        Scans `modules/` directory, imports each module's router,
        and registers their routes onto the Starlette app.
        """
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        try:
            mod_pkg = importlib.import_module(modules_package)
        except ImportError as e:
            logger.error(f"Could not import {modules_package}: {e}")
            return []

        discovered = []
        for _, name, is_pkg in pkgutil.iter_modules(mod_pkg.__path__):
            if is_pkg:
                router_mod_name = f"{modules_package}.{name}.router"
                try:
                    router_mod = importlib.import_module(router_mod_name)
                    if hasattr(router_mod, "routes"):
                        for route in router_mod.routes:
                            app.router.routes.append(route)
                        logger.info(f"Attached {len(router_mod.routes)} routes from module '{name}'")
                    discovered.append(name)
                except Exception as e:
                    logger.error(f"Failed to load module router '{router_mod_name}': {e}", exc_info=True)

        return discovered

    @classmethod
    def clear(cls):
        """Clears registered modules (useful for testing)."""
        cls._modules.clear()

