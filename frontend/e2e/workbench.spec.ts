import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const config = JSON.parse(readFileSync(resolve('../research/docs/agent_engineering_upgrade/s1_web_upgrade/.private/demo_api.json'),'utf8'));
const auth = (subject: 'a'|'b') => ({ Authorization: `Bearer ${config.tokens[subject]}` });
async function login(page: Page, subject: 'a'|'b' = 'a') {
  await page.goto('/'); await page.getByLabel('本地开发凭证').fill(config.tokens[subject]);
  await page.getByRole('button',{name:'验证并进入'}).click();
  await expect(page.getByTitle('服务端认证主体')).toHaveText(`web_demo_${subject}`);
}
async function send(page:Page,message:string) {
  const response = page.waitForResponse(r=>/\/api\/v1\/chat(?:\/stream)?$/.test(new URL(r.url()).pathname)&&r.request().method()==='POST');
  await page.getByLabel('输入消息').fill(message); await page.getByRole('button',{name:'发送消息'}).click();
  const r=await response;expect(r.ok()).toBeTruthy();const body=await r.text();
  const data=r.headers()['content-type']?.includes('event-stream') ? body.split(/\r?\n/).filter(l=>l.startsWith('data:')).map(l=>JSON.parse(l.slice(5))).find(e=>e.event==='answer')?.data : JSON.parse(body);
  expect(Boolean(data?.session_id)).toBeTruthy();
  await expect(page.getByRole('button',{name:'发送消息'})).toBeVisible();
  return data;
}

test('01 multi-turn Memory + actual tool state + HTTP/SSE + session switching',async({page})=>{
  await login(page);
  const first=await send(page,'请查询 ORD95101 的订单状态和金额');
  expect(first.answer).toContain('68');
  await page.getByRole('button',{name:/Agent Execution/}).last().click();
  await expect(page.locator('.execution-details').last()).toContainText('get_order');
  await expect(page.locator('.execution-details').last()).toContainText('M2');
  const second=await send(page,'这单的商品明细和是否定制也帮我核实');
  expect(second.session_id).toBe(first.session_id); expect(second.answer).toContain('演示帆布包');
  await page.getByRole('button',{name:/Agent Execution/}).last().click();
  await expect(page.locator('.execution-details').last()).toContainText('get_order_items');
  const trace=await page.request.get(`/api/v1/sessions/${second.session_id}/traces/${second.root_run_id}`,{headers:auth('a')});
  expect(trace.status()).toBe(200);expect((await trace.json()).memory.message_count).toBeGreaterThan(0);
  await page.getByRole('button',{name:'新对话',exact:true}).first().click();
  await page.getByLabel('响应模式').selectOption('http');
  const third=await send(page,'查询 ORD95101 的订单状态');expect(third.session_id).not.toBe(first.session_id);
  await page.getByRole('button',{name:'请查询 ORD95101 的订单状态和金额',exact:true}).click();
  await expect(page.locator('.user-message')).toHaveCount(2);
});

test('02 private KB upload/search/citations/update/delete and cross-tenant opaque rejection',async({page})=>{
  await login(page);await page.getByRole('tab',{name:'私有知识库'}).click();
  const id='web-policy-'+Date.now(); const policy='鲸蓝'+Date.now()+'会员退货规则';
  await page.getByLabel('上传纯文本文档').setInputFiles({name:id+'.md',mimeType:'text/markdown',buffer:Buffer.from(`# ${policy}\n${policy}：演示商品签收后三十天内可以退货，需保留合成凭证。`)});
  await page.getByLabel('文档 ID',{exact:true}).fill(id);await page.getByLabel('标题',{exact:true}).fill(policy);
  await page.getByRole('button',{name:'创建文档',exact:true}).click();
  await expect(page.getByLabel('文档列表')).toContainText(policy);
  await page.getByLabel('检索问题').fill(policy);await page.getByRole('button',{name:'检索',exact:true}).click();
  await expect(page.locator('.knowledge-search')).toContainText('三十天');
  await page.getByRole('button',{name:'返回对话'}).click();
  const result=await send(page,`${policy}是什么？`);expect(result.citations.some((c:{document_id:string})=>c.document_id===id)).toBeTruthy();
  await expect(page.getByLabel('回答来源')).toContainText(policy);
  await page.getByRole('button',{name:/Agent Execution/}).last().click();await expect(page.locator('.retrieval-card').filter({hasText:id})).toContainText('三十天');
  const foreign=await page.request.get(`/api/v1/sessions/${result.session_id}/traces/${result.root_run_id}`,{headers:auth('b')});expect(foreign.status()).toBe(404);
  const forged=await page.request.post('/api/v1/chat',{headers:auth('b'),data:{message:'查询 ORD95101',user_id:'web_demo_a'}});expect(forged.status()).toBe(403);
  const deletion=await page.request.delete('/api/v1/knowledge/documents/'+id,{headers:auth('b')});expect(deletion.status()).toBe(404);
  await page.getByRole('button',{name:'切换身份'}).click();await page.getByLabel('本地开发凭证').fill(config.tokens.b);await page.getByRole('button',{name:'验证并进入'}).click();
  await expect(page.locator('.user-message')).toHaveCount(0);await page.getByRole('tab',{name:'私有知识库'}).click();await expect(page.getByLabel('文档列表')).not.toContainText(policy);
  const bsearch=await page.request.post('/api/v1/knowledge/search',{headers:auth('b'),data:{query:policy,mode:'hybrid'}});expect((await bsearch.json()).chunks).toHaveLength(0);
  await page.getByRole('button',{name:'切换身份'}).click();await page.getByLabel('本地开发凭证').fill(config.tokens.a);await page.getByRole('button',{name:'验证并进入'}).click();await page.getByRole('tab',{name:'私有知识库'}).click();
  const ownRow=page.getByLabel('文档列表').locator('li').filter({hasText:id}); await ownRow.getByRole('button',{name:'编辑',exact:true}).click();
  await page.getByLabel('文档正文').fill(`${policy}：更新后四十天内退货，仅合成演示。`);await page.getByRole('button',{name:'保存更新'}).click();
  await page.getByLabel('检索问题').fill(policy);await page.getByRole('button',{name:'检索',exact:true}).click();await expect(page.locator('.knowledge-search')).toContainText('四十天');
  await ownRow.getByRole('button',{name:`删除 ${policy}`,exact:true}).click();await page.getByRole('button',{name:'确认删除',exact:true}).click();await expect(page.getByLabel('文档列表')).not.toContainText(id);
});

test('03 Planner + HITL confirmation + actual cancellation + idempotent replay',async({page})=>{
  await login(page);const order=process.env.S1WEB_CANCEL_ORDER||'ORD95102';
  const proposal=await send(page,`请取消订单 ${order}`);expect(proposal.pending_action?.tool_name).toBe('cancel_order');
  await expect(page.getByRole('button',{name:'确认执行',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:/Agent Execution/}).last().click();await expect(page.locator('.execution-details')).toContainText('cancel_order');
  const action=proposal.pending_action.action_id;
  const wrong=await page.request.post(`/api/v1/sessions/${proposal.session_id}/actions/${action}/cancel`,{headers:auth('b')});expect(wrong.status()).toBe(404);
  await page.getByRole('button',{name:'确认执行',exact:true}).click();await expect(page.getByRole('button',{name:'幂等重放（同一 Action）'})).toBeEnabled();
  await expect(page.locator('.assistant-body').last()).toContainText('已取消');
  await page.getByRole('button',{name:'幂等重放（同一 Action）'}).click();await expect(page.getByRole('button',{name:'幂等重放（同一 Action）'}).first()).toBeEnabled();
  const status=await page.request.get(`/api/v1/sessions/${proposal.session_id}/actions/${action}`,{headers:auth('a')});expect((await status.json()).status).toBe('completed');
  const cancel=await page.request.post(`/api/v1/sessions/${proposal.session_id}/actions/${action}/cancel`,{headers:auth('a')});expect(cancel.status()).toBe(409);
});

test('04 revoke pending proposal + cross-user session and refresh credential isolation',async({page})=>{
  await login(page);const proposal=await send(page,'请取消订单 ORD95104');
  const action=proposal.pending_action.action_id;
  await expect(page.getByRole('button',{name:'取消操作'})).toBeEnabled();await page.getByRole('button',{name:'取消操作'}).click();await expect(page.locator('.action-card')).toContainText('已撤销');
  const confirm=await page.request.post('/api/v1/chat',{headers:auth('a'),data:{message:'确认执行',session_id:proposal.session_id,confirm_action_id:action,idempotency_key:action}});expect(confirm.status()).toBe(400);
  const hijack=await page.request.post('/api/v1/chat',{headers:auth('b'),data:{message:'查询 ORD95201',session_id:proposal.session_id}});expect(hijack.status()).toBe(400);
  expect(await page.evaluate(()=>Object.values(localStorage).some(s=>s.includes('Bearer')||s.includes('ORD95104')))).toBeFalsy();
  await page.reload();await expect(page.getByLabel('本地开发凭证')).toBeVisible();
});

test('05 honest Experience history + responsive workbench',async({page})=>{
  await login(page);await page.getByRole('tab',{name:'Experience Shadow'}).click();
  await expect(page.getByText('EXPERIENCE_BENEFIT=NOT_ESTABLISHED',{exact:true})).toBeVisible();await expect(page.getByRole('switch')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});await expect(page.getByRole('heading',{name:'经验与 Shadow'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

test('06 actual offline network failure and transport cancellation do not auto-replay',async({page,context})=>{
  await login(page);
  await context.setOffline(true);
  await page.getByLabel('输入消息').fill('查询 ORD95101 的订单状态');await page.getByRole('button',{name:'发送消息'}).click();
  await expect(page.locator('.message-error')).toContainText('NETWORK_ERROR');
  await expect(page.locator('.message-error')).toContainText('结果可能已提交');
  await context.setOffline(false);
  const session=await context.newCDPSession(page);
  await session.send('Network.enable');
  await session.send('Network.emulateNetworkConditions',{offline:false,latency:1500,downloadThroughput:200000,uploadThroughput:200000});
  await page.getByLabel('输入消息').fill('再查询 ORD95101 的订单状态');await page.getByRole('button',{name:'发送消息'}).click();
  await page.getByRole('button',{name:'停止生成'}).click();
  await expect(page.locator('.assistant-body').last()).toContainText('服务端结果可能已提交');
  await session.send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await session.detach();
});
