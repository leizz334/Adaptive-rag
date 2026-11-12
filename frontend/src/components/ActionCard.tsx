import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { requestJson } from "../lib/api";
import type { ActionProposal } from "../types";

interface Status { action_id: string; status: "pending" | "expired" | "completed" | "cancelled"; expires_at?: string }
export function ActionCard({ action, sessionId, onConfirm, onCancel, disabled }: { action: ActionProposal; sessionId?: string; onConfirm: () => void; onCancel: () => void; disabled: boolean }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const path = sessionId ? `/sessions/${encodeURIComponent(sessionId)}/actions/${encodeURIComponent(action.action_id)}` : "";
  useEffect(() => {
    if (!path || disabled) return;
    const controller = new AbortController();
    void requestJson<Status>(path, {signal:controller.signal}).then((s) => {setStatus(s);setError("");}).catch((e: unknown) => {if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "状态读取失败");});
    return () => controller.abort();
  }, [path, disabled]);
  const canConfirm = status?.status === "pending" || status?.status === "completed";
  async function cancel() {
    if (!path || cancelling) return; setCancelling(true); setError("");
    try {setStatus(await requestJson<Status>(`${path}/cancel`, {method:"POST"}));}
    catch(e) {setError(e instanceof Error ? e.message : "撤销失败");}
    finally {setCancelling(false);}
  }
  return <div className="action-card"><div className="action-icon"><ShieldCheck size={19}/></div><div className="action-content"><strong>{status?.status === "completed" ? "已完成 · 可幂等重放" : status?.status === "cancelled" ? "已撤销待确认提案" : status?.status === "expired" ? "提案已过期" : "需要你的确认"}</strong><p>{action.summary}</p><code className="field-summary">{action.tool_name} · {JSON.stringify(action.arguments)}</code><small>Action: {action.action_id}</small>{status?.expires_at && <small className="inspection-note">有效期至 {new Date(status.expires_at).toLocaleString()}</small>}
    {error && <p role="alert" className="inline-error">{error}</p>}
    <div className="action-buttons"><button className="confirm-button" disabled={disabled || cancelling || !canConfirm} onClick={onConfirm}>{disabled ? "执行中…" : status?.status === "completed" ? "幂等重放（同一 Action）" : "确认执行"}</button>{status?.status === "pending" && <button className="cancel-button" disabled={disabled || cancelling} onClick={() => void cancel()}>{cancelling ? "撤销中…" : "取消操作"}</button>}{["cancelled","expired"].includes(status?.status ?? "") && <button className="cancel-button" onClick={onCancel}>关闭提案</button>}</div><small className="inspection-note">只撤销尚未执行的提案；不能回滚已提交的业务操作。重复确认复用同一幂等键。</small>
  </div></div>;
}
