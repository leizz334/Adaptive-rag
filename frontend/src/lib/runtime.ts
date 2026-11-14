import { clearCredential, getPendingRequests } from "./api";

export type Mode = "offline" | "deepseek";
export interface ModeStatus { mode: Mode; available: boolean; reason: string; message: string; verification_only: boolean }
export const MODE_ORIGINS: Record<Mode, string> = { offline: "http://127.0.0.1:8000", deepseek: "http://127.0.0.1:8001" };
const REASONS: Record<string, string> = {
  ready: "服务可用",
  payment_not_authorized: "未授权付费，无法使用 DeepSeek 模式。",
  budget_not_ready: "预算未就绪，请由管理员检查服务配置。",
  budget_exhausted: "预算已耗尽，当前无法使用此模式。",
  dependencies_unavailable: "服务依赖不可用，请稍后检查。",
  unsupported_deployment: "当前部署不支持此模式。",
  invalid_status: "模式不匹配或服务状态无效，已禁止切换。",
  unreachable: "无法连接此模式的服务，请确认服务已启动。",
  timeout: "服务状态检查超时，请手动重试。",
  cancelled: "服务状态检查已取消。",
};
const SERVER_REASONS = new Set(["ready", "payment_not_authorized", "budget_not_ready", "budget_exhausted", "dependencies_unavailable", "unsupported_deployment"]);
export function unavailableMode(mode: Mode, reason: string): ModeStatus {
  return { mode, available: false, reason, message: REASONS[reason] ?? REASONS.invalid_status!, verification_only: false };
}
export async function probeMode(mode: Mode, signal?: AbortSignal, timeoutMs = 3000): Promise<ModeStatus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new DOMException("Probe timed out", "TimeoutError")), timeoutMs);
  const combined = AbortSignal.any([controller.signal, ...(signal ? [signal] : [])]);
  try {
    const response = await fetch(`${MODE_ORIGINS[mode]}/api/v1/runtime-status`, {
      method: "GET", credentials: "omit", redirect: "error", referrerPolicy: "no-referrer", cache: "no-store", signal: combined,
    });
    if (!response.ok) return unavailableMode(mode, "unreachable");
    const value: unknown = await response.json();
    if (combined.aborted) throw combined.reason;
    if (!value || typeof value !== "object") return unavailableMode(mode, "invalid_status");
    const status = value as Partial<ModeStatus>;
    if (status.mode !== mode || typeof status.available !== "boolean" || typeof status.verification_only !== "boolean" || typeof status.reason !== "string" || !SERVER_REASONS.has(status.reason) || typeof status.message !== "string" || status.available !== (status.reason === "ready")) return unavailableMode(mode, "invalid_status");
    return { mode, available: status.available, reason: status.reason, message: REASONS[status.reason]!, verification_only: status.verification_only };
  } catch {
    return unavailableMode(mode, signal?.aborted ? "cancelled" : controller.signal.aborted ? "timeout" : "unreachable");
  } finally { clearTimeout(timeout); }
}
export function switchMode(mode: Mode, status: ModeStatus, busy: boolean, leave: () => void, navigate: (url: string) => void): boolean {
  if (busy || getPendingRequests() > 0 || !status.available || status.reason !== "ready" || status.mode !== mode) return false;
  clearCredential();
  leave();
  navigate(`${MODE_ORIGINS[mode]}/`);
  return true;
}
export async function probeAndSwitchMode(mode: Mode, signal: AbortSignal, onStatus: (status: ModeStatus) => void, isBusy: () => boolean, leave: () => void, navigate: (url: string) => void): Promise<boolean> {
  if (signal.aborted) return false;
  const status = await probeMode(mode, signal);
  if (signal.aborted) return false;
  onStatus(status);
  return switchMode(mode, status, isBusy(), leave, navigate);
}
