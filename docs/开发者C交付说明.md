# 开发者 C 前端交付说明

本次修改基于你提供的 `XH-agent2-main.zip`，完成三天冲刺方案中的前端图表、学习路径和分步答疑集成。后端已有路径生成器、统一响应中的 `learning_path` 和 `/api/exams/scaffold`，本次直接复用，没有更改 A/B 的实现或接口契约。

## 已完成

- 两个独立纯 SVG 组件：`frontend/src/learning-charts.tsx` 中的 `KnowledgeRadarChart` 与 `DifficultyMatchCurve`。支持空数据提示，雷达图过滤非有限数值、限制百分比范围、少于三维时显示数值列表；长知识点名通过编号和完整图例展示。难度图按资源顺序对比资源难度和学习者推荐难度，未知难度不会冒充入门。
- `frontend/src/learning-path.tsx` 展示后端节点原始顺序、前置依赖、预计时长和完成状态。按资源 ID 优先匹配，未提供 ID 时按类型关联；有资源时可以跳转。接口没有路径时保留原知识体系展示；空路径会明确提示。
- `frontend/src/scaffold-panel.tsx` 接入真实脚手架接口，逐次请求并保留 L1/L2/L3 历史；支持提交思考和“我不知道”跳级；新问题从零开始。只有完整答案或普通答疑结果可以加入资源。
- `frontend/src/learning-session.ts` 新增类型化 API 适配，发送学习者 ID、原始问题、当前档位、学生回答和薄弱知识点。校验响应档位与答案标记，阻止请求连点，脚手架请求超时后可重试；直接答疑继续走原 `/api/learning-questions`。
- 在侧栏工作台、全屏工作台、诊断弹窗接入路径；修正旧 CSS 把全屏路径隐藏的问题。
- 新增浏览器集成测试和隔离测试服务。Playwright 仅作为开发依赖，不增加生产图表库。

## 启动正常项目

在项目根目录，按原 README 配置 Python 环境、知识库及模型密钥，然后启动后端：

```sh
pip install -r requirements.txt
python main.py
```

另开终端启动前端：

```sh
cd frontend
npm ci
npm run dev
```

生成资源后进入工作台，查看图表和学习路径，点击配套资源，在下方答疑面板输入“机器人坐标系如何选择？”。点击“下一步提示”进入 L2，再点击“查看完整答案”进入 L3。输入“你好”可检查普通答疑分支。

旧 `samples.json` 若不含 `learning_path`，不会伪造个性化路径；请使用新后端生成结果，或下述测试服务的样例验收。

## 可重复的浏览器集成测试

测试服务复用真实 `exams` 路由和路径生成器；资源生成样例、普通答疑响应是固定测试数据，不调用 LLM。请先停止占用 8000 端口的普通后端，避免把测试服务和生产服务混用。

终端一，在项目根目录启动隔离测试服务：

```sh
pip install fastapi uvicorn pydantic python-dotenv loguru
python -m uvicorn tests.dev_c_server:app --host 127.0.0.1 --port 8000
```

终端二：

```sh
cd frontend
npm ci
npm run build
node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5175
```

终端三：

```sh
cd frontend
npx playwright install chromium
npm run test:integration
```

Windows 已安装 Edge 时，可在 PowerShell 用 `$env:BROWSER_CHANNEL='msedge'` 后运行测试，免下载 Chromium。可选环境变量 `APP_URL`、`API_URL` 用于测试地址，`SCREENSHOT_DIR` 用于截图。生产预览默认沿用 Vite 的 API 代理配置，后端端口为 8000。

测试覆盖：L1 → L2 → L3、卡住直接 L3、新问题重置、普通答疑回退、503 后重试、完整答案加入资源、路径跳转、SVG 展示、全屏模式、390px 窄屏答疑、浏览器异常检查。

## 验证结果与范围

- `npm run build`：通过，包含 TypeScript 类型检查和 Vite 生产构建。
- `ruff check .`：通过。
- `pytest backend/tests/test_k1_path_planner.py backend/tests/test_k1_scaffold.py backend/tests/test_exam_api.py -q`：24 项通过。
- 浏览器集成测试：使用 Edge 无头浏览器通过；人工查看了图表、路径、答疑截图。
- 全仓 `pytest -q --maxfail=1` 已尝试，但在收集 `agent1/test_run.py` 时因当前隔离测试环境缺少 `requests` 中止，因此不声称全仓测试通过。
- 未配置真实模型密钥及完整知识库，没有验证真实模型生成、知识检索和画像持久化的整条生产链路。提交前请在团队环境完成“诊断 → 路径 → 资源 → 答题 → 脚手架”的最终验收。

## 合入方式

压缩包包含完整源码，不含 `node_modules`、虚拟环境或临时测试缓存。也提供相对于原压缩包的 `developer-c.patch`；如团队已有后续修改，优先审阅补丁并选择性合入，不要直接覆盖队友代码。

新测试服务只用于开发验证；后端业务文件未修改。
