import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { getPendingRequests, subscribeRequestActivity } from "../lib/api";
import { MODE_ORIGINS, probeAndSwitchMode, probeMode, type Mode, type ModeStatus } from "../lib/runtime";

const MODES: Mode[] = ["offline", "deepseek"];
const LABELS: Record<Mode, string> = { offline: "Offline · 8000", deepseek: "DeepSeek · 8001" };
type Statuses = Record<Mode, ModeStatus | null>;

export function ModeChoices({ statuses, currentOrigin, busy, onSelect }: {statuses:Statuses;currentOrigin:string;busy:boolean;onSelect:(mode:Mode)=>void}) {
  return <div className="mode-choices">{MODES.map(mode => {
    const status = statuses[mode];
    const current = currentOrigin === MODE_ORIGINS[mode];
    const reason = status?.message ?? "正在检查服务状态…";
    return <div className="mode-choice" key={mode}>
      <button type="button" data-testid={`mode-${mode}`} aria-label={`切换到 ${mode === "offline" ? "Offline" : "DeepSeek"} 模式`} aria-current={current ? "true" : undefined} disabled={current || busy || !status?.available} title={current ? "当前模式" : reason} onClick={() => onSelect(mode)}>
        <strong>{LABELS[mode]}</strong><span>{current ? "当前模式" : status?.available ? "切换并重新认证" : "不可用"}</span>
      </button>
      <p data-testid={`mode-${mode}-status`} role="status">{reason}{status?.verification_only && <b>仅用于 Mock 验证，不代表真实 DeepSeek 可用。</b>}</p>
    </div>;
  })}{busy && <p className="mode-busy" role="status">请求处理中，完成后可切换模式。</p>}</div>;
}

export function ModeSelector({ busy = false, onLeave = () => {}, compact = false }: {busy?:boolean;onLeave?:()=>void;compact?:boolean}) {
  const [statuses, setStatuses] = useState<Statuses>({offline:null,deepseek:null});
  const [revision, setRevision] = useState(0);
  const [checking, setChecking] = useState(true);
  const [leaving, setLeaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const leavingRef = useRef(false);
  const selectionRef = useRef<AbortController | null>(null);
  const busyRef = useRef(busy);
  const pending = useSyncExternalStore(subscribeRequestActivity, getPendingRequests, () => 0);
  busyRef.current = busy || pending > 0;
  const blocked = busy || pending > 0 || leaving || verifying;
  const currentOrigin = typeof window === "undefined" ? "" : window.location.origin;
  useEffect(() => () => selectionRef.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setChecking(true);
    setStatuses({offline:null,deepseek:null});
    void Promise.all(MODES.map(async mode => {
      const status = await probeMode(mode, controller.signal);
      if (!controller.signal.aborted) setStatuses(current => ({...current,[mode]:status}));
    })).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [revision]);
  async function select(mode: Mode) {
    const status = statuses[mode];
    if (!status?.available || blocked || leavingRef.current || selectionRef.current || currentOrigin === MODE_ORIGINS[mode]) return;
    const controller = new AbortController();
    selectionRef.current = controller;
    setVerifying(true);
    try {
      await probeAndSwitchMode(mode, controller.signal, fresh => setStatuses(current => ({...current,[mode]:fresh})), () => busyRef.current || leavingRef.current, () => {
        leavingRef.current = true;
        setLeaving(true);
        onLeave();
      }, url => window.location.assign(url));
    } finally {
      if (selectionRef.current === controller) selectionRef.current = null;
      if (!controller.signal.aborted) setVerifying(false);
    }
  }
  return <details className={`mode-selector ${compact ? "mode-selector-compact" : ""}`} open={compact ? undefined : true} aria-label="运行模式">
    <summary>运行模式{currentOrigin === MODE_ORIGINS.offline ? " · Offline" : currentOrigin === MODE_ORIGINS.deepseek ? " · DeepSeek" : ""}{currentOrigin === MODE_ORIGINS.deepseek && statuses.deepseek?.verification_only ? "（Mock 验证）" : ""}</summary>
    <div className="mode-menu">
      <ModeChoices statuses={statuses} currentOrigin={currentOrigin} busy={blocked} onSelect={select} />
      <p className="mode-hint">切换将清空本页状态，目标服务需重新认证。会话、草稿和私有知识库不随模式转移。</p>
      <button type="button" className="text-button mode-refresh" disabled={checking || leaving || verifying} onClick={() => setRevision(value => value + 1)}>{checking || verifying ? "检查中…" : "重新检查模式"}</button>
    </div>
  </details>;
}
