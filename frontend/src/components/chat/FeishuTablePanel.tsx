import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, Plus, RefreshCw, Table2 } from "lucide-react";
import { Pressable } from "../ui/Pressable";
import type { FeishuAccount, FeishuTableConfig } from "../../shared/types/api";
import type { SaveFeishuAccountPayload, SaveFeishuTablePayload } from "../../features/feishu/api";

interface FeishuTablePanelProps {
  account: FeishuAccount | null;
  tables: FeishuTableConfig[];
  selectedTableId: string | null;
  locked: boolean;
  busy: boolean;
  onSelectTable: (tableId: string) => void;
  onSaveAccount: (payload: SaveFeishuAccountPayload) => Promise<boolean | void>;
  onCreateTable: (payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onUpdateTable: (tableId: string, payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onSetDefault: (tableId: string) => Promise<boolean | void>;
  onTestTable: (tableId: string) => Promise<boolean | void>;
}

export function FeishuTablePanel({
  account,
  tables,
  selectedTableId,
  locked,
  busy,
  onSelectTable,
  onSaveAccount,
  onCreateTable,
  onUpdateTable,
  onSetDefault,
  onTestTable
}: FeishuTablePanelProps) {
  const selected = useMemo(() => tables.find((item) => item.id === selectedTableId) ?? tables.find((item) => item.isDefault) ?? tables[0], [tables, selectedTableId]);
  const [expanded, setExpanded] = useState(false);
  const [appId, setAppId] = useState(account?.appId ?? "");
  const [appSecret, setAppSecret] = useState("");
  const [tenantAccessToken, setTenantAccessToken] = useState("");
  const [userIdType, setUserIdType] = useState(account?.userIdType ?? "open_id");
  const [displayName, setDisplayName] = useState("");
  const [tableUrl, setTableUrl] = useState("");
  const [fieldMapText, setFieldMapText] = useState("{}");
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editTableUrl, setEditTableUrl] = useState("");
  const [editFieldMapText, setEditFieldMapText] = useState("{}");
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setAppId(account?.appId ?? "");
    setUserIdType(account?.userIdType ?? "open_id");
  }, [account?.appId, account?.userIdType]);

  useEffect(() => {
    setEditDisplayName(selected?.displayName ?? "");
    setEditTableUrl(selected?.tableUrl ?? "");
    setEditFieldMapText(JSON.stringify(selected?.fieldNameMap ?? {}, null, 2));
  }, [selected?.id, selected?.displayName, selected?.tableUrl, selected?.fieldNameMap]);

  const needsSetup = !account?.configured || tables.length === 0;

  async function saveAccount(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    await onSaveAccount({ enabled: true, appId, appSecret, tenantAccessToken, userIdType });
    setAppSecret("");
    setTenantAccessToken("");
  }

  async function addTable(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    const fieldNameMap = parseFieldMap(fieldMapText);
    if (!fieldNameMap) {
      setLocalError("字段映射必须是 JSON 对象。");
      return;
    }
    const ok = await onCreateTable({ displayName, tableUrl, enabled: true, fieldNameMap });
    if (ok !== false) {
      setDisplayName("");
      setTableUrl("");
      setFieldMapText("{}");
    }
  }

  async function saveCurrentTable(event: FormEvent) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setLocalError("");
    const fieldNameMap = parseFieldMap(editFieldMapText);
    if (!fieldNameMap) {
      setLocalError("字段映射必须是 JSON 对象。");
      return;
    }
    await onUpdateTable(selected.id, {
      displayName: editDisplayName,
      tableUrl: editTableUrl,
      enabled: selected.enabled,
      fieldNameMap
    });
  }

  return (
    <section className={`feishu-table-panel${needsSetup ? " is-setup" : ""}`}>
      <div className="feishu-table-panel__summary">
        <div className="feishu-table-panel__title">
          <Table2 size={18} />
          <div>
            <b>{selected?.displayName ?? "未设置飞书表"}</b>
            <span>{selected ? `${selected.tableId}${selected.viewId ? ` / ${selected.viewId}` : ""}` : "先保存凭证并添加表 URL"}</span>
          </div>
        </div>
        <Pressable className="secondary-button feishu-table-panel__toggle" disabled={busy || locked} onClick={() => setExpanded((value) => !value)}>
          {expanded || needsSetup ? "收起" : "设置"}
        </Pressable>
      </div>

      {tables.length > 0 && (
        <div className="feishu-table-panel__chooser">
          <select value={selected?.id ?? ""} disabled={busy || locked} onChange={(event) => onSelectTable(event.target.value)}>
            {tables.map((table) => (
              <option key={table.id} value={table.id}>
                {table.displayName}{table.isDefault ? " 默认" : ""}
              </option>
            ))}
          </select>
          {selected && (
            <div className="feishu-table-panel__quick-actions">
              <Pressable className="icon-button" disabled={busy || locked || selected.isDefault} onClick={() => onSetDefault(selected.id)} aria-label="设为默认">
                <Check size={17} />
              </Pressable>
              <Pressable className="icon-button" disabled={busy || locked} onClick={() => onTestTable(selected.id)} aria-label="测试连接">
                <RefreshCw size={17} />
              </Pressable>
            </div>
          )}
        </div>
      )}

      {(expanded || needsSetup) && (
        <div className="feishu-table-panel__forms">
          <form className="feishu-form" onSubmit={saveAccount}>
            <label>
              App ID
              <input value={appId} disabled={busy || locked} onChange={(event) => setAppId(event.target.value)} placeholder="cli_xxx" />
            </label>
            <label>
              App Secret
              <input value={appSecret} disabled={busy || locked} onChange={(event) => setAppSecret(event.target.value)} placeholder={account?.appSecretConfigured ? "已保存，留空不修改" : "必填"} type="password" />
            </label>
            <label>
              Tenant Token
              <input value={tenantAccessToken} disabled={busy || locked} onChange={(event) => setTenantAccessToken(event.target.value)} placeholder={account?.tenantAccessTokenConfigured ? "已保存，留空不修改" : "可选"} type="password" />
            </label>
            <label>
              User ID Type
              <select value={userIdType} disabled={busy || locked} onChange={(event) => setUserIdType(event.target.value)}>
                <option value="open_id">open_id</option>
                <option value="union_id">union_id</option>
                <option value="user_id">user_id</option>
              </select>
            </label>
            <Pressable className="primary-button" type="submit" disabled={busy || locked || !appId.trim()}>
              保存凭证
            </Pressable>
          </form>

          {localError && <p className="field-error feishu-table-panel__error">{localError}</p>}

          {selected && (
            <form className="feishu-form" onSubmit={saveCurrentTable}>
              <label>
                当前表别名
                <input value={editDisplayName} disabled={busy || locked} onChange={(event) => setEditDisplayName(event.target.value)} placeholder="每日记录" />
              </label>
              <label>
                当前表 URL
                <input value={editTableUrl} disabled={busy || locked} onChange={(event) => setEditTableUrl(event.target.value)} placeholder="https://xxx.feishu.cn/base/app...?table=tbl...&view=vew..." />
              </label>
              <label>
                当前字段映射
                <textarea value={editFieldMapText} disabled={busy || locked} onChange={(event) => setEditFieldMapText(event.target.value)} />
              </label>
              <Pressable className="primary-button" type="submit" disabled={busy || locked || !editTableUrl.trim()}>
                保存当前表
              </Pressable>
            </form>
          )}

          <form className="feishu-form" onSubmit={addTable}>
            <label>
              表名称
              <input value={displayName} disabled={busy || locked} onChange={(event) => setDisplayName(event.target.value)} placeholder="每日记录" />
            </label>
            <label>
              表 URL
              <input value={tableUrl} disabled={busy || locked} onChange={(event) => setTableUrl(event.target.value)} placeholder="https://xxx.feishu.cn/base/app...?table=tbl...&view=vew..." />
            </label>
            <label>
              字段映射
              <textarea value={fieldMapText} disabled={busy || locked} onChange={(event) => setFieldMapText(event.target.value)} />
            </label>
            <Pressable className="primary-button" type="submit" disabled={busy || locked || !tableUrl.trim()}>
              <Plus size={17} /> 添加表
            </Pressable>
          </form>
        </div>
      )}
      {locked && <p className="feishu-table-panel__lock">当前草稿或写入确认进行中，暂不能切换飞书表。</p>}
    </section>
  );
}

function parseFieldMap(value: string) {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}
