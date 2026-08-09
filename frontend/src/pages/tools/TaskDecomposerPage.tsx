import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { get, invokeTool } from "../../lib/api";
import type {
  AnalyzeTaskData,
  HistoryRecord,
  ListHistoryData,
  PublicConfig,
  TaskAnalysis,
} from "../../types";

const DRAFT_KEY = "taskDecomposer.aiDraft";

interface Draft {
  raw_task: string;
  context: string;
  task_type: string;
  model: string;
  risk_hints: string[];
}

function getDefaultDraft(): Draft {
  return {
    raw_task: "",
    context: "",
    task_type: "feature",
    model: "deepseek-v4-flash",
    risk_hints: [],
  };
}

function loadDraft(): Draft {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return getDefaultDraft();
    return { ...getDefaultDraft(), ...JSON.parse(raw) };
  } catch {
    localStorage.removeItem(DRAFT_KEY);
    return getDefaultDraft();
  }
}

function saveDraft(draft: Draft) {
  if (!draft.raw_task && !draft.context && draft.risk_hints.length === 0) {
    localStorage.removeItem(DRAFT_KEY);
    return;
  }
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

const RISK_LABELS: Record<string, string> = {
  data_loss: "可能写入、覆盖或删除数据",
  compatibility: "可能影响旧数据或兼容性",
  permission: "涉及权限、身份或越权风险",
  browser_api: "依赖浏览器、本地文件或下载能力",
  external_service: "依赖外部服务或网络",
};

export default function TaskDecomposerPage() {
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [apiKey, setApiKey] = useState("");
  const [models, setModels] = useState<string[]>(["deepseek-v4-flash", "deepseek-v4-pro"]);
  const [defaultModel, setDefaultModel] = useState("deepseek-v4-flash");
  const [analysis, setAnalysis] = useState<TaskAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [outputState, setOutputState] = useState("等待分析");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [historyFilter, setHistoryFilter] = useState("");
  const toastRef = useRef<HTMLDivElement>(null);

  // ── Model list is the backend's single source of truth ──
  useEffect(() => {
    get<PublicConfig>("/config")
      .then((res) => {
        if (res.success && res.data) {
          const cfg = res.data;
          setModels(cfg.deepseek_models);
          setDefaultModel(cfg.deepseek_default_model);
          setDraft((prev) =>
            cfg.deepseek_models.includes(prev.model)
              ? prev
              : { ...prev, model: cfg.deepseek_default_model }
          );
        }
      })
      .catch(() => {
        // Fall back to the hardcoded defaults above.
      });
  }, []);

  // ── Toast ──
  const showToast = useCallback((msg: string) => {
    const el = toastRef.current;
    if (!el) return;
    el.textContent = msg;
    el.classList.add("td-toast-show");
    setTimeout(() => el.classList.remove("td-toast-show"), 1800);
  }, []);

  // ── Persist draft to localStorage on change ──
  useEffect(() => {
    saveDraft(draft);
  }, [draft]);

  // ── History fetch ──
  const fetchHistory = useCallback(async () => {
    try {
      const res = await invokeTool<ListHistoryData>("task_decomposer", {
        action: "list_history",
        task_type: historyFilter || undefined,
      });
      if (res.success && res.data) {
        setHistory(res.data.records);
      }
    } catch {
      // History fetch failure is non-critical
    }
  }, [historyFilter]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // ── Field helpers ──
  const updateField = (field: keyof Draft, value: string) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const toggleRiskHint = (value: string) => {
    setDraft((prev) => {
      const hints = prev.risk_hints.includes(value)
        ? prev.risk_hints.filter((h) => h !== value)
        : [...prev.risk_hints, value];
      return { ...prev, risk_hints: hints };
    });
  };

  // ── Sample ──
  const loadSample = () => {
    setDraft({
      raw_task: "给历史训练记录增加 JSON 导入功能，导入前要确认，不能覆盖现有历史，坏文件要提示。",
      context: "项目是本地 HTML 练习工具，历史记录保存在 localStorage。上一轮已经支持 JSON / Markdown 导出。",
      task_type: "feature",
      model: "deepseek-v4-flash",
      risk_hints: ["data_loss", "compatibility", "browser_api"],
    });
    showToast("示例已载入");
  };

  // ── Analyze ──
  const analyzeTask = async () => {
    const raw_task = draft.raw_task.trim();
    if (!raw_task) {
      showToast("请先输入原始任务");
      return;
    }

    setAnalysis(null);
    setError("");
    setOutputState("模型分析中");
    setAnalyzing(true);

    try {
      const res = await invokeTool<AnalyzeTaskData>(
        "task_decomposer",
        {
          action: "analyze_task",
          raw_task,
          context: draft.context,
          task_type: draft.task_type,
          model: draft.model,
          risk_hints: draft.risk_hints,
          session_api_key: apiKey || undefined,
        },
        { timeoutMs: 90_000 } // DeepSeek analysis can take a while
      );
      if (res.success && res.data) {
        setAnalysis(res.data.analysis);
        setOutputState("已完成");
        showToast("任务卡已生成");
        fetchHistory();
      } else {
        const msg = res.error?.message ?? "分析失败";
        setError(msg);
        setOutputState("失败");
        showToast(msg);
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : `请求失败：${String(err)}`;
      setError(msg);
      setOutputState("失败");
      showToast(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Copy Markdown ──
  const copyMarkdown = () => {
    if (!analysis) {
      showToast("请先生成任务卡");
      return;
    }
    const md = buildMarkdown(analysis);
    navigator.clipboard
      .writeText(md)
      .then(() => showToast("Markdown 已复制"))
      .catch(() => {
        const area = document.createElement("textarea");
        area.value = md;
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        area.remove();
        showToast(ok ? "Markdown 已复制" : "复制失败，请手动选择");
      });
  };

  // ── Clear ──
  const clearAll = () => {
    setDraft(getDefaultDraft());
    setAnalysis(null);
    setError("");
    setOutputState("等待分析");
    showToast("已清空");
  };

  // ── History interactions ──
  const viewHistory = (record: HistoryRecord) => {
    setAnalysis(record.structured_output);
    setOutputState("已完成（历史）");
    setError("");
  };

  const deleteHistory = async (id: string) => {
    try {
      const res = await invokeTool("task_decomposer", {
        action: "delete_history",
        id,
      });
      if (res.success) {
        setHistory((prev) => prev.filter((r) => r.id !== id));
        showToast("已删除");
      }
    } catch {
      showToast("删除失败");
    }
  };

  return (
    <div className="td-page">
      <div className="td-shell">
        {/* Back link */}
        <Link to="/" className="td-back-link">← Back to Tools</Link>

        {/* Top bar */}
        <header className="td-topbar">
          <div>
            <p className="td-eyebrow">DeepSeek 驱动 / 非流式任务分析</p>
            <h1>Task Decomposer</h1>
            <p>输入一句模糊任务，由后端调用 DeepSeek 分析成可执行任务卡。</p>
          </div>
          <section className="td-key-panel">
            <p className="td-eyebrow">DeepSeek API Key</p>
            <div className="td-key-grid">
              <div className="td-field" style={{ marginBottom: 0 }}>
                <label htmlFor="tdApiKey">临时 Key（留空使用服务器 .env）</label>
                <input
                  id="tdApiKey"
                  type="password"
                  autoComplete="off"
                  placeholder="sk-..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
            </div>
            <p>
              <span
                className={`td-status-pill${apiKey ? "" : " td-status-pill-missing"}`}
              >
                {apiKey ? "使用临时 Key" : "使用服务器 Key（如已配置）"}
              </span>
            </p>
          </section>
        </header>

        {/* Workspace */}
        <section className="td-workspace">
          {/* Left: Input */}
          <section className="td-panel">
            <div className="td-panel-head">
              <h2>输入</h2>
              <button className="td-btn" type="button" onClick={loadSample}>
                载入示例
              </button>
            </div>
            <div className="td-panel-body">
              <div className="td-field">
                <label htmlFor="rawTask">原始任务</label>
                <textarea
                  id="rawTask"
                  placeholder="例如：帮我做一个 JSON 导入功能，但不能覆盖已有历史。"
                  value={draft.raw_task}
                  onChange={(e) => updateField("raw_task", e.target.value)}
                />
              </div>
              <div className="td-field">
                <label htmlFor="context">仓库 / 模块背景</label>
                <textarea
                  id="context"
                  placeholder="例如：本地 HTML 工具，历史记录保存在 localStorage，上一轮已经支持导出。"
                  value={draft.context}
                  onChange={(e) => updateField("context", e.target.value)}
                />
              </div>
              <div className="td-grid-2">
                <div className="td-field">
                  <label htmlFor="taskType">任务类型</label>
                  <select
                    id="taskType"
                    value={draft.task_type}
                    onChange={(e) => updateField("task_type", e.target.value)}
                  >
                    <option value="feature">功能迭代</option>
                    <option value="bugfix">Bug 修复</option>
                    <option value="review">代码审查</option>
                    <option value="refactor">重构计划</option>
                    <option value="test">测试补强</option>
                  </select>
                </div>
                <div className="td-field">
                  <label htmlFor="model">模型</label>
                  <select
                    id="model"
                    value={draft.model}
                    onChange={(e) => updateField("model", e.target.value)}
                  >
                    {models.length === 0 && <option value="">加载中...</option>}
                    {models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                        {m === defaultModel ? " (默认)" : ""}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="td-field">
                <label>风险提示</label>
                <div className="td-risk-list" id="tdRiskList">
                  {Object.entries(RISK_LABELS).map(([value, label]) => (
                    <label key={value} className="td-risk-option">
                      <input
                        type="checkbox"
                        value={value}
                        checked={draft.risk_hints.includes(value)}
                        onChange={() => toggleRiskHint(value)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="td-actions">
                <button
                  className="td-btn td-btn-primary"
                  type="button"
                  onClick={analyzeTask}
                  disabled={analyzing}
                >
                  {analyzing ? "分析中..." : "分析任务"}
                </button>
                <button className="td-btn" type="button" onClick={copyMarkdown}>
                  复制 Markdown
                </button>
                <button className="td-btn td-btn-warning" type="button" onClick={clearAll}>
                  清空
                </button>
              </div>
            </div>
          </section>

          {/* Right: Output + History */}
          <div>
            <section className="td-panel">
              <div className="td-panel-head">
                <h2>输出</h2>
                <span className="td-eyebrow">{outputState}</span>
              </div>
              <div className="td-flow-ruler">
                <span>Goal</span>
                <span>Context</span>
                <span>Constraints</span>
                <span>Done when</span>
                <span>Failure</span>
                <span>Verify</span>
              </div>
              <div className="td-task-card">
                {!analysis && !error && (
                  <div className="td-empty">
                    启动后端，配置 DeepSeek API Key，然后点击"分析任务"。
                  </div>
                )}
                {error && <div className="td-error">{error}</div>}
                {analysis && (
                  <>
                    <section className="td-section">
                      <h3>
                        Goal / {analysis.risk_level} / {draft.model}
                      </h3>
                      <p>{analysis.goal}</p>
                    </section>
                    {renderListSection("Context", analysis.context)}
                    {renderListSection("Constraints", analysis.constraints)}
                    {renderListSection("Done when", analysis.done_when)}
                    {renderListSection("Failure cases", analysis.failure_cases)}
                    {renderListSection("Verification", analysis.verification)}
                    {renderListSection(
                      "Missing questions",
                      analysis.missing_questions.length
                        ? analysis.missing_questions
                        : ["暂无"]
                    )}
                    {renderListSection(
                      "Non-goals",
                      analysis.non_goals.length ? analysis.non_goals : ["暂无"]
                    )}
                    <section className="td-section">
                      <h3>Prompt 给 Coding Agent</h3>
                      <pre>{analysis.agent_prompt}</pre>
                    </section>
                  </>
                )}
              </div>
            </section>

            {/* History */}
            <section className="td-history-section">
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                <h3>分析历史</h3>
                <select
                  value={historyFilter}
                  onChange={(e) => setHistoryFilter(e.target.value)}
                  style={{
                    border: "1px solid var(--td-line)",
                    borderRadius: 4,
                    padding: "4px 8px",
                    fontSize: 12,
                    background: "var(--td-panel)",
                    color: "var(--td-ink)",
                  }}
                >
                  <option value="">全部类型</option>
                  <option value="feature">功能迭代</option>
                  <option value="bugfix">Bug 修复</option>
                  <option value="review">代码审查</option>
                  <option value="refactor">重构计划</option>
                  <option value="test">测试补强</option>
                </select>
              </div>
              <div className="td-history-list">
                {history.length === 0 && (
                  <div className="td-history-empty">暂无分析记录</div>
                )}
                {history.map((r) => (
                  <div
                    key={r.id}
                    className="td-history-item"
                    onClick={() => viewHistory(r)}
                  >
                    <div className="td-history-meta">
                      <span className="td-history-type">{r.task_type}</span>
                      <span className="td-history-task">{r.raw_task}</span>
                      <span className="td-history-date">
                        {r.created_at
                          ? new Date(r.created_at).toLocaleString("zh-CN")
                          : ""}
                      </span>
                    </div>
                    <button
                      className="td-history-del"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteHistory(r.id);
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </section>
      </div>

      <div ref={toastRef} className="td-toast" role="status" aria-live="polite" />
    </div>
  );
}

// ── Helper components ──

function renderListSection(title: string, items: string[]) {
  return (
    <section className="td-section">
      <h3>{title}</h3>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function buildMarkdown(analysis: TaskAnalysis): string {
  const lines = [
    "# Coding Agent 任务卡",
    "",
    "## Goal",
    analysis.goal,
    "",
    "## Context",
    ...analysis.context.map((i) => `- ${i}`),
    "",
    "## Constraints",
    ...analysis.constraints.map((i) => `- ${i}`),
    "",
    "## Done when",
    ...analysis.done_when.map((i) => `- ${i}`),
    "",
    "## Failure cases",
    ...analysis.failure_cases.map((i) => `- ${i}`),
    "",
    "## Verification",
    ...analysis.verification.map((i) => `- ${i}`),
    "",
    "## Missing questions",
    ...(analysis.missing_questions.length
      ? analysis.missing_questions
      : ["暂无"]
    ).map((i) => `- ${i}`),
    "",
    "## Non-goals",
    ...(analysis.non_goals.length ? analysis.non_goals : ["暂无"]).map(
      (i) => `- ${i}`
    ),
    "",
    "## Prompt 给 Coding Agent",
    "```text",
    analysis.agent_prompt,
    "```",
  ];
  return lines.join("\n");
}
