"""Filesystem package discovery for development-time tool plugins."""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

from app.tool_host.contracts import ToolPlugin
from app.tool_host.registry import ToolRegistry

DEFAULT_PLUGIN_PACKAGE = "app.tool_plugins"


def discover_plugins(package_name: str = DEFAULT_PLUGIN_PACKAGE) -> ToolRegistry:
    package = importlib.import_module(package_name)
    registry = ToolRegistry()
    discovered = sorted(
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.ispkg and not module.name.startswith("_")
    )
    for name in discovered:
        module_name = f"{package_name}.{name}.plugin"
        module = importlib.import_module(module_name)
        plugin = getattr(module, "plugin", None)
        if not isinstance(plugin, ToolPlugin):
            raise TypeError(f"{module_name} must export 'plugin: ToolPlugin'")
        registry.register(plugin)
    if len(registry) == 0:
        raise RuntimeError(f"no tool plugins found in {package_name}")
    return registry


@lru_cache(maxsize=1)
def get_registry() -> ToolRegistry:
    return discover_plugins()
