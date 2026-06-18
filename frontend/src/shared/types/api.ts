export type Role = "USER" | "PARTNER" | "OPS_ADMIN" | "ADMIN";
export type ViewRole = "USER" | "BOUND_ADMIN" | "OPS_ADMIN";

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

export interface BindingInfo {
  active: boolean;
  bindingId?: string;
  boundUser?: Person | null;
  permissions: string[];
}

export interface IdentityContext {
  person: Person;
  currentViewRole: ViewRole;
  viewOwner: Person;
  binding: BindingInfo;
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
  boundComment?: RecordComment;
  managerComment?: string;
  managerScore?: number;
}

export interface RecordComment {
  id: string;
  recordId: string;
  authorUserId: string;
  authorDisplayName?: string;
  content: string;
  score: number;
  updatedAt?: string;
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

export interface PointAccount {
  ownerUserId: string;
  balance: number;
  checkedInToday: boolean;
}

export interface PointSummary {
  currentUser: PointAccount;
  viewOwner: PointAccount;
  currentViewRole: ViewRole;
}

export interface RewardItem {
  id: string;
  ownerUserId: string;
  title: string;
  description?: string;
  costPoints: number;
  status: string;
  redeemable: boolean;
  createdByUserId?: string;
  redeemedAt?: string | null;
}

export interface RewardList {
  ownerUserId: string;
  items: RewardItem[];
}

export interface RewardRedemption {
  id: string;
  rewardId: string;
  userId: string;
  title: string;
  description?: string;
  costPoints: number;
  status: string;
  createdAt?: string;
  notifiedAt?: string | null;
}

export interface RewardRedemptionList {
  ownerUserId: string;
  items: RewardRedemption[];
}
