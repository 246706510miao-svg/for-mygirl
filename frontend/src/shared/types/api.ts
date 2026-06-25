export type Role = "USER" | "PARTNER" | "OPS_ADMIN" | "ADMIN";
export type ViewRole = "USER" | "BOUND_ADMIN" | "OPS_ADMIN";

export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T | null;
  requestId: string;
}

export interface Person {
  id: string;
  role: Role;
  displayName: string;
  enabled: boolean;
  loginName?: string;
}

export interface BindingInvitation {
  id: string;
  status: string;
  requester: Person;
  target: Person;
  createdAt?: string;
  updatedAt?: string;
}

export interface AuthResult {
  expiresIn: number;
  person: Person;
}

export interface BindingInfo {
  active: boolean;
  bindingId?: string;
  boundUser?: Person | null;
  permissions: string[];
  incomingInvitations?: BindingInvitation[];
  outgoingInvitations?: BindingInvitation[];
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
  feishuTableConfigId?: string | null;
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

export interface PendingThirdConfirmation {
  status: string;
  thirdSessionId: string;
  confirmationId: string;
  requestText?: string;
  preview: Record<string, unknown>;
  clientConfirmId?: string;
  draftId?: string | null;
}

export interface ConfirmRecordResult {
  session: RecordSession;
  pendingConfirmation?: PendingThirdConfirmation;
  record?: Record<string, unknown>;
  feishuSync?: Record<string, unknown>;
  display?: Partial<RecordDisplay>;
  replyMessage?: Record<string, unknown>;
  status?: string;
  thirdStatus?: string;
  draft?: RecordDraft;
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
  draft?: RecordDraft;
  pendingConfirmation?: PendingThirdConfirmation;
  thirdStatus?: string;
}

export interface FeishuAccount {
  configured: boolean;
  enabled: boolean;
  appId?: string;
  appSecretConfigured: boolean;
  tenantAccessTokenConfigured: boolean;
  userIdType: string;
  updatedAt?: string;
}

export interface FeishuTableConfig {
  id: string;
  displayName: string;
  tableUrl: string;
  tableId: string;
  tableName?: string;
  viewId?: string;
  isDefault: boolean;
  enabled: boolean;
  fieldNameMap: Record<string, unknown>;
  lastTestStatus?: string;
  lastTestMessage?: string;
  lastTestAt?: string;
  updatedAt?: string;
}

export interface FeishuTableList {
  items: FeishuTableConfig[];
}

export interface FeishuTableTestResult {
  status: string;
  message?: string;
  tableName?: string;
  fieldCount?: number;
  fieldNames?: string[];
  table?: FeishuTableConfig;
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
