export interface TaskAnalysis {
  goal: string;
  context: string[];
  constraints: string[];
  done_when: string[];
  failure_cases: string[];
  verification: string[];
  missing_questions: string[];
  risk_level: "low" | "medium" | "high";
  non_goals: string[];
  agent_prompt: string;
}

export interface HistoryRecord {
  id: string;
  raw_task: string;
  context: string;
  task_type: string;
  model_name: string;
  risk_hints: string[];
  risk_level: string;
  structured_output: TaskAnalysis;
  created_at: string | null;
}

export interface AnalyzeTaskData {
  analysis: TaskAnalysis;
  model: string;
}

export interface ListHistoryData {
  records: HistoryRecord[];
}
