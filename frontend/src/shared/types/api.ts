export type Role = "USER" | "ADMIN";

export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
  requestId: string;
}

export interface Person {
  id: string;
  role: Role;
  displayName: string;
  enabled: boolean;
}

export interface AuthResult {
  accessToken: string;
  expiresIn: number;
  person: Person;
}

export interface RecordSession {
  id: string;
  status: string;
  currentDraftId: string | null;
  createdAt?: string;
  updatedAt?: string;
}

export interface RecordDraft {
  id: string;
  versionNo: number;
  status: string;
  previewText: string;
  draft: {
    title?: string;
    recordDate?: string;
    summary?: string;
    score?: number;
    tags?: string[];
    suggestion?: string;
  };
}

export interface RecordDisplay {
  recordId: string;
  recordDate?: string;
  title: string;
  summary: string;
  score?: number;
  displayStatus: string;
  adminContent?: Record<string, unknown>;
}

export interface UserHome {
  date: string;
  homeContent: {
    mainText?: string;
    subText?: string;
    background?: Record<string, unknown>;
  };
  recordGuide: {
    title?: string;
    items?: string[];
  };
  latestRecord?: Partial<RecordDisplay>;
}

export interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface SendMessageResult {
  session: RecordSession;
  userMessage: Record<string, unknown>;
  aiMessage: Record<string, unknown>;
  draft: RecordDraft;
}
