import type { Conversation, Message } from "../types";
import { ApiError } from "./api";
export interface SessionSummary { session_id: string; title: string; updated_at: string }
export function mergeSessions(local: Conversation[], remote: SessionSummary[], hidden: Set<string>): Conversation[] {
  if (!Array.isArray(remote) || remote.some(s => typeof s.session_id !== "string" || typeof s.title !== "string" || !Number.isFinite(Date.parse(s.updated_at)))) throw new ApiError("PROTOCOL_ERROR");
  const known = new Set(local.map(s => s.sessionId));
  return [...local, ...remote.filter(s => !known.has(s.session_id) && !hidden.has(s.session_id)).map(s => ({id:`server-${s.session_id}`,sessionId:s.session_id,title:s.title,updatedAt:Date.parse(s.updated_at),messages:[],historyLoaded:false}))].sort((a,b) => b.updatedAt-a.updatedAt).slice(0,50);
}
export function restoreMessages(value: unknown): Message[] {
  if (!Array.isArray(value) || value.length > 100) throw new ApiError("PROTOCOL_ERROR");
  return value.map(m => {
    if (!m || typeof m.id !== "string" || !["user","assistant"].includes(m.role) || typeof m.content !== "string" || typeof m.created_at !== "string") throw new ApiError("PROTOCOL_ERROR");
    return {id:`history-${m.id}`,role:m.role,content:m.content,state:"complete"};
  });
}

export function collapseCompletedSession(items: Conversation[], liveId: string, sessionId: string): Conversation[] {
  return items.filter(item => item.id === liveId || item.sessionId !== sessionId);
}
