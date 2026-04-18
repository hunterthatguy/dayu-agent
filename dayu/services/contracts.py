"""服务层公共 DTO 定义。

该模块只定义 UI -> Service 与 Service -> UI 的稳定契约，
不承载装配逻辑，也不暴露 Host 层内部记录类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional

from dayu.contracts.events import AppEvent
from dayu.contracts.execution_metadata import ExecutionDeliveryContext, empty_execution_delivery_context
from dayu.contracts.fins import FinsCommand, FinsEvent, FinsResult
from dayu.contracts.reply_outbox import ReplyOutboxState
from dayu.execution.options import ExecutionOptions


@dataclass
class SceneModelConfig:
    """写作流水线中单个 scene 的生效模型配置。

    Attributes:
        name: 生效模型名。
        temperature: 生效 temperature。
    """

    name: str
    temperature: float


@dataclass
class WriteRunConfig:
    """写作运行配置。

    Attributes:
        ticker: 公司股票代码。
        company: 公司名称。
        template_path: 模板文件绝对路径。
        output_dir: 输出目录绝对路径。
        write_max_retries: 章节重写最大次数。
        web_provider: 联网 provider 策略。
        resume: 是否启用断点恢复。
        write_model_override_name: 主写作场景模型覆盖名。
        audit_model_override_name: 审计场景模型覆盖名。
        scene_models: 各 scene 实际生效模型映射。
        chapter_filter: 章节过滤表达式。
        fast: 是否仅执行写作，不进入 audit/confirm/repair。
        force: 是否强制放宽第0章/第10章的 audit 前置门禁。
        infer: 是否仅执行一次公司级 facet 归因并写回 manifest。
    """

    ticker: str
    company: str
    template_path: str
    output_dir: str
    write_max_retries: int
    web_provider: str
    resume: bool
    write_model_override_name: str = ""
    audit_model_override_name: str = ""
    scene_models: dict[str, SceneModelConfig] = field(default_factory=dict)
    chapter_filter: str = ""
    fast: bool = False
    force: bool = False
    infer: bool = False


class SessionResolutionPolicy(str, Enum):
    """Service 层会话解析策略。

    UI 通过该策略声明“这次请求希望怎样解析 session”，
    Service 只理解会话生命周期，不再通过请求来源推断 UI 特例。
    """

    AUTO = "auto"
    CREATE_NEW = "create_new"
    REQUIRE_EXISTING = "require_existing"
    ENSURE_DETERMINISTIC = "ensure_deterministic"


@dataclass(frozen=True)
class ChatTurnRequest:
    """聊天单轮请求。

    Attributes:
        user_text: 用户输入文本。
        session_id: 可选会话 ID；首轮可不传，由 Service 创建。
        ticker: 可选股票代码。
        execution_options: 可选请求级执行参数覆盖。
        scene_name: 可选 scene 名称；未传时由 Service 使用默认值。
        session_resolution_policy: 会话解析策略。
        delivery_context: UI 侧交付上下文，用于 pending turn 恢复后重新投递回复。
    """

    user_text: str
    session_id: str | None = None
    ticker: Optional[str] = None
    execution_options: ExecutionOptions | None = None
    scene_name: str | None = None
    session_resolution_policy: SessionResolutionPolicy = SessionResolutionPolicy.AUTO
    delivery_context: ExecutionDeliveryContext | None = None


@dataclass(frozen=True)
class PromptRequest:
    """单轮 Prompt 请求。

    Attributes:
        user_text: 用户输入文本。
        ticker: 可选股票代码。
        session_id: 可选会话 ID；未传时由 Service 创建。
        execution_options: 可选请求级执行参数覆盖。
        session_resolution_policy: 会话解析策略。
    """

    user_text: str
    ticker: Optional[str] = None
    session_id: Optional[str] = None
    execution_options: ExecutionOptions | None = None
    session_resolution_policy: SessionResolutionPolicy = SessionResolutionPolicy.AUTO


@dataclass(frozen=True)
class FinsSubmitRequest:
    """财报服务提交请求。

    Attributes:
        command: 财报命令。
        session_resolution_policy: 会话解析策略。
    """

    command: FinsCommand
    session_resolution_policy: SessionResolutionPolicy = SessionResolutionPolicy.AUTO


@dataclass(frozen=True)
class ChatTurnSubmission:
    """聊天单轮提交句柄。

    Attributes:
        session_id: Service 解析后的会话 ID。
        event_stream: 事件流句柄。
    """

    session_id: str
    event_stream: AsyncIterator[AppEvent]


@dataclass(frozen=True)
class ChatPendingTurnView:
    """聊天服务暴露给 UI 的 pending turn 视图。"""

    pending_turn_id: str
    session_id: str
    scene_name: str
    user_text: str
    source_run_id: str
    resumable: bool
    state: str
    metadata: ExecutionDeliveryContext


@dataclass(frozen=True)
class ChatResumeRequest:
    """聊天恢复请求。

    Attributes:
        session_id: 当前请求所属会话 ID。
        pending_turn_id: 需要恢复的 pending turn ID。
    """

    session_id: str
    pending_turn_id: str


@dataclass(frozen=True)
class ReplyDeliverySubmitRequest:
    """reply delivery 提交请求。

    Attributes:
        delivery_key: 渠道层提供的稳定幂等键。
        session_id: 关联会话 ID。
        scene_name: 关联 scene 名。
        source_run_id: 产生该回复的执行 run ID。
        reply_content: 待交付的最终文本回复。
        metadata: 渠道交付上下文。
    """

    delivery_key: str
    session_id: str
    scene_name: str
    source_run_id: str
    reply_content: str
    metadata: ExecutionDeliveryContext = field(default_factory=empty_execution_delivery_context)


@dataclass(frozen=True)
class ReplyDeliveryFailureRequest:
    """reply delivery 失败回写请求。

    Attributes:
        delivery_id: 交付记录 ID。
        retryable: 是否允许后续重试。
        error_message: 失败说明。
    """

    delivery_id: str
    retryable: bool
    error_message: str


@dataclass(frozen=True)
class ReplyDeliveryView:
    """渠道层可见的交付视图。"""

    delivery_id: str
    delivery_key: str
    session_id: str
    scene_name: str
    source_run_id: str
    reply_content: str
    metadata: ExecutionDeliveryContext
    state: ReplyOutboxState
    created_at: str
    updated_at: str
    delivery_attempt_count: int
    last_error_message: str | None = None


@dataclass(frozen=True)
class PromptSubmission:
    """Prompt 提交句柄。

    Attributes:
        session_id: Service 解析后的会话 ID。
        event_stream: 事件流句柄。
    """

    session_id: str
    event_stream: AsyncIterator[AppEvent]


@dataclass(frozen=True)
class FinsSubmission:
    """财报服务提交句柄。

    Attributes:
        session_id: Service 解析后的会话 ID。
        execution: 同步结果或流式事件句柄。
    """

    session_id: str
    execution: FinsResult | AsyncIterator[FinsEvent]


@dataclass(frozen=True)
class SessionAdminView:
    """宿主管理面的会话视图。

    Attributes:
        session_id: 会话 ID。
        source: 会话来源。
        state: 会话状态。
        scene_name: 首次使用的 scene 名称。
        created_at: 创建时间的 ISO 文本。
        last_activity_at: 最后活跃时间的 ISO 文本。
    """

    session_id: str
    source: str
    state: str
    scene_name: str | None
    created_at: str
    last_activity_at: str


@dataclass(frozen=True)
class RunAdminView:
    """宿主管理面的运行视图。

    Attributes:
        run_id: 运行 ID。
        session_id: 关联会话 ID。
        service_type: 服务类型。
        state: 运行状态。
        cancel_requested_at: 请求取消时间。
        cancel_requested_reason: 请求取消原因。
        cancel_reason: 取消原因。
        scene_name: scene 名称。
        created_at: 创建时间的 ISO 文本。
        started_at: 开始时间的 ISO 文本。
        finished_at: 结束时间的 ISO 文本。
        error_summary: 错误摘要。
    """

    run_id: str
    session_id: str | None
    service_type: str
    state: str
    cancel_requested_at: str | None
    cancel_requested_reason: str | None
    cancel_reason: str | None
    scene_name: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    error_summary: str | None


@dataclass(frozen=True)
class HostCleanupResult:
    """宿主清理结果。

    Attributes:
        orphan_run_ids: 被清理的孤儿 run ID。
        stale_permit_ids: 被清理的过期 permit ID。
    """

    orphan_run_ids: tuple[str, ...]
    stale_permit_ids: tuple[str, ...]


@dataclass(frozen=True)
class LaneStatusView:
    """并发通道状态视图。

    Attributes:
        lane: 通道名称。
        active: 当前活跃运行数。
        max_concurrent: 最大并发数。
    """

    lane: str
    active: int
    max_concurrent: int


@dataclass(frozen=True)
class HostStatusView:
    """宿主状态视图。

    Attributes:
        active_session_count: 活跃会话数量。
        total_session_count: 会话总数。
        active_run_count: 活跃运行数量。
        active_runs_by_type: 按服务类型聚合的活跃运行数。
        lane_statuses: 并发通道状态快照。
    """

    active_session_count: int
    total_session_count: int
    active_run_count: int
    active_runs_by_type: dict[str, int]
    lane_statuses: dict[str, LaneStatusView]


@dataclass(frozen=True)
class WriteRequest:
    """写作服务请求。"""

    write_config: WriteRunConfig
    execution_options: ExecutionOptions | None = None


@dataclass(frozen=True)
class CompanyView:
    """portfolio 浏览视图：单家公司条目。

    Attributes:
        ticker: 公司股票代码（规范化后）。
        company_name: 公司名称。
        market: 市场代码（如 ``US`` / ``HK`` / ``CN``）。
        company_id: 内部 company_id。
        updated_at: meta 最近更新时间（ISO8601）。
        ticker_aliases: 公司别名（输入规范化前的候选）。
        directory_name: 工作区目录名（与扫描状态一同帮助 UI 展示异常条目）。
        status: 公司目录扫描状态（``available`` / ``hidden_directory`` / ``missing_meta`` / ``invalid_meta``）。
        detail: 异常条目附加说明；``status=available`` 时为空串。
        filing_count: 当前公司活跃 filings 数量；扫描异常时为 ``0``。
        processed_count: 当前公司活跃 processed 文档数量；扫描异常时为 ``0``。
    """

    ticker: str
    company_name: str
    market: str
    company_id: str
    updated_at: str
    ticker_aliases: tuple[str, ...]
    directory_name: str
    status: str
    detail: str
    filing_count: int
    processed_count: int


@dataclass(frozen=True)
class FilingFileView:
    """单个 filing 内的文件条目视图。

    Attributes:
        name: 文件名。
        size: 文件字节数；未知时为 ``None``。
        content_type: HTTP content-type；未知时为 ``None``。
        sha256: 内容 sha256；未知时为 ``None``。
    """

    name: str
    size: Optional[int]
    content_type: Optional[str]
    sha256: Optional[str]


@dataclass(frozen=True)
class FilingView:
    """portfolio 浏览视图：单份 filing 列表条目。

    Attributes:
        ticker: 股票代码。
        document_id: 文档 ID（含 ``fil_`` 前缀的稳定标识）。
        form_type: 报告类型（如 ``10-K``）。
        fiscal_year: 财年。
        fiscal_period: 财季。
        report_date: 报告期。
        filing_date: 报送日期。
        amended: 是否为修正版。
        ingest_complete: 入库是否完成。
        is_deleted: 是否已逻辑删除。
        has_xbrl: 是否包含 XBRL；未知时为 ``None``。
        has_processed: 是否存在对应 processed 产物。
        primary_document: 主文档名；未知时为空串。
    """

    ticker: str
    document_id: str
    form_type: Optional[str]
    fiscal_year: Optional[int]
    fiscal_period: Optional[str]
    report_date: Optional[str]
    filing_date: Optional[str]
    amended: bool
    ingest_complete: bool
    is_deleted: bool
    has_xbrl: Optional[bool]
    has_processed: bool
    primary_document: str


@dataclass(frozen=True)
class FilingDetailView:
    """portfolio 浏览视图：单份 filing 详情。

    Attributes:
        filing: 列表级摘要。
        files: filing 目录内文件清单。
        processed_summary: 关联 processed 文档摘要；不存在时为 ``None``。
        section_count: processed 内 section 数量；无 processed 时为 ``0``。
        table_count: processed 内 table 数量；无 processed 时为 ``0``。
        has_financials: processed 是否产出了 financial statements。
    """

    filing: FilingView
    files: tuple[FilingFileView, ...]
    processed_summary: Optional["ProcessedArtifactView"]
    section_count: int
    table_count: int
    has_financials: bool


@dataclass(frozen=True)
class ProcessedArtifactView:
    """portfolio 浏览视图：单份 processed 产物条目。

    Attributes:
        ticker: 股票代码。
        document_id: 文档 ID。
        source_kind: 来源类型（``filing`` / ``material``）。
        form_type: 报告类型。
        fiscal_year: 财年。
        fiscal_period: 财季。
        report_date: 报告期。
        filing_date: 报送日期。
        amended: 是否为修正版。
        is_deleted: 是否已逻辑删除。
        document_version: 文档版本。
        quality: processed 质量标签（如 ``full`` / ``degraded``）。
        has_financials: 是否产出 financial statements。
        section_count: section 数量。
        table_count: table 数量。
    """

    ticker: str
    document_id: str
    source_kind: str
    form_type: Optional[str]
    fiscal_year: Optional[int]
    fiscal_period: Optional[str]
    report_date: Optional[str]
    filing_date: Optional[str]
    amended: bool
    is_deleted: bool
    document_version: str
    quality: str
    has_financials: bool
    section_count: int
    table_count: int


@dataclass(frozen=True)
class FilingSectionView:
    """单份 filing processed 产物内的 section 条目。

    Attributes:
        section_id: section 稳定标识。
        title: section 标题。
        depth: 标题层级。
        order: 在文档中的全局序号。
        char_count: 字符数。
    """

    section_id: str
    title: str
    depth: int
    order: int
    char_count: int


@dataclass(frozen=True)
class FilingTableView:
    """单份 filing processed 产物内的 table 条目。

    Attributes:
        table_id: table 稳定标识。
        caption: 表标题。
        section_id: 所属 section ID；无归属时为空串。
        row_count: 行数。
        column_count: 列数。
    """

    table_id: str
    caption: str
    section_id: str
    row_count: int
    column_count: int


@dataclass(frozen=True)
class XbrlFactView:
    """单份 filing 关联的 XBRL fact 条目。

    Attributes:
        concept: 概念 QName 或本地名。
        unit: 计量单位；未知时为空串。
        value: 标量值的字符串表达。
        period_start: 周期起始日；时点事实时为空串。
        period_end: 周期结束日。
        decimals: 精度声明；未知时为空串。
        context_id: XBRL context 标识；未知时为空串。
    """

    concept: str
    unit: str
    value: str
    period_start: str
    period_end: str
    decimals: str
    context_id: str


@dataclass(frozen=True)
class FilingProcessedView:
    """单份 filing 的 processed 详情视图。

    Attributes:
        artifact: processed 产物摘要。
        sections: section 列表。
        tables: table 列表。
        xbrl_facts: XBRL fact 列表。
    """

    artifact: ProcessedArtifactView
    sections: tuple[FilingSectionView, ...]
    tables: tuple[FilingTableView, ...]
    xbrl_facts: tuple[XbrlFactView, ...]


@dataclass(frozen=True)
class RejectedFilingView:
    """portfolio 浏览视图：被拒绝的 filing 条目。

    Attributes:
        ticker: 股票代码。
        document_id: 文档 ID。
        accession_number: SEC accession 编号。
        form_type: 报告类型。
        filing_date: 报送日期。
        rejection_reason: 拒绝原因短描述。
        rejection_category: 拒绝分类。
        rejected_at: 拒绝发生时间（ISO8601）。
    """

    ticker: str
    document_id: str
    accession_number: str
    form_type: str
    filing_date: str
    rejection_reason: str
    rejection_category: str
    rejected_at: str


@dataclass(frozen=True)
class PortfolioHealthView:
    """portfolio 浏览视图：单家公司健康度摘要。

    Attributes:
        ticker: 股票代码。
        total_filings: 活跃 filings 数量。
        ingest_incomplete_filings: 未完成入库的 filings 数量。
        deleted_filings: 已逻辑删除的 filings 数量。
        processed_filings: 已生成 processed 产物的 filings 数量。
        missing_processed_filings: 已入库但缺 processed 的 filings 数量。
        rejected_filings: 被拒绝的 filings 数量。
        rejected_samples: 最近若干条被拒绝条目（最多 10 条）。
    """

    ticker: str
    total_filings: int
    ingest_incomplete_filings: int
    deleted_filings: int
    processed_filings: int
    missing_processed_filings: int
    rejected_filings: int
    rejected_samples: tuple[RejectedFilingView, ...]


@dataclass(frozen=True)
class FilingFileBlob:
    """单文件读取结果。

    Attributes:
        filename: 文件名。
        content: 文件原始字节。
        content_type: HTTP content-type；未知时为 ``application/octet-stream``。
    """

    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True)
class SceneModelOptionView:
    """配置浏览视图：某 scene 下可选模型条目。

    Attributes:
        model_name: 模型名。
        is_default: 该模型是否为默认。
    """

    model_name: str
    is_default: bool


@dataclass(frozen=True)
class SceneMatrixRowView:
    """配置浏览视图：scene 矩阵单行。

    Attributes:
        scene_name: scene 名。
        default_model: 默认模型名；未指定时为空串。
        allowed_models: 允许该 scene 调用的模型列表。
    """

    scene_name: str
    default_model: str
    allowed_models: tuple[SceneModelOptionView, ...]


@dataclass(frozen=True)
class SceneMatrixView:
    """配置浏览视图：scene × 模型矩阵全量快照。

    Attributes:
        all_models: 工作区已配置的全部模型名（用于矩阵列）。
        rows: scene 行视图。
    """

    all_models: tuple[str, ...]
    rows: tuple[SceneMatrixRowView, ...]


@dataclass(frozen=True)
class PromptDocumentView:
    """配置浏览视图：单份 prompt 文档。

    该视图覆盖 ``manifests``、``scenes``、``base``、``tasks`` 四类目录下的 markdown / json 文档，
    用于前端 prompt 控制台浏览与编辑。

    Attributes:
        category: 类别（``manifests`` / ``scenes`` / ``base`` / ``tasks``）。
        name: 不带扩展名的文档名。
        relative_path: 相对 prompts 根目录的路径，便于路由定位与回写。
        size: 字节数。
        updated_at: 文件最近修改时间（ISO8601）。
    """

    category: str
    name: str
    relative_path: str
    size: int
    updated_at: str


@dataclass(frozen=True)
class PromptDocumentDetailView:
    """配置浏览视图：单份 prompt 文档详情。

    Attributes:
        document: 文档摘要。
        content: 文档原文文本（UTF-8）。
    """

    document: PromptDocumentView
    content: str


@dataclass(frozen=True)
class ScenePromptCompositionView:
    """scene 拼接后的系统提示视图。

    Attributes:
        scene_name: scene 名。
        composed_text: 拼接好的完整系统提示文本。
        fragments: 参与拼接的 prompt 文档名列表（按拼接顺序）。
    """

    scene_name: str
    composed_text: str
    fragments: tuple[str, ...]


class PipelineStageState(str, Enum):
    """流水线阶段状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PipelineStageView:
    """upload 流水线单阶段视图。

    Attributes:
        key: 阶段键名（如 ``download`` / ``process``）。
        title: 展示标题。
        state: 阶段状态。
        message: 末次状态描述；无信息时为空串。
        started_at: 阶段开始时间（ISO8601）；未开始时为空串。
        finished_at: 阶段结束时间（ISO8601）；未结束时为空串。
    """

    key: str
    title: str
    state: PipelineStageState
    message: str
    started_at: str
    finished_at: str


@dataclass(frozen=True)
class PipelineProgressView:
    """upload 流水线整体进度视图。

    Attributes:
        ticker: 股票代码。
        run_id: 当前关注的 run id；未启动时为空串。
        session_id: 关联 session id；未启动时为空串。
        stages: 阶段列表（按顺序）。
        active_stage_key: 当前正在执行的阶段键；都已结束时为空串。
        terminal_state: 整体终态（``running`` / ``succeeded`` / ``failed`` / ``cancelled``）。
        updated_at: 进度对象最近更新时间（ISO8601）。
    """

    ticker: str
    run_id: str
    session_id: str
    stages: tuple[PipelineStageView, ...]
    active_stage_key: str
    terminal_state: str
    updated_at: str


__all__ = [
    "ChatPendingTurnView",
    "ChatResumeRequest",
    "ChatTurnSubmission",
    "ChatTurnRequest",
    "CompanyView",
    "FilingDetailView",
    "FilingFileBlob",
    "FilingFileView",
    "FilingProcessedView",
    "FilingSectionView",
    "FilingTableView",
    "FilingView",
    "FinsSubmission",
    "FinsSubmitRequest",
    "HostCleanupResult",
    "HostStatusView",
    "LaneStatusView",
    "PipelineProgressView",
    "PipelineStageState",
    "PipelineStageView",
    "PortfolioHealthView",
    "ProcessedArtifactView",
    "PromptDocumentDetailView",
    "PromptDocumentView",
    "PromptRequest",
    "PromptSubmission",
    "RejectedFilingView",
    "ReplyDeliveryFailureRequest",
    "ReplyDeliverySubmitRequest",
    "ReplyDeliveryView",
    "RunAdminView",
    "SceneMatrixRowView",
    "SceneMatrixView",
    "SceneModelConfig",
    "SceneModelOptionView",
    "ScenePromptCompositionView",
    "SessionResolutionPolicy",
    "SessionAdminView",
    "WriteRequest",
    "WriteRunConfig",
    "XbrlFactView",
]
