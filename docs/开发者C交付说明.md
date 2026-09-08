# 开发者 C B6 联调交付说明

本次基于 `XH-agent2-开发者C完成版(2).zip` 修正答疑面板的 direct 分支，落实开发者 B 的附录 B6。原图表、学习路径和分步脚手架继续保留。

## 本次完成

- 答疑先调用 `POST /api/exams/scaffold`；前端保留档位和提示历史，后续请求携带原问题、`current_tier` 和学生回答，支持 L1 → L2 → L3，以及“不知道”跳至 L3。
- 返回 `mode=direct, tier=0` 时，不读取其空 content，也兼容只有 mode/tier/reason 的最小响应。三个 reason 均统一调用 `GET /api/knowledge/search?q=<编码后的原问题>&top_k=5`。
- 新增 `frontend/src/knowledge-search.tsx`，由全局知识检索面板与答疑面板共用请求函数及结果组件。答疑展示 results 的文档标题、原文片段与文档来源，不把检索片段包装成模型生成的完整答案。
- 未命中结果时提示补充问题；检索 HTTP 错误、非法响应及 30 秒超时均可重试。空结果不可加入资源，有结果时加入资源会保留文档来源。
- 本次答疑链路不再请求 `/api/learning-questions`。该旧函数仍供其他既有功能使用，未删除。没有新增或修改生产后端接口。
- 隔离测试服务以固定知识检索结果替换旧自由文本答疑样例；浏览器测试增加全部 B6 分支验证。

## 合入方式

`developer-c-b6.patch` 是相对于你本次提供的“开发者 C 完成版”的增量补丁，不是相对于最初项目的累计补丁。已有旧版 C 代码的团队仓库，建议先提交或备份当前修改，然后在仓库根目录执行：

```sh
git apply --check developer-c-b6.patch
git apply developer-c-b6.patch
```

如果团队只有原始项目，需先合入原来的 `developer-c(2).patch`，再合入本次增量。若队友已修改同一文件，请审阅冲突后选择性合入；完整源码包适合独立运行，不宜直接覆盖队友的最新仓库。

## 启动与验收

正常项目按 README 配置后端和知识库，运行 `python main.py`；前端运行 `npm ci`、`npm run dev`。本次没有改变依赖清单或 npm 锁文件。

隔离浏览器验收不调用真实模型或知识库，先确保 8000、5175 端口空闲。分别打开三个终端：

```sh
# 终端一：项目根目录
pip install fastapi uvicorn pydantic python-dotenv loguru
python -m uvicorn tests.dev_c_server:app --host 127.0.0.1 --port 8000
```

```sh
# 终端二
cd frontend
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 5175
```

```sh
# 终端三
cd frontend
npx playwright install chromium
npm run test:integration
```

Windows 已安装 Edge 可用 PowerShell 设置 `$env:BROWSER_CHANNEL='msedge'` 后运行测试，无需安装 Chromium。

人工验收：加载样例、打开配套资源，在答疑面板输入“机器人坐标系如何选择？”并逐步展开；输入“你好”“这个是什么？”“ROS2 如何入门？”分别验证三种 direct 原因。真实服务下的检索结果取决于团队知识库，没有匹配时应显示空结果提示。

## 本次实测

- TypeScript 检查及 Vite 生产构建通过（Node 24.19.0；本机通过 pnpm 按 package.json 安装依赖，Vite 6.4.3、TypeScript 5.9.3；未声称已运行 npm ci）。
- Edge 无头浏览器集成测试通过：真实脚手架路由的 L1/L2/L3、卡住跳级、新问题重置；三种真实 direct reason；原问题编码和 top_k=5；最小 direct 响应；空结果；检索 503/非法结构后的重试；不调用旧 QA；加入资源；路径导航、图表、全屏和 390px 窄屏结果展示。无浏览器异常，已查看截图。
- `pytest backend/tests/test_k1_scaffold.py backend/tests/test_exam_api.py backend/tests/test_k1_path_planner.py -q`：24 项通过，有测试配置/依赖弃用警告。
- `git diff --check` 通过。补丁在旧版源码基线上校验。

验证范围：脚手架使用项目真实后端逻辑，知识检索使用隔离样例及浏览器故障注入。未配置真实模型、ChromaDB 或团队知识库，尚未完成生产环境全链路验收；本次未运行全仓测试。部分 API 返回模拟数据的测试仅验证前端契约和展示，不证明真实检索质量。
