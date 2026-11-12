import { useState } from "react";
import { Activity, ChevronDown } from "lucide-react";
import { requestJson } from "../lib/api";

export interface ExecutionTrace {
  root_run_id: string; session_id: string;
  availability: { storage: string; ttl_seconds: number };
  nodes: string[];
  spans: {id: string; parent_id: string | null; name: string; kind: string; status: string; latency_ms: number; metadata: Record<string, unknown>}[];
  planner_steps: { step_id: number; tool_name: string; needs_retrieval: boolean; arguments?: Record<string, unknown> }[];
  tools: { name: string; success: boolean; result?: Record<string, unknown> }[];
  retrieval: { document_id: string; chunk_id: string; title: string; excerpt: string; source?: string }[];
  memory: { mode: string; message_count: number; summary_used: boolean };
}
export function ExecutionDetails({ trace }: { trace: ExecutionTrace }) {
  return <div className="execution-details">
    <p className="inspection-note">真实服务端执行快照 · 单进程保留 {trace.availability.ttl_seconds / 60} 分钟，重启或切换进程后可能不可用。</p>
    <div className="trace-meta"><span>Memory <strong>{trace.memory.mode}</strong></span><span>历史消息 <strong>{trace.memory.message_count}</strong></span><span>摘要使用 <strong>{trace.memory.summary_used ? "是" : "否"}</strong></span></div>
    <h4>LangGraph 节点完成顺序</h4>{trace.nodes.length ? <div className="node-sequence">{trace.nodes.map((n,i) => <span key={`${i}-${n}`}><b>{i+1}</b>{n}</span>)}</div> : <p>没有已完成节点记录。</p>}
    <h4>Planner 步骤</h4>{trace.planner_steps.length ? <ol>{trace.planner_steps.map((p) => <li key={p.step_id}><code>{p.tool_name || "检索/回答"}</code> {p.needs_retrieval && <small>需要检索</small>}{p.arguments && <code className="field-summary">{JSON.stringify(p.arguments)}</code>}</li>)}</ol> : <p>该轮未生成工具计划。</p>}
    <h4>工具执行结果</h4>{trace.tools.length ? trace.tools.map((t,i) => <div className="tool-result" key={i}><strong>{t.name}</strong><span className={t.success ? "status-ok" : "status-error"}>{t.success ? "成功" : "失败"}</span>{t.result && <code className="field-summary">{JSON.stringify(t.result)}</code>}</div>) : <p>该轮没有工具执行。</p>}
    <h4>RAG 检索片段</h4>{trace.retrieval.length ? trace.retrieval.map((r) => <article className="retrieval-card" key={r.chunk_id}><strong>{r.title}</strong><small>{r.document_id} · {r.chunk_id}{r.source ? ` · ${r.source}` : ""}</small><p>{r.excerpt}</p></article>) : <p>该轮没有可公开的检索片段。</p>}
    <details><summary>节点与依赖耗时</summary><div className="span-table">{trace.spans.map((s) => <div key={s.id}><code>{s.name}</code><span>{s.status}</span><span>{s.latency_ms.toFixed(1)} ms</span></div>)}</div></details>
    <small className="trace-id">Root Run: {trace.root_run_id}</small>
  </div>;
}
export function ExecutionPanel({ sessionId, rootRunId, traceId, liveNodes = [] }: { sessionId?: string; rootRunId?: string | null; traceId?: string; liveNodes?: string[] }) {
  const [open, setOpen] = useState(false);
  const [trace, setTrace] = useState<ExecutionTrace | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function load() {
    if (!sessionId || !rootRunId || busy) return;
    setBusy(true); setError("");
    void requestJson<ExecutionTrace>(`/sessions/${encodeURIComponent(sessionId)}/traces/${encodeURIComponent(rootRunId)}`).then(setTrace).catch((e: unknown) => setError(e instanceof Error ? e.message : "快照不可用")).finally(() => setBusy(false));
  }
  return <section className="execution-panel"><button className="execution-toggle" aria-expanded={open} onClick={() => {setOpen(!open); if (!open && !trace) load();}}><Activity size={15}/><span>Agent Execution</span><small>{liveNodes.length ? `${liveNodes.length} 个实时节点事件` : "执行与来源"}</small><ChevronDown size={14}/></button>
    {open && <div>{traceId && <small className="trace-id">Trace: {traceId}</small>}{busy ? <p role="status">读取真实执行快照…</p> : trace ? <ExecutionDetails trace={trace} /> : <><p>{error || "尚无可查询快照；未开启 tracing、执行尚未完成或快照已过期。"}</p>{rootRunId && <button className="text-button" onClick={load}>重新读取快照</button>}{liveNodes.length > 0 && <p className="inspection-note">SSE 已收到完成事件：{liveNodes.join(" → ")}</p>}</>}</div>}
  </section>;
}
