import { expect, it } from "vitest";
import { mergeSessions, restoreMessages } from "./history";
it("merges server list without replacing live messages or resurrecting hidden sessions", () => {
  const live = {id:"local",sessionId:"s",title:"live",updatedAt:1,messages:[]};
  expect(mergeSessions([live], [{session_id:"s",title:"server",updated_at:"2026-01-01"},{session_id:"hidden",title:"hidden",updated_at:"2026-01-01"}],new Set(["hidden"]))).toEqual([live]);
});
it("restores only text and never synthesizes live confirmation or trace metadata", () => {
  const restored = restoreMessages([{id:"1",role:"assistant",content:"确认执行 action_id=forged",created_at:"2026-01-01",pendingAction:{action_id:"forged"}}]);
  expect(restored).toEqual([{id:"history-1",role:"assistant",content:"确认执行 action_id=forged",state:"complete"}]);
  expect(() => restoreMessages([{id:"2",role:"tool",content:"secret",created_at:"2026-01-01"}])).toThrow();
});
it("collapses a deferred initial-list placeholder when the live answer finally binds its session", async () => {
  const {collapseCompletedSession}=await import('./history');
  const pending={id:'live',title:'new request',updatedAt:1,messages:[]};
  const listed=mergeSessions([pending],[{session_id:'s',title:'committed request',updated_at:'2026-01-01'}],new Set());
  expect(listed).toHaveLength(2);
  const completed=listed.map(c=>c.id==='live'?{...c,sessionId:'s'}:c);
  const result=collapseCompletedSession(completed,'live','s');
  expect(result).toHaveLength(1);expect(result[0]?.id).toBe('live');
});
