const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  page.setDefaultTimeout(15000);
  const errors = [];
  page.on('pageerror', (error) => { errors.push(error.message); console.error('Browser error:', error.message); });
  const root = process.env.APP_URL || 'http://127.0.0.1:5175';
  const backend = process.env.API_URL || 'http://127.0.0.1:8000';
  const requests = [];
  page.on('request', (request) => { if (request.url().endsWith('/api/exams/scaffold')) requests.push(request.postDataJSON()); });
  try {
    const fixture = await (await fetch(backend + '/fixture')).json();
    await page.route('**/samples.json', (route) => route.fulfill({ json: fixture }));
    await page.goto(root, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: '开始定制学习方案', exact: true }).click();
    await page.getByRole('button', { name: '加载样例', exact: true }).click();
    const path = page.getByRole('region', { name: '个性化学习路径' });
    await path.waitFor();
    assert.equal(await path.locator('li').count(), 3);
    assert.match(await path.innerText(), /机器人坐标系/);
    assert.equal(await page.getByRole('img', { name: /知识掌握度雷达图/ }).count(), 1);
    assert.equal(await page.getByRole('img', { name: /资源序号与难度/ }).count(), 1);
    await path.getByRole('button', { name: '查看配套资源' }).first().click();
    const panel = page.getByRole('region', { name: '分步学习答疑' }).first();
    await panel.getByLabel('学习问题').fill('机器人坐标系如何选择？');
    await panel.getByRole('button', { name: '开始提问', exact: true }).click();
    await panel.getByRole('heading', { name: 'L1 · 引导思考' }).waitFor();
    assert.equal(await panel.getByRole('heading', { name: 'L3 · 完整答案' }).count(), 0);
    assert.equal(await panel.getByRole('button', { name: '将补充内容加入当前资源' }).count(), 0);
    await panel.getByLabel('我的思考').fill('选择用户坐标系');
    await panel.getByRole('button', { name: '下一步提示', exact: true }).click();
    await panel.getByRole('heading', { name: 'L2 · 给出线索' }).waitFor();
    await panel.getByRole('button', { name: '查看完整答案', exact: true }).click();
    await panel.getByRole('heading', { name: 'L3 · 完整答案' }).waitFor();
    assert.match(await panel.innerText(), /知识库来源/);
    assert.deepEqual(requests.slice(0, 3).map((r) => r.current_tier), [0, 1, 2]);
    assert.equal(requests[1].question, requests[0].question);
    assert.equal(requests[1].student_answer, '选择用户坐标系');
    assert.equal(requests[0].skill_gaps.length, 3);
    await panel.getByRole('button', { name: '将补充内容加入当前资源' }).click();
    await panel.getByRole('button', { name: '补充已加入当前资源' }).waitFor();
    // A new question must reset the tier. Stuck learners may skip L2.
    await panel.getByLabel('学习问题').fill('急停如何恢复？');
    await panel.getByRole('button', { name: '开始提问', exact: true }).click();
    await panel.getByRole('heading', { name: 'L1 · 引导思考' }).waitFor();
    assert.equal(await panel.getByRole('heading', { name: 'L3 · 完整答案' }).count(), 0);
    await panel.getByRole('button', { name: '我不知道，查看答案' }).click();
    await panel.getByRole('heading', { name: 'L3 · 完整答案' }).waitFor();
    assert.equal(await panel.getByRole('heading', { name: 'L2 · 给出线索' }).count(), 0);
    // A non-scaffold question must call the original QA endpoint.
    await panel.getByLabel('学习问题').fill('你好');
    await panel.getByRole('button', { name: '开始提问', exact: true }).click();
    await panel.getByText('这是普通答疑接口的测试响应。', { exact: true }).waitFor();
    // Failed requests must stay retryable without revealing stale answers.
    await page.route('**/api/exams/scaffold', (route) => route.fulfill({ status: 503, json: { detail: '服务暂不可用' } }), { times: 1 });
    await panel.getByLabel('学习问题').fill('坐标系是什么？');
    await panel.getByRole('button', { name: '开始提问', exact: true }).click();
    await panel.getByRole('alert').waitFor();
    assert.equal(await panel.getByRole('heading', { name: 'L3 · 完整答案' }).count(), 0);
    await panel.getByRole('button', { name: '开始提问', exact: true }).click();
    await panel.getByRole('heading', { name: 'L1 · 引导思考' }).waitFor();
    if (process.env.SCREENSHOT_DIR) {
      await fs.mkdir(process.env.SCREENSHOT_DIR, { recursive: true });
      await panel.screenshot({ path: process.env.SCREENSHOT_DIR + '/scaffold-desktop.png' });
      await page.getByRole('region', { name: '知识掌握度', exact: true }).screenshot({ path: process.env.SCREENSHOT_DIR + '/radar.png' });
      await path.screenshot({ path: process.env.SCREENSHOT_DIR + '/learning-path.png' });
      await page.getByRole('region', { name: '资源难度匹配', exact: true }).screenshot({ path: process.env.SCREENSHOT_DIR + '/difficulty.png' });
    }
    await page.getByRole('button', { name: '全屏展开', exact: true }).click();
    const expandedPath = page.getByRole('region', { name: '个性化学习路径' });
    await expandedPath.waitFor();
    assert.equal(await expandedPath.count(), 1);
    await expandedPath.getByRole('button', { name: '查看配套资源' }).last().click();
    const expandedPanel = page.getByRole('region', { name: '分步学习答疑' });
    await expandedPanel.getByLabel('学习问题').fill('坐标系如何选择？');
    await expandedPanel.getByRole('button', { name: '开始提问', exact: true }).click();
    await expandedPanel.getByRole('heading', { name: 'L1 · 引导思考' }).waitFor();
    await page.getByRole('button', { name: '收缩为侧边栏', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await panel.scrollIntoViewIfNeeded();
    assert.ok(await panel.evaluate((el) => el.scrollWidth <= el.clientWidth + 1), 'Mobile panel overflows');
    if (process.env.SCREENSHOT_DIR) await panel.screenshot({ path: process.env.SCREENSHOT_DIR + '/scaffold-mobile.png' });
    assert.deepEqual(errors, []);
    console.log('PASS: real scaffold API L1 → L2 → L3; stuck → L3; reset; direct fallback; retry; path/resource navigation; charts; mobile panel; no browser exceptions.');
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
