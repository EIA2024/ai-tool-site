import { useEffect, useMemo, useState } from "react";
import { get } from "../lib/api";
import type { AuditListData, AuditSummaryData } from "../types";

const RECENT_LIMIT = 20;

/** Truncate a logged payload for display; keep it on one line. */
function summarize(data: string | null): string {
  if (!data) return "—";
  const flat = data.replace(/\s+/g, " ").trim();
  return flat.length > 80 ? `${flat.slice(0, 80)}…` : flat;
}

export default function UsagePage() {
  const [summary, setSummary] = useState<AuditSummaryData | null>(null);
  const [recent, setRecent] = useState<AuditListData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      get<AuditSummaryData>("/audit/summary"),
      get<AuditListData>(`/audit/tool-calls?limit=${RECENT_LIMIT}`),
    ])
      .then(([sumRes, listRes]) => {
        if (sumRes.success && sumRes.data) setSummary(sumRes.data);
        if (listRes.success && listRes.data) setRecent(listRes.data);
        if (!sumRes.success) {
          setError(sumRes.error?.message ?? "加载用量数据失败");
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  const totals = useMemo(() => {
    const byTool = summary?.by_tool ?? [];
    const failures = byTool.reduce((acc, t) => acc + t.failures, 0);
    const calls = byTool.reduce((acc, t) => acc + t.calls, 0);
    const successRate = calls > 0 ? Math.round(((calls - failures) / calls) * 100) : 100;
    return { calls, failures, successRate, tools: byTool.length };
  }, [summary]);

  if (loading) return <p className="status-text">Loading usage data...</p>;
  if (error)
    return (
      <div className="usage-page">
        <p className="error-text">{error}</p>
      </div>
    );

  return (
    <div className="usage-page">
      <h1>Usage &amp; Audit</h1>
      <p className="subtitle">Tool-call history and failure rates</p>

      <div className="usage-cards">
        <div className="usage-card">
          <span className="usage-card-label">Total calls</span>
          <span className="usage-card-value">{totals.calls}</span>
        </div>
        <div className="usage-card">
          <span className="usage-card-label">Failures</span>
          <span className="usage-card-value">{totals.failures}</span>
        </div>
        <div className="usage-card">
          <span className="usage-card-label">Success rate</span>
          <span className="usage-card-value">{totals.successRate}%</span>
        </div>
        <div className="usage-card">
          <span className="usage-card-label">Tools</span>
          <span className="usage-card-value">{totals.tools}</span>
        </div>
      </div>

      <h2>Per-tool summary</h2>
      {(summary?.by_tool.length ?? 0) === 0 ? (
        <p className="status-text">No tool calls recorded yet.</p>
      ) : (
        <table className="usage-table">
          <thead>
            <tr>
              <th>Tool</th>
              <th>Calls</th>
              <th>Failures</th>
              <th>Success rate</th>
            </tr>
          </thead>
          <tbody>
            {(summary?.by_tool ?? []).map((t) => {
              const rate =
                t.calls > 0 ? Math.round(((t.calls - t.failures) / t.calls) * 100) : 100;
              return (
                <tr key={t.tool_id}>
                  <td>
                    <code>{t.tool_id}</code>
                  </td>
                  <td>{t.calls}</td>
                  <td>{t.failures}</td>
                  <td>
                    <div className="usage-rate">
                      <div
                        className="usage-rate-bar"
                        style={{ width: `${rate}%` }}
                        aria-hidden="true"
                      />
                      <span>{rate}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <h2>Recent calls</h2>
      {(recent?.records.length ?? 0) === 0 ? (
        <p className="status-text">No recent calls.</p>
      ) : (
        <table className="usage-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Tool</th>
              <th>Result</th>
              <th>Input</th>
            </tr>
          </thead>
          <tbody>
            {(recent?.records ?? []).map((r) => (
              <tr key={r.id}>
                <td className="usage-time">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                </td>
                <td>
                  <code>{r.tool_id}</code>
                </td>
                <td>
                  <span className={`usage-badge usage-${r.success ? "ok" : "fail"}`}>
                    {r.success ? "ok" : "failed"}
                  </span>
                </td>
                <td className="usage-input">{summarize(r.input_data)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
