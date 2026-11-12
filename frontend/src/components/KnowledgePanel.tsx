import { useEffect, useState } from "react";
import { ArrowLeft, FileText, Plus, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import { ApiError, requestJson } from "../lib/api";
import "./KnowledgePanel.css";

export interface KnowledgeDraft { document_id: string; title: string; content: string }
interface KnowledgeDocument { document_id: string; title: string; revision: number; character_count: number }
interface KnowledgeChunk { chunk_id: string; document_id: string; title: string; content: string; score: number; source: string; section?: string | null }
type SearchMode = "hybrid" | "bm25" | "dense";
class InputError extends Error {}
const emptyDraft: KnowledgeDraft = { document_id: "", title: "", content: "" };
const length = (value: string) => Array.from(value).length;

export function prepareKnowledgeDocument(draft: KnowledgeDraft): KnowledgeDraft {
  const value = { document_id: draft.document_id.trim(), title: draft.title.trim(), content: draft.content.trim() };
  if ([".", ".."].includes(value.document_id) || !/^[A-Za-z0-9_.-]{1,64}$/.test(value.document_id)) throw new InputError("文档 ID 需为 1–64 位英文字母、数字、点、下划线或短横线。");
  if (!value.title || length(value.title) > 200) throw new InputError("标题需为 1–200 个字符。");
  if (!value.content || length(value.content) > 10000 || value.content.includes("\0")) throw new InputError("正文需为 1–10000 个字符的纯文本。");
  return value;
}

export function parseKnowledgeText(filename: string, content: string): KnowledgeDraft {
  if (!/\.(txt|md)$/i.test(filename)) throw new InputError("仅支持 .txt / .md 纯文本文件，不支持 PDF、图片或 Word。");
  if (!content.trim() || length(content) > 10000 || /[\u0000\uFFFD]/.test(content)) throw new InputError("文件需为有效 UTF-8 纯文本，且正文为 1–10000 个字符。");
  const title = filename.replace(/\.(txt|md)$/i, "").trim().slice(0, 200) || "未命名文档";
  const document_id = title.replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64) || "document";
  return { document_id, title, content };
}

function safeMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof InputError ? error.message : "操作未完成，请稍后检查服务状态。";
}

export function KnowledgePanel({ onClose }: { onClose?: () => void }) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [draft, setDraft] = useState<KnowledgeDraft>(emptyDraft);
  const [editing, setEditing] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocument | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [topK, setTopK] = useState(5);
  const [chunks, setChunks] = useState<KnowledgeChunk[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  async function refresh(signal?: AbortSignal) {
    setLoading(true); setListError("");
    try {
      const value = await requestJson<{ documents: KnowledgeDocument[] }>("/knowledge/documents", { signal });
      if (!signal?.aborted) setDocuments(value.documents);
    } catch (cause) { if (!signal?.aborted) setListError(safeMessage(cause)); }
    finally { if (!signal?.aborted) setLoading(false); }
  }
  useEffect(() => { const controller = new AbortController(); void refresh(controller.signal); return () => controller.abort(); }, []);

  function resetEditor() { setDraft(emptyDraft); setEditing(false); setError(""); setNotice(""); setPendingDelete(null); }
  async function save() {
    if (busy || searching) return;
    setError(""); setNotice("");
    let value: KnowledgeDraft;
    try { value = prepareKnowledgeDocument(draft); } catch (cause) { setError(safeMessage(cause)); return; }
    setBusy(true);
    try {
      await requestJson(`/knowledge/documents/${encodeURIComponent(value.document_id)}`, { method: editing ? "PUT" : "POST", body: JSON.stringify({ title: value.title, content: value.content }) });
      setNotice(editing ? "文档已更新。可在下方检索验证。" : "文档已创建。可在下方检索验证。");
      setDraft(emptyDraft); setEditing(false); setChunks(null);
      await refresh();
    } catch (cause) { setError(safeMessage(cause)); }
    finally { setBusy(false); }
  }
  async function importFile(file: File) {
    if (busy || searching) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (file.size > 40000) throw new InputError("文件过大；仅支持最多 10000 个字符的纯文本。");
      const imported = parseKnowledgeText(file.name, await file.text());
      setDraft((current) => editing ? { ...current, content: imported.content } : imported);
      setNotice("文件已读入编辑器，尚未保存。请检查文档 ID、标题和正文后保存。");
    } catch (cause) { setError(safeMessage(cause)); }
    finally { setBusy(false); }
  }
  async function removeDocument() {
    if (!pendingDelete || busy || searching) return;
    const document = pendingDelete;
    setBusy(true); setError(""); setNotice("");
    try {
      await requestJson(`/knowledge/documents/${encodeURIComponent(document.document_id)}`, { method: "DELETE" });
      setPendingDelete(null); setNotice(`已删除「${document.title}」。`); setChunks(null);
      if (editing && draft.document_id === document.document_id) { setDraft(emptyDraft); setEditing(false); }
      await refresh();
    } catch (cause) { setError(safeMessage(cause)); }
    finally { setBusy(false); }
  }
  async function search() {
    if (searching || busy) return;
    if (!query.trim() || length(query.trim()) > 2000) { setSearchError("请输入 1–2000 个字符的检索问题。"); return; }
    setSearching(true); setSearchError(""); setChunks(null);
    try {
      const result = await requestJson<{ chunks: KnowledgeChunk[] }>("/knowledge/search", { method: "POST", body: JSON.stringify({ query: query.trim(), top_k: topK, mode }) });
      setChunks(result.chunks);
    } catch (cause) { setSearchError(safeMessage(cause)); }
    finally { setSearching(false); }
  }

  return <section className="knowledge-panel" aria-label="知识库">
    <header className="knowledge-heading"><div><p className="knowledge-eyebrow">PRIVATE KNOWLEDGE</p><h1>你的知识库</h1><p>管理当前身份的文档，并检索原文与来源。</p></div>{onClose && <button className="text-button" onClick={onClose}><ArrowLeft size={16} />返回对话</button>}</header>
    <div className="knowledge-columns">
      <section className="knowledge-card knowledge-documents" aria-label="文档列表">
        <div className="knowledge-card-heading"><h2><FileText size={18} />文档</h2><button className="icon-button" title="刷新文档" aria-label="刷新文档" disabled={loading || busy || searching} onClick={() => void refresh()}><RefreshCw size={16} /></button></div>
        {loading ? <p className="knowledge-muted" role="status">正在加载文档…</p> : listError ? <p className="knowledge-error" role="alert">{listError}</p> : documents.length === 0 ? <div className="knowledge-empty"><FileText size={28} /><p>还没有文档</p><small>从右侧创建文档或导入纯文本。</small></div> : <ul className="knowledge-document-list">{documents.map((document) => <li key={document.document_id}><div><strong>{document.title}</strong><small>{document.document_id} · 版本 {document.revision} · {document.character_count} 字符</small></div><div className="knowledge-document-actions"><button className="text-button" disabled={busy || searching} onClick={() => { setDraft({ document_id: document.document_id, title: document.title, content: "" }); setEditing(true); setPendingDelete(null); setNotice(""); setError(""); }}>编辑</button><button className="icon-button" disabled={busy || searching} aria-label={`删除 ${document.title}`} onClick={() => { setPendingDelete(document); setError(""); setNotice(""); }}><Trash2 size={15} /></button></div></li>)}</ul>}
        {pendingDelete && <div className="knowledge-delete" role="alertdialog" aria-label="确认删除文档"><strong>删除「{pendingDelete.title}」？</strong><p>文档及其检索片段将被移除。此操作无法撤销。</p><div><button className="knowledge-danger" disabled={busy || searching} onClick={() => void removeDocument()}>{busy ? "处理中…" : "确认删除"}</button><button className="text-button" disabled={busy || searching} onClick={() => setPendingDelete(null)}>取消</button></div></div>}
      </section>
      <section className="knowledge-card" aria-label="文档编辑器">
        <div className="knowledge-card-heading"><h2>{editing ? "更新文档" : "创建文档"}</h2><button className="text-button" disabled={busy || searching} onClick={resetEditor}><Plus size={15} />新建</button></div>
        <label className="knowledge-upload"><Upload size={18} /><span>导入 .txt / .md 纯文本</span><input type="file" accept="text/plain,text/markdown,.txt,.md" aria-label="上传纯文本文档" disabled={busy || searching} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importFile(file); }} /></label>
        <p className="knowledge-muted">仅支持 UTF-8 纯文本，最多 10000 字符。PDF、Word 和图片请先转成文本。</p>
        <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
          <label className="knowledge-field">文档 ID<input value={draft.document_id} readOnly={editing} disabled={busy || searching} placeholder="例如 return-policy" maxLength={64} required onChange={(event) => setDraft({ ...draft, document_id: event.target.value })} /></label>
          <label className="knowledge-field">标题<input value={draft.title} disabled={busy || searching} maxLength={200} required onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          {editing && <p className="knowledge-edit-note">更新会替换全部正文。请输入或导入完整的新正文；此处不自动读取旧文档内容。</p>}
          <label className="knowledge-field">文档正文<textarea rows={8} value={draft.content} disabled={busy || searching} required placeholder="粘贴知识原文，或导入文本文件…" onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
          <div className="knowledge-form-footer"><small>{length(draft.content)} / 10000 字符</small><button className="primary-button" disabled={busy || searching || !draft.document_id.trim() || !draft.title.trim() || !draft.content.trim() || length(draft.content) > 10000}>{busy ? "处理中…" : editing ? "保存更新" : "创建文档"}</button></div>
        </form>
      </section>
    </div>
    {notice && <p className="knowledge-notice" role="status">{notice}</p>}{error && <p className="knowledge-error" role="alert">{error}</p>}
    <section className="knowledge-card knowledge-search" aria-label="知识检索">
      <h2><Search size={18} />检索知识</h2><p className="knowledge-muted">查看匹配的原文片段及来源；检索结果不等于已完成业务操作。</p>
      <form onSubmit={(event) => { event.preventDefault(); void search(); }} className="knowledge-search-form">
        <label className="knowledge-field knowledge-query">检索问题<input value={query} maxLength={2000} disabled={searching || busy} required placeholder="例如：定制商品的退货条件" onChange={(event) => setQuery(event.target.value)} /></label>
        <label className="knowledge-field">检索方式<select value={mode} disabled={searching || busy} onChange={(event) => setMode(event.target.value as SearchMode)}><option value="hybrid">混合检索</option><option value="bm25">关键词检索</option><option value="dense">向量检索</option></select></label>
        <label className="knowledge-field">片段数<select value={topK} disabled={searching || busy} onChange={(event) => setTopK(Number(event.target.value))}>{[3, 5, 10, 20].map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
        <button className="primary-button" disabled={searching || busy || !query.trim()}>{searching ? "检索中…" : "检索"}</button>
      </form>
      {searchError && <p className="knowledge-error" role="alert">{searchError}</p>}{searching && <p className="knowledge-muted" role="status">正在检索当前身份的知识…</p>}
      {chunks !== null && (chunks.length === 0 ? <p className="knowledge-empty" role="status">没有找到匹配片段。试试调整关键词或检索方式。</p> : <div className="knowledge-results">{chunks.map((chunk) => <article key={chunk.chunk_id}><h3>{chunk.title}</h3><p>{chunk.content}</p><footer>来源：{chunk.source || "知识库"} · {chunk.document_id}{chunk.section ? ` · ${chunk.section}` : ""}<small>片段 {chunk.chunk_id}</small></footer></article>)}</div>)}
    </section>
  </section>;
}
