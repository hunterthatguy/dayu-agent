# 前端可视化技术方案（v1.0.1）

> 本文档是一份**可独立执行**的完整技术方案：覆盖目标、决策、架构、后端 / 前端 / 测试 / 文档全量细节。
> 阅读对象：负责实施的下一棒模型或工程师。
> 强制约束：必须严格遵守仓库根 `AGENTS.md`，所有冲突以 `AGENTS.md` 为准。

---

## 0. 总览

### 0.1 目标

为 `dayu-agent` 项目新增一个金融严谨风格的可视化前端，支持四大功能模块：

1. **Portfolio 浏览**：公司列表 / Filings 列表 / Filing 详情 / Processed 浏览 / 健康度
2. **Upload 流水线**：手动上传 → 流水线框线图实时进度 → 任务完成后展示分析结果
3. **Config 配置**：Scene 矩阵（13 个 scene × 可用模型）+ Prompt 控制台（浏览/编辑）
4. **Interact 主动交互**：Chat 控制台（输入框 + ticker + scene 下拉 + 实时事件流）

### 0.2 用户体验最高原则（来自需求）

> 用户体验是所有产品的最高准则，优先级高于技术偏好、代码整洁度、架构优雅度。

执行落地：

- 为目标设计而非功能堆砌
- 不要让用户思考 —— 缺省值齐全、自动推断
- 系统承担复杂性 —— 后端异步 + 前端乐观更新
- 渐进式展示 —— 列表给摘要，详情按需展开
- 反馈引导行动 —— 每个错误必须给"下一步建议"

---

## 1. 关键决策记录（已与产品确认）

| 决策项 | 选择 | 影响 |
|---|---|---|
| 前端技术栈 | **React 19 + Vite + TypeScript + Tailwind v3 + shadcn/ui** | 独立 SPA |
| 实施范围 | **全量但不做全文搜索** | 不引入 FTS5/Whoosh/tantivy |
| Upload 进度模型 | **PipelineProgressProjector 聚合 SSE** | 后端新增 Projector + DTO |
| 前端工程位置 | **仓库根 `frontend/`** | 独立 npm 工程 |
| 前端开发模式 | **Vite dev server + 反向代理到 FastAPI** | 同源、无 CORS（dev 用） |
| 生产部署 | **`npm run build` 产物由 FastAPI `StaticFiles` 挂载** | 单端口部署 |
| 鉴权 | **不需要**（本地工具） | 简化 |

### 1.1 已 PASS 不做的事项

- 全文搜索：不引入索引引擎
- Streamlit 路线
- 多渠道认证 / RBAC
- 多用户隔离

---

## 2. 仓库现状（实施前的事实基线）

实施者必须先理解以下事实，否则会重复造轮子或破坏分层。

### 2.1 已有后端能力

```
dayu/
├── services/                       # ChatService / PromptService / FinsService / HostAdminService / ...
│   ├── contracts.py                # 稳定 DTO（已含 ChatTurnRequest / FinsSubmission / ...）
│   ├── protocols.py                # Service Protocol 定义
│   └── ...
├── web/
│   ├── fastapi_app.py              # FastAPI 工厂（已挂 sessions/runs/events/chat/prompt/fins/...）
│   └── routes/
│       ├── sessions.py             # /api/sessions
│       ├── runs.py                 # /api/runs
│       ├── events.py               # /api/runs/{id}/events SSE / /api/sessions/{id}/events SSE
│       ├── chat.py                 # POST /api/chat ...
│       ├── prompt.py               # POST /api/prompt ...
│       └── fins.py                 # POST /api/fins/download / /api/fins/process
├── fins/storage/
│   ├── repository_protocols.py     # Company/Source/Processed/Blob/Maintenance 五窄协议
│   └── fs_*_repository.py          # 文件系统实现
└── prompting/
    ├── scene_definition.py         # SceneDefinition / load_scene_definition
    └── prompt_plan.py              # PromptAssemblyPlan / build_prompt_assembly_plan
```

### 2.2 关键缺口

- **没有 portfolio 浏览 Service**（Web 层无法直接读取 storage —— 违反分层）
- **没有 scene/prompt 配置浏览 Service**
- **没有 upload 流水线进度聚合 DTO**（SSE 事件零散，前端难以渲染状态机）
- **没有前端工程**（`dayu/gui/__init__.py` 是空占位）
- **没有 `dayu web` CLI 子命令**

### 2.3 数据布局事实

```
workspace/
├── portfolio/<TICKER>/
│   ├── meta.json                   # CompanyMeta（company_name/market/ticker/...）
│   ├── filings/
│   │   ├── filing_manifest.json    # 全量 filings 清单
│   │   └── fil_<accession>/        # 单份 filing
│   │       ├── meta.json
│   │       ├── <primary>.htm
│   │       └── <xbrl>.xml ...
│   ├── processed/
│   │   ├── manifest.json
│   │   └── fil_<accession>/        # 单份 processed
│   │       └── meta.json (含 sections / tables / xbrl_facts)
│   ├── materials/                  # 用户上传非 SEC 材料
│   └── .rejections/                # 被拒绝的 filings
└── config/
    ├── llm_models.json
    ├── run.json
    └── prompts/                    # 工作区覆盖；缺则回落 dayu/config/prompts
        ├── manifests/<scene>.json
        ├── scenes/<scene>.md
        ├── base/<name>.md
        └── tasks/<task>.md(+.contract.yaml)
```

### 2.4 已开工进度（实施者可继承）

> 以下文件已写好且测试已通过。**实施者无需重写**，但需要继续在此基础上推进。

- `dayu/services/contracts.py` —— 已新增以下 DTO：
  - `CompanyView / FilingFileView / FilingView / FilingDetailView / ProcessedArtifactView`
  - `FilingSectionView / FilingTableView / XbrlFactView / FilingProcessedView`
  - `RejectedFilingView / PortfolioHealthView / FilingFileBlob`
  - `SceneModelOptionView / SceneMatrixRowView / SceneMatrixView`
  - `PromptDocumentView / PromptDocumentDetailView / ScenePromptCompositionView`
  - `PipelineStageState / PipelineStageView / PipelineProgressView`
- `dayu/services/protocols.py` —— 已新增 `PortfolioBrowsingServiceProtocol` / `SceneConfigServiceProtocol`
- `dayu/services/portfolio_browsing_service.py` —— **完整实现 + 9 个单测全过 + pyright 0 错误**
- `dayu/services/internal/prompt_document_repository.py` —— 已实现
- `dayu/services/scene_config_service.py` —— 已实现（待补单测）
- `pyrightconfig.json` —— 已加 `venvPath/.venv` 与 `frontend` 排除

---

## 3. 整体架构

```
浏览器
   │ HTTP / SSE
   ▼
┌──────────────────────────────────┐
│ FastAPI (dayu/web/fastapi_app.py)│
│  ├─ /api/* 路由（Service 适配层）  │
│  └─ /  StaticFiles (build 产物)   │
└──────────┬───────────────────────┘
           │ Service Protocol (DTO only)
           ▼
┌──────────────────────────────────┐
│ Services (dayu/services/*)       │
│  ├─ PortfolioBrowsingService     │
│  ├─ SceneConfigService           │
│  ├─ PipelineProgressProjector    │
│  ├─ ChatService / PromptService  │
│  ├─ FinsService                  │
│  └─ HostAdminService             │
└──────────┬───────────────────────┘
           │ Repository Protocol / Host Protocol
           ▼
┌──────────────────────────────────┐
│ Host (dayu/host/*)               │
│  ├─ Run / Session / Event Bus    │
│  └─ Cancellation / Concurrency   │
└──────────┬───────────────────────┘
           ▼
┌──────────────────────────────────┐
│ Agent + fins.storage + Engine    │
└──────────────────────────────────┘
```

**强约束（来自 AGENTS.md）：**

1. UI → Service → Host → Agent 单向。Web 层（路由）只能依赖 Service Protocol。
2. 财报存取**只能**通过 `dayu.fins.storage` 仓储协议；新 Service 不得直接 open 文件。
3. 禁止兼容性 wrapper / re-export。
4. 单文件测试覆盖率 ≥ 80%；pyright 0 新增错误。
5. 完整中文 docstring（参数/返回/异常）。

---

## 4. 后端详细设计

### 4.1 PortfolioBrowsingService（已实现，仅记录契约）

文件：`dayu/services/portfolio_browsing_service.py`（已完成）

**依赖（构造参数）：**

```python
@dataclass(frozen=True)
class PortfolioBrowsingService:
    company_meta_repository: CompanyMetaRepositoryProtocol
    source_document_repository: SourceDocumentRepositoryProtocol
    processed_document_repository: ProcessedDocumentRepositoryProtocol
    document_blob_repository: DocumentBlobRepositoryProtocol
    filing_maintenance_repository: FilingMaintenanceRepositoryProtocol
```

**对外方法（已落地）：**

| 方法 | 返回 | 说明 |
|---|---|---|
| `list_companies()` | `list[CompanyView]` | 按 ticker 升序；含异常目录 |
| `list_filings(ticker, *, form_type, fiscal_year, fiscal_period, include_deleted)` | `list[FilingView]` | 按 filing_date 倒序 |
| `get_filing_detail(ticker, document_id)` | `FilingDetailView` | 含文件清单 + processed 摘要 |
| `get_filing_processed(ticker, document_id)` | `FilingProcessedView` | sections + tables + xbrl_facts |
| `list_processed_artifacts(ticker, ...)` | `list[ProcessedArtifactView]` | 按 filing_date 倒序 |
| `get_portfolio_health(ticker)` | `PortfolioHealthView` | 缺失 / 失败 / 拒绝聚合 |
| `read_filing_file(ticker, document_id, filename)` | `FilingFileBlob` | bytes + content_type |

**实施验收（已通过）：**

- `tests/application/test_portfolio_browsing_service.py` 9 个用例
- pyright 0 错误

### 4.2 SceneConfigService（部分实现，需补单测）

文件：`dayu/services/scene_config_service.py`（已写） + `dayu/services/internal/prompt_document_repository.py`（已写）

**依赖：**

```python
@dataclass(frozen=True)
class SceneConfigService:
    prompt_asset_store: PromptFragmentAssetStoreProtocol  # 来自 dayu.prompting.prompt_plan
    prompt_document_repository: PromptDocumentRepository  # 来自 internal/
```

**对外方法：**

| 方法 | 返回 | 说明 |
|---|---|---|
| `get_scene_matrix()` | `SceneMatrixView` | 扫 manifests 目录 → 解析 → 行视图 |
| `list_prompt_documents()` | `list[PromptDocumentView]` | 4 类目录全量 |
| `get_prompt_document(relative_path)` | `PromptDocumentDetailView` | 工作区优先 |
| `update_prompt_document(relative_path, content)` | `PromptDocumentDetailView` | 仅写工作区目录 |
| `get_scene_prompt_composition(scene_name)` | `ScenePromptCompositionView` | 简单 join，不渲染变量 |

**`PromptDocumentRepository` 设计要点：**

- 构造：`workspace_prompts_dir: Path | None`、`package_prompts_dir: Path`
- 列表：合并两个目录；工作区优先；分类限定为 `manifests / scenes / base / tasks`
- 读：覆盖式 fallback
- 写：**只写工作区目录**；若 workspace_prompts_dir 为 None 抛 `PermissionError`
- 路径校验：拒绝 `..`、空 token、非法 category

**待补单测（必须）：**

- `tests/application/test_scene_config_service.py`：构造 fake `PromptFragmentAssetStoreProtocol` 与临时目录，覆盖：
  1. `get_scene_matrix` 聚合多 scene 的 default/allowed_models
  2. `list_prompt_documents` 工作区覆盖包内
  3. `get_prompt_document` 工作区优先返回
  4. `update_prompt_document` 写入工作区且不污染包内目录；只接收非空内容
  5. `update_prompt_document` 路径越界（`../`）抛 PermissionError
  6. `update_prompt_document` 在 `workspace_prompts_dir is None` 时抛 PermissionError
  7. `get_scene_prompt_composition` 按 fragment.order 拼接

- `tests/application/test_prompt_document_repository.py`：单独覆盖仓储边界。

### 4.3 PipelineProgressProjector（待实施）

> **目标**：把 fins SSE 事件序列折叠为前端可直接渲染的 `PipelineProgressView` 状态机。

#### 4.3.1 阶段定义（固定顺序）

| key | title | 触发事件 | 完成事件 |
|---|---|---|---|
| `resolve` | 解析 ticker | upload 提交即开始（同步） | resolver 完成（fins 内部 event 暂用 download 启动作为 proxy） |
| `download` | 下载财报 | fins download `accepted`/`started` | fins download `finished` 或 `failed` |
| `process` | 解析与抽取 | fins process `accepted`/`started` | fins process `finished` 或 `failed` |
| `analyze` | 维度分析 | （MVP 暂留 `pending`，后续接入 chat run） | 后续阶段 |

> **注**：`analyze` 阶段在 v1 中保持 `pending`/`skipped`。当用户后续显式提交分析任务时再推进。前端必须能优雅地展示 `skipped`。

#### 4.3.2 文件位置与签名

- 文件：`dayu/services/pipeline_progress_projector.py`
- 不依赖 Host；**只输入** `FinsEvent` / `AppEvent`，**只输出** `PipelineProgressView`

```python
@dataclass(frozen=True)
class PipelineProgressProjector:
    """SSE 事件 → PipelineProgressView 投影器（无状态纯函数风格的累加器）。"""

    ticker: str
    run_id: str
    session_id: str

    def initial(self) -> PipelineProgressView: ...
    def apply(self, current: PipelineProgressView, event: FinsEvent | AppEvent) -> PipelineProgressView: ...
```

**实现要点：**

- `apply` **必须是纯函数**：返回新的 `PipelineProgressView`，不修改入参（DTO 已 frozen）。
- 通过事件类型/命令名分派到 `_advance_download / _advance_process` 私有函数。
- `terminal_state` 推断：所有阶段完成且无失败 → `succeeded`；任意失败 → `failed`；用户取消 → `cancelled`；否则 `running`。
- `updated_at` 用 `datetime.now(UTC).isoformat()`；测试中可注入 clock。

#### 4.3.3 单测要求

- `tests/application/test_pipeline_progress_projector.py`：
  1. `initial()` 全 `pending`
  2. download 启动 → resolve+download 状态正确
  3. download 失败 → terminal_state=failed
  4. download 完成 + process 启动 → 状态串接
  5. cancelled 事件 → terminal_state=cancelled
  6. 未知事件 → 状态不变（apply 幂等）

#### 4.3.4 何处使用

- Web 层 `/api/upload/progress/{run_id}` SSE 路由：内部订阅 fins 事件流，每个事件喂给 projector，把新 view 序列化为 SSE event。
- 前端订阅这个端点直接拿到聚合状态。

### 4.4 Web Routes（待实施）

#### 4.4.1 新增路由文件

```
dayu/web/routes/
├── portfolio.py    # 新增
├── config.py       # 新增
├── upload.py       # 新增
├── files.py        # 新增（filing 文件下载）
└── (现有 sessions/runs/events/chat/prompt/fins/...)
```

#### 4.4.2 完整 API 契约

> 所有路由统一 `prefix=/api`，错误统一 `{detail: str}`。
> 列表类型：成功 200；创建：202（异步）；不存在：404；非法参数：400；越权：403；服务异常：500。

##### Portfolio

| 方法 | 路径 | 请求 | 响应 | 备注 |
|---|---|---|---|---|
| GET | `/api/portfolio/companies` | — | `CompanyView[]` | 按 ticker 排序 |
| GET | `/api/portfolio/companies/{ticker}/filings` | query: `form_type, fiscal_year, fiscal_period, include_deleted` | `FilingView[]` | |
| GET | `/api/portfolio/companies/{ticker}/filings/{document_id}` | — | `FilingDetailView` | |
| GET | `/api/portfolio/companies/{ticker}/filings/{document_id}/processed` | — | `FilingProcessedView` | 404 当无 processed |
| GET | `/api/portfolio/companies/{ticker}/processed` | 同 filings 过滤 | `ProcessedArtifactView[]` | |
| GET | `/api/portfolio/companies/{ticker}/health` | — | `PortfolioHealthView` | |
| GET | `/api/portfolio/companies/{ticker}/filings/{document_id}/files/{filename}` | — | binary | `Content-Type` 来自 blob meta |

##### Config

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | `/api/config/scenes/matrix` | — | `SceneMatrixView` |
| GET | `/api/config/prompts` | — | `PromptDocumentView[]` |
| GET | `/api/config/prompts/{relative_path:path}` | — | `PromptDocumentDetailView` |
| PUT | `/api/config/prompts/{relative_path:path}` | `{content: string}` | `PromptDocumentDetailView` |
| GET | `/api/config/scenes/{scene_name}/composition` | — | `ScenePromptCompositionView` |

##### Upload

> 以新 endpoint 编排现有 fins 能力，**不重写下载/处理逻辑**。

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| POST | `/api/upload/manual` | `multipart/form-data: ticker?, market?, files[]` 或 `{ticker, forms[], start_date, end_date}` | `{run_id, session_id, ticker}` | 文件上传 → 调用现有 fins upload；纯 ticker → 调用 fins download |
| GET | `/api/upload/progress/{run_id}` | — | SSE: `data: <PipelineProgressView json>\n\n` | 内部包装 fins 事件流 + projector |

> v1 上传策略：MVP **优先**实现"输入 ticker 触发已有 download+process 流水线"路径。文件上传走现有 `dayu.fins.upload_recognition` 即可，不引入新管线。

##### 既有路由（不动）

`/api/sessions/*`、`/api/runs/*`、`/api/runs/{id}/events`、`/api/chat`、`/api/prompt`、`/api/fins/*`、`/api/reply_outbox/*`、`/api/write/*`

#### 4.4.3 路由实现风格

- 所有路由工厂签名：`def create_xxx_router(service: XxxServiceProtocol) -> APIRouter`
- 在工厂内定义 Pydantic `BaseModel` 请求/响应（与现有 `sessions.py` 一致）
- DTO → 响应：手动字段映射（**不要直接 dataclasses.asdict**，避免泄漏内部字段）
- Path/Query 参数校验：用 `fastapi.Query / Path` + `Annotated`

#### 4.4.4 fastapi_app 装配扩展

修改 `dayu/web/fastapi_app.py`：

```python
def create_fastapi_app(
    *,
    chat_service, prompt_service, fins_service, host_admin_service, reply_delivery_service,
    portfolio_browsing_service: PortfolioBrowsingServiceProtocol,
    scene_config_service: SceneConfigServiceProtocol,
    static_dir: Path | None = None,        # 生产构建产物目录
    cors_allow_origins: tuple[str, ...] = (),  # dev 用
) -> FastAPI:
    app = FastAPI(title="Dayu Web")

    if cors_allow_origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_allow_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # API 路由（先于 static 挂载，避免被 catch-all 吞掉）
    app.include_router(create_session_router(host_admin_service))
    # ... 现有
    app.include_router(create_portfolio_router(portfolio_browsing_service))
    app.include_router(create_config_router(scene_config_service))
    app.include_router(create_upload_router(fins_service, host_admin_service))

    if static_dir is not None:
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app
```

### 4.5 启动入口（待实施）

#### 4.5.1 新增 `dayu web` CLI 子命令

文件：`dayu/cli/web_command.py`

职责：
- 构建 PortfolioBrowsingService / SceneConfigService 所需依赖
- 复用现有 `_prepare_cli_host_dependencies` 装配 chat/prompt/fins/host_admin
- 调用 `create_fastapi_app(...)` 并 `uvicorn.run` 启动

argparse：

```
dayu web [--host 0.0.0.0] [--port 9000]
         [--static-dir frontend/dist]
         [--reload]
         [--cors-allow-origins http://localhost:5175]
```

集成到 `dayu/cli/main.py` 的命令分派。

**PortfolioBrowsingService 装配示例：**

```python
from dayu.fins.storage import (
    FsCompanyMetaRepository, FsSourceDocumentRepository, FsProcessedDocumentRepository,
    FsDocumentBlobRepository, FsFilingMaintenanceRepository,
)
from dayu.fins.storage._fs_repository_factory import build_fs_repository_set

def _build_portfolio_browsing_service(workspace_root: Path) -> PortfolioBrowsingService:
    repository_set = build_fs_repository_set(workspace_root=workspace_root / "portfolio")
    return PortfolioBrowsingService(
        company_meta_repository=FsCompanyMetaRepository(workspace_root / "portfolio", repository_set=repository_set),
        source_document_repository=FsSourceDocumentRepository(workspace_root / "portfolio", repository_set=repository_set),
        processed_document_repository=FsProcessedDocumentRepository(workspace_root / "portfolio", repository_set=repository_set),
        document_blob_repository=FsDocumentBlobRepository(workspace_root / "portfolio", repository_set=repository_set),
        filing_maintenance_repository=FsFilingMaintenanceRepository(workspace_root / "portfolio", repository_set=repository_set),
    )
```

> **必须验证**：与现有 fins CLI 命令（download/process）使用同一个 workspace 根，避免 ticker 看不到。

### 4.6 后端 Web 路由测试

文件：`tests/application/test_web_routes_portfolio.py`、`test_web_routes_config.py`、`test_web_routes_upload.py`

参考 `tests/application/test_web_routes.py` 既有风格：
- 用 `cast(Any, module)` 注入假 fastapi/pydantic 模块（项目约定）
- 注入 fake Service 实现协议
- 验证 router 把请求/响应正确映射

每个新路由文件至少 5 个用例，覆盖：
- 正常 200 / 列表为空
- 404 不存在
- 400 非法参数
- DTO → JSON 字段名一致
- query 参数透传

---

## 5. 前端详细设计

### 5.1 工程结构

```
frontend/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── components.json                 # shadcn/ui 配置
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── routes.tsx                  # react-router v6 路由表
    ├── lib/
    │   ├── api.ts                  # 类型化 fetch 包装
    │   ├── sse.ts                  # EventSource 封装
    │   ├── format.ts               # 数字 / 日期格式化
    │   └── cn.ts                   # tailwind merge 助手
    ├── types/
    │   └── api.ts                  # 与后端 DTO 一一对应（手动维护，详见 §5.4）
    ├── components/
    │   ├── ui/                     # shadcn/ui 生成的基础组件
    │   ├── layout/
    │   │   ├── AppShell.tsx        # 全局壳：侧边栏 + 顶栏
    │   │   ├── Sidebar.tsx
    │   │   └── TopBar.tsx
    │   └── shared/
    │       ├── DataTable.tsx       # 通用表格（金融风格）
    │       ├── EmptyState.tsx
    │       ├── ErrorBoundary.tsx
    │       ├── PipelineGraph.tsx   # 流水线框线图
    │       ├── StatusBadge.tsx
    │       └── KeyMetric.tsx
    └── pages/
        ├── portfolio/
        │   ├── PortfolioPage.tsx           # 公司列表
        │   ├── CompanyDetailPage.tsx       # 单公司：filings 列表 + 健康度
        │   ├── FilingDetailPage.tsx        # 单 filing：原文 + sections + processed
        │   └── components/
        ├── upload/
        │   ├── UploadPage.tsx              # 表单 + 流水线图
        │   └── components/
        ├── config/
        │   ├── SceneMatrixPage.tsx
        │   ├── PromptConsolePage.tsx
        │   └── components/
        └── interact/
            ├── ChatConsolePage.tsx
            └── components/
```

### 5.2 技术决策

| 项 | 选择 | 理由 |
|---|---|---|
| Node | ≥ 20 | Vite 7 / React 19 要求 |
| 包管理 | npm | 默认；不引入 pnpm/yarn 学习成本 |
| React | 19.x | 最新 stable |
| 路由 | react-router-dom v6 | 成熟、与 SSR 无关 |
| 数据获取 | `@tanstack/react-query` v5 | 内置缓存/轮询/无效化；前端最少代码 |
| 表单 | `react-hook-form` + `zod` | 类型安全 |
| UI | Tailwind v3 + shadcn/ui | 严肃风格、可深度定制 |
| 图表 | `recharts`（仅 dashboard 用） | shadcn 推荐；体积合理 |
| Markdown 渲染 | `react-markdown` + `remark-gfm` | Prompt 预览 |
| 代码编辑器 | `@monaco-editor/react` | Prompt 编辑 |
| HTML 预览 | `iframe sandbox` | filing 原文 |
| 图标 | `lucide-react` | shadcn 默认 |
| 状态共享 | react-query 缓存 + URL search params | 不引入 zustand/redux |

**严禁引入：**
- 任何 jQuery / Bootstrap / Material UI
- 任何 chrome 扩展依赖
- TypeScript 关闭 strict 模式

### 5.3 全局视觉规范（金融严谨风格）

- **主色**：`zinc` 系（near-black on near-white） + 单点蓝（`#1d4ed8`）作为高亮
- **数字**：`font-mono tabular-nums` —— 表格内所有金额/数量统一等宽
- **表格密度**：`text-sm`、行高 `36px`、`border-b border-zinc-200`
- **空白**：每个 page 顶部 `px-6 py-4`，section 间距 `space-y-4`
- **圆角**：`rounded-md`（不要大圆角，避免软糯感）
- **阴影**：除 dropdown / dialog 外不用阴影
- **状态色**：
  - succeeded → `text-emerald-600 bg-emerald-50`
  - running → `text-blue-600 bg-blue-50`
  - failed → `text-rose-600 bg-rose-50`
  - pending / skipped → `text-zinc-500 bg-zinc-100`
- **动效**：仅 `transition-colors duration-150`；禁止跳动 / 旋转 spinner（用进度条）

shadcn 主题变量（`tailwind.config.ts` 中）配置 `neutral` palette、禁用默认 `accent` 调色。

### 5.4 类型契约（前端 = 后端 DTO 镜像）

文件 `src/types/api.ts`，**手工维护**与后端 `dayu/services/contracts.py` 一致。

> 不引入 OpenAPI 自动生成（避免增加 CI 复杂度）。一旦后端 DTO 改名，必须同步修改此文件 —— 在 PR Checklist 中固化。

示例（仅核心，全量按 §4.1 / §4.2 / §4.3 复刻）：

```ts
export interface CompanyView {
  ticker: string;
  company_name: string;
  market: string;
  company_id: string;
  updated_at: string;
  ticker_aliases: string[];
  directory_name: string;
  status: "available" | "hidden_directory" | "missing_meta" | "invalid_meta";
  detail: string;
  filing_count: number;
  processed_count: number;
}

export interface FilingView {
  ticker: string;
  document_id: string;
  form_type: string | null;
  fiscal_year: number | null;
  fiscal_period: string | null;
  report_date: string | null;
  filing_date: string | null;
  amended: boolean;
  ingest_complete: boolean;
  is_deleted: boolean;
  has_xbrl: boolean | null;
  has_processed: boolean;
  primary_document: string;
}

export type PipelineStageState = "pending" | "running" | "succeeded" | "failed" | "skipped";

export interface PipelineStageView {
  key: string;
  title: string;
  state: PipelineStageState;
  message: string;
  started_at: string;
  finished_at: string;
}

export interface PipelineProgressView {
  ticker: string;
  run_id: string;
  session_id: string;
  stages: PipelineStageView[];
  active_stage_key: string;
  terminal_state: "running" | "succeeded" | "failed" | "cancelled";
  updated_at: string;
}
```

### 5.5 API Client

`src/lib/api.ts`：

```ts
const BASE = ""; // 同源；dev 由 vite proxy 转发

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new ApiError(resp.status, detail.detail ?? resp.statusText);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  portfolio: {
    listCompanies: () => request<CompanyView[]>("/api/portfolio/companies"),
    listFilings: (ticker: string, params?: ListFilingsParams) =>
      request<FilingView[]>(`/api/portfolio/companies/${ticker}/filings${qs(params)}`),
    getFilingDetail: (ticker: string, id: string) =>
      request<FilingDetailView>(`/api/portfolio/companies/${ticker}/filings/${id}`),
    // ...
  },
  config: { ... },
  upload: { ... },
  chat: { ... },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
```

### 5.6 SSE 客户端

`src/lib/sse.ts`：

```ts
export function subscribeSse<T>(
  url: string,
  onEvent: (data: T) => void,
  onError?: (err: Event) => void,
): () => void {
  const es = new EventSource(url);
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data) as T); }
    catch { /* ignore non-JSON keepalive */ }
  };
  if (onError) es.onerror = onError;
  return () => es.close();
}
```

每个使用 SSE 的 hook 必须在 `useEffect` cleanup 中调用 `close()`。

### 5.7 路由

`src/routes.tsx`：

```
/                            → redirect to /portfolio
/portfolio                   → PortfolioPage（公司列表）
/portfolio/:ticker           → CompanyDetailPage（filings 列表 + 健康度）
/portfolio/:ticker/filings/:documentId  → FilingDetailPage
/upload                      → UploadPage
/config/scenes               → SceneMatrixPage
/config/prompts              → PromptConsolePage
/config/prompts/:path*       → PromptConsolePage（编辑指定文档）
/interact                    → ChatConsolePage
```

### 5.8 页面详细设计

#### 5.8.1 PortfolioPage

**目的**：用户一眼看到 workspace 里有哪些公司、各自情况。

**布局**（左右两栏）：
- 顶部：搜索框（按 ticker / 公司名过滤）+ "新建分析" 按钮（链到 /upload）
- 主区：DataTable
  - 列：Ticker（粗体）/ 公司名 / 市场 / Filings 数 / Processed 数 / 健康度徽章 / 最后更新
  - 行点击 → `/portfolio/:ticker`
- 异常公司（status≠available）显示在底部小折叠区，避免污染主表

**数据流**：`useQuery(['companies'], api.portfolio.listCompanies)`。

#### 5.8.2 CompanyDetailPage

**布局**：
- 头部：公司名 + ticker + 市场 + 别名
- 三个 Tab：
  1. Filings（默认）
  2. Processed
  3. 健康度
- Filings Tab：DataTable
  - 过滤器（form_type 多选、fiscal_year 下拉、include_deleted 开关）
  - 列：Filing Date / Form Type / FY / Period / XBRL / Processed / 操作
  - 行点击 → `/portfolio/:ticker/filings/:documentId`
- 健康度 Tab：KeyMetric 卡片网格（4 个）+ 最近被拒绝 filings 列表

#### 5.8.3 FilingDetailPage

**布局**（左右两栏，左侧目录 / 右侧主区）：
- 左侧 sticky：目录树（sections）
- 右侧 Tabs：
  1. **原文**（默认）：iframe sandbox 加载 `/api/portfolio/companies/{ticker}/filings/{documentId}/files/{primary}`
  2. **结构化 sections**：列表 + 字符数；点击 section 跳到内嵌渲染
  3. **Tables**：DataTable，可点开查看
  4. **XBRL Facts**：DataTable + 文本搜索（前端过滤）

**注意**：原文 iframe 必须 `sandbox="allow-same-origin"`，禁用 scripts。

#### 5.8.4 UploadPage

**两栏**：左输入表单 / 右流水线图

**左侧表单**：
- ticker 输入框（必填，自动 trim/uppercase）
- 市场下拉（US/HK/CN，默认 US）
- 高级（折叠）：forms 多选、start_date、end_date、overwrite
- "开始分析" 按钮 → POST `/api/upload/manual`

**右侧 PipelineGraph**：
- 4 个圆角矩形横向排列：解析 → 下载 → 处理 → 分析
- 每个矩形带状态色（见 §5.3）+ 当前消息 + 时间
- 节点之间用箭头连接
- 顶部进度条（已完成 stage 数 / 总数）
- 终态：succeeded → 整体绿色 + 跳转到 `/portfolio/:ticker`；failed → 红色 + 错误详情 + "重试"

**实现要点**：
- 提交后立即拿到 `run_id`，开始 SSE 订阅 `/api/upload/progress/{run_id}`
- 每收到 `PipelineProgressView` 用 `setState` 整体替换（不要增量合并，projector 已经聚合好）
- 离开页面 / 终态后取消订阅

#### 5.8.5 SceneMatrixPage

**布局**：单张大表
- 行：scene 名（13 个）
- 列：所有出现过的模型
- 单元格：默认模型 → 实心圆点；可选模型 → 空心圆点；未声明 → 空
- 表格上方：图例 + scene 描述（鼠标悬停 row 显示）

**v1 只读**：不需要勾选编辑。

#### 5.8.6 PromptConsolePage

**布局**（三栏）：
- 左：分类导航（manifests / scenes / base / tasks）+ 文件树
- 中：选中文档的 Monaco 编辑器（语法高亮：md / json / yaml）
- 右：sticky 信息面板：
  - 文件信息（路径 / 大小 / 更新时间）
  - 如果是 manifest：show "查看拼接系统提示" 按钮 → 打开 Sheet 显示 `/api/config/scenes/{name}/composition` 结果
  - 编辑：未保存提示 + 「保存」按钮（PUT）
  - 错误反馈：保存失败给出 detail + 「恢复」

#### 5.8.7 ChatConsolePage

**布局**：
- 顶部：scene 下拉 + ticker 输入框 + 「新会话」
- 中部：消息流（user/assistant 气泡）
- 底部：textarea + 提交（Cmd+Enter）

**数据流**：
- 提交 → POST `/api/chat` 拿到 `session_id` + `run_id`
- 同时 SSE 订阅 `/api/runs/{run_id}/events`
- 渲染 `agent.token_delta` / `tool.start` / `tool.finish` / `agent.message_finish`
- 复用现有 events.py 的事件 schema；前端只挑选关心的字段渲染

**MVP 简化**：不实现历史会话切换、不实现 pending turn 恢复（这些已有后端支持，后续迭代加 UI）。

### 5.9 开发与部署

#### 5.9.1 dev

```bash
# 终端 1：后端
.venv/bin/python -m dayu web --port 9000 --cors-allow-origins http://localhost:5175

# 终端 2：前端
cd frontend
npm install
npm run dev   # http://localhost:5175；vite proxy /api → http://localhost:9000
```

`vite.config.ts` 关键：

```ts
server: {
  port: 5175,
  proxy: {
    "/api": { target: "http://localhost:9000", changeOrigin: true, ws: false },
  },
},
```

#### 5.9.2 生产

```bash
cd frontend && npm run build   # 产物：frontend/dist
.venv/bin/python -m dayu web --port 9000 --static-dir frontend/dist
# 浏览器打开 http://localhost:9000 → React SPA
```

#### 5.9.3 .gitignore 追加

```
frontend/node_modules/
frontend/dist/
frontend/.vite/
```

---

## 6. 测试策略

### 6.1 后端

| 测试 | 位置 | 覆盖率目标 |
|---|---|---|
| PortfolioBrowsingService | `tests/application/test_portfolio_browsing_service.py` | ≥ 80%（已 9 用例） |
| SceneConfigService | `tests/application/test_scene_config_service.py` | ≥ 80% |
| PromptDocumentRepository | `tests/application/test_prompt_document_repository.py` | ≥ 80% |
| PipelineProgressProjector | `tests/application/test_pipeline_progress_projector.py` | ≥ 80% |
| Web routes（portfolio） | `tests/application/test_web_routes_portfolio.py` | ≥ 80% |
| Web routes（config） | `tests/application/test_web_routes_config.py` | ≥ 80% |
| Web routes（upload） | `tests/application/test_web_routes_upload.py` | ≥ 80% |

每次代码改动后必须执行：

```bash
.venv/bin/python -m pytest tests/application/ -x -q
.venv/bin/python -m pyright dayu tests
```

### 6.2 前端

> v1 不要求单测覆盖率，**必须**做以下手工验收：

1. dev 启动后访问 4 大页面无 console 报错
2. 实际从 workspace 拉到至少一家公司的真实 filings 列表
3. 上传流水线 SSE 在 download 阶段实时切换状态
4. PromptConsole 编辑 manifest 后保存 → 重新加载后内容仍为新版本
5. Chat 提交后能看到流式 token

可选：`vitest` + `@testing-library/react` 做关键 hook 测试。本次 MVP 不强制。

---

## 7. README 更新

按 AGENTS.md "README 触发更新规则"，本次需更新：

### 7.1 根 `README.md`

- §11 项目全景与模型矩阵：补 `frontend/`、`dayu/web/` 新路由、`PortfolioBrowsing/SceneConfig` 服务
- 目录结构图：加 `frontend/`
- 安装与启动：新增 "前端开发" 与 "生产部署" 子节
- CLI 命令清单：补 `dayu web`

### 7.2 `dayu/README.md`

- 架构图加 Web 层、`PortfolioBrowsing/SceneConfig`
- 扩展入口：补"如何新增前端可视化页面"

### 7.3 `tests/README.md`

- 列出新增测试文件位置与定位

### 7.4 不需要改

- `dayu/engine/README.md`、`dayu/fins/README.md`、`dayu/config/README.md`：本次未触发其负责范围。

---

## 8. 实施顺序与里程碑

> 按依赖顺序，每个里程碑结束**必须**通过 pytest + pyright，否则不进入下一里程碑。

### M1：后端 Service 层（已完成 80%）

- [x] DTO 与 Protocol 扩充
- [x] PortfolioBrowsingService + 单测
- [x] SceneConfigService + PromptDocumentRepository
- [ ] **补**：SceneConfigService / PromptDocumentRepository 单测
- [ ] PipelineProgressProjector + 单测

**验收**：`pytest tests/application/test_*service*.py test_*projector*.py test_*repository*.py` 全绿；pyright 0 错。

### M2：Web 路由层

- [ ] portfolio.py / config.py / upload.py / files.py
- [ ] fastapi_app.py 装配扩展（CORS + StaticFiles + 新路由）
- [ ] dayu/cli/web_command.py + 集成到 main.py
- [ ] 4 个路由测试文件

**验收**：`curl localhost:9000/api/portfolio/companies` 返回真实 workspace 数据；`pytest tests/application/test_web_routes_*.py` 全绿；pyright 0 错。

### M3：前端骨架

- [ ] `frontend/` 工程初始化（npm init / vite / tailwind / shadcn）
- [ ] AppShell + Sidebar + 路由 + 主题
- [ ] api.ts + sse.ts + types/api.ts 全量

**验收**：`npm run dev` 起得来，4 个空页面可路由切换。

### M4：Portfolio 页面

- [ ] PortfolioPage / CompanyDetailPage / FilingDetailPage
- [ ] 与真实 workspace 联调：能列出 AAPL / SY 并查看 filing 原文

### M5：Upload 页面

- [ ] UploadPage + PipelineGraph
- [ ] SSE 实时进度联调

### M6：Config + Interact 页面

- [ ] SceneMatrixPage / PromptConsolePage（含 Monaco 编辑器）
- [ ] ChatConsolePage（含 SSE）

### M7：收尾

- [ ] 全量 pytest + pyright + 手工验收
- [ ] 三处 README 更新
- [ ] `.gitignore` 追加 frontend 产物
- [ ] CHANGELOG 简单一行：`feat(web): 新增可视化前端 + portfolio/config/upload 浏览 API`

---

## 9. 风险与未覆盖项

| 风险 | 缓解 |
|---|---|
| Filing 原文 HTML 内含外链脚本 | iframe `sandbox` 严格隔离，不允许 same-origin |
| Prompt 编辑写坏 manifest 导致 scene 加载失败 | 后端写入前 schema 校验（v1 暂不做，仅文档提醒；v2 加 manifest schema 校验） |
| SSE 长连接堆积 | 前端 useEffect cleanup 必须 close；后端 events.py 已有取消机制 |
| 大 XBRL facts（>5000 条）渲染卡顿 | 前端表格强制虚拟滚动（`@tanstack/react-virtual`） |
| 不同 OS 路径分隔符 | 后端 `PromptDocumentRepository._validate_relative_path` 已规范化为 `/`；前端始终用 `/` |
| Workspace 同时被 CLI 与 Web 写入 | 后端写操作仍走现有 fins 管线（带文件锁），Web 不直接写 portfolio；prompt 写入只针对 workspace/config 不冲突 |

### 不在本期范围

- 多用户、登录、权限
- 全文搜索（FTS5/Whoosh/tantivy）
- Filing 编辑 / 删除（删除走 CLI）
- 历史会话 UI 切换
- pending turn 恢复 UI
- 移动端适配
- i18n（默认中文）

---

## 10. AGENTS.md 强约束自检清单

实施每一项变更前对照：

- [ ] 是否破坏 UI → Service → Host → Agent 单向？
- [ ] 是否绕过 `dayu.fins.storage` 直接读写文件？
- [ ] 函数有完整中文 docstring（参数 / 返回 / 异常）？
- [ ] 公共签名是否使用 `Any` / `object` / 无类型？
- [ ] 是否引入 god class / 兼容性 wrapper / re-export？
- [ ] 是否新增了魔法数字 / 字符串而非常量？
- [ ] schema 变更是否按"全新建库"处理（拒绝迁移与兼容读取）？
- [ ] 单文件测试覆盖率 ≥ 80%？
- [ ] pyright 0 新增报错？
- [ ] 改了哪些 README 已按触发规则更新？

---

## 11. 文件清单（供另一模型直接执行）

### 11.1 已存在（继承）

- `dayu/services/contracts.py`（已添加全量 DTO）
- `dayu/services/protocols.py`（已添加 PortfolioBrowsing / SceneConfig 协议）
- `dayu/services/portfolio_browsing_service.py`（已实现 + 测试）
- `dayu/services/scene_config_service.py`（已实现）
- `dayu/services/internal/prompt_document_repository.py`（已实现）
- `tests/application/test_portfolio_browsing_service.py`（已 9 用例通过）
- `pyrightconfig.json`（已加 venv + frontend 排除）

### 11.2 待新建

后端：

- `dayu/services/pipeline_progress_projector.py`
- `dayu/web/routes/portfolio.py`
- `dayu/web/routes/config.py`
- `dayu/web/routes/upload.py`
- `dayu/web/routes/files.py`
- `dayu/cli/web_command.py`
- `tests/application/test_scene_config_service.py`
- `tests/application/test_prompt_document_repository.py`
- `tests/application/test_pipeline_progress_projector.py`
- `tests/application/test_web_routes_portfolio.py`
- `tests/application/test_web_routes_config.py`
- `tests/application/test_web_routes_upload.py`

后端待修改：

- `dayu/web/fastapi_app.py`（装配扩展）
- `dayu/cli/main.py`（注册 web 子命令）
- `dayu/services/__init__.py`（导出 PortfolioBrowsingService / SceneConfigService）

前端（全部新建）：

- `frontend/` 工程根目录（package.json, vite.config.ts, tailwind.config.ts 等配置）
- `frontend/src/` 全量代码（结构见 §5.1）

文档：

- `README.md` §11 / 启动节
- `dayu/README.md` 架构图与扩展入口
- `tests/README.md` 测试位置
- `.gitignore` 追加 frontend/

---

## 12. 终止条件（DOD）

任何一项不满足，本次任务都不算完成：

1. `dayu web` 命令可启动；浏览器访问能看到 4 大页面真实数据
2. Upload 流水线在 SSE 中能看到至少 download/process 阶段切换
3. Prompt 编辑保存后回读内容一致
4. Chat 输入后流式输出 token
5. `pytest tests/` 全绿，无新增 skip
6. `pyright dayu tests` 0 错误
7. 三处 README 更新完成
8. PR 描述里列明：改了什么、验证了什么、风险与未覆盖项

---

## 附录 A：参考实现快照

> 用于另一模型快速对照已落地代码风格。具体源码见对应文件。

- `PortfolioBrowsingService` 9 个单测构造的 Fake 仓储模式 → 复用到 SceneConfigService 测试
- `dayu/web/routes/sessions.py` 的路由工厂 + 内嵌 Pydantic 模型 → 复用到 portfolio/config/upload
- `dayu/web/routes/events.py` 的 SSE 生成器 → 复用到 upload/progress
- `dayu/services/scene_definition_reader.py` 的极简服务 dataclass 风格 → 全部新 service 沿用

---

**结束。**
执行者请按 §8 里程碑顺序推进，每个里程碑闭环后再开下一阶段。所有疑问回到 `AGENTS.md`。
