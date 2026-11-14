import { useEffect, useRef, useState } from "react";
import { ArrowDown, CircleHelp, Menu, PanelLeftOpen } from "lucide-react";
import { checkHealth, getCapabilities, clearCredential, type Identity } from "./lib/api";
import { useChat } from "./hooks/useChat";
import { Composer } from "./components/Composer";
import { Logo } from "./components/Logo";
import { MessageView } from "./components/MessageView";
import { SearchDialog } from "./components/SearchDialog";
import { Sidebar } from "./components/Sidebar";
import { KnowledgePanel } from "./components/KnowledgePanel";
import { CredentialGate } from "./components/CredentialGate";
import { ModeSelector } from "./components/ModeSelector";
import type { ActionProposal } from "./types";

const SUGGESTIONS = [
  { icon: "↗", title: "退货政策", prompt: "定制商品过了七天，但有质量问题还能退吗？" },
  { icon: "◎", title: "物流进度", prompt: "帮我查一下 ORD10001 的物流进度" },
  { icon: "◇", title: "支付与发票", prompt: "电子发票一般多久可以开具？" },
  { icon: "✳", title: "售后处理", prompt: "退货申请需要提供哪些信息？" },
];

export function Workbench({ identity, onDisconnect }: { identity: Identity; onDisconnect: () => void }) {
  const chat = useChat();
  const [tab, setTab] = useState<"chat" | "knowledge">("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [modelMode, setModelMode] = useState<string | null>(null);
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("adaptive-rag-theme") === "dark" ? "dark" : "light");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("adaptive-rag-theme", theme);
  }, [theme]);
  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(controller.signal).then(setHealthy);
    void getCapabilities(controller.signal).then((c) => { if (!controller.signal.aborted) setModelMode(c?.llm ?? "模型信息不可用"); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    function onKey(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
      if (event.key === "Escape") { setSearchOpen(false); setSidebarOpen(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function newChat() {
    setTab("chat");
    chat.select(null);
    setDraft("");
    setSidebarOpen(false);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  function selectChat(id: string) { setTab("chat"); chat.select(id); setSidebarOpen(false); setSearchOpen(false); }
  function suggest(prompt: string) { setDraft(prompt); inputRef.current?.focus(); }
  function confirm(action: ActionProposal, messageId: string) {
    if (!chat.active) return;
    void messageId;
    void chat.send("确认执行", action.action_id);
  }

  return <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
    <Sidebar listBusy={chat.listBusy} listError={chat.listError} conversations={chat.conversations} activeId={chat.active?.id ?? null} open={sidebarOpen} onClose={() => { setSidebarOpen(false); setSidebarCollapsed(true); }} onNew={newChat} onSelect={selectChat} onRemove={chat.remove} onSearch={() => setSearchOpen(true)} onTheme={() => setTheme(theme === "light" ? "dark" : "light")} theme={theme} />
    <main className="main-panel">
      <header className="topbar">
        <button className="icon-button open-sidebar" aria-label="打开侧栏" title="打开侧栏" onClick={() => { setSidebarCollapsed(false); setSidebarOpen(true); }}>{sidebarCollapsed ? <PanelLeftOpen size={20} /> : <Menu size={20} />}</button>
        <span className="model-title">Adaptive RAG <small>智能助手</small></span>
        <div className="topbar-right"><ModeSelector compact busy={chat.busy || chat.listBusy} onLeave={onDisconnect} /><span className="identity-label" title="服务端认证主体">{identity.subject}</span><button className="text-button" onClick={onDisconnect}>切换身份</button><span className={`connection-pill ${healthy === false ? "offline" : ""}`}><span />{healthy === null ? "连接中" : healthy ? "已连接" : "服务未连接"}</span><button className="icon-button help-button" title="说明" aria-label="说明" onClick={() => window.open("https://github.com/leizz334/Adaptive-rag", "_blank", "noopener,noreferrer")}><CircleHelp size={19} /></button></div>
      </header>
      {healthy === false && <div className="service-banner" role="status"><strong>暂时无法连接服务</strong><span>请确认后端已启动后重试。</span></div>}
      <nav className="workspace-tabs" aria-label="工作台视图">{([["chat","对话工作台"],["knowledge","私有知识库"]] as const).map(([key,label]) => <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>{label}</button>)}</nav>
      {modelMode === "offline" && <div className="model-notice" role="status" aria-label="模型模式说明"><strong>当前服务使用 Offline 离线模式</strong><span>此模式仅支持有限的规则回答与工具操作，知识问答可能直接返回原文片段。请先在私有知识库上传相关文档，再提问并核对回答来源。</span></div>}
      {tab === "knowledge" ? <KnowledgePanel onClose={() => setTab("chat")} /> : <>
      <div className="workspace-toolbar"><span>当前模型：{modelMode ?? "读取中"}</span><label>响应模式 <select aria-label="响应模式" disabled={chat.busy} value={chat.transport} onChange={(e) => chat.setTransport(e.target.value as "sse" | "http")}><option value="sse">SSE</option><option value="http">HTTP</option></select></label></div>
      {chat.historyBusy && <p role="status">正在读取历史…</p>}
      {chat.historyError && <p role="alert">{chat.historyError}。请重新选择会话重试。</p>}
      {chat.active?.historical && <p role="status">历史文本：不含实时引用、Trace 或人工确认状态。操作需重新提出请求生成新提案。{chat.active.truncated ? "仅展示最近 100 条消息。" : ""}</p>}
      {chat.active ? <div className="chat-content"><MessageView conversation={chat.active} busy={chat.busy} onConfirm={confirm} onCancel={(messageId) => chat.dismissAction(chat.active!.id, messageId)} /></div>
        : <div className="welcome"><div className="welcome-inner"><Logo /><h1>今天有什么可以帮你？</h1><p>查询订单与售后问题，或上传文档后询问相关知识。</p><div className="suggestions">{SUGGESTIONS.map((item) => <button key={item.title} onClick={() => suggest(item.prompt)}><span className="suggestion-icon">{item.icon}</span><span><strong>{item.title}</strong><small>{item.prompt}</small></span><ArrowDown size={15} /></button>)}</div></div></div>}
      <Composer busy={chat.busy} onSend={(message) => void chat.send(message)} onStop={chat.stop} draft={draft} onDraft={setDraft} inputRef={inputRef} />
      </>}
    </main>
    {searchOpen && <SearchDialog conversations={chat.conversations} onClose={() => setSearchOpen(false)} onSelect={selectChat} />}
  </div>;
}

function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [generation, setGeneration] = useState(0);
  const disconnect = () => { clearCredential(); setIdentity(null); setGeneration(value => value + 1); };
  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => { if (event.persisted) disconnect(); };
    window.addEventListener("credential-expired", disconnect);
    window.addEventListener("pagehide", disconnect);
    window.addEventListener("pageshow", onPageShow);
    return () => { window.removeEventListener("credential-expired", disconnect); window.removeEventListener("pagehide", disconnect); window.removeEventListener("pageshow", onPageShow); };
  }, []);
  return identity ? <Workbench key={`${generation}:${identity.subject}`} identity={identity} onDisconnect={disconnect} /> : <CredentialGate key={generation} onAuthenticated={setIdentity} onLeave={disconnect} />;
}
export default App;
