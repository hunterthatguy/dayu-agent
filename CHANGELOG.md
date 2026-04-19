# Changelog

本项目的所有重要变更都会记录在这里。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- Web UI 前端骨架（React 19 + Vite + Tailwind CSS + TanStack Query）：
  - Portfolio 浏览页面（公司列表 / Filings 列表 / Filing 详情 + Tables/XBRL 标签页）
  - Upload 页面（SEC 下载 + 本地文件上传 + SSE 实时进度流）
  - Config 页面（Scene 矩阵视图 / Prompt 控制台完整实现）
  - Interact 页面（Chat 控制台完整实现 + SSE 事件流）
  - shadcn/ui 基础组件（Button / Card / Input / DataTable / EmptyState / KeyMetric / StatusBadge）
  - 路由嵌套结构：Portfolio（列表 → 详情 → Filing）/ Config（Scene/Prompt 子路由）
- Web API 端点：
  - `/api/portfolio/*`：公司/filings/processed/健康度浏览
  - `/api/config/*`：scene 矩阵、prompt 文档浏览与编辑、scene composition
  - `/api/upload/*`：手动上传触发 + 本地文件上传 + SSE 进度聚合
- CLI 子命令 `dayu-cli web`：启动 Web UI 服务（默认端口 9000）
- 新 Service：`PortfolioBrowsingService`、`SceneConfigService`、`PipelineProgressProjector`
- 新 Repository：`PromptDocumentRepository`（prompt 文件系统访问）
- Web 路由测试：`test_web_routes_portfolio.py`、`test_web_routes_config.py`、`test_web_routes_upload.py`
- 可选依赖 `[web]`：uvicorn + python-multipart（文件上传支持）
- `dayu-cli init` 支持 hg（Mercurial）镜像仓库配置（#9 from main）

### 修复

- Portfolio 浏览服务路径错误：传入 `portfolio_root` 导致嵌套路径，修复为传入 `workspace_dir`
- Upload 页面缺少本地文件上传功能：新增 `/api/upload/files` 端点与前端文件选择
- 前端开发端口冲突：默认端口从 5173/8000 改为 5175/9000
- FastAPI Path/Query 参数命名冲突：`pathlib.Path` vs `fastapi.Path` 导致 TypeError，修复为别名导入
- Pydantic ForwardRef 错误：`Annotated[str, Path(...)]` 参数风格改为直接参数声明
- **FastAPI request body 解析错误**：Pydantic 模型在函数内部定义导致 body 被解析为 query 参数（422），移至模块级别并使用 `Body(...)` 显式声明
- React Router 子路由不渲染：Portfolio 页面缺少 `<Outlet />`，新增 `PortfolioLayout` 组件
- Sidebar 导航高亮：Config 子路由匹配逻辑，添加 `matchPath` 函数
- Tailwind CSS PostCSS 错误：`@import "tailwindcss"` 改为标准 `@tailwind` 指令
- Web 路由测试：简化为验证路由注册而非 handler 行为，避免 monkeypatch 问题
- 前端错误提示：FastAPI 验证错误数组格式正确显示（不再显示 `[object Object]`）
- 安装链接更新：v0.1.0 → v0.1.1 wheel 地址（#8 from main）

## [0.1.0] - 2026-04-17

首次开源发布。

### 新增

- 分层架构：`UI -> Service -> Host -> Agent`，边界稳定。
- Engine：Runner / Agent 事件流、状态机、ToolTrace、截断与压缩管理、SSE 解析。
- Fins：财报 capability 定位、两条执行路径、文件系统仓储实现。
- 财报数据管线：SEC 10-K / 10-Q / 20-F 下载与预处理，XBRL 与 HTML 双路径提取。
- CLI 入口 `dayu`（`python -m dayu.cli` 等价）：`prompt`、`interactive`、`download`、`write` 四类工作流。
- 配置系统：默认配置 + `workspace/config/` 覆盖，prompt 模板可插拔。
- Web 骨架：FastAPI 路由与应用装配。
- WeChat 入口：iLink 文本消息首版。
- 渲染：Markdown -> HTML / PDF / Word。
- 文档：用户手册（根 README）、开发总览（`dayu/README.md`）、Engine / Fins / Config / Tests 分册手册、贡献指南。

### 已知限制

- A 股、港股财报下载未实现。
- GUI 未实现；Web UI 仅有骨架。
- 财报电话会议音频转录后的问答区分未实现。
- 定性分析模板对不同公司的差异化判断路径仍偏机械。

[Unreleased]: https://github.com/noho/dayu-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/noho/dayu-agent/releases/tag/v0.1.0
