"""Upload 流水线进度投影器。

该模块把 fins SSE 事件序列折叠为前端可直接渲染的 ``PipelineProgressView`` 状态机，
不依赖 Host，只输入 FinsEvent / AppEvent，只输出 PipelineProgressView。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from dayu.contracts.events import AppEvent, AppEventType
from dayu.contracts.fins import (
    FinsCommandName,
    FinsEvent,
    FinsEventType,
    FinsProgressEventName,
)
from dayu.services.contracts import (
    PipelineProgressView,
    PipelineStageState,
    PipelineStageView,
)


_STAGE_KEYS: tuple[str, ...] = ("resolve", "download", "process", "analyze")
_STAGE_TITLES: dict[str, str] = {
    "resolve": "解析 ticker",
    "download": "下载财报",
    "process": "解析与抽取",
    "analyze": "维度分析",
}
_DOWNLOAD_START_EVENTS: tuple[FinsProgressEventName, ...] = (
    FinsProgressEventName.PIPELINE_STARTED,
    FinsProgressEventName.COMPANY_RESOLVED,
    FinsProgressEventName.FILING_STARTED,
)
_DOWNLOAD_END_EVENTS: tuple[FinsProgressEventName, ...] = (
    FinsProgressEventName.FILING_COMPLETED,
    FinsProgressEventName.PIPELINE_COMPLETED,
)
_PROCESS_START_EVENTS: tuple[FinsProgressEventName, ...] = (
    FinsProgressEventName.DOCUMENT_STARTED,
)
_PROCESS_END_EVENTS: tuple[FinsProgressEventName, ...] = (
    FinsProgressEventName.DOCUMENT_COMPLETED,
    FinsProgressEventName.DOCUMENT_SKIPPED,
    FinsProgressEventName.PIPELINE_COMPLETED,
)


@dataclass(frozen=True)
class PipelineProgressProjector:
    """SSE 事件 → PipelineProgressView 投影器（无状态纯函数风格的累加器）。

    Attributes:
        ticker: 目标股票代码。
        run_id: 关联 run ID。
        session_id: 关联 session ID。
    """

    ticker: str
    run_id: str
    session_id: str
    _clock: Callable[[], datetime] = datetime.now  # 测试中可注入

    def initial(self) -> PipelineProgressView:
        """返回初始状态（所有阶段 pending）。

        Returns:
            全阶段 pending 的 ``PipelineProgressView``。
        """

        now_iso = self._clock().isoformat()
        stages = tuple(
            PipelineStageView(
                key=key,
                title=_STAGE_TITLES[key],
                state=PipelineStageState.PENDING,
                message="",
                started_at="",
                finished_at="",
            )
            for key in _STAGE_KEYS
        )
        return PipelineProgressView(
            ticker=self.ticker,
            run_id=self.run_id,
            session_id=self.session_id,
            stages=stages,
            active_stage_key="resolve",
            terminal_state="running",
            updated_at=now_iso,
        )

    def apply(
        self,
        current: PipelineProgressView,
        event: FinsEvent | AppEvent,
    ) -> PipelineProgressView:
        """应用单个事件到当前进度，返回新的 ``PipelineProgressView``。

        Args:
            current: 当前进度视图。
            event: Fins 或 App 事件。

        Returns:
            更新后的 ``PipelineProgressView``；未知事件时返回原视图（幂等）。
        """

        if isinstance(event, FinsEvent):
            return self._apply_fins_event(current, event)
        if isinstance(event, AppEvent):
            return self._apply_app_event(current, event)
        return current

    def _apply_fins_event(
        self,
        current: PipelineProgressView,
        event: FinsEvent,
    ) -> PipelineProgressView:
        """处理 FinsEvent。"""

        if event.type != FinsEventType.PROGRESS:
            return current
        payload = event.payload
        event_name = getattr(payload, "event_type", None)
        if event_name is None:
            return current

        if event.command == FinsCommandName.DOWNLOAD:
            return self._advance_download(current, event_name, payload)
        if event.command == FinsCommandName.PROCESS:
            return self._advance_process(current, event_name, payload)

        return current

    def _apply_app_event(
        self,
        current: PipelineProgressView,
        event: AppEvent,
    ) -> PipelineProgressView:
        """处理 AppEvent。"""

        if event.type == AppEventType.CANCELLED:
            return self._mark_cancelled(current)
        if event.type == AppEventType.ERROR:
            return self._mark_failed(current, str(event.payload))
        return current

    def _advance_download(
        self,
        current: PipelineProgressView,
        event_name: FinsProgressEventName,
        payload: object,
    ) -> PipelineProgressView:
        """推进 download 阶段状态。"""

        stages = list(current.stages)
        now_iso = self._clock().isoformat()

        # resolve 阶段：download 启动即视为完成
        if event_name in _DOWNLOAD_START_EVENTS:
            resolve_stage = self._mark_stage_running(stages[0], now_iso)
            resolve_stage = self._mark_stage_succeeded(resolve_stage, now_iso)
            stages[0] = resolve_stage

            # download 阶段启动
            download_stage = self._mark_stage_running(stages[1], now_iso)
            download_stage = self._apply_download_event_message(download_stage, event_name, payload)
            stages[1] = download_stage

            return self._build_view(current, stages, "download", "running", now_iso)

        # download 阶段完成或失败
        if event_name == FinsProgressEventName.FILING_FAILED:
            download_stage = self._mark_stage_failed(stages[1], "下载失败", now_iso)
            stages[1] = download_stage
            return self._build_view(current, stages, "", "failed", now_iso)

        if event_name in _DOWNLOAD_END_EVENTS:
            download_stage = self._mark_stage_succeeded(stages[1], now_iso)
            stages[1] = download_stage

            # 检查是否所有 filings 都完成
            if event_name == FinsProgressEventName.PIPELINE_COMPLETED:
                # download pipeline 完成，等待 process 启动
                return self._build_view(current, stages, "", "running", now_iso)

            return self._build_view(current, stages, "download", "running", now_iso)

        # 其他事件（如 FILE_DOWNLOADED）仅更新 message
        if event_name == FinsProgressEventName.FILE_DOWNLOADED:
            message = self._extract_file_message(payload, "已下载")
            download_stage = self._update_stage_message(stages[1], message)
            stages[1] = download_stage
            return self._build_view(current, stages, "download", "running", now_iso)

        return current

    def _advance_process(
        self,
        current: PipelineProgressView,
        event_name: FinsProgressEventName,
        payload: object,
    ) -> PipelineProgressView:
        """推进 process 阶段状态。"""

        stages = list(current.stages)
        now_iso = self._clock().isoformat()

        # process 阶段启动（仅在 download 完成后）
        if event_name in _PROCESS_START_EVENTS:
            # 确保 download 已完成
            if stages[1].state != PipelineStageState.SUCCEEDED:
                download_stage = self._mark_stage_succeeded(stages[1], now_iso)
                stages[1] = download_stage

            process_stage = self._mark_stage_running(stages[2], now_iso)
            process_stage = self._apply_process_event_message(process_stage, event_name, payload)
            stages[2] = process_stage
            return self._build_view(current, stages, "process", "running", now_iso)

        # process 阶段失败
        if event_name == FinsProgressEventName.DOCUMENT_FAILED:
            process_stage = self._mark_stage_failed(stages[2], "处理失败", now_iso)
            stages[2] = process_stage
            return self._build_view(current, stages, "", "failed", now_iso)

        # process 阶段完成
        if event_name in _PROCESS_END_EVENTS:
            process_stage = self._mark_stage_succeeded(stages[2], now_iso)
            stages[2] = process_stage

            if event_name == FinsProgressEventName.PIPELINE_COMPLETED:
                # analyze 阶段：v1 保持 skipped
                analyze_stage = self._mark_stage_skipped(stages[3])
                stages[3] = analyze_stage
                return self._build_view(current, stages, "", "succeeded", now_iso)

            return self._build_view(current, stages, "process", "running", now_iso)

        return current

    def _mark_stage_running(
        self,
        stage: PipelineStageView,
        started_at: str,
    ) -> PipelineStageView:
        """标记阶段为 running。"""

        return PipelineStageView(
            key=stage.key,
            title=stage.title,
            state=PipelineStageState.RUNNING,
            message=stage.message,
            started_at=started_at,
            finished_at="",
        )

    def _mark_stage_succeeded(
        self,
        stage: PipelineStageView,
        finished_at: str,
    ) -> PipelineStageView:
        """标记阶段为 succeeded。"""

        return PipelineStageView(
            key=stage.key,
            title=stage.title,
            state=PipelineStageState.SUCCEEDED,
            message=stage.message or "完成",
            started_at=stage.started_at,
            finished_at=finished_at,
        )

    def _mark_stage_failed(
        self,
        stage: PipelineStageView,
        message: str,
        finished_at: str,
    ) -> PipelineStageView:
        """标记阶段为 failed。"""

        return PipelineStageView(
            key=stage.key,
            title=stage.title,
            state=PipelineStageState.FAILED,
            message=message,
            started_at=stage.started_at,
            finished_at=finished_at,
        )

    def _mark_stage_skipped(self, stage: PipelineStageView) -> PipelineStageView:
        """标记阶段为 skipped。"""

        return PipelineStageView(
            key=stage.key,
            title=stage.title,
            state=PipelineStageState.SKIPPED,
            message="v1 暂不支持",
            started_at="",
            finished_at="",
        )

    def _update_stage_message(
        self,
        stage: PipelineStageView,
        message: str,
    ) -> PipelineStageView:
        """更新阶段 message（保持其他字段不变）。"""

        return PipelineStageView(
            key=stage.key,
            title=stage.title,
            state=stage.state,
            message=message,
            started_at=stage.started_at,
            finished_at=stage.finished_at,
        )

    def _apply_download_event_message(
        self,
        stage: PipelineStageView,
        event_name: FinsProgressEventName,
        payload: object,
    ) -> PipelineStageView:
        """根据 download 事件更新阶段 message。"""

        if event_name == FinsProgressEventName.PIPELINE_STARTED:
            return self._update_stage_message(stage, "开始下载")
        if event_name == FinsProgressEventName.COMPANY_RESOLVED:
            return self._update_stage_message(stage, "公司信息已解析")
        if event_name == FinsProgressEventName.FILING_STARTED:
            filing_id = getattr(payload, "document_id", None)
            if filing_id:
                return self._update_stage_message(stage, f"开始下载 filing: {filing_id}")
        return stage

    def _apply_process_event_message(
        self,
        stage: PipelineStageView,
        event_name: FinsProgressEventName,
        payload: object,
    ) -> PipelineStageView:
        """根据 process 事件更新阶段 message。"""

        if event_name == FinsProgressEventName.DOCUMENT_STARTED:
            doc_id = getattr(payload, "document_id", None)
            if doc_id:
                return self._update_stage_message(stage, f"开始处理: {doc_id}")
        return stage

    def _extract_file_message(
        self,
        payload: object,
        prefix: str,
    ) -> str:
        """从 payload 提取文件名用于 message。"""

        name = getattr(payload, "name", None)
        if name:
            return f"{prefix}: {name}"
        return prefix

    def _mark_cancelled(self, current: PipelineProgressView) -> PipelineProgressView:
        """标记整体为 cancelled。"""

        now_iso = self._clock().isoformat()
        stages = list(current.stages)
        # 将当前活跃阶段标记为 failed（取消）
        active_key = current.active_stage_key
        if active_key:
            active_idx = _STAGE_KEYS.index(active_key)
            stages[active_idx] = self._mark_stage_failed(
                stages[active_idx],
                "用户取消",
                now_iso,
            )
        return self._build_view(current, stages, "", "cancelled", now_iso)

    def _mark_failed(
        self,
        current: PipelineProgressView,
        message: str,
    ) -> PipelineProgressView:
        """标记整体为 failed。"""

        now_iso = self._clock().isoformat()
        stages = list(current.stages)
        # 将当前活跃阶段标记为 failed
        active_key = current.active_stage_key
        if active_key:
            active_idx = _STAGE_KEYS.index(active_key)
            stages[active_idx] = self._mark_stage_failed(
                stages[active_idx],
                message,
                now_iso,
            )
        return self._build_view(current, stages, "", "failed", now_iso)

    def _build_view(
        self,
        current: PipelineProgressView,
        stages: list[PipelineStageView],
        active_stage_key: str,
        terminal_state: str,
        updated_at: str,
    ) -> PipelineProgressView:
        """构造新的 PipelineProgressView。"""

        return PipelineProgressView(
            ticker=current.ticker,
            run_id=current.run_id,
            session_id=current.session_id,
            stages=tuple(stages),
            active_stage_key=active_stage_key,
            terminal_state=terminal_state,
            updated_at=updated_at,
        )


__all__ = ["PipelineProgressProjector"]