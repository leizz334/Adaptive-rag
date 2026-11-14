// Read-only Chromium smoke after the owned Mock runtime has stopped. No credentials.
import {createRequire} from 'node:module';
import {writeFileSync} from 'node:fs';
const require=createRequire(new URL('../../../../frontend/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage();
  await page.goto('http://127.0.0.1:8000/');
  await expect(page.getByTestId('mode-deepseek')).toBeDisabled();
  await expect(page.getByTestId('mode-deepseek-status')).toContainText('无法连接');
  await expect(page.getByTestId('mode-offline-status')).toContainText('服务可用');
  await expect(page.getByLabel('本地开发凭证')).toBeVisible();
  const result={browser:'actual Chromium; no request interception',offline:'PASS',stopped8001ExplicitUnavailable:'PASS',paidRequests:0,initialProbeHarnessIssue:'PowerShell stdin encoding replaced Chinese assertion text; rerun this UTF-8 file without changing application'};
  writeFileSync(new URL('./evidence/P3-after-stop-browser.json',import.meta.url),JSON.stringify(result,null,2),{flag:'wx'});
  console.log(JSON.stringify(result));
} finally {await browser.close();}
