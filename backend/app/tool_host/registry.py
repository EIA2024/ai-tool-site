"""Validated in-memory registry for discovered tool plugins."""

from app.tool_host.contracts import ToolManifest, ToolPlugin


class ToolRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, ToolPlugin] = {}

    def register(self, plugin: ToolPlugin) -> None:
        manifest = plugin.manifest()
        if manifest.id in self._plugins:
            raise ValueError(f"duplicate tool id: {manifest.id}")
        self._plugins[manifest.id] = plugin

    def get(self, tool_id: str) -> ToolPlugin | None:
        return self._plugins.get(tool_id)

    def manifests(self) -> list[ToolManifest]:
        return [plugin.manifest() for plugin in self._plugins.values()]

    def __len__(self) -> int:
        return len(self._plugins)
