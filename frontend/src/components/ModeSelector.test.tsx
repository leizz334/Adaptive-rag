import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import { CredentialGate } from "./CredentialGate";
import { ModeChoices } from "./ModeSelector";
import type { ModeStatus } from "../lib/runtime";

afterEach(() => vi.unstubAllGlobals());
const offline: ModeStatus = {mode:"offline",available:true,reason:"ready",message:"服务可用",verification_only:false};
const blocked: ModeStatus = {mode:"deepseek",available:false,reason:"payment_not_authorized",message:"未授权付费，无法使用 DeepSeek 模式。",verification_only:false};

it("offers the mode entry before authentication without hiding the credential form", () => {
  const html = renderToStaticMarkup(<CredentialGate onAuthenticated={() => {}} />);
  expect(html).toContain('aria-label="运行模式"');
  expect(html).toContain('data-testid="mode-offline"');
  expect(html).toContain('data-testid="mode-deepseek"');
  expect(html).toContain('id="dev-credential"');
});

it("keeps the current Offline app available while explaining a disabled DeepSeek target", () => {
  const html = renderToStaticMarkup(<ModeChoices statuses={{offline,deepseek:blocked}} currentOrigin="http://127.0.0.1:8000" busy={false} onSelect={() => {}} />);
  expect(html).toContain("未授权付费");
  expect(html).toMatch(/data-testid="mode-deepseek"[^>]*disabled=""/);
  expect(html).toContain('aria-current="true"');
  expect(html).toContain("当前模式");
});

it("labels an isolated Mock deployment and blocks switching during active work", () => {
  const deepseek = {...blocked, available:true,reason:"ready",message:"服务可用",verification_only:true};
  const html = renderToStaticMarkup(<ModeChoices statuses={{offline,deepseek}} currentOrigin="http://127.0.0.1:8000" busy onSelect={() => {}} />);
  expect(html).toContain("仅用于 Mock 验证");
  expect(html).toContain("请求处理中");
  expect(html).toMatch(/data-testid="mode-deepseek"[^>]*disabled=""/);
});
