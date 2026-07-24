import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "../../lib/api";
import type {
  ListRecordsData,
  PracticeRecord,
  SaveRecordData,
  StageDefinition,
} from "../../types";

/* ── 9-Stage Workflow Definition ── */

const STAGES: StageDefinition[] = [
  {
    key: "goal_setting",
    number: 1,
    title: "Goal Setting & Task Decomposition",
    goals: [
      "Clearly define what you want the Coding Agent to accomplish",
      "Break the goal into small, testable sub-tasks",
      "Prioritize tasks and identify dependencies",
    ],
    promptTemplate:
      "I need to {task}. Please help me break this down into actionable steps.\n\nConstraints:\n- {constraints}\n\nExpected outcome:\n- {outcome}",
    variables: ["task", "constraints", "outcome"],
    checklist: [
      "Goal is specific and measurable",
      "Sub-tasks are independent where possible",
      "Priority order is clear",
    ],
    commonErrors: [
      "Goal too vague — agent produces unfocused output",
      "Too many tasks at once — exceeds context window",
    ],
    completionCriteria: [
      "A list of 3–7 concrete sub-tasks",
      "Each sub-task has a clear definition of done",
    ],
  },
  {
    key: "context_gathering",
    number: 2,
    title: "Context Gathering",
    goals: [
      "Provide all relevant background information",
      "Share codebase structure, file paths, and conventions",
      "Include examples of expected input/output",
    ],
    promptTemplate:
      "Here is the relevant context:\n\nProject structure:\n{project_structure}\n\nKey files:\n{key_files}\n\nCurrent state:\n{current_state}\n\n{additional_context}",
    variables: ["project_structure", "key_files", "current_state", "additional_context"],
    checklist: [
      "All relevant file paths are included",
      "Existing patterns and conventions are described",
      "Error messages or logs are attached if relevant",
    ],
    commonErrors: [
      "Too little context — agent makes wrong assumptions",
      "Irrelevant context — wastes tokens and confuses the agent",
    ],
    completionCriteria: [
      "Agent can answer basic questions about the codebase",
      "No obvious gaps in the provided context",
    ],
  },
  {
    key: "solution_design",
    number: 3,
    title: "Solution Design",
    goals: [
      "Design the architecture or approach before coding",
      "Evaluate trade-offs between different solutions",
      "Get agent feedback on the proposed design",
    ],
    promptTemplate:
      "I need to design a solution for {problem}.\n\nRequirements:\n- {requirement_1}\n- {requirement_2}\n\nConstraints:\n- {constraints}\n\nPlease propose 2–3 approaches with trade-offs.",
    variables: ["problem", "requirement_1", "requirement_2", "constraints"],
    checklist: [
      "At least 2 alternative approaches considered",
      "Trade-offs are documented",
      "Design aligns with existing architecture",
    ],
    commonErrors: [
      "Jumping straight to code without design",
      "Over-engineering — solving problems that don't exist yet",
    ],
    completionCriteria: [
      "A clear design decision with rationale",
      "Implementation plan for the chosen approach",
    ],
  },
  {
    key: "implementation",
    number: 4,
    title: "Implementation (Coding)",
    goals: [
      "Write clean, maintainable code",
      "Follow project conventions and style guide",
      "Include error handling and logging",
    ],
    promptTemplate:
      "Please implement {feature} following these specifications:\n\nDesign:\n{design}\n\nFile to modify:\n{file_path}\n\nConventions:\n- Use {language} with {framework}\n- Follow existing patterns in {reference_file}\n- Add error handling for edge cases",
    variables: ["feature", "design", "file_path", "language", "framework", "reference_file"],
    checklist: [
      "Code compiles without errors",
      "Follows project style guide",
      "Includes appropriate error handling",
      "No debug code or console.log leftovers",
    ],
    commonErrors: [
      "Not following existing patterns — inconsistent code style",
      "Missing edge case handling",
      "Overly complex solution for a simple problem",
    ],
    completionCriteria: [
      "Code compiles and passes linting",
      "All sub-tasks from the design are addressed",
    ],
  },
  {
    key: "testing_debugging",
    number: 5,
    title: "Testing & Debugging",
    goals: [
      "Write tests for the new functionality",
      "Verify existing tests still pass",
      "Debug any failures systematically",
    ],
    promptTemplate:
      "Please write tests for {component}.\n\nTest requirements:\n- {test_requirement_1}\n- {test_requirement_2}\n\nEdge cases to cover:\n- {edge_case_1}\n- {edge_case_2}\n\nTesting framework: {test_framework}",
    variables: [
      "component",
      "test_requirement_1",
      "test_requirement_2",
      "edge_case_1",
      "edge_case_2",
      "test_framework",
    ],
    checklist: [
      "Happy path is covered",
      "Error/edge cases are covered",
      "Tests are deterministic (no flaky tests)",
      "Existing tests still pass",
    ],
    commonErrors: [
      "Testing implementation details instead of behavior",
      "Missing negative test cases",
      "Flaky tests due to shared state or timing",
    ],
    completionCriteria: [
      "Test coverage for the new code is adequate",
      "All tests pass consistently",
    ],
  },
  {
    key: "code_review",
    number: 6,
    title: "Code Review",
    goals: [
      "Review the agent-generated code for quality",
      "Check for security issues and performance concerns",
      "Verify adherence to project standards",
    ],
    promptTemplate:
      "Please review the following code changes:\n\nFiles changed:\n{files_changed}\n\nDiff:\n{diff}\n\nFocus on:\n- Correctness\n- Security vulnerabilities\n- Performance\n- Adherence to {coding_standards}",
    variables: ["files_changed", "diff", "coding_standards"],
    checklist: [
      "No security vulnerabilities introduced",
      "No performance regressions",
      "Code is readable and well-structured",
      "No unnecessary dependencies",
    ],
    commonErrors: [
      "Rubber-stamping without actually reviewing",
      "Missing subtle logic errors in large diffs",
    ],
    completionCriteria: [
      "All review comments are resolved",
      "Code meets the team's quality bar",
    ],
  },
  {
    key: "documentation",
    number: 7,
    title: "Documentation",
    goals: [
      "Document what was built and why",
      "Update README, API docs, or inline comments",
      "Include usage examples for other developers",
    ],
    promptTemplate:
      "Please document {feature}.\n\nContext:\n- What it does: {description}\n- Why it was built: {rationale}\n- How to use: {usage}\n\nFormat: {doc_format}\n\nInclude:\n- API reference\n- Code examples\n- Configuration options",
    variables: ["feature", "description", "rationale", "usage", "doc_format"],
    checklist: [
      "Purpose is clearly explained",
      "Usage examples are runnable",
      "Configuration options are documented",
    ],
    commonErrors: [
      "Documenting what instead of why",
      "Outdated docs after code changes",
      "Missing setup or prerequisite steps",
    ],
    completionCriteria: [
      "A developer new to the feature can use it from the docs",
    ],
  },
  {
    key: "deployment_release",
    number: 8,
    title: "Deployment & Release",
    goals: [
      "Prepare the changes for deployment",
      "Write release notes or changelog entries",
      "Verify the deployment process",
    ],
    promptTemplate:
      "Please help me prepare the release for {version}.\n\nChanges included:\n{changes}\n\nDeployment target:\n{target}\n\nRollback plan:\n{rollback_plan}\n\nChecklist:\n- Database migrations: {migrations}\n- Environment variables: {env_vars}\n- Breaking changes: {breaking_changes}",
    variables: [
      "version",
      "changes",
      "target",
      "rollback_plan",
      "migrations",
      "env_vars",
      "breaking_changes",
    ],
    checklist: [
      "Database migrations are reversible",
      "Release notes are accurate",
      "Rollback plan is in place",
      "Smoke tests pass on staging",
    ],
    commonErrors: [
      "Forgetting to document breaking changes",
      "Missing environment variable updates",
    ],
    completionCriteria: [
      "Release is deployed to target environment",
      "Smoke tests pass in production",
    ],
  },
  {
    key: "reflection_iteration",
    number: 9,
    title: "Reflection & Iteration",
    goals: [
      "Review what worked well and what didn't",
      "Identify improvements for the next iteration",
      "Update prompt strategies based on experience",
    ],
    promptTemplate:
      "Let me reflect on this Coding Agent session.\n\nWhat went well:\n{went_well}\n\nWhat could be improved:\n{improvements}\n\nPrompt adjustments for next time:\n{prompt_adjustments}\n\nKey takeaways:\n{takeaways}",
    variables: ["went_well", "improvements", "prompt_adjustments", "takeaways"],
    checklist: [
      "Honest assessment of agent performance",
      "Concrete prompt improvements identified",
      "Patterns to repeat are captured",
    ],
    commonErrors: [
      "Skipping reflection — missing learning opportunity",
      "Vague takeaways that don't lead to action",
    ],
    completionCriteria: [
      "List of actionable improvements for the next session",
      "Updated prompt templates based on lessons learned",
    ],
  },
];

/* ── Helper: render stage variables as highlighted spans ── */

function renderTemplate(template: string, variables: string[]): string {
  let result = template;
  for (const v of variables) {
    const placeholder = `{${v}}`;
    const regex = new RegExp(placeholder.replace(/{/g, "\\{").replace(/}/g, "\\}"), "g");
    result = result.replace(regex, `<span class="viz-var">${placeholder}</span>`);
  }
  return result;
}

/* ── Component ── */

export default function CodeAgentFlowVizPage() {
  const [selectedStage, setSelectedStage] = useState<StageDefinition>(STAGES[0]);
  const [userInput, setUserInput] = useState("");
  const [agentOutput, setAgentOutput] = useState("");
  const [feedback, setFeedback] = useState("");
  const [nextSteps, setNextSteps] = useState("");
  const [records, setRecords] = useState<PracticeRecord[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* Load records on mount */
  useEffect(() => {
    loadRecords();
  }, []);

  const loadRecords = useCallback(async () => {
    try {
      const res = await post<ListRecordsData>("/tools/code_agent_flow_viz/invoke", {
        action: "list_records",
      });
      if (res.success && res.data) {
        setRecords(res.data.records);
        setBackendOk(true);
      } else {
        setBackendOk(false);
      }
    } catch {
      setBackendOk(false);
    }
  }, []);

  const handleSave = async () => {
    setError(null);
    setSummary(null);
    try {
      const res = await post<SaveRecordData>("/tools/code_agent_flow_viz/invoke", {
        action: "save_record",
        stage_key: selectedStage.key,
        user_input: userInput,
        agent_output: agentOutput,
        feedback,
        next_steps: nextSteps,
      });
      if (res.success && res.data) {
        const data = res.data;
        if (data.created) {
          setRecords((prev) => [data.record, ...prev]);
        }
        setBackendOk(true);
      } else {
        setError(res.error?.message ?? "Save failed");
        setBackendOk(false);
      }
    } catch (err) {
      setError(`Backend unreachable: ${String(err)}`);
      setBackendOk(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await post("/tools/code_agent_flow_viz/invoke", {
        action: "delete_record",
        id,
      });
      if (res.success) {
        setRecords((prev) => prev.filter((r) => r.id !== id));
      } else {
        setError(res.error?.message ?? "Delete failed");
        setBackendOk(false);
      }
    } catch {
      setBackendOk(false);
    }
  };

  const handleGenerateSummary = () => {
    const stage = selectedStage;
    const lines = [
      `# Code Agent Practice Summary — Stage ${stage.number}: ${stage.title}`,
      "",
      "## User Input",
      userInput || "(empty)",
      "",
      "## Agent Output",
      agentOutput || "(empty)",
      "",
      "## Feedback",
      feedback || "(empty)",
      "",
      "## Next Steps",
      nextSteps || "(empty)",
      "",
      "---",
      `*Generated at ${new Date().toLocaleString()}*`,
    ];
    setSummary(lines.join("\n"));
  };

  const handleCopyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(selectedStage.promptTemplate);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement("textarea");
      textarea.value = selectedStage.promptTemplate;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClear = () => {
    setUserInput("");
    setAgentOutput("");
    setFeedback("");
    setNextSteps("");
    setSummary(null);
    setError(null);
  };

  const handleExportJSON = () => {
    const json = JSON.stringify(records, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    downloadBlob(blob, "code-agent-practice-records.json");
  };

  const handleExportMarkdown = () => {
    if (records.length === 0) {
      setError("No records to export.");
      return;
    }
    const lines: string[] = ["# Code Agent Practice Records", ""];
    for (const r of records) {
      const stage = STAGES.find((s) => s.key === r.stage_key);
      lines.push(`## Stage ${stage?.number ?? "?"}: ${stage?.title ?? r.stage_key}`);
      lines.push("");
      lines.push("**User Input:**");
      lines.push(r.user_input || "(empty)");
      lines.push("");
      lines.push("**Agent Output:**");
      lines.push(r.agent_output || "(empty)");
      lines.push("");
      lines.push("**Feedback:**");
      lines.push(r.feedback || "(empty)");
      lines.push("");
      lines.push("**Next Steps:**");
      lines.push(r.next_steps || "(empty)");
      lines.push("");
      lines.push(`*Recorded at: ${r.created_at ?? "unknown"}*`);
      lines.push("---");
      lines.push("");
    }
    const md = lines.join("\n");
    const blob = new Blob([md], { type: "text/markdown" });
    downloadBlob(blob, "code-agent-practice-records.md");
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportResult(null);
    setError(null);

    let imported: unknown[];
    try {
      const text = await file.text();
      imported = JSON.parse(text);
      if (!Array.isArray(imported)) throw new Error("Not an array");
    } catch {
      setError("Invalid JSON file. Import cancelled, existing data preserved.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const confirmed = window.confirm(
      `Found ${imported.length} record(s) in the file. Import will skip duplicates. Continue?`
    );
    if (!confirmed) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setImporting(true);
    let createdCount = 0;
    let skippedCount = 0;

    for (const item of imported) {
      const rec = item as Record<string, unknown>;
      try {
        const res = await post<SaveRecordData>("/tools/code_agent_flow_viz/invoke", {
          action: "save_record",
          stage_key: String(rec.stage_key ?? ""),
          user_input: String(rec.user_input ?? ""),
          agent_output: String(rec.agent_output ?? ""),
          feedback: String(rec.feedback ?? ""),
          next_steps: String(rec.next_steps ?? ""),
        });
        if (res.success && res.data) {
          const data = res.data;
          if (data.created) {
            createdCount++;
          } else {
            skippedCount++;
          }
        }
      } catch {
        // skip individual failures
      }
    }

    setImporting(false);
    setImportResult(`Imported: ${createdCount} new, ${skippedCount} skipped.`);

    if (fileInputRef.current) fileInputRef.current.value = "";
    await loadRecords();
  };

  return (
    <div className="tool-page viz-page">
      <h2>Code Agent Flow Visualizer</h2>
      <p>Explore the 9 stages of a Coding Agent collaboration and record your practice sessions.</p>

      {!backendOk && (
        <div className="viz-notice viz-notice-warn">
          ⚠ Backend is unreachable. Stage browsing and prompt copying still work, but saving records
          is unavailable.
        </div>
      )}

      {/* ── Stage Node Navigator ── */}
      <div className="viz-navigator">
        {STAGES.map((stage, i) => (
          <div key={stage.key} className="viz-node-wrapper">
            <button
              className={`viz-node ${selectedStage.key === stage.key ? "viz-node-active" : ""}`}
              onClick={() => {
                setSelectedStage(stage);
                setSummary(null);
                setError(null);
              }}
              title={stage.title}
            >
              <span className="viz-node-num">{stage.number}</span>
              <span className="viz-node-label">{stage.title}</span>
            </button>
            {i < STAGES.length - 1 && <div className="viz-connector" />}
          </div>
        ))}
      </div>

      {/* ── Stage Detail Panel ── */}
      <div className="viz-detail-panel">
        <h3>
          Stage {selectedStage.number}: {selectedStage.title}
        </h3>

        <section>
          <h4>Goals</h4>
          <ul>
            {selectedStage.goals.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Prompt Template</h4>
          <div
            className="viz-template-box"
            dangerouslySetInnerHTML={{
              __html: renderTemplate(selectedStage.promptTemplate, selectedStage.variables),
            }}
          />
          <div className="viz-var-legend">
            <strong>Variables:</strong>{" "}
            {selectedStage.variables.map((v) => (
              <code key={v} className="viz-var">
                {`{${v}}`}
              </code>
            ))}
          </div>
          <button className="viz-copy-btn" onClick={handleCopyPrompt}>
            {copied ? "✓ Copied!" : "Copy Prompt"}
          </button>
        </section>

        <section>
          <h4>Checklist</h4>
          <ul className="viz-checklist">
            {selectedStage.checklist.map((c, i) => (
              <li key={i}>
                <label>
                  <input type="checkbox" /> {c}
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Common Errors</h4>
          <ul className="viz-errors">
            {selectedStage.commonErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Completion Criteria</h4>
          <ul>
            {selectedStage.completionCriteria.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </section>
      </div>

      {/* ── Practice Record Form ── */}
      <div className="viz-form-section">
        <h3>Practice Record — Stage {selectedStage.number}</h3>
        <div className="viz-form">
          <label>
            Your Input (Prompt)
            <textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              placeholder="What did you prompt the agent with?"
              rows={3}
            />
          </label>
          <label>
            Agent Output
            <textarea
              value={agentOutput}
              onChange={(e) => setAgentOutput(e.target.value)}
              placeholder="What did the agent respond?"
              rows={3}
            />
          </label>
          <label>
            Your Feedback
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="What worked well? What didn't?"
              rows={2}
            />
          </label>
          <label>
            Next Steps / Improvements
            <textarea
              value={nextSteps}
              onChange={(e) => setNextSteps(e.target.value)}
              placeholder="What will you do differently next time?"
              rows={2}
            />
          </label>
        </div>

        <div className="viz-actions">
          <button onClick={handleSave} disabled={!backendOk}>
            Save Record
          </button>
          <button className="viz-btn-secondary" onClick={handleGenerateSummary}>
            Generate Summary
          </button>
          <button className="viz-btn-secondary" onClick={handleClear}>
            Clear
          </button>
          <button className="viz-btn-secondary" onClick={handleExportJSON} disabled={records.length === 0}>
            Export JSON
          </button>
          <button className="viz-btn-secondary" onClick={handleExportMarkdown} disabled={records.length === 0}>
            Export Markdown
          </button>
          <button className="viz-btn-secondary" onClick={handleImportClick} disabled={importing}>
            {importing ? "Importing..." : "Import JSON"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
        </div>

        {error && <div className="viz-notice viz-notice-error">{error}</div>}
        {importResult && <div className="viz-notice viz-notice-success">{importResult}</div>}

        {summary && (
          <div className="viz-summary-box">
            <h4>Generated Summary</h4>
            <pre>{summary}</pre>
            <button
              className="viz-copy-btn"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(summary);
                } catch {
                  const ta = document.createElement("textarea");
                  ta.value = summary;
                  document.body.appendChild(ta);
                  ta.select();
                  document.execCommand("copy");
                  document.body.removeChild(ta);
                }
              }}
            >
              Copy Summary
            </button>
          </div>
        )}
      </div>

      {/* ── History ── */}
      <div className="viz-history-section">
        <h3>Saved Records ({records.length})</h3>
        {records.length === 0 ? (
          <p className="status-text">No records yet. Save your first practice record above.</p>
        ) : (
          <div className="viz-history-list">
            {records.map((r) => {
              const stage = STAGES.find((s) => s.key === r.stage_key);
              return (
                <div key={r.id} className="viz-history-item">
                  <div className="viz-history-meta">
                    <strong>
                      Stage {stage?.number ?? "?"}: {stage?.title ?? r.stage_key}
                    </strong>
                    <span className="viz-history-date">
                      {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                  <div className="viz-history-preview">
                    <span>Input: {r.user_input.slice(0, 80)}{r.user_input.length > 80 ? "…" : ""}</span>
                    <span>Output: {r.agent_output.slice(0, 80)}{r.agent_output.length > 80 ? "…" : ""}</span>
                  </div>
                  <button
                    className="viz-delete-btn"
                    onClick={() => handleDelete(r.id)}
                    title="Delete record"
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
