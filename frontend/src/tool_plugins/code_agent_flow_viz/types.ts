export interface StageDefinition {
  key: string;
  number: number;
  title: string;
  hint: string;
  goals: string[];
  promptTemplate: string;
  promptTemplateZh: string;
  variables: string[];
  checklist: string[];
  commonErrors: string[];
  completionCriteria: string[];
}

export interface PracticeRecord {
  id: string;
  stage_key: string;
  user_input: string;
  agent_output: string;
  feedback: string;
  next_steps: string;
  content_hash: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ListRecordsData {
  records: PracticeRecord[];
  total: number;
}

export interface SaveRecordData {
  record: PracticeRecord;
  created: boolean;
}

export interface ImportRecordsData {
  imported: number;
  skipped: number;
}
