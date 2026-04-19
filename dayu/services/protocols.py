"""服务层协议定义。"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from dayu.contracts.events import AppEvent, PublishedRunEventProtocol
from dayu.services.contracts import (
    ApiKeyStatusView,
    ChatPendingTurnView,
    ChatResumeRequest,
    ChatTurnRequest,
    ChatTurnSubmission,
    CompanyView,
    FilingDetailView,
    FilingFileBlob,
    FilingProcessedView,
    FilingView,
    FinsSubmitRequest,
    FinsSubmission,
    HostCleanupResult,
    HostStatusView,
    ModelApiKeyRequirementView,
    PortfolioHealthView,
    ProcessedArtifactView,
    PromptDocumentDetailView,
    PromptDocumentView,
    PromptRequest,
    PromptSubmission,
    ReplyDeliveryFailureRequest,
    ReplyDeliverySubmitRequest,
    ReplyDeliveryView,
    RunAdminView,
    SceneDefaultModelUpdateView,
    SceneMatrixView,
    ScenePromptCompositionView,
    SessionAdminView,
    WriteRequest,
)


@runtime_checkable
class BaseServiceProtocol(Protocol):
    """服务基础协议。"""


@runtime_checkable
class ChatServiceProtocol(BaseServiceProtocol, Protocol):
    """聊天服务协议。"""

    async def submit_turn(self, request: ChatTurnRequest) -> ChatTurnSubmission:
        """提交聊天单轮请求并返回会话句柄。

        Args:
            request: 聊天单轮请求。

        Returns:
            包含 `session_id` 与事件流句柄的提交结果。
        """
        ...

    async def resume_pending_turn(self, request: ChatResumeRequest) -> ChatTurnSubmission:
        """恢复指定 pending conversation turn 并返回事件流句柄。"""
        ...

    def list_resumable_pending_turns(
        self,
        *,
        session_id: str | None = None,
        scene_name: str | None = None,
    ) -> list[ChatPendingTurnView]:
        """列出可恢复的 pending conversation turn。"""
        ...


@runtime_checkable
class PromptServiceProtocol(BaseServiceProtocol, Protocol):
    """单轮 Prompt 服务协议。"""

    async def submit(self, request: PromptRequest) -> PromptSubmission:
        """提交单轮 Prompt 请求并返回会话句柄。

        Args:
            request: Prompt 请求。

        Returns:
            包含 `session_id` 与事件流句柄的提交结果。
        """
        ...


@runtime_checkable
class WriteServiceProtocol(BaseServiceProtocol, Protocol):
    """写作服务协议。"""

    def run(self, request: WriteRequest) -> int:
        """执行写作流程。"""
        ...

    @staticmethod
    def print_report(output_dir: str) -> int:
        """打印写作报告。"""
        ...


@runtime_checkable
class FinsServiceProtocol(BaseServiceProtocol, Protocol):
    """财报服务协议。"""

    def submit(self, request: FinsSubmitRequest) -> FinsSubmission:
        """提交财报命令并返回执行句柄。

        Args:
            request: 财报服务提交请求。

        Returns:
            包含 `session_id` 与执行句柄的提交结果。
        """
        ...


@runtime_checkable
class HostAdminServiceProtocol(BaseServiceProtocol, Protocol):
    """宿主管理服务协议。"""

    def create_session(self, *, source: str = "web", scene_name: str | None = None) -> SessionAdminView:
        """创建宿主会话。"""
        ...

    def list_sessions(self, *, state: str | None = None) -> list[SessionAdminView]:
        """列出宿主会话。"""
        ...

    def get_session(self, session_id: str) -> SessionAdminView | None:
        """获取单个宿主会话。"""
        ...

    def close_session(self, session_id: str) -> tuple[SessionAdminView, list[str]]:
        """关闭宿主会话并取消其下活跃运行。"""
        ...

    def list_runs(
        self,
        *,
        session_id: str | None = None,
        state: str | None = None,
        service_type: str | None = None,
        active_only: bool = False,
    ) -> list[RunAdminView]:
        """列出宿主运行记录。"""
        ...

    def get_run(self, run_id: str) -> RunAdminView | None:
        """获取单个运行记录。"""
        ...

    def cancel_run(self, run_id: str) -> RunAdminView:
        """取消指定运行。"""
        ...

    def cancel_session_runs(self, session_id: str) -> list[str]:
        """取消指定会话下的所有活跃运行。"""
        ...

    def cleanup(self) -> HostCleanupResult:
        """执行宿主清理。"""
        ...

    def get_status(self) -> HostStatusView:
        """获取宿主状态快照。"""
        ...

    def subscribe_run_events(self, run_id: str) -> AsyncIterator[PublishedRunEventProtocol]:
        """订阅单个运行的事件流。"""
        ...

    def subscribe_session_events(self, session_id: str) -> AsyncIterator[PublishedRunEventProtocol]:
        """订阅单个会话下所有运行的事件流。"""
        ...


@runtime_checkable
class ReplyDeliveryServiceProtocol(BaseServiceProtocol, Protocol):
    """渠道层使用的 reply delivery 服务协议。"""

    def submit_reply_for_delivery(self, request: ReplyDeliverySubmitRequest) -> ReplyDeliveryView:
        """显式提交待交付回复。"""
        ...

    def get_delivery(self, delivery_id: str) -> ReplyDeliveryView | None:
        """按 ID 查询交付记录。"""
        ...

    def list_deliveries(
        self,
        *,
        session_id: str | None = None,
        scene_name: str | None = None,
        state: str | None = None,
    ) -> list[ReplyDeliveryView]:
        """列出交付记录。"""
        ...

    def claim_delivery(self, delivery_id: str) -> ReplyDeliveryView:
        """把交付记录推进到发送中状态。"""
        ...

    def mark_delivery_delivered(self, delivery_id: str) -> ReplyDeliveryView:
        """标记交付完成。"""
        ...

    def mark_delivery_failed(self, request: ReplyDeliveryFailureRequest) -> ReplyDeliveryView:
        """标记交付失败。"""
        ...


@runtime_checkable
class PortfolioBrowsingServiceProtocol(BaseServiceProtocol, Protocol):
    """portfolio 只读浏览服务协议。

    该协议聚合 ``dayu.fins.storage`` 仓储数据，向 UI 暴露稳定 DTO，
    本身不涉及写操作；所有写入仍走 fins 管线。
    """

    def list_companies(self) -> list[CompanyView]:
        """列出 workspace 中所有公司及其汇总状态。"""
        ...

    def list_filings(
        self,
        ticker: str,
        *,
        form_type: str | None = None,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
        include_deleted: bool = False,
    ) -> list[FilingView]:
        """列出指定公司的 filings。"""
        ...

    def get_filing_detail(self, ticker: str, document_id: str) -> FilingDetailView:
        """读取单份 filing 的详情（含文件清单与 processed 摘要）。

        Raises:
            FileNotFoundError: filing 不存在时抛出。
        """
        ...

    def get_filing_processed(self, ticker: str, document_id: str) -> FilingProcessedView:
        """读取单份 filing 关联的 processed 详情（sections / tables / xbrl facts）。

        Raises:
            FileNotFoundError: 对应 processed 产物不存在时抛出。
        """
        ...

    def list_processed_artifacts(
        self,
        ticker: str,
        *,
        form_type: str | None = None,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
        include_deleted: bool = False,
    ) -> list[ProcessedArtifactView]:
        """列出指定公司的 processed 产物。"""
        ...

    def get_portfolio_health(self, ticker: str) -> PortfolioHealthView:
        """计算单家公司的健康度（缺失 processed、被拒绝 filings 等）。"""
        ...

    def read_filing_file(
        self,
        ticker: str,
        document_id: str,
        filename: str,
    ) -> FilingFileBlob:
        """读取 filing 目录下的指定文件。

        Raises:
            FileNotFoundError: filing 或文件不存在时抛出。
        """
        ...


@runtime_checkable
class SceneConfigServiceProtocol(BaseServiceProtocol, Protocol):
    """scene 与 prompt 配置浏览/编辑服务协议。"""

    def get_scene_matrix(self) -> SceneMatrixView:
        """读取 scene × 模型矩阵全量快照。"""
        ...

    def list_prompt_documents(self) -> list[PromptDocumentView]:
        """列出全部 prompt 文档（manifests / scenes / base / tasks）。"""
        ...

    def get_prompt_document(self, relative_path: str) -> PromptDocumentDetailView:
        """读取单份 prompt 文档详情。

        Raises:
            FileNotFoundError: 文档不存在时抛出。
            PermissionError: 路径越界（试图访问 prompts 根目录之外）时抛出。
        """
        ...

    def update_prompt_document(self, relative_path: str, content: str) -> PromptDocumentDetailView:
        """覆盖写入 prompt 文档原文。

        Raises:
            FileNotFoundError: 文档不存在时抛出。
            PermissionError: 路径越界时抛出。
            ValueError: 内容非法（如空文本）时抛出。
        """
        ...

    def get_scene_prompt_composition(self, scene_name: str) -> ScenePromptCompositionView:
        """读取指定 scene 的拼接系统提示。

        Raises:
            FileNotFoundError: scene manifest 不存在时抛出。
        """
        ...

    def update_scene_default_model(self, scene_name: str, model_name: str) -> SceneDefaultModelUpdateView:
        """更新 scene 的默认模型。

        Args:
            scene_name: Scene 名称。
            model_name: 新默认模型名。

        Returns:
            更新结果视图。

        Raises:
            FileNotFoundError: scene manifest 不存在时抛出。
            ValueError: 模型不在 allowed_names 中时抛出。
        """
        ...


@runtime_checkable
class ApiKeyConfigServiceProtocol(BaseServiceProtocol, Protocol):
    """API Key 配置服务协议。"""

    def list_api_key_status(self) -> list[ApiKeyStatusView]:
        """返回所有可配置 API key 的状态列表。"""
        ...

    def get_api_key(self, key_name: str) -> str | None:
        """获取指定 API key 的值。"""
        ...

    def set_api_key(self, key_name: str, value: str) -> None:
        """设置 API key。

        Raises:
            ValueError: key_name 不支持或值为空时抛出。
        """
        ...

    def clear_api_key(self, key_name: str) -> None:
        """清空 API key。

        Raises:
            ValueError: key_name 不支持时抛出。
        """
        ...

    def get_model_api_key_requirements(self) -> list[ModelApiKeyRequirementView]:
        """返回各模型的 API key 要求。"""
        ...

    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用（是否配置了所需 API key）。"""
        ...


__all__ = [
    "ApiKeyConfigServiceProtocol",
    "BaseServiceProtocol",
    "ChatServiceProtocol",
    "FinsServiceProtocol",
    "HostAdminServiceProtocol",
    "PortfolioBrowsingServiceProtocol",
    "PromptServiceProtocol",
    "ReplyDeliveryServiceProtocol",
    "SceneConfigServiceProtocol",
    "WriteServiceProtocol",
]
