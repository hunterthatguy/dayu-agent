"""PipelineProgressProjector 单元测试。

测试覆盖 SSE 事件 → PipelineProgressView 状态折叠场景：
- initial() 全 pending
- download 启动 → resolve+download 状态正确
- download 失败 → terminal_state=failed
- download 完成 + process 启动 → 状态串接
- cancelled 事件 → terminal_state=cancelled
- 未知事件 → 状态不变（apply 幂等）
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import pytest

from dayu.contracts.events import AppEvent, AppEventType
from dayu.contracts.fins import (
    FinsCommandName,
    FinsEvent,
    FinsEventType,
    FinsProgressEventName,
    DownloadProgressPayload,
    ProcessProgressPayload,
)
from dayu.services.contracts import PipelineProgressView, PipelineStageState
from dayu.services.pipeline_progress_projector import PipelineProgressProjector


def _fixed_clock(timestamp: str) -> Callable[[], datetime]:
    """返回固定时间的 clock 函数。"""

    parsed = datetime.fromisoformat(timestamp)
    return lambda: parsed


def _build_projector(
    ticker: str = "AAPL",
    run_id: str = "run_001",
    session_id: str = "sess_001",
    clock: Callable[[], datetime] | None = None,
) -> PipelineProgressProjector:
    """构造 projector 实例。"""

    return PipelineProgressProjector(
        ticker=ticker,
        run_id=run_id,
        session_id=session_id,
        _clock=clock or _fixed_clock("2026-04-18T10:00:00+00:00"),
    )


def _make_download_progress(
    event_type: FinsProgressEventName,
    ticker: str = "AAPL",
    document_id: str | None = None,
    message: str | None = None,
) -> DownloadProgressPayload:
    """构造 download progress payload。"""

    return DownloadProgressPayload(
        event_type=event_type,
        ticker=ticker,
        document_id=document_id,
        message=message,
    )


def _make_process_progress(
    event_type: FinsProgressEventName,
    ticker: str = "AAPL",
    document_id: str | None = None,
) -> ProcessProgressPayload:
    """构造 process progress payload。"""

    return ProcessProgressPayload(
        event_type=event_type,
        ticker=ticker,
        document_id=document_id,
    )


def test_initial_all_stages_pending() -> None:
    """initial() 应返回全阶段 pending 的视图。"""

    projector = _build_projector()
    view = projector.initial()

    assert view.ticker == "AAPL"
    assert view.run_id == "run_001"
    assert view.session_id == "sess_001"
    assert view.terminal_state == "running"
    assert view.active_stage_key == "resolve"
    assert len(view.stages) == 4
    for stage in view.stages:
        assert stage.state == PipelineStageState.PENDING
        assert stage.started_at == ""
        assert stage.finished_at == ""


def test_download_started_advances_resolve_and_download() -> None:
    """download 启动事件应推进 resolve 为 succeeded，download 为 running。"""

    projector = _build_projector(clock=_fixed_clock("2026-04-18T10:01:00+00:00"))
    current = projector.initial()

    event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
    )

    updated = projector.apply(current, event)

    resolve_stage = updated.stages[0]
    assert resolve_stage.state == PipelineStageState.SUCCEEDED
    assert resolve_stage.finished_at == "2026-04-18T10:01:00+00:00"

    download_stage = updated.stages[1]
    assert download_stage.state == PipelineStageState.RUNNING
    assert download_stage.started_at == "2026-04-18T10:01:00+00:00"
    assert download_stage.message == "开始下载"

    assert updated.active_stage_key == "download"


def test_download_failed_sets_terminal_state_failed() -> None:
    """download 失败事件应设置 terminal_state 为 failed。"""

    projector = _build_projector(clock=_fixed_clock("2026-04-18T10:02:00+00:00"))
    current = projector.initial()

    # 先启动 download
    start_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.FILING_STARTED),
    )
    current = projector.apply(current, start_event)

    # 然后失败
    fail_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.FILING_FAILED),
    )

    updated = projector.apply(current, fail_event)

    download_stage = updated.stages[1]
    assert download_stage.state == PipelineStageState.FAILED
    assert download_stage.message == "下载失败"

    assert updated.terminal_state == "failed"
    assert updated.active_stage_key == ""


def test_download_completed_then_process_started() -> None:
    """download 完成 + process 启动应正确串接状态。"""

    clock = _fixed_clock("2026-04-18T10:03:00+00:00")
    projector = _build_projector(clock=clock)
    current = projector.initial()

    # 启动 download
    start_download = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
    )
    current = projector.apply(current, start_download)

    # 完成 download
    complete_download = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_COMPLETED),
    )
    current = projector.apply(current, complete_download)

    # 启动 process
    start_process = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.PROCESS,
        payload=_make_process_progress(
            FinsProgressEventName.DOCUMENT_STARTED,
            document_id="fil_001",
        ),
    )

    updated = projector.apply(current, start_process)

    download_stage = updated.stages[1]
    assert download_stage.state == PipelineStageState.SUCCEEDED

    process_stage = updated.stages[2]
    assert process_stage.state == PipelineStageState.RUNNING
    assert process_stage.started_at == "2026-04-18T10:03:00+00:00"
    assert "fil_001" in process_stage.message

    assert updated.active_stage_key == "process"


def test_cancelled_event_sets_terminal_state_cancelled() -> None:
    """cancelled AppEvent 应设置 terminal_state 为 cancelled。"""

    projector = _build_projector(clock=_fixed_clock("2026-04-18T10:04:00+00:00"))
    current = projector.initial()

    # 先启动 download
    start_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
    )
    current = projector.apply(current, start_event)

    # 用户取消
    cancel_event = AppEvent(type=AppEventType.CANCELLED, payload=None)

    updated = projector.apply(current, cancel_event)

    assert updated.terminal_state == "cancelled"
    assert updated.stages[1].state == PipelineStageState.FAILED
    assert updated.stages[1].message == "用户取消"


def test_unknown_event_returns_same_view() -> None:
    """未知事件应返回原视图（apply 幂等）。"""

    projector = _build_projector()
    current = projector.initial()

    # 使用 RESULT 类型的事件（不在 projector 处理范围）
    from dayu.contracts.fins import DownloadResultData

    unknown_event = FinsEvent(
        type=FinsEventType.RESULT,
        command=FinsCommandName.DOWNLOAD,
        payload=DownloadResultData(
            pipeline="download",
            status="completed",
            ticker="AAPL",
        ),
    )

    updated = projector.apply(current, unknown_event)

    assert updated == current


def test_process_completed_sets_analyze_skipped() -> None:
    """process 完成（PIPELINE_COMPLETED）应设置 analyze 为 skipped，整体 succeeded。"""

    clock = _fixed_clock("2026-04-18T10:05:00+00:00")
    projector = _build_projector(clock=clock)
    current = projector.initial()

    # 启动并完成 download
    current = projector.apply(
        current,
        FinsEvent(
            type=FinsEventType.PROGRESS,
            command=FinsCommandName.DOWNLOAD,
            payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
        ),
    )
    current = projector.apply(
        current,
        FinsEvent(
            type=FinsEventType.PROGRESS,
            command=FinsCommandName.DOWNLOAD,
            payload=_make_download_progress(FinsProgressEventName.PIPELINE_COMPLETED),
        ),
    )

    # 启动 process
    current = projector.apply(
        current,
        FinsEvent(
            type=FinsEventType.PROGRESS,
            command=FinsCommandName.PROCESS,
            payload=_make_process_progress(
                FinsProgressEventName.DOCUMENT_STARTED,
                document_id="fil_001",
            ),
        ),
    )

    # 完成 process pipeline
    complete_process = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.PROCESS,
        payload=_make_process_progress(FinsProgressEventName.PIPELINE_COMPLETED),
    )

    updated = projector.apply(current, complete_process)

    process_stage = updated.stages[2]
    assert process_stage.state == PipelineStageState.SUCCEEDED

    analyze_stage = updated.stages[3]
    assert analyze_stage.state == PipelineStageState.SKIPPED
    assert analyze_stage.message == "v1 暂不支持"

    assert updated.terminal_state == "succeeded"


def test_error_event_sets_terminal_state_failed() -> None:
    """ERROR AppEvent 应设置 terminal_state 为 failed。"""

    projector = _build_projector(clock=_fixed_clock("2026-04-18T10:06:00+00:00"))
    current = projector.initial()

    # 先启动 download
    start_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
    )
    current = projector.apply(current, start_event)

    # 发生错误
    error_event = AppEvent(type=AppEventType.ERROR, payload="网络连接失败")

    updated = projector.apply(current, error_event)

    assert updated.terminal_state == "failed"
    assert updated.stages[1].state == PipelineStageState.FAILED


def test_file_downloaded_updates_download_message() -> None:
    """FILE_DOWNLOADED 事件应更新 download 阶段的 message。"""

    projector = _build_projector(clock=_fixed_clock("2026-04-18T10:07:00+00:00"))
    current = projector.initial()

    # 启动 download
    start_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=_make_download_progress(FinsProgressEventName.PIPELINE_STARTED),
    )
    current = projector.apply(current, start_event)

    # 下载单个文件（使用 name 字段）
    file_event = FinsEvent(
        type=FinsEventType.PROGRESS,
        command=FinsCommandName.DOWNLOAD,
        payload=DownloadProgressPayload(
            event_type=FinsProgressEventName.FILE_DOWNLOADED,
            ticker="AAPL",
            name="aapl.htm",
        ),
    )

    updated = projector.apply(current, file_event)

    assert updated.stages[1].state == PipelineStageState.RUNNING
    assert "aapl.htm" in updated.stages[1].message