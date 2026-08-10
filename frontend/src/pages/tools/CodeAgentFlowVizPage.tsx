import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { invokeTool } from "../../lib/api";
import type {
  ImportRecordsData,
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
    title: "Goal Setting",
    hint: "Clarify what you want the agent to accomplish",
    goals: [
      "Articulate what you want to build or change",
      "Define success criteria before starting",
      "Separate must-haves from nice-to-haves",
    ],
    promptTemplate:
      "I need help with the following:\n\n{task}\n\nBefore we start, please ask me clarifying questions about:\n- What I'm trying to accomplish\n- What success looks like\n- What's out of scope for now\n\nThen help me break this into actionable steps with clear acceptance criteria.",
    promptTemplateZh:
      "我需要做以下事情：\n\n{task}\n\n在开始之前，请先向我提澄清问题：\n- 我到底要达成什么\n- 怎样才算完成\n- 哪些暂时不做\n\n然后帮我拆解成可执行的小步，每步有明确的验收标准。",
    variables: ["task"],
    checklist: [
      "目标具体且可衡量，避免模糊表述",
      "完成与否有明确的判定标准",
      "不纳入范围的需求已清晰界定",
      "工作量适合在一轮会话内完成",
    ],
    commonErrors: [
      "将多个不相关的目标混杂在同一个任务中",
      "未定义明确的完成标准",
      "需求描述过于模糊，导致 Agent 依赖猜测进行实现",
    ],
    completionCriteria: [
      "目标变更或构建的内容已明确表述",
      "成功标准具备可验证性",
      "范围的边界已清晰界定",
    ],
  },
  {
    key: "context_research",
    number: 2,
    title: "Context & Research",
    hint: "Read-only survey — understand before changing",
    goals: [
      "Survey the codebase before making changes",
      "Identify relevant files, patterns, and dependencies",
      "Surface risks before writing code",
    ],
    promptTemplate:
      "Please do a read-only survey of the project. Do not modify any files.\n\nI want to work on: {topic}\n\nRead the relevant areas of the codebase and report:\n1. Relevant files you found and what each does\n2. How things currently work\n3. Existing patterns and conventions to follow\n4. Risks and uncertainties\n5. Your recommended approach with file-level scope\n\nAll conclusions must reference file paths or command output.",
    promptTemplateZh:
      "请对项目进行只读调查，不要修改任何文件。\n\n待处理事项：{topic}\n\n请阅读代码库的相关模块，并提供以下报告：\n1. 发现了哪些相关文件及其各自的作用\n2. 当前实现方式\n3. 可复用的设计模式与编码规范\n4. 潜在风险与不确定因素\n5. 建议的方案及涉及的文件范围\n\n所有结论须附上文件路径或命令输出作为依据。",
    variables: ["topic"],
    checklist: [
      "调查过程中未修改任何文件",
      "结论均有文件路径或命令输出作为依据",
      "已识别并记录潜在风险",
      "调查范围未无限制扩展",
    ],
    commonErrors: [
      "跳过调查环节，直接进入编码阶段",
      "仅阅读入口文件而未追踪完整调用链路",
      "采用「先写再看」的方式而非先充分理解",
    ],
    completionCriteria: [
      "明确知晓需要修改哪些文件",
      "明确知晓不应修改哪些文件",
      "对当前状态的理解有充分的证据支撑",
    ],
  },
  {
    key: "task_specification",
    number: 3,
    title: "Task Specification",
    hint: "Turn intent into a verifiable contract",
    goals: [
      "Write a spec that another agent could execute",
      "Make requirements unambiguous and testable",
      "Define constraints based on project reality",
    ],
    promptTemplate:
      "Based on what we've discussed and what you found in the codebase, help me write a clear task specification.\n\nThe goal is: {goal}\n\nFrom your research you know:\n- The project structure\n- Existing patterns and conventions\n- Relevant files\n\nPlease produce a spec with:\n- Goal (verifiable outcome)\n- Context (with file evidence)\n- Constraints (what not to touch)\n- Done when (checkable items)\n\nFlag any places where the spec is still ambiguous.",
    promptTemplateZh:
      "基于我们讨论的内容和你对代码库的调查，帮我写一份清晰的任务规格。\n\n目标是：{goal}\n\n从调查中你已经知道：\n- 项目结构\n- 现有模式和约定\n- 相关文件\n\n请输出包含以下内容的规格：\n- 目标（可验证的结果）\n- 上下文（附文件证据）\n- 约束条件（不能动什么）\n- 完成标准（可检查的条目）\n\n标出规格中仍然模糊的地方。",
    variables: ["goal"],
    checklist: [
      "目标描述的是结果而非动作",
      "上下文信息附有文件层面的证据",
      "约束条件具有清晰的边界",
      "完成标准可客观验证，不依赖主观判断",
    ],
    commonErrors: [
      "将愿望清单误作为任务规格",
      "未定义验收标准",
      "让 Agent 自行揣摩「足够好」的标准",
    ],
    completionCriteria: [
      "该规格可直接交由另一个 Agent 执行",
      "阅读者能够明确知晓应做与不应做之事",
    ],
  },
  {
    key: "solution_planning",
    number: 4,
    title: "Solution Design & Planning",
    hint: "Design first, then plan the steps",
    goals: [
      "Evaluate alternative approaches before committing",
      "Break the work into small, ordered steps",
      "Identify risks early",
    ],
    promptTemplate:
      "Design a solution and create an implementation plan.\n\nRequirements:\n- {requirement_1}\n- {requirement_2}\n\nPropose 2-3 approaches with trade-offs. For the chosen approach:\n\nList every file to create or modify with:\n- What changes and why\n- Order of work\n- Risks and mitigation\n- How to verify each step\n\nDo not write code yet. Wait for my approval on the plan.",
    promptTemplateZh:
      "设计方案并制定实施计划。\n\n需求：\n- {requirement_1}\n- {requirement_2}\n\n请提出 2-3 种方案并比较优劣。对于选中的方案：\n\n列出每个要创建或修改的文件：\n- 改什么以及为什么改\n- 执行顺序\n- 风险与应对\n- 每步如何验证\n\n暂时不要写代码，等我确认计划。",
    variables: ["requirement_1", "requirement_2"],
    checklist: [
      "至少评估了两种候选方案",
      "各方案的优劣对比已记录在案",
      "计划可按步执行、循序渐进",
      "每个步骤均附带验证手段",
    ],
    commonErrors: [
      "计划规模过大，超出单轮会话的承载能力",
      "修改内容与验证方式未明确说明",
      "引入了范围之外的功能模块（如数据库、API 等）",
    ],
    completionCriteria: [
      "你理解每个步骤并认同执行次序",
      "你有能力识别并拒绝过度扩展的计划",
      "第一步足够小，可以立即着手实施",
    ],
  },
  {
    key: "implementation",
    number: 5,
    title: "Implementation",
    hint: "Build a working version — one step at a time",
    goals: [
      "Write clean code following project conventions",
      "Make minimal, focused changes per step",
      "Keep the codebase working at each step",
    ],
    promptTemplate:
      "Implement the approved plan. \n\nCurrent step: {step_description}\n\nRules:\n- Read the existing files first to match conventions\n- Make minimal changes — only what the plan specifies\n- Do not add features beyond scope\n- Keep the project runnable after each change\n- If you encounter an uncertainty, flag it rather than guessing\n\nAfter implementing, summarize:\n1. What you changed and why\n2. How to verify\n3. What's left for the next step",
    promptTemplateZh:
      "按已确认的计划实现。\n\n当前步骤：{step_description}\n\n规则：\n- 先读现有文件，遵循项目约定\n- 做最小改动——只改计划指定的内容\n- 不添加计划外的功能\n- 每次改动后保持项目可运行\n- 遇到不确定的地方先标出来，不要猜测\n\n实现完成后总结：\n1. 改了哪些文件以及为什么改\n2. 如何验证\n3. 下一步还剩什么",
    variables: ["step_description"],
    checklist: [
      "每次仅推进一个步骤",
      "每个修改均有充分的理由",
      "未超出既定范围",
      "改动结果可立即预览或测试",
    ],
    commonErrors: [
      "在实现过程中随意添加额外功能",
      "为微小改进引入了重量级依赖",
      "未经验证即宣称完成",
    ],
    completionCriteria: [
      "当前步骤已完成并通过验证",
      "下一步的执行内容已明确",
    ],
  },
  {
    key: "testing_validation",
    number: 6,
    title: "Testing & Validation",
    hint: "Prove it works with evidence",
    goals: [
      "Write tests that validate the changes",
      "Verify edge cases are handled",
      "Confirm existing functionality still works",
    ],
    promptTemplate:
      "Write tests for the changes made. \n\nYou know:\n- What changed (from the implementation)\n- The test framework used in this project (read it from config)\n- Existing test patterns (read existing tests)\n\nCover:\n- The happy path\n- Edge cases: {edge_cases}\n- Error handling\n\nThen run the test suite and report results. If tests fail, fix and retry.\n\nFinally, confirm: does the implementation meet the 'Done when' from the spec?",
    promptTemplateZh:
      "为刚才的改动编写测试。\n\n你已经知道：\n- 改了什么（从实现步骤中可知）\n- 项目用的测试框架（从配置文件读取）\n- 现有的测试模式（读取现有测试文件）\n\n覆盖：\n- 正常路径\n- 边界情况：{edge_cases}\n- 错误处理\n\n然后运行测试并报告结果。如果测试失败，修复后重试。\n\n最后确认：实现是否满足规格中的「完成标准」？",
    variables: ["edge_cases"],
    checklist: [
      "正常流程已覆盖",
      "边界条件已覆盖",
      "测试结果稳定可靠，不存在偶发失败",
      "既有测试仍全部通过",
    ],
    commonErrors: [
      "测试针对的是实现细节而非外部行为",
      "缺少反面用例（应明确验证系统拒绝了什么）",
      "测试因共享状态或时序问题而产生不稳定性",
    ],
    completionCriteria: [
      "测试覆盖程度对当前改动而言足够充分",
      "所有测试一致通过",
      "功能经验证确实可用",
    ],
  },
  {
    key: "code_review",
    number: 7,
    title: "Code Review",
    hint: "Check the diff carefully before accepting",
    goals: [
      "Review every line changed in this session",
      "Catch security issues, regressions, and design problems",
      "Ensure nothing unrelated was modified",
    ],
    promptTemplate:
      "Review all changes from this session.\n\nGenerate the diff and list changed files:\n- Run `git diff` to see every change\n- Run `git diff --stat` for the summary\n\nCheck each change for:\n1. Does it meet the original goal?\n2. Are there any unrelated changes?\n3. Any security vulnerabilities?\n4. Any performance concerns?\n5. Does it follow the project's conventions?\n\nFor each issue found, provide the file:line reference.\nRank issues by severity.",
    promptTemplateZh:
      "审查本轮所有改动。\n\n生成 diff 并列出改动的文件：\n- 运行 `git diff` 查看每个改动\n- 运行 `git diff --stat` 查看汇总\n\n逐条检查：\n1. 是否满足最初的目标？\n2. 有没有无关的改动？\n3. 是否有安全漏洞？\n4. 是否有性能问题？\n5. 是否遵循项目约定？\n\n每个问题附上文件:行号引用，按严重程度排序。",
    variables: [],
    checklist: [
      "每个修改均有合理的解释",
      "未涉及无关文件",
      "未引入重型依赖",
      "问题已按严重程度排序",
    ],
    commonErrors: [
      "仅关注最终效果而未审查实际 diff",
      "将个人风格偏好与真正的缺陷混为一谈",
      "发现缺陷但未记录以供后续跟进",
    ],
    completionCriteria: [
      "明确哪些改动应当保留",
      "明确哪些改动需要返工",
      "下一步的修改范围已界定清楚",
    ],
  },
  {
    key: "documentation_commit",
    number: 8,
    title: "Documentation & Commit",
    hint: "Package the result for your future self",
    goals: [
      "Document what was built and why",
      "Write a clear commit message for the changes",
      "Record verification results and known limitations",
    ],
    promptTemplate:
      "Prepare the deliverables for this session.\n\nYou know:\n- What changed (from git diff)\n- Why it changed (from the goal and plan)\n- How it was verified (from testing)\n\nPlease produce:\n1. A concise commit title\n2. Summary of changes (bullet points, file-level)\n3. Verification results\n4. Known limitations or risks\n5. Suggested next steps\n\nAlso update any README or docs if the changes affect how the project is used.",
    promptTemplateZh:
      "准备本轮的交付物。\n\n你已经知道：\n- 改了什么（从 git diff 可知）\n- 为什么改（从目标和计划可知）\n- 如何验证的（从测试阶段可知）\n\n请输出：\n1. 简洁的提交标题\n2. 改动摘要（要点式，按文件列出）\n3. 验证结果\n4. 已知限制或风险\n5. 下一步建议\n\n如果改动了项目使用方式，同步更新 README 或文档。",
    variables: [],
    checklist: [
      "提交信息具备独立可读性，无需额外上下文即可理解",
      "验证结果已包含在提交内容中",
      "已知的限制与风险已如实记录",
      "标题未夸大成果范围",
    ],
    commonErrors: [
      "将未完成的工作标记为已完成",
      "提交信息仅有一行，缺乏必要的上下文",
      "未记录潜在风险与已知问题",
    ],
    completionCriteria: [
      "提交信息完整说明了改动的背景与内容",
      "下一轮可以从当前状态无缝衔接继续工作",
      "当前状态不存在模糊之处",
    ],
  },
  {
    key: "reflection_retro",
    number: 9,
    title: "Reflection & Retro",
    hint: "Turn this session into reusable skill",
    goals: [
      "Review what worked and what didn't in the collaboration",
      "Distill reusable prompt patterns",
      "Identify one thing to improve next session",
    ],
    promptTemplate:
      "Let's reflect on this session together.\n\nI'll share:\n- What I think went well: {went_well}\n- What could be improved: {improvements}\n- Whether the output met my expectations: {outcome}\n\nYou share:\n- Which parts of my instructions were clearest\n- Where you needed more context\n- What I should prepare differently next time\n\nTogether, distill:\n1. One prompt pattern to repeat\n2. One thing to do differently next session\n3. A small next-step task to start the next session",
    promptTemplateZh:
      "一起复盘这一轮协作。\n\n我来分享：\n- 我觉得做得好的地方：{went_well}\n- 可以改进的地方：{improvements}\n- 输出是否符合我的预期：{outcome}\n\n你来回馈：\n- 我哪部分指令表达得最清楚\n- 哪里缺上下文让你困惑\n- 下次我该提前准备什么\n\n共同提炼：\n1. 一条值得复用的提示词模式\n2. 下一次要改变的一个做法\n3. 下一轮可以开始的一个小任务",
    variables: ["went_well", "improvements", "outcome"],
    checklist: [
      "区分表达层面的问题与实现层面的问题",
      "提炼可复用的模式而非一次性观察",
      "下一步任务足够小，可以立即着手",
      "不归咎于 Agent，聚焦于自身可控的改进",
    ],
    commonErrors: [
      "仅总结功能产出，未总结协作模式",
      "未记录有效的提示词模式以供复用",
      "下一轮的任务规模与当前轮相当，缺乏递进",
    ],
    completionCriteria: [
      "提炼出一条可复用的表达规范",
      "产出一个足够小的下一步任务",
      "学习记录已保存，可供后续回顾参考",
    ],
  },
];

/* ── Component ── */

export default function CodeAgentFlowVizPage() {
  const [selectedStage, setSelectedStage] = useState<StageDefinition>(STAGES[0]);
  const [userInput, setUserInput] = useState("");
  const [agentOutput, setAgentOutput] = useState("");
  const [feedback, setFeedback] = useState("");
  const [nextSteps, setNextSteps] = useState("");
  const [records, setRecords] = useState<PracticeRecord[]>([]);
  const [recordsTotal, setRecordsTotal] = useState(0);
  const [summary, setSummary] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedZh, setCopiedZh] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadRecords = useCallback(async () => {
    try {
      const res = await invokeTool<ListRecordsData>("code_agent_flow_viz", {
        action: "list_records",
      });
      if (res.success && res.data) {
        setRecords(res.data.records);
        setRecordsTotal(res.data.total ?? res.data.records.length);
        setBackendOk(true);
      } else {
        setBackendOk(false);
      }
    } catch {
      setBackendOk(false);
    }
  }, []);

  /* Fetch every record across pages — used by export, which must not silently
     truncate at the list action's page size. */
  const fetchAllRecords = useCallback(async (): Promise<PracticeRecord[]> => {
    const all: PracticeRecord[] = [];
    const PAGE = 1000;
    for (let offset = 0; offset <= 1_000_000; offset += PAGE) {
      const res = await invokeTool<ListRecordsData>("code_agent_flow_viz", {
        action: "list_records",
        limit: PAGE,
        offset,
      });
      if (!res.success || !res.data) break;
      const page = res.data.records;
      if (page.length === 0) break;
      all.push(...page);
      if (page.length < PAGE) break; // last page
    }
    return all;
  }, []);

  /* Load records on mount */
  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleSave = async () => {
    setError(null);
    setSummary(null);
    try {
      const res = await invokeTool<SaveRecordData>("code_agent_flow_viz", {
        action: "save_record",
        stage_key: selectedStage.key,
        user_input: userInput,
        agent_output: agentOutput,
        feedback,
        next_steps: nextSteps,
      });
      if (res.success && res.data) {
        const d = res.data;
        if (d.created) {
          setRecords((prev) => [d.record, ...prev]);
          setRecordsTotal((prev) => prev + 1);
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
      const res = await invokeTool("code_agent_flow_viz", {
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

  const handleCopyPromptZh = async () => {
    try {
      await navigator.clipboard.writeText(selectedStage.promptTemplateZh);
      setCopiedZh(true);
      setTimeout(() => setCopiedZh(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = selectedStage.promptTemplateZh;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopiedZh(true);
      setTimeout(() => setCopiedZh(false), 2000);
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

  const handleExportJSON = async () => {
    let all: PracticeRecord[];
    try {
      all = await fetchAllRecords();
    } catch (err) {
      setError(`Export failed: ${String(err)}`);
      return;
    }
    if (all.length === 0) {
      setError("No records to export.");
      return;
    }
    const json = JSON.stringify(all, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    downloadBlob(blob, "code-agent-practice-records.json");
  };

  const handleExportMarkdown = async () => {
    let all: PracticeRecord[];
    try {
      all = await fetchAllRecords();
    } catch (err) {
      setError(`Export failed: ${String(err)}`);
      return;
    }
    if (all.length === 0) {
      setError("No records to export.");
      return;
    }
    const lines: string[] = ["# Code Agent Practice Records", ""];
    for (const r of all) {
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
    let resultText = "";
    try {
      // One batch call instead of one save_record per row: importing N records
      // as N invokes trips the per-minute rate limit once N passes the cap,
      // and the old per-row catch silently swallowed those 429 failures —
      // a data-loss bug. The backend import_records action dedups and returns
      // imported/skipped counts in a single request.
      const res = await invokeTool<ImportRecordsData>("code_agent_flow_viz", {
        action: "import_records",
        records: imported as Record<string, unknown>[],
      });
      if (res.success && res.data) {
        const d = res.data;
        resultText = `Imported: ${d.imported} new, ${d.skipped} skipped.`;
      } else {
        setError(res.error?.message ?? "Import failed.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadRecords();
    }
    if (resultText) setImportResult(resultText);
  };

  const toastRef = useRef<HTMLDivElement>(null);
  const showToast = (msg: string) => {
    if (!toastRef.current) return;
    toastRef.current.textContent = msg;
    toastRef.current.classList.add("viz-toast-show");
    setTimeout(() => toastRef.current?.classList.remove("viz-toast-show"), 1600);
  };

  /* ── Render ── */

  return (
    <div className="viz-app">
      {/* Toast */}
      <div ref={toastRef} className="viz-toast" role="status" aria-live="polite" />

      {/* Header */}
      <header className="viz-header">
        <div>
          <h1>Code Agent Flow Visualizer</h1>
          <p>Select a stage, copy the prompt, record your practice session.</p>
        </div>
        <Link to="/" className="viz-back-link">← Back to Tools</Link>
      </header>

      {!backendOk && (
        <div className="viz-banner-warn">
          ⚠ Backend is unreachable. Stage browsing and prompt copying still work, but saving records
          is unavailable.
        </div>
      )}

      {/* Main */}
      <main className="viz-main">
        {/* Left: Stage List */}
        <aside className="viz-sidebar">
          <h2 className="viz-sidebar-title">9 Stages</h2>
          <div className="viz-stage-list">
            {STAGES.map((stage) => (
              <button
                key={stage.key}
                className={`viz-stage-btn${selectedStage.key === stage.key ? " active" : ""}`}
                onClick={() => {
                  setSelectedStage(stage);
                  setSummary(null);
                  setError(null);
                }}
              >
                <span className="viz-stage-no">{stage.number}</span>
                <span>
                  <span className="viz-stage-name">{stage.title}</span>
                  <span className="viz-stage-hint">{stage.hint}</span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        {/* Right: Workspace */}
        <section className="viz-workspace">
          {/* Detail Panel */}
          <div className="viz-panel viz-detail">
            <div className="viz-detail-head">
              <div>
                <div className="viz-eyebrow">Stage {selectedStage.number}</div>
                <h2>{selectedStage.title}</h2>
                <p className="viz-goal">{selectedStage.goals[0]}</p>
              </div>
            </div>

            <div className="viz-prompt-grid">
              <div className="viz-prompt-column">
                <div className="viz-prompt-section">
                  <div className="viz-prompt-lang">🇬🇧 English</div>
                  <pre className="viz-prompt-box">{selectedStage.promptTemplate}</pre>
                  <button className="viz-btn viz-btn-sm viz-btn-primary" onClick={handleCopyPrompt}>
                    {copied ? "✓ Copied!" : "Copy Prompt"}
                  </button>
                </div>
                <div className="viz-prompt-section">
                  <div className="viz-prompt-lang">🇨🇳 中文</div>
                  <pre className="viz-prompt-box">{selectedStage.promptTemplateZh}</pre>
                  <button className="viz-btn viz-btn-sm viz-btn-primary" onClick={handleCopyPromptZh}>
                    {copiedZh ? "✓ 已复制!" : "复制 Prompt"}
                  </button>
                </div>
              </div>
              <div>
                <div className="viz-meta-card">
                  <h3>可替换变量</h3>
                  <ul>
                    {selectedStage.variables.map((v) => (
                      <li key={v}><code>{`{${v}}`}</code></li>
                    ))}
                  </ul>
                </div>
                <div className="viz-meta-card">
                  <h3>检查清单</h3>
                  <ul>
                    {selectedStage.checklist.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="viz-meta-card">
                  <h3>常见错误</h3>
                  <ul>
                    {selectedStage.commonErrors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
                <div className="viz-meta-card">
                  <h3>完成标准</h3>
                  <ul>
                    {selectedStage.completionCriteria.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Practice Panel */}
          <div className="viz-panel viz-practice">
            <h2>Practice Record — Stage {selectedStage.number}</h2>

            <div className="viz-practice-grid">
              <div>
                <label htmlFor="viz-input">Your Input</label>
                <textarea
                  id="viz-input"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="What did you prompt the agent with?"
                />
              </div>
              <div>
                <label htmlFor="viz-output">Agent Output</label>
                <textarea
                  id="viz-output"
                  value={agentOutput}
                  onChange={(e) => setAgentOutput(e.target.value)}
                  placeholder="What did the agent respond?"
                />
              </div>
              <div>
                <label htmlFor="viz-feedback">Your Feedback</label>
                <textarea
                  id="viz-feedback"
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="What worked well? What didn't?"
                />
              </div>
              <div>
                <label htmlFor="viz-next">Next Steps</label>
                <textarea
                  id="viz-next"
                  value={nextSteps}
                  onChange={(e) => setNextSteps(e.target.value)}
                  placeholder="What will you do differently next time?"
                />
              </div>
            </div>

            <div className="viz-practice-actions">
              <button className="viz-btn viz-btn-primary" onClick={handleSave} disabled={!backendOk}>
                Save Record
              </button>
              <button className="viz-btn viz-btn-secondary" onClick={handleGenerateSummary}>
                Generate Summary
              </button>
              <button className="viz-btn viz-btn-secondary" onClick={handleClear}>
                Clear
              </button>
              <button className="viz-btn viz-btn-secondary" onClick={handleExportJSON} disabled={records.length === 0}>
                Export JSON
              </button>
              <button className="viz-btn viz-btn-secondary" onClick={handleExportMarkdown} disabled={records.length === 0}>
                Export Markdown
              </button>
              <button className="viz-btn viz-btn-secondary" onClick={handleImportClick} disabled={importing}>
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

            {error && <div className="viz-msg viz-msg-error">{error}</div>}
            {importResult && <div className="viz-msg viz-msg-success">{importResult}</div>}

            {summary && (
              <div className="viz-summary-box">
                <h3>Generated Summary</h3>
                <pre>{summary}</pre>
                <button
                  className="viz-btn viz-btn-secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(summary);
                      showToast("Summary copied");
                    } catch {
                      const ta = document.createElement("textarea");
                      ta.value = summary;
                      document.body.appendChild(ta);
                      ta.select();
                      document.execCommand("copy");
                      document.body.removeChild(ta);
                      showToast("Summary copied");
                    }
                  }}
                >
                  Copy Summary
                </button>
              </div>
            )}

            {/* History */}
            <div className="viz-history-section">
              <div className="viz-history-head">
                <h3>History ({recordsTotal || records.length})</h3>
                <div className="viz-history-actions-top">
                  <button className="viz-btn viz-btn-secondary viz-btn-sm" onClick={handleExportJSON} disabled={records.length === 0}>
                    Export JSON
                  </button>
                  <button className="viz-btn viz-btn-secondary viz-btn-sm" onClick={handleExportMarkdown} disabled={records.length === 0}>
                    Export Markdown
                  </button>
                  <button className="viz-btn viz-btn-secondary viz-btn-sm" onClick={handleImportClick} disabled={importing}>
                    Import JSON
                  </button>
                </div>
              </div>

              {records.length === 0 ? (
                <div className="viz-history-empty">No records yet. Save your first practice record above.</div>
              ) : (
                <div className="viz-history-list">
                  {records.map((r) => {
                    const stage = STAGES.find((s) => s.key === r.stage_key);
                    const preview = r.user_input.slice(0, 60);
                    return (
                      <div key={r.id} className="viz-history-item">
                        <div className="viz-history-top">
                          <span className="viz-history-stage">
                            Stage {stage?.number ?? "?"} — {stage?.title ?? r.stage_key}
                          </span>
                          <span className="viz-history-date">
                            {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
                          </span>
                        </div>
                        <div className="viz-history-preview">
                          {preview}{r.user_input.length > 60 ? "…" : ""}
                        </div>
                        <div className="viz-history-actions">
                          <button
                            className="viz-btn viz-danger-btn viz-btn-sm"
                            onClick={() => handleDelete(r.id)}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
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
