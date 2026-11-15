// Single real business chat from Chromium. Called only by the budget-audited driver.
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
const require=createRequire(new URL('../../../../frontend/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const config=JSON.parse(readFileSync('\\\\wsl.localhost\\Ubuntu-24.04\\home\\panda\\.adaptive-rag-business-20261114\\browser-config.json','utf8'));
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage();
  await page.goto('http://127.0.0.1:8000/');
  await expect(page.getByTestId('mode-deepseek')).toBeEnabled({timeout:15000});
  await page.getByTestId('mode-deepseek').click();
  await expect(page).toHaveURL('http://127.0.0.1:8001/');
  await expect(page.getByLabel('本地开发凭证')).toHaveValue('');
  await page.getByLabel('本地开发凭证').fill(config.tokens.a);
  await page.getByRole('button',{name:'验证并进入'}).click();
  await expect(page.getByLabel('输入消息')).toBeVisible();
  await expect(page.locator('.mode-selector summary')).not.toContainText('Mock');
  await page.getByLabel('响应模式').selectOption('http');
  const pending=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/chat' && r.request().method()==='POST',{timeout:150000});
  await page.getByLabel('输入消息').fill('请查询 ORD95101 的订单状态和金额。');
  await page.getByRole('button',{name:'发送消息'}).click();
  const response=await pending;
  const body=await response.json();
  let rendered=false;
  if(response.ok()) {
    await expect(page.locator('.assistant-body').last()).toBeVisible({timeout:15000});
    rendered=(await page.locator('.assistant-body').last().innerText()).trim().length>0;
  }
  console.log(JSON.stringify({http_status:response.status(),body,ui:{origin:page.url(),chromium:true,mode_switch:true,fresh_credentials:true,rendered}}));
} finally {await browser.close();}
