import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TaskDecomposerPlugin from "../src/tool_plugins/task_decomposer";
import type {
  AnalyzeTaskData,
  HistoryRecord,
  ListHistoryData,
  TaskAnalysis,
} from "../src/tool_plugins/task_decomposer/types";
import type { ApiResponse, ToolClient, ToolManifest } from "../src/types";

vi.mock("../src/lib/api", () => ({
  get: vi.fn().mockResolvedValue({
    success: true,
    data: { models: ["test-model"], default_model: "test-model" },
  }),
}));

const MANIFEST = {} as ToolManifest;

const ANALYSIS: TaskAnalysis = {
  goal: "旧分析结果",
  context: [],
  constraints: [],
  done_when: [],
  failure_cases: [],
  verification: [],
  missing_questions: [],
  risk_level: "low",
  non_goals: [],
  agent_prompt: "prompt",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function renderPlugin(invoke: ToolClient["invoke"]) {
  const client = {
    toolId: "task_decomposer",
    invoke,
    connect: vi.fn(),
  } as unknown as ToolClient;

  return render(
    <MemoryRouter>
      <TaskDecomposerPlugin client={client} manifest={MANIFEST} />
    </MemoryRouter>
  );
}

function historyRecord(id: string, rawTask: string): HistoryRecord {
  return {
    id,
    raw_task: rawTask,
    context: "",
    task_type: "feature",
    model_name: "test-model",
    risk_hints: [],
    risk_level: "low",
    structured_output: ANALYSIS,
    created_at: null,
  };
}

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
});

describe("TaskDecomposerPlugin request ordering", () => {
  it("does not restore an in-flight analysis after Clear", async () => {
    const analyze = deferred<ApiResponse<AnalyzeTaskData>>();
    const invoke = vi.fn((operation: string) => {
      if (operation === "analyze_task") return analyze.promise;
      return Promise.resolve({ success: true, data: { records: [] } });
    }) as ToolClient["invoke"];

    renderPlugin(invoke);
    fireEvent.change(screen.getByLabelText("原始任务"), {
      target: { value: "待分析任务" },
    });
    fireEvent.click(screen.getByRole("button", { name: "分析任务" }));
    await waitFor(() => expect(screen.getByText("模型分析中")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "清空" }));
    await act(async () => {
      analyze.resolve({
        success: true,
        data: { analysis: ANALYSIS, model: "test-model" },
      });
      await analyze.promise;
    });

    expect(screen.queryByText("旧分析结果")).not.toBeInTheDocument();
    expect(screen.getByText("等待分析")).toBeInTheDocument();
  });

  it("only accepts the latest history filter response", async () => {
    const feature = deferred<ApiResponse<ListHistoryData>>();
    const bugfix = deferred<ApiResponse<ListHistoryData>>();
    const invoke = vi.fn(
      (_operation: string, payload?: Record<string, unknown>) => {
        if (payload?.task_type === "feature") return feature.promise;
        if (payload?.task_type === "bugfix") return bugfix.promise;
        return Promise.resolve({ success: true, data: { records: [] } });
      }
    ) as ToolClient["invoke"];

    renderPlugin(invoke);
    const filter = screen.getByDisplayValue("全部类型");
    fireEvent.change(filter, { target: { value: "feature" } });
    fireEvent.change(filter, { target: { value: "bugfix" } });

    await act(async () => {
      bugfix.resolve({
        success: true,
        data: { records: [historyRecord("new", "最新筛选结果")] },
      });
      await bugfix.promise;
    });
    expect(screen.getByText("最新筛选结果")).toBeInTheDocument();

    await act(async () => {
      feature.resolve({
        success: true,
        data: { records: [historyRecord("old", "过期筛选结果")] },
      });
      await feature.promise;
    });
    expect(screen.queryByText("过期筛选结果")).not.toBeInTheDocument();
    expect(screen.getByText("最新筛选结果")).toBeInTheDocument();
  });
});

describe("TaskDecomposerPlugin draft recovery", () => {
  it("falls back to defaults for corrupted JSON", () => {
    localStorage.setItem("taskDecomposer.aiDraft", "{not-json");

    expect(() =>
      renderPlugin(vi.fn().mockResolvedValue({ success: true, data: { records: [] } }))
    ).not.toThrow();
    expect(screen.getByLabelText("原始任务")).toHaveValue("");
    expect(screen.getByLabelText("任务类型")).toHaveValue("feature");
  });

  it("falls back field by field for malformed draft values", () => {
    localStorage.setItem(
      "taskDecomposer.aiDraft",
      JSON.stringify({
        raw_task: "保留合法任务",
        context: 42,
        task_type: "bugfix",
        model: null,
        risk_hints: ["data_loss", 7],
      })
    );

    expect(() =>
      renderPlugin(vi.fn().mockResolvedValue({ success: true, data: { records: [] } }))
    ).not.toThrow();
    expect(screen.getByLabelText("原始任务")).toHaveValue("保留合法任务");
    expect(screen.getByLabelText("仓库 / 模块背景")).toHaveValue("");
    expect(screen.getByLabelText("任务类型")).toHaveValue("bugfix");
    expect(screen.getByLabelText("可能写入、覆盖或删除数据")).not.toBeChecked();
  });

  it("keeps a valid stored draft compatible", () => {
    localStorage.setItem(
      "taskDecomposer.aiDraft",
      JSON.stringify({
        raw_task: "合法任务",
        context: "合法背景",
        task_type: "test",
        model: "test-model",
        risk_hints: ["compatibility"],
      })
    );

    renderPlugin(vi.fn().mockResolvedValue({ success: true, data: { records: [] } }));
    expect(screen.getByLabelText("原始任务")).toHaveValue("合法任务");
    expect(screen.getByLabelText("仓库 / 模块背景")).toHaveValue("合法背景");
    expect(screen.getByLabelText("任务类型")).toHaveValue("test");
    expect(screen.getByLabelText("可能影响旧数据或兼容性")).toBeChecked();
  });
});
