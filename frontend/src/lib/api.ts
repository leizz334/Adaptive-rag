import type { Capabilities, ChatRequest, ChatResponse, StreamEvent } from "../types";
import { SseDecoder } from "./sse";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
let credential = "";
let credentialScope = new AbortController();
const responseSignals = new WeakMap<Response, AbortSignal>();
let pendingRequests = 0;
const activityListeners = new Set<() => void>();
export const getPendingRequests = () => pendingRequests;
export function subscribeRequestActivity(listener: () => void) { activityListeners.add(listener); return () => { activityListeners.delete(listener); }; }
async function trackRequest<T>(request: () => Promise<T>): Promise<T> {
  pendingRequests++; activityListeners.forEach(listener => listener());
  try { return await request(); }
  finally { pendingRequests--; activityListeners.forEach(listener => listener()); }
}
export interface Identity { subject: string; roles: string[] }
export class ApiError extends Error {
  constructor(public code: string, public status = 0, public traceId = "") {
    const messages: Record<string, string> = {
      AUTH_REQUIRED: "请先配置本地开发凭证。", UNAUTHORIZED: "凭证无效或已过期，请重新配置。",
      FORBIDDEN: "当前身份无权执行此操作。", NOT_FOUND: "记录不存在、已过期或不属于当前身份。",
      RATE_LIMITED: "请求过于频繁，请稍后手动重试。", PROTOCOL_ERROR: "响应协议异常，未自动重试。",
      TIMEOUT: "请求超时，结果可能已提交。请先核对状态，不要重复执行。",
      NETWORK_ERROR: "网络异常，结果可能已提交。请先核对状态。",
      INTERNAL_ERROR: "服务暂时不可用，请稍后检查。",
    };
    super(messages[code] ?? (status === 503 ? "依赖不可用，操作已被安全拒绝。" : `操作未完成（${code} / HTTP ${status}）`));
  }
}
export function clearCredential() { credentialScope.abort(); credentialScope = new AbortController(); credential = ""; }
function headers(token = credential): Headers {
  if (!token) throw new ApiError("AUTH_REQUIRED", 401);
  return new Headers({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" });
}
function assertBase() {
  if (!API_BASE) return;
  try {
    const url = new URL(API_BASE, window.location.origin);
    if (url.origin !== window.location.origin || url.username || url.password || url.search || url.hash || !["http:", "https:"].includes(url.protocol)) throw new Error("Unsafe API base");
  } catch { throw new ApiError("PROTOCOL_ERROR"); }
}
async function checked(path: string, init: RequestInit = {}, token = credential): Promise<Response> {
  assertBase();
  const authHeaders = headers(token);
  const scope = credentialScope;
  const combined = AbortSignal.any([scope.signal, ...(init.signal ? [init.signal] : []), AbortSignal.timeout(120_000)]);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, { ...init, headers: authHeaders, signal: combined, credentials: "omit", redirect: "error" });
  } catch (error) {
    if (init.signal?.aborted || scope.signal.aborted) throw error;
    throw new ApiError(error instanceof DOMException && error.name === "TimeoutError" ? "TIMEOUT" : "NETWORK_ERROR");
  }
  if (scope.signal.aborted) throw new DOMException("Credential scope ended", "AbortError");
  responseSignals.set(response, combined);
  if (!response.ok) {
    let code = ({ 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMITED" } as Record<number, string>)[response.status] ?? "INTERNAL_ERROR";
    let trace = response.headers.get("x-trace-id") ?? "";
    try { const data = await response.json(); if (typeof data.error_code === "string" && /^[A-Z_]{1,64}$/.test(data.error_code)) code = data.error_code; if (typeof data.trace_id === "string") trace = data.trace_id.slice(0, 128); } catch { /* safe status-based text */ }
    if (response.status === 401 && credential === token && credentialScope === scope) { clearCredential(); if (typeof window !== "undefined") window.dispatchEvent(new Event("credential-expired")); }
    throw new ApiError(code, response.status, trace);
  }
  return response;
}
export function authenticate(token: string): Promise<Identity> { return trackRequest(() => authenticateCredential(token)); }
async function authenticateCredential(token: string): Promise<Identity> {
  clearCredential();
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(token)) throw new ApiError("UNAUTHORIZED", 401);
  const scope = credentialScope;
  const response = await checked("/auth/me", {}, token);
  let value: Identity;
  try { value = await response.json() as Identity; } catch(error) { throw bodyError(error, response); }
  if (!value || typeof value.subject !== "string" || !Array.isArray(value.roles)) throw new ApiError("PROTOCOL_ERROR");
  if (scope !== credentialScope) throw new DOMException("Credential scope ended", "AbortError");
  credential = token;
  return value;
}
export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  return trackRequest(async () => {
    const response = await checked(path, init);
    try { return await response.json() as T; } catch (error) { throw bodyError(error, response, init.signal ?? undefined); }
  });
}
function bodyError(error: unknown, response: Response, userSignal?: AbortSignal): unknown {
  if (error instanceof ApiError || userSignal?.aborted) return error;
  const reason = responseSignals.get(response)?.reason;
  if (reason instanceof DOMException && reason.name === "TimeoutError" || error instanceof DOMException && error.name === "TimeoutError") return new ApiError("TIMEOUT");
  if (reason instanceof DOMException && reason.name === "AbortError") return reason;
  return new ApiError(error instanceof SyntaxError ? "PROTOCOL_ERROR" : "NETWORK_ERROR");
}
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try { assertBase(); return (await fetch(`${API_BASE}/api/v1/health`, { signal, credentials: "omit", redirect: "error" })).ok; } catch { return false; }
}
export async function getCapabilities(signal?: AbortSignal): Promise<Capabilities | null> {
  try { return await requestJson<Capabilities>("/capabilities", { signal }); } catch { return null; }
}
function chatEnvelope(value: unknown): ChatResponse {
  if (typeof value !== "object" || value === null) throw new ApiError("PROTOCOL_ERROR");
  const v = value as Partial<ChatResponse>;
  if (typeof v.answer !== "string" || typeof v.session_id !== "string" || typeof v.trace_id !== "string" || !v.latency || !Number.isFinite(v.latency.total_ms) || !Array.isArray(v.citations)) throw new ApiError("PROTOCOL_ERROR");
  if (v.citations.some(c => !c || typeof c.title !== "string" || typeof c.document_id !== "string" || typeof c.chunk_id !== "string")) throw new ApiError("PROTOCOL_ERROR");
  return v as ChatResponse;
}
export async function chatHttp(payload: ChatRequest, signal: AbortSignal): Promise<ChatResponse> {
  return chatEnvelope(await requestJson<unknown>("/chat", { method: "POST", body: JSON.stringify(payload), signal }));
}
export function streamChat(payload: ChatRequest, onEvent: (event: StreamEvent) => void, signal: AbortSignal): Promise<void> {
  return trackRequest(() => consumeChatStream(payload, onEvent, signal));
}
async function consumeChatStream(payload: ChatRequest, onEvent: (event: StreamEvent) => void, signal: AbortSignal): Promise<void> {
  const response = await checked("/chat/stream", { method: "POST", body: JSON.stringify(payload), signal });
  if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) throw new ApiError("PROTOCOL_ERROR");
  const reader = response.body.getReader();
  const decoder = new SseDecoder();
  const emit = (event: StreamEvent) => {
    if (event.event === "error") throw new ApiError(/^[A-Z_]{1,64}$/.test(event.error_code) ? event.error_code : "INTERNAL_ERROR", 0, event.trace_id);
    if (event.event === "answer") event = {event:"answer",data:chatEnvelope(event.data)};
    if (event.event === "token" && typeof event.text !== "string" || event.event === "node" && typeof event.node !== "string") throw new ApiError("PROTOCOL_ERROR");
    onEvent(event);
  };
  try {
    while (true) { const { done, value } = await reader.read(); if (done) break; for (const event of decoder.feed(value)) emit(event); }
    for (const event of decoder.finish()) emit(event);
  } catch (error) { throw bodyError(error, response, signal); } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
