"""Upload 流水线 REST 端点。

该路由封装 ``FinsService`` 与 ``HostAdminService`` 能力，向 UI 暴露统一上传入口：
- POST /api/upload/manual：触发 download 或 process 流水线
- POST /api/upload/files：上传本地财报文件
- POST /api/upload/process：触发解析与抽取阶段（手动触发下一阶段）
- POST /api/upload/analyze：触发维度分析阶段（手动触发下一阶段）
- GET /api/upload/progress/{run_id}：SSE 进度流（聚合 fins 事件）
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, Body, File, HTTPException, Path as FastApiPath, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dayu.contracts.events import AppEvent
from dayu.contracts.fins import (
    DownloadCommandPayload,
    FinsCommand,
    FinsCommandName,
    FinsEvent,
    FinsEventType,
    FinsProgressEventName,
    FinsResult,
    ProcessCommandPayload,
    UploadFilingsFromCommandPayload,
)
from dayu.services.contracts import FinsSubmitRequest, PipelineProgressView
from dayu.services.protocols import FinsServiceProtocol, HostAdminServiceProtocol, PortfolioBrowsingServiceProtocol
from dayu.services.pipeline_progress_projector import PipelineProgressProjector
from dayu.services.dimension_analysis_service import DimensionAnalysisService
from dayu.log import Log

_MODULE = "upload_routes"


# === 请求/响应模型（模块级别定义，避免 FastAPI ForwardRef 问题） ===

class ManualUploadRequest(BaseModel):
    """手动上传请求。

    v1 MVP 仅支持 ticker 触发 download 流水线。
    """

    ticker: str
    market: str = "US"
    form_types: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    overwrite: bool = False


class ManualUploadResponse(BaseModel):
    """手动上传响应。"""

    run_id: str
    session_id: str
    ticker: str


class FileUploadResponse(BaseModel):
    """文件上传响应。"""

    run_id: str
    session_id: str
    ticker: str
    files_received: int


class ProcessTriggerRequest(BaseModel):
    """触发process阶段请求。"""

    ticker: str
    session_id: str


class ProcessTriggerResponse(BaseModel):
    """触发process阶段响应。"""

    run_id: str
    session_id: str
    ticker: str


class AnalyzeTriggerRequest(BaseModel):
    """触发analyze阶段请求。"""

    ticker: str
    session_id: str
    document_id: str | None = None  # 可选，默认分析最新的processed document


class AnalyzeTriggerResponse(BaseModel):
    """触发analyze阶段响应。"""

    ticker: str
    document_id: str
    metrics_count: int
    summary: str
    insights: list[str]


def create_upload_router(
    fins_service: FinsServiceProtocol,
    host_admin_service: HostAdminServiceProtocol,
    portfolio_browsing_service: PortfolioBrowsingServiceProtocol | None = None,
) -> Any:
    """创建 upload 路由。

    Args:
        fins_service: 财报服务实例。
        host_admin_service: 宿主管理服务实例。

    Returns:
        FastAPI 路由对象。

    Raises:
        无。
    """

    router = APIRouter(prefix="/api/upload", tags=["upload"])

    # === SSE 辅助函数 ===

    async def _progress_generator(
        run_id: str,
        ticker: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """将 fins 事件流转换为聚合的 PipelineProgressView SSE 流。

        Args:
            run_id: 运行 ID。
            ticker: 股票代码。
            session_id: 会话 ID。

        Yields:
            SSE 文本片段。

        Raises:
            无。
        """

        projector = PipelineProgressProjector(
            ticker=ticker,
            run_id=run_id,
            session_id=session_id,
        )
        current = projector.initial()

        Log.info(f"SSE 连接建立: session_id={session_id}", module=_MODULE)

        # 订阅 session 事件流（因为 run_id 实际是 session_id）
        stream = host_admin_service.subscribe_session_events(session_id)

        # 发送初始状态
        Log.debug(f"SSE 发送初始状态: session_id={session_id}", module=_MODULE)
        yield f"data: {json.dumps(_view_to_dict(current), ensure_ascii=False)}\n\n"

        event_count = 0
        async for event in stream:
            event_count += 1
            # 从 PublishedRunEventProtocol 提取 payload
            payload = event.payload
            Log.debug(
                f"SSE 收到事件 #{event_count}: session_id={session_id}, payload_type={type(payload).__name__}",
                module=_MODULE,
            )
            if isinstance(payload, (FinsEvent, AppEvent)):
                updated = projector.apply(current, payload)
                if updated != current:
                    current = updated
                    Log.debug(
                        f"SSE 发送更新: session_id={session_id}, active_stage={current.active_stage_key}, terminal={current.terminal_state}",
                        module=_MODULE,
                    )
                    yield f"data: {json.dumps(_view_to_dict(current), ensure_ascii=False)}\n\n"

            # 终态后停止
            if current.terminal_state in ("succeeded", "failed", "cancelled"):
                Log.info(
                    f"SSE 流结束: session_id={session_id}, total_events={event_count}, terminal_state={current.terminal_state}",
                    module=_MODULE,
                )
                break

    def _view_to_dict(view: PipelineProgressView) -> dict[str, Any]:
        """将 PipelineProgressView 转为可序列化 dict。"""

        return {
            "ticker": view.ticker,
            "run_id": view.run_id,
            "session_id": view.session_id,
            "stages": [
                {
                    "key": stage.key,
                    "title": stage.title,
                    "state": stage.state.value,
                    "message": stage.message,
                    "started_at": stage.started_at,
                    "finished_at": stage.finished_at,
                }
                for stage in view.stages
            ],
            "active_stage_key": view.active_stage_key,
            "terminal_state": view.terminal_state,
            "updated_at": view.updated_at,
        }

    # === 后台任务驱动器 ===

    async def _drive_execution(execution: AsyncIterator[FinsEvent], session_id: str) -> None:
        """在后台驱动 Fins execution 流，确保事件发布到 event bus。

        Args:
            execution: Fins 流式 execution（异步生成器）。
            session_id: 会话 ID（用于日志）。

        Raises:
            无（错误仅记录日志）。
        """

        try:
            async for _event in execution:
                # 迭代 execution 驱动流水线执行
                # 事件已由 Host executor 发布到 event bus，无需额外处理
                pass
            Log.info(f"Fins 流水线完成: session_id={session_id}", module=_MODULE)
        except Exception as exc:
            Log.error(f"Fins 流水线异常: session_id={session_id}, error={exc}", module=_MODULE)

    # === 路由端点 ===

    @router.post("/manual", response_model=ManualUploadResponse, status_code=202)
    async def manual_upload(body: ManualUploadRequest = Body(...)) -> ManualUploadResponse:
        """触发 download 流水线。

        v1 MVP 优先实现 ticker → download 路径。
        """

        ticker = body.ticker.strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker 不能为空")

        # 构建 download 命令
        command = FinsCommand(
            name=FinsCommandName.DOWNLOAD,
            payload=DownloadCommandPayload(
                ticker=ticker,
                form_type=tuple(body.form_types) if body.form_types else (),
                start_date=body.start_date,
                end_date=body.end_date,
                overwrite=body.overwrite,
            ),
            stream=True,
        )

        # 提交到 fins 服务
        submission = fins_service.submit(FinsSubmitRequest(command=command))

        # 启动后台任务驱动 execution 流
        execution = submission.execution
        assert not isinstance(execution, FinsResult), "stream=True 应返回 AsyncIterator"
        asyncio.create_task(_drive_execution(execution, submission.session_id))

        return ManualUploadResponse(
            run_id=submission.session_id,  # 暂用 session_id 作为 run_id 标识
            session_id=submission.session_id,
            ticker=ticker,
        )

    @router.post("/files", response_model=FileUploadResponse, status_code=202)
    async def upload_files(
        ticker: str = Query(description="股票代码"),
        files: list[UploadFile] = File(default=None, description="财报文件列表"),  # type: ignore[assignment]
    ) -> FileUploadResponse:
        """上传本地财报文件并触发处理流水线。

        Args:
            ticker: 股票代码。
            files: 上传的财报文件列表。

        Returns:
            包含 run_id 的响应。

        Raises:
            HTTPException: ticker 为空或文件列表为空时抛出。
        """

        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise HTTPException(status_code=400, detail="ticker 不能为空")

        if not files:
            raise HTTPException(status_code=400, detail="文件列表不能为空")

        # 保存上传文件到临时目录
        temp_dir = Path(tempfile.mkdtemp(prefix=f"upload_{normalized_ticker}_"))
        saved_files: list[Path] = []

        try:
            for upload_file in files:
                if not upload_file.filename:
                    continue
                # 检查文件扩展名
                from dayu.fins.upload_recognition import SUPPORTED_UPLOAD_FROM_SUFFIXES
                suffix = Path(upload_file.filename).suffix.lower()
                if suffix not in SUPPORTED_UPLOAD_FROM_SUFFIXES:
                    continue
                target_path = temp_dir / upload_file.filename
                with target_path.open("wb") as f:
                    shutil.copyfileobj(upload_file.file, f)
                saved_files.append(target_path)

            if not saved_files:
                raise HTTPException(status_code=400, detail="没有有效的财报文件")

            # 构建 upload_filings_from 命令（支持自动识别财期和类型）
            command = FinsCommand(
                name=FinsCommandName.UPLOAD_FILINGS_FROM,
                payload=UploadFilingsFromCommandPayload(
                    ticker=normalized_ticker,
                    source_dir=temp_dir,
                    infer=True,  # 自动识别财期和类型
                    overwrite=False,
                ),
                stream=True,
            )

            # 提交到 fins 服务
            submission = fins_service.submit(FinsSubmitRequest(command=command))

            # 启动后台任务驱动 execution 流
            execution = submission.execution
            assert not isinstance(execution, FinsResult), "stream=True 应返回 AsyncIterator"
            asyncio.create_task(_drive_execution(execution, submission.session_id))

            return FileUploadResponse(
                run_id=submission.session_id,
                session_id=submission.session_id,
                ticker=normalized_ticker,
                files_received=len(saved_files),
            )
        finally:
            # 注意：不清理临时目录，因为 upload_filings_from 流水线需要读取文件
            # 清理由 fins 流水线完成后处理
            pass

    @router.get("/progress/{run_id}")
    async def upload_progress(
        run_id: str = FastApiPath(description="运行 ID"),
        ticker: str = Query(description="股票代码"),
        session_id: str = Query(description="会话 ID"),
    ) -> StreamingResponse:
        """订阅 upload 进度 SSE 流。"""

        return StreamingResponse(
            _progress_generator(run_id, ticker, session_id),
            media_type="text/event-stream",
        )

    # === 分阶段触发端点 ===

    @router.post("/process", response_model=ProcessTriggerResponse, status_code=202)
    async def trigger_process(body: ProcessTriggerRequest = Body(...)) -> ProcessTriggerResponse:
        """手动触发解析与抽取阶段。

        在download完成后，用户可点击触发process阶段。
        """

        ticker = body.ticker.strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker 不能为空")

        Log.info(f"触发process阶段: ticker={ticker}, session_id={body.session_id}", module=_MODULE)

        # 构建process命令（处理该ticker下所有已下载的filings）
        command = FinsCommand(
            name=FinsCommandName.PROCESS,
            payload=ProcessCommandPayload(
                ticker=ticker,
                document_ids=(),  # 空表示处理所有未处理的
                overwrite=False,
            ),
            stream=True,
        )

        submission = fins_service.submit(FinsSubmitRequest(command=command))

        execution = submission.execution
        assert not isinstance(execution, FinsResult), "stream=True 应返回 AsyncIterator"
        asyncio.create_task(_drive_execution(execution, submission.session_id))

        return ProcessTriggerResponse(
            run_id=submission.session_id,
            session_id=submission.session_id,
            ticker=ticker,
        )

    @router.post("/analyze", response_model=AnalyzeTriggerResponse, status_code=200)
    async def trigger_analyze(body: AnalyzeTriggerRequest = Body(...)) -> AnalyzeTriggerResponse:
        """手动触发维度分析阶段。

        在process完成后，用户可点击触发analyze阶段。
        分析已处理的财报数据，提取财务指标并生成洞察。
        """

        ticker = body.ticker.strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker 不能为空")

        if portfolio_browsing_service is None:
            raise HTTPException(status_code=500, detail="portfolio browsing service 未配置")

        Log.info(f"触发analyze阶段: ticker={ticker}, document_id={body.document_id or 'auto'}", module=_MODULE)

        # 获取最新的processed document
        if body.document_id:
            document_id = body.document_id
        else:
            # 获取最新处理的文档
            processed_list = portfolio_browsing_service.list_processed_artifacts(ticker)
            if not processed_list:
                raise HTTPException(status_code=404, detail="未找到已处理的财报数据，请先执行解析与抽取阶段")
            document_id = processed_list[0].document_id

        # 获取processed数据（包含XBRL facts）
        processed_view = portfolio_browsing_service.get_filing_processed(ticker, document_id)

        # 执行维度分析
        analysis_service = DimensionAnalysisService()
        result = analysis_service.analyze(
            ticker=ticker,
            document_id=document_id,
            processed_data={
                "xbrl_facts": [fact.__dict__ for fact in processed_view.xbrl_facts],
            },
        )

        return AnalyzeTriggerResponse(
            ticker=ticker,
            document_id=document_id,
            metrics_count=len(result.metrics),
            summary=result.summary,
            insights=list(result.insights),
        )

    return router


__all__ = ["create_upload_router"]