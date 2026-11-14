import { afterEach, describe, expect, it, vi } from "vitest";
import { authenticate, clearCredential, getPendingRequests, requestJson, streamChat } from "./api";
import { probeAndSwitchMode, probeMode, switchMode, type ModeStatus } from "./runtime";

afterEach(() => { clearCredential(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const ready = (mode = "deepseek") => ({ mode, available: true, reason: "ready", message: "ready", verification_only: false });

describe("public runtime metadata", () => {
  it("probes only the fixed origin without sending an authenticated identity", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:"local",roles:[]})))
      .mockResolvedValueOnce(new Response(JSON.stringify(ready())));
    vi.stubGlobal("fetch", fetcher);
    await authenticate("x".repeat(43));
    const status = await probeMode("deepseek");
    expect(status).toMatchObject({ mode: "deepseek", available: true, reason: "ready" });
    const [url, init] = fetcher.mock.calls[1]!;
    expect(url).toBe("http://127.0.0.1:8001/api/v1/runtime-status");
    expect(init.credentials).toBe("omit");
    expect(init.redirect).toBe("error");
    expect(init.referrerPolicy).toBe("no-referrer");
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
    expect(init.body).toBeUndefined();
  });

  it.each([
    ["payment_not_authorized", "未授权付费"],
    ["budget_not_ready", "预算未就绪"],
    ["budget_exhausted", "预算已耗尽"],
    ["dependencies_unavailable", "依赖不可用"],
    ["unsupported_deployment", "不支持"],
  ])("explains %s without trusting raw server text", async (reason, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...ready(), available:false, reason, message:"RAW_SECRET" }))));
    const status = await probeMode("deepseek");
    expect(status.available).toBe(false);
    expect(status.message).toContain(message);
    expect(status.message).not.toContain("RAW_SECRET");
  });

  it.each([
    { ...ready("offline") },
    { ...ready(), available: "true" },
    { ...ready(), reason: "unexpected_reason" },
    { ...ready(), verification_only: "true" },
    { ...ready(), available: true, reason: "payment_not_authorized" },
  ])("fails closed on mismatched or malformed metadata %#", async value => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));
    expect(await probeMode("deepseek")).toMatchObject({ available:false, reason:"invalid_status" });
  });

  it("reports HTTP and network failures without a business request or fallback", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response("unavailable", {status:503})).mockRejectedValueOnce(new TypeError("private details"));
    vi.stubGlobal("fetch", fetcher);
    expect(await probeMode("offline")).toMatchObject({available:false, reason:"unreachable"});
    expect(await probeMode("deepseek")).toMatchObject({available:false, reason:"unreachable"});
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("aborts a slow probe and reports its timeout", async () => {
    vi.useFakeTimers();
    let signal!: AbortSignal;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      signal = init.signal;
      return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason)));
    }));
    const pending = probeMode("deepseek", undefined, 25);
    await vi.advanceTimersByTimeAsync(26);
    expect(signal.aborted).toBe(true);
    expect(await pending).toMatchObject({available:false,reason:"timeout"});
  });

  it("cancels probes when the selector unmounts", async () => {
    const controller = new AbortController();
    let signal!: AbortSignal;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      signal = init.signal;
      return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason)));
    }));
    const pending = probeMode("offline", controller.signal);
    controller.abort();
    expect(signal.aborted).toBe(true);
    expect(await pending).toMatchObject({available:false,reason:"cancelled"});
  });
});

describe("whole-page mode isolation", () => {
  const status: ModeStatus = { ...ready(), mode:"deepseek" };
  it("clears the credential and private view before navigating to a canonical root", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({subject:"local",roles:[]}))));
    await authenticate("x".repeat(43));
    const calls: string[] = [];
    const navigated = switchMode("deepseek", status, false, () => calls.push("cleared"), url => calls.push(url));
    expect(navigated).toBe(true);
    expect(calls).toEqual(["cleared", "http://127.0.0.1:8001/"]);
    await expect(requestJson("/sessions")).rejects.toMatchObject({code:"AUTH_REQUIRED"});
  });

  it("refuses unavailable, mismatched and busy targets without clearing the current app", () => {
    const leave = vi.fn(), navigate = vi.fn();
    expect(switchMode("deepseek", {...status, available:false}, false, leave, navigate)).toBe(false);
    expect(switchMode("offline", status, false, leave, navigate)).toBe(false);
    expect(switchMode("deepseek", status, true, leave, navigate)).toBe(false);
    expect(leave).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("blocks a switch synchronously while any business request is in flight", async () => {
    let finish!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:"local",roles:[]})))
      .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; })));
    await authenticate("x".repeat(43));
    const pending = requestJson("/knowledge/documents", {method:"POST",body:"{}"});
    const leave = vi.fn(), navigate = vi.fn();
    expect(switchMode("deepseek", status, false, leave, navigate)).toBe(false);
    finish(new Response("{}")); await pending;
    expect(switchMode("deepseek", status, false, leave, navigate)).toBe(true);
  });

  it.each(["json", "sse"])("keeps switching blocked until the entire %s response body finishes", async transport => {
    let body!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({start(controller) { body = controller; }});
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:"local",roles:[]})))
      .mockResolvedValueOnce(new Response(stream,{headers:{"content-type":transport === "sse" ? "text/event-stream" : "application/json"}})));
    await authenticate("x".repeat(43));
    const pending = transport === "sse" ? streamChat({message:"synthetic"},() => {},new AbortController().signal) : requestJson("/knowledge/documents");
    await Promise.resolve(); await Promise.resolve();
    expect(getPendingRequests()).toBe(1);
    expect(switchMode("deepseek",status,false,vi.fn(),vi.fn())).toBe(false);
    body.enqueue(new TextEncoder().encode(transport === "sse" ? 'data: {"event":"done","trace_id":"synthetic"}\n\n' : "{}"));
    body.close(); await pending;
    expect(getPendingRequests()).toBe(0);
    expect(switchMode("deepseek",status,false,vi.fn(),vi.fn())).toBe(true);
  });
});

describe("fresh availability before navigation", () => {
  it("rechecks a previously ready target and retains the current credential when authorization is revoked", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:"local",roles:[]})))
      .mockResolvedValueOnce(new Response(JSON.stringify(ready())))
      .mockResolvedValueOnce(new Response(JSON.stringify({...ready(),available:false,reason:"payment_not_authorized"})))
      .mockResolvedValueOnce(new Response("{\"documents\":[]}"));
    vi.stubGlobal("fetch",fetcher);
    await authenticate("x".repeat(43));
    expect((await probeMode("deepseek")).available).toBe(true);
    const onStatus = vi.fn(), leave = vi.fn(), navigate = vi.fn();
    expect(await probeAndSwitchMode("deepseek",new AbortController().signal,onStatus,() => false,leave,navigate)).toBe(false);
    expect(onStatus).toHaveBeenCalledWith(expect.objectContaining({available:false,reason:"payment_not_authorized"}));
    expect(leave).not.toHaveBeenCalled(); expect(navigate).not.toHaveBeenCalled();
    await expect(requestJson("/knowledge/documents")).resolves.toEqual({documents:[]});
  });

  it("checks the latest busy state after a fresh successful probe", async () => {
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify(ready()))));
    const isBusy = vi.fn(() => true), leave = vi.fn(), navigate = vi.fn();
    expect(await probeAndSwitchMode("deepseek",new AbortController().signal,vi.fn(),isBusy,leave,navigate)).toBe(false);
    expect(isBusy).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled(); expect(leave).not.toHaveBeenCalled();
  });

  it("only clears state and navigates after a fresh ready probe", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(ready())));
    vi.stubGlobal("fetch",fetcher);
    const calls: string[] = [];
    expect(await probeAndSwitchMode("deepseek",new AbortController().signal,() => calls.push("status"),() => false,() => calls.push("clear"),url => calls.push(url))).toBe(true);
    expect(fetcher.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8001/api/v1/runtime-status");
    expect(calls).toEqual(["status","clear","http://127.0.0.1:8001/"]);
  });

  it("does not update an unmounted selector or navigate after its probe is aborted", async () => {
    const controller = new AbortController(); controller.abort();
    const fetcher = vi.fn().mockRejectedValue(new DOMException("aborted","AbortError"));
    vi.stubGlobal("fetch",fetcher);
    const onStatus = vi.fn(), leave = vi.fn(), navigate = vi.fn();
    expect(await probeAndSwitchMode("deepseek",controller.signal,onStatus,() => false,leave,navigate)).toBe(false);
    expect(onStatus).not.toHaveBeenCalled(); expect(leave).not.toHaveBeenCalled(); expect(navigate).not.toHaveBeenCalled();
  });
});
