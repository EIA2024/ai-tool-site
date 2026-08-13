import type { ToolManifest } from "../types";

/**
 * Shown when a tool declares `ui.kind: "custom"` but no matching frontend
 * plugin UI (`src/tool_plugins/<id>/index.tsx`) exists. It must not crash the
 * whole site — the Dock and every other tool keep working.
 */
export default function PluginMissing({ manifest }: { manifest: ToolManifest }) {
  return (
    <div className="tool-page">
      <h2>{manifest.name}</h2>
      <div className="plugin-missing" role="alert">
        <p>
          该工具声明了自定义 UI（<code>kind: "custom"</code>），但前端没有找到对应的插件
          入口 <code>src/tool_plugins/{manifest.id}/index.tsx</code>。
        </p>
        <p>
          请补充插件的前端入口后重新构建前端；或将后端 manifest 的 <code>ui.kind</code>{" "}
          改为 <code>"schema"</code>，由通用表单渲染。
        </p>
      </div>
    </div>
  );
}
