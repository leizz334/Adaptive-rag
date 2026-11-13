import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import { Workbench } from "./App";

afterEach(() => vi.unstubAllGlobals());

it("offers only chat and private knowledge tabs while keeping session navigation and the composer", () => {
  vi.stubGlobal("localStorage", { getItem: () => null });
  const html = renderToStaticMarkup(<Workbench identity={{ subject: "test-user", roles: [] }} onDisconnect={() => {}} />);
  const navigation = html.match(/<nav class="workspace-tabs"[^>]*>(.*?)<\/nav>/s)?.[1] ?? "";
  const tabs = [...navigation.matchAll(/<button[^>]*role="tab"[^>]*>(.*?)<\/button>/g)].map(match => match[1]);

  expect(tabs).toEqual(["对话工作台", "私有知识库"]);
  expect(navigation).toContain('aria-selected="true"');
  expect(html).toContain('aria-label="会话列表"');
  expect(html).toContain('aria-label="输入消息"');
  expect(html).toContain('aria-label="响应模式"');
});
