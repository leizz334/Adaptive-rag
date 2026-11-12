import { afterEach, describe, expect, it, vi } from "vitest";
import { authenticate, clearCredential, requestJson, streamChat } from "./api";

afterEach(() => { clearCredential(); vi.unstubAllGlobals(); });
describe("verified credential transport", () => {
  it("binds the returned subject and sends bearer only in headers", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ subject: "owner-a", roles: ["user"] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ documents: [] })));
    vi.stubGlobal("fetch", fetcher);
    expect((await authenticate("x".repeat(43))).subject).toBe("owner-a");
    await requestJson("/knowledge/documents");
    expect(new Headers(fetcher.mock.calls[1]?.[1]?.headers).get("Authorization")).toBe(`Bearer ${"x".repeat(43)}`);
    expect(fetcher.mock.calls[1]?.[1]?.body).toBeUndefined();
  });
  it("fails closed with no credential without making a request", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    await expect(requestJson("/knowledge/documents")).rejects.toMatchObject({ code: "AUTH_REQUIRED" });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("handles server error codes without exposing raw detail or token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ subject: "owner-a", roles: [] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error_code: "RATE_LIMIT_BACKEND_UNAVAILABLE", message: "redis://secret" }), { status: 503 })));
    await authenticate("x".repeat(43));
    await expect(requestJson("/knowledge/documents")).rejects.toMatchObject({ code: "RATE_LIMIT_BACKEND_UNAVAILABLE", status: 503 });
  });
  it("rejects an SSE error rather than treating done as success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ subject: "owner-a", roles: [] })))
      .mockResolvedValueOnce(new Response('data: {"event":"error","error_code":"INTERNAL_ERROR","message":"secret"}\n\ndata: {"event":"done","trace_id":"t"}\n\n', { headers: { "content-type": "text/event-stream" } })));
    await authenticate("x".repeat(43));
    await expect(streamChat({ message: "hello" }, () => {}, new AbortController().signal)).rejects.toMatchObject({ code: "INTERNAL_ERROR" });
  });
  it("rejects an invalid stream MIME type", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ subject: "owner-a", roles: [] })))
      .mockResolvedValueOnce(new Response('{}', { headers: { "content-type": "application/json" } })));
    await authenticate("x".repeat(43));
    await expect(streamChat({ message: "hi" }, () => {}, new AbortController().signal)).rejects.toMatchObject({ code: "PROTOCOL_ERROR" });
  });
});

describe("credential lifecycle races", () => {
  it("a late previous identity 401 cannot clear the current verified credential", async () => {
    let finish!: (value: Response) => void;
    const oldResponse = new Promise<Response>((resolve) => { finish = resolve; });
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({subject:"owner-a",roles:[]})))
      .mockReturnValueOnce(oldResponse)
      .mockResolvedValueOnce(new Response(JSON.stringify({subject:"owner-b",roles:[]})))
      .mockResolvedValueOnce(new Response(JSON.stringify({documents:[]})));
    vi.stubGlobal("fetch", fetcher);
    await authenticate("a".repeat(43));
    const previous = requestJson("/knowledge/documents").catch(() => null);
    await authenticate("b".repeat(43));
    finish(new Response(JSON.stringify({error_code:"UNAUTHORIZED"}),{status:401}));
    await previous;
    await expect(requestJson("/knowledge/documents")).resolves.toEqual({documents:[]});
    expect(new Headers(fetcher.mock.calls[3]?.[1]?.headers).get("Authorization") === `Bearer ${"b".repeat(43)}`).toBe(true);
  });
  it("identity change aborts requests attached to the prior credential", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({subject:"owner-a",roles:[]})));
    vi.stubGlobal("fetch",fetcher);await authenticate("a".repeat(43));
    const pending = requestJson("/knowledge/documents").catch(() => null);
    const signal=fetcher.mock.calls[1]?.[1]?.signal as AbortSignal;
    clearCredential();expect(signal.aborted).toBe(true);await pending;
  });
});

describe("response body transport errors", () => {
  it.each([['TimeoutError','TIMEOUT'],['TypeError','NETWORK_ERROR']])("normalizes an SSE body %s", async (name, code) => {
    const body = new ReadableStream({start(controller) { controller.error(name === 'TypeError' ? new TypeError('RAW_SOCKET_DETAIL') : new DOMException('RAW_TIMEOUT_DETAIL','TimeoutError')); }});
    vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:'a',roles:[]})))
      .mockResolvedValueOnce(new Response(body,{headers:{'content-type':'text/event-stream'}})));
    await authenticate('x'.repeat(43));
    await expect(streamChat({message:'hello'},()=>{},new AbortController().signal)).rejects.toMatchObject({code});
  });
});

it("rejects a malformed HTTP chat envelope before the view reads nested fields",async()=>{
  const {chatHttp}=await import('./api');
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({subject:'a',roles:[]})))
    .mockResolvedValueOnce(new Response(JSON.stringify({answer:'partial'}))));
  await authenticate('x'.repeat(43));
  await expect(chatHttp({message:'hi'},new AbortController().signal)).rejects.toMatchObject({code:'PROTOCOL_ERROR'});
});
