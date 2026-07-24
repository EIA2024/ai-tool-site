import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get } from "../lib/api";
import type { ToolMeta } from "../types";

export default function ToolList() {
  const [tools, setTools] = useState<ToolMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<{ tools: ToolMeta[] }>("/tools")
      .then((res) => {
        if (res.success && res.data) {
          setTools(res.data.tools);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status-text">Loading tools...</p>;

  return (
    <div className="tool-list">
      <h1>AI Tools</h1>
      <p className="subtitle">Select a tool to get started</p>
      <div className="tool-grid">
        {tools.map((tool) => (
          <Link
            key={tool.tool_id}
            to={`/tools/${tool.tool_id}`}
            className="tool-card"
          >
            <h3>{tool.name}</h3>
            <p>{tool.description}</p>
            <span className={`tool-mode mode-${tool.mode}`}>{tool.mode}</span>
          </Link>
        ))}
        <span className="tool-card placeholder">More tools coming soon...</span>
      </div>
    </div>
  );
}
