// Actual Chromium against both stacks, deliberately no chat/model traffic.
import {createRequire} from 'node:module';
import {readFileSync,writeFileSync} from 'node:fs';
const require=createRequire(new URL('../../../../frontend/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const privateRoot='\\\\wsl.localhost\\Ubuntu-24.04\\home\\panda\\';
const offline=JSON.parse(readFileSync(privateRoot+'.adaptive-rag-usability-20261114\\browser-config.json','utf8'));
const real=JSON.parse(readFileSync(privateRoot+'.adaptive-rag-business-20261114\\browser-config.json','utf8'));
const browser=await chromium.launch({headless:true});
let chats=0;
try {
  const page=await browser.newPage();
  await page.route('**/api/v1/chat**',async route=>{chats++;await route.abort();});
  await page.goto('http://127.0.0.1:8000/');
  await expect(page.getByTestId('mode-offline-status')).toContainText('服务可用');
  await expect(page.getByTestId('mode-deepseek-status')).toContainText('未授权付费');
  await expect(page.getByTestId('mode-deepseek')).toBeDisabled();
  await page.getByLabel('本地开发凭证').fill(offline.tokens.a);
  await page.getByRole('button',{name:'验证并进入'}).click();
  await expect(page.getByLabel('输入消息')).toBeVisible();
  await page.goto('http://127.0.0.1:8001/');
  await expect(page.getByLabel('本地开发凭证')).toHaveValue('');
  await page.getByLabel('本地开发凭证').fill(real.tokens.a);
  await page.getByRole('button',{name:'验证并进入'}).click();
  await expect(page.getByLabel('输入消息')).toBeVisible();
  await expect(page.locator('.mode-selector summary')).toContainText('DeepSeek');
  await expect(page.locator('.mode-selector summary')).not.toContainText('Mock');
  const result={offlineLogin:'PASS',real8001Login:'PASS',independentCredentialGate:'PASS',explicitServerPaidGateReason:'PASS',modelChatRequests:chats,paidRequests:0};
  expect(chats).toBe(0);
  writeFileSync(new URL('./evidence/D2-browser-safe.json',import.meta.url),JSON.stringify(result,null,2),{flag:'wx'});
  console.log(JSON.stringify(result));
} finally {await browser.close();}
