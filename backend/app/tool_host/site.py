"""Website-owned presentation configuration for the Tool Dock."""

from app.tool_host.contracts import ToolManifest

TOOL_ORDER = ("chat_tool", "code_agent_flow_viz", "task_decomposer")
HIDDEN_TOOL_IDS = frozenset({"blank_tool"})


def public_manifests(manifests: list[ToolManifest]) -> list[ToolManifest]:
    visible = [manifest for manifest in manifests if manifest.id not in HIDDEN_TOOL_IDS]
    order = {tool_id: index for index, tool_id in enumerate(TOOL_ORDER)}
    return sorted(
        visible,
        key=lambda manifest: (order.get(manifest.id, len(order)), manifest.name.lower()),
    )
