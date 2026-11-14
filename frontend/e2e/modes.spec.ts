import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Root supplies fresh synthetic credentials for the two independent registries.
// This suite never loads provider credentials or starts a backend/model process.
type Mode = "offline" | "deepseek";
type Config = Record<Mode, {token:string;verification_only?:boolean}>;
const config: Config | null = process.env.S1WEB_MODE_CONFIG ? JSON.parse(readFileSync(resolve(process.env.S1WEB_MODE_CONFIG), "utf8")) : null;
const origins = {offline:"http://127.0.0.1:8000",deepseek:"http://127.0.0.1:8001"};
test.skip(!config, "Requires S1WEB_MODE_CONFIG with isolated Offline and Mock credentials");
test.beforeEach(() => {
  if (!config || ![config.offline.token,config.deepseek.token].every(token => /^[A-Za-z0-9_-]{43,128}$/.test(token)) || config.offline.token === config.deepseek.token) throw new Error("Mode test requires two valid, distinct synthetic credentials");
});

async function login(page: Page, mode: Mode) {
  await page.getByLabel("本地开发凭证").fill(config![mode].token);
  await page.getByRole("button", {name:"验证并进入"}).click();
  await expect(page.getByLabel("输入消息")).toBeVisible();
}
async function openModes(page: Page) {
  const selector = page.locator(".mode-selector");
  if ((await selector.getAttribute("open")) === null) await selector.locator("summary").click();
}
async function switchTo(page: Page, mode: Mode) {
  await openModes(page);
  const button = page.getByTestId(`mode-${mode}`);
  await expect(button).toBeEnabled();
  await button.click();
  await expect(page).toHaveURL(`${origins[mode]}/`);
  await expect(page.getByLabel("本地开发凭证")).toHaveValue("");
  await expect(page.getByLabel("输入消息")).toHaveCount(0);
}
function watchIsolation(page: Page) {
  const violations: string[] = [];
  page.on("request", request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/v1/")) return;
    const authorization = request.headers().authorization;
    if (url.pathname === "/api/v1/runtime-status") {
      if (authorization || request.headers().cookie) violations.push("metadata carried identity");
      if (!Object.values(origins).includes(url.origin)) violations.push("metadata used another origin");
    } else if (authorization) {
      const expected = url.origin === origins.offline ? config!.offline.token : url.origin === origins.deepseek ? config!.deepseek.token : null;
      if (!expected || authorization !== `Bearer ${expected}`) violations.push("credential crossed backend origin");
    }
  });
  return violations;
}

test("mode gate switches whole pages without credential, query or input transfer; Back requires authentication", async ({page}) => {
  const violations = watchIsolation(page);
  await page.goto(`${origins.offline}/?session_id=synthetic-source-only#synthetic-draft`);
  await page.getByLabel("本地开发凭证").fill(config!.offline.token);
  await switchTo(page,"deepseek");
  if (config!.deepseek.verification_only !== false) await expect(page.getByTestId("mode-deepseek-status")).toContainText("仅用于 Mock 验证");
  await page.goBack();
  await expect(page.getByLabel("本地开发凭证")).toHaveValue("");
  await expect(page.getByLabel("输入消息")).toHaveCount(0);
  await switchTo(page,"deepseek");
  await switchTo(page,"offline");
  expect(violations).toEqual([]);
});

test("authenticated modes keep server history and private knowledge on their own origin and clear drafts", async ({page}) => {
  const violations = watchIsolation(page);
  const marker = `mode-${Date.now()}`;
  const documentId = `${marker}-document`;
  let created = false;
  await page.goto(`${origins.offline}/`);
  await login(page,"offline");
  try {
    await page.getByLabel("响应模式").selectOption("http");
    const responsePromise = page.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/chat" && response.request().method() === "POST");
    await page.getByLabel("输入消息").fill(`${marker} 请介绍当前服务`);
    await page.getByRole("button",{name:"发送消息"}).click();
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    const sessionId = (await response.json()).session_id;
    await expect(page.getByRole("button",{name:"发送消息"})).toBeVisible();
    await page.getByLabel("输入消息").fill(`${marker} 未发送草稿`);
    await page.getByRole("tab",{name:"私有知识库"}).click();
    await page.getByLabel("文档 ID",{exact:true}).fill(documentId);
    await page.getByLabel("标题",{exact:true}).fill(marker);
    await page.getByLabel("文档正文").fill(`${marker}：仅供模式隔离验证的合成文档。`);
    await page.getByRole("button",{name:"创建文档",exact:true}).click();
    await expect(page.getByLabel("文档列表")).toContainText(documentId);
    created = true;
    await page.getByLabel("文档正文").fill(`${marker} 未保存知识库草稿`);
    await switchTo(page,"deepseek");
    await login(page,"deepseek");
    if (config!.deepseek.verification_only !== false) await expect(page.locator(".mode-selector summary")).toContainText("Mock 验证");
    await expect(page.getByLabel("输入消息")).toHaveValue("");
    await expect(page.getByRole("navigation",{name:"会话列表"})).not.toContainText(marker);
    const foreign = await page.request.get(`${origins.deepseek}/api/v1/sessions/${encodeURIComponent(sessionId)}/messages`,{headers:{Authorization:`Bearer ${config!.deepseek.token}`}});
    expect(foreign.status()).toBe(404);
    await page.getByRole("tab",{name:"私有知识库"}).click();
    await expect(page.getByLabel("文档列表")).not.toContainText(documentId);
    await expect(page.getByLabel("文档正文")).toHaveValue("");
    await page.getByLabel("文档正文").fill("Mock 模式未保存的独立草稿");
    await switchTo(page,"offline");
    await login(page,"offline");
    await expect(page.getByLabel("输入消息")).toHaveValue("");
    await expect(page.getByRole("navigation",{name:"会话列表"})).toContainText(marker);
    await page.getByRole("tab",{name:"私有知识库"}).click();
    await expect(page.getByLabel("文档列表")).toContainText(documentId);
    await expect(page.getByLabel("文档正文")).toHaveValue("");
    expect(await page.evaluate(value => Object.values(localStorage).some(item => item.includes(value)),marker)).toBe(false);
    expect(violations).toEqual([]);
  } finally {
    if (created) {
      const deletion = await page.request.delete(`${origins.offline}/api/v1/knowledge/documents/${documentId}`,{headers:{Authorization:`Bearer ${config!.offline.token}`}});
      expect(deletion.status()).toBe(200);
    }
  }
});

test("unavailable, mismatched and timed-out targets explain the reason while Offline stays usable", async ({page}) => {
  const metadata = `${origins.deepseek}/api/v1/runtime-status`;
  await page.route(metadata,route => route.fulfill({json:{mode:"deepseek",available:false,reason:"payment_not_authorized",message:"untrusted",verification_only:false}}));
  await page.goto(`${origins.offline}/`);
  await expect(page.getByTestId("mode-deepseek-status")).toContainText("未授权付费");
  await expect(page.getByTestId("mode-deepseek")).toBeDisabled();
  await login(page,"offline");
  await openModes(page);
  await expect(page.getByTestId("mode-deepseek-status")).toContainText("未授权付费");
  await expect(page.getByLabel("输入消息")).toBeEnabled();
  await page.unroute(metadata);
  await page.route(metadata,route => route.fulfill({json:{mode:"offline",available:true,reason:"ready",message:"ready",verification_only:false}}));
  await page.getByRole("button",{name:"重新检查模式"}).click();
  await expect(page.getByTestId("mode-deepseek-status")).toContainText("模式不匹配");
  await page.unroute(metadata);
  await page.route(metadata,async route => { await new Promise(resolve => setTimeout(resolve,3500)); await route.abort().catch(() => {}); });
  await page.getByRole("button",{name:"重新检查模式"}).click();
  await expect(page.getByTestId("mode-deepseek-status")).toContainText("超时");
  await expect(page.getByTestId("mode-deepseek")).toBeDisabled();
  await expect(page).toHaveURL(`${origins.offline}/`);
  await expect(page.getByLabel("输入消息")).toBeEnabled();
});

test("active API requests block mode switching and restored pages require fresh credentials", async ({page,context}) => {
  await page.goto(`${origins.offline}/`); await login(page,"offline");
  await openModes(page);
  await expect(page.getByTestId("mode-deepseek")).toBeEnabled();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions",{offline:false,latency:2000,downloadThroughput:200000,uploadThroughput:200000});
  const read = page.waitForRequest(request => new URL(request.url()).pathname === "/api/v1/knowledge/documents");
  await page.getByRole("tab",{name:"私有知识库"}).click(); await read;
  await expect(page.getByTestId("mode-deepseek")).toBeDisabled();
  await expect(page.locator(".mode-busy")).toContainText("请求处理中");
  await cdp.send("Network.emulateNetworkConditions",{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await cdp.detach();
  await expect(page.getByTestId("mode-deepseek")).toBeEnabled();
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true})));
  await expect(page.getByLabel("本地开发凭证")).toHaveValue("");
  await expect(page.getByLabel("输入消息")).toHaveCount(0);
  await page.getByLabel("本地开发凭证").fill("synthetic-input-not-to-restore");
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true})));
  await expect(page.getByLabel("本地开发凭证")).toHaveValue("");
});

test("a ready target revoked at click time preserves the current login and draft and shows its new reason", async ({page}) => {
  const metadata = `${origins.deepseek}/api/v1/runtime-status`;
  await page.route(metadata,route => route.fulfill({json:{mode:"deepseek",available:true,reason:"ready",message:"ready",verification_only:true}}));
  await page.goto(`${origins.offline}/`); await login(page,"offline");
  await openModes(page);
  await expect(page.getByTestId("mode-deepseek")).toBeEnabled();
  const draft = "仅供验证：目标付费授权撤销后保留本页草稿";
  await page.getByLabel("输入消息").fill(draft);
  await page.unroute(metadata);
  await page.route(metadata,route => route.fulfill({json:{mode:"deepseek",available:false,reason:"payment_not_authorized",message:"untrusted",verification_only:true}}));
  await page.getByTestId("mode-deepseek").click();
  await expect(page.getByTestId("mode-deepseek-status")).toContainText("未授权付费");
  await expect(page).toHaveURL(`${origins.offline}/`);
  await expect(page.getByLabel("输入消息")).toHaveValue(draft);
  await expect(page.getByTestId("mode-deepseek")).toBeDisabled();
  await expect(page.getByLabel("本地开发凭证")).toHaveCount(0);
});
