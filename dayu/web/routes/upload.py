"""Upload 流水线 REST 端点。

该路由封装 ``FinsService`` 与 ``HostAdminService`` 能力，向 UI 暴露统一上传入口：
- POST /api/upload/manual：触发 download 或 process 流水线
- POST /api/upload/files：上传本地财报文件
- GET /api/upload/progress/{run_id}：SSE 进度流（聚合 fins 事件）
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, HTTPException, Path as FastApiPath, Query, UploadFile
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
    UploadFilingsFromCommandPayload,
)
from dayu.services.contracts import FinsSubmitRequest, PipelineProgressView
from dayu.services.protocols import FinsServiceProtocol, HostAdminServiceProtocol
from dayu.services.pipeline_progress_projector import PipelineProgressProjector


def create_upload_router(
    fins_service: FinsServiceProtocol,
    host_admin_service: HostAdminServiceProtocol,
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

    # === 请求/响应模型 ===

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

        # 订阅 run 事件流
        stream = host_admin_service.subscribe_run_events(run_id)

        # 发送初始状态
        yield f"data: {json.dumps(_view_to_dict(current), ensure_ascii=False)}\n\n"

        async for event in stream:
            # 从 PublishedRunEventProtocol 提取 payload
            payload = event.payload
            if isinstance(payload, (FinsEvent, AppEvent)):
                updated = projector.apply(current, payload)
                if updated != current:
                    current = updated
                    yield f"data: {json.dumps(_view_to_dict(current), ensure_ascii=False)}\n\n"

            # 终态后停止
            if current.terminal_state in ("succeeded", "failed", "cancelled"):
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

    # === 路由端点 ===

    @router.post("/manual", response_model=ManualUploadResponse, status_code=202)
    async def manual_upload(body: ManualUploadRequest) -> ManualUploadResponse:
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

    return router


__all__ = ["create_upload_router"]