import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get } from "../lib/api";
import type { ToolManifest } from "../types";

/** A realtime-capable tool is one with at least one realtime operation. */
function transportBadge(tool: ToolManifest): "realtime" | "request-response" {
  return tool.operations.some((op) => op.transport === "realtime")
    ? "realtime"
    : "request-response";
}

/** The Dock: generated entirely from `GET /api/tools`. The backend already
 * hides the Blank example, so no hardcoded visibility list lives here. */
export default function ToolList() {
  const [tools, setTools] = useState<ToolManifest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    get<{ tools: ToolManifest[] }>("/tools")
      .then((res) => {
        if (res.success && res.data) setTools(res.data.tools);
        else setError(res.error?.message ?? "加载工具失败");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status-text">Loading tools...</p>;
  if (error)
    return (
      <div className="tool-list">
        <p className="error-text">{error}</p>
      </div>
    );

  return (
    <div className="tool-list">
      <h1>AI Tools</h1>
      <p className="subtitle">Select a tool to get started</p>
      <div className="tool-grid">
        {tools.map((tool) => (
          <Link key={tool.id} to={`/tools/${tool.id}`} className="tool-card">
            <h3>{tool.name}</h3>
            <p>{tool.description}</p>
            <span className={`tool-mode mode-${transportBadge(tool)}`}>
              {transportBadge(tool)}
            </span>
          </Link>
        ))}
        {tools.length === 0 && (
          <span className="tool-card placeholder">No tools available.</span>
        )}
      </div>
    </div>
  );
}
