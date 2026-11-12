import { defineConfig } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
const runId = process.env.S1WEB_BROWSER_RUN ?? `${Date.now()}`;
if (!/^[A-Za-z0-9_-]{1,64}$/.test(runId)) throw new Error('Invalid isolated browser run id');
const outputRoot = process.env.S1WEB_OUTPUT_ROOT ?? '../research/docs/agent_engineering_upgrade/s1_web_upgrade/.private';
const report = `${outputRoot}/browser-${runId}.json`;
if (existsSync(report)) throw new Error('Browser result already exists; choose a fresh run id');
const config = JSON.parse(readFileSync(resolve(process.env.S1WEB_DEMO_CONFIG ?? '../research/docs/agent_engineering_upgrade/s1_web_upgrade/.private/demo_api.json'), 'utf8'));
export default defineConfig({
  testDir: './e2e', timeout: 45_000, expect: { timeout: 12_000 }, fullyParallel: false, workers: 1, retries: 0,
  outputDir: `${outputRoot}/browser-artifacts-${runId}`,
  reporter: [['list'], ['json', { outputFile: report }]],
  use: { baseURL: `http://127.0.0.1:${config.port}`, browserName: 'chromium', headless: true, viewport: {width:1440,height:1000}, trace:'off', screenshot:'off', video:'off' },
});
