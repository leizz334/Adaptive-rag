import { useState } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { authenticate, type Identity } from "../lib/api";

export function CredentialGate({ onAuthenticated }: { onAuthenticated: (identity: Identity) => void }) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <main className="credential-page"><section className="credential-card">
    <div className="brand-mark"><ShieldCheck size={28} /></div><p className="eyebrow">ADAPTIVE RAG / AGENT WORKBENCH</p>
    <h1>连接你的开发工作台</h1><p>使用由本地可信管理员签发的 Bearer 开发凭证。此页面不提供生产登录或发证服务。</p>
    <form onSubmit={(e) => { e.preventDefault(); if (busy) return; setBusy(true); setError(""); const input = token.trim(); setToken(""); void authenticate(input).then(onAuthenticated).catch((e: unknown) => setError(e instanceof Error ? e.message : "认证失败")).finally(() => setBusy(false)); }}>
      <label htmlFor="dev-credential">本地开发凭证</label><div className="credential-input"><KeyRound size={18} /><input id="dev-credential" name="development-credential" type="password" autoComplete="off" spellCheck={false} value={token} onChange={(e) => setToken(e.target.value)} placeholder="粘贴一次性提供的开发凭证" required /></div>
      <button className="primary-button" disabled={busy || !token.trim()}>{busy ? "服务端验证中…" : "验证并进入"}</button>
    </form>{error && <p className="inline-error" role="alert">{error}</p>}
    <small>凭证不写入 localStorage、会话记录或日志；刷新页面后需重新配置。身份以服务端验证结果为准。</small>
  </section></main>;
}
