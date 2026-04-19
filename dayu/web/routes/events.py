"""SSE 事件流端点。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from typing import Any, cast

from dayu.contracts.events import PublishedRunEventProtocol
from dayu.services.protocols import HostAdminServiceProtocol


from dayu.log import Log

_MODULE = "WEB.EVENTS"


def _normalize_event_payload(payload: object) -> object:
    """把事件负载规范化为可 JSON 序列化结构。"""

    if not isinstance(payload, type) and is_dataclass(payload):
        return asdict(cast(Any, payload))
    return payload


def _normalize_event_discriminator(value: object) -> str:
    """把事件判别字段规范化为稳定字符串。"""

    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _build_sse_event_payload(event: PublishedRunEventProtocol) -> dict[str, object]:
    """构造稳定 SSE 事件包络。

    Args:
        event: 宿主管理面透传的运行事件。

    Returns:
        可直接 JSON 序列化的 SSE 事件数据。

    Raises:
        无。
    """

    payload: dict[str, object] = {
        "type": _normalize_event_discriminator(event.type),
        "payload": _normalize_event_payload(event.payload),
    }
    command = getattr(event, "command", None)
    if command is not None:
        payload["command"] = _normalize_event_discriminator(command)
    return payload


def create_events_router(host_admin_service: HostAdminServiceProtocol):
    """创建 SSE 事件流路由。

    Args:
        无。

    Returns:
        FastAPI 路由对象。

    Raises:
        无。
    """

    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/api", tags=["events"])

    # 批量合并 delta 事件的配置
    _DELTA_BATCH_SIZE = 32  # 每 32 个 delta 事件合并一次
    _DELTA_BATCH_TIMEOUT_MS = 100  # 或每 100ms 发送一次

    async def _sse_generator(stream):
        """将事件流转为 SSE 文本流，合并 delta 事件减少发送频率。

        Args:
            stream: 应用层事件流（Subscription 对象）。

        Yields:
            SSE 文本片段。

        Raises:
            无。
        """

        Log.info(
            f"SSE._sse_generator: generator 启动, 等待第一个事件",
            module=_MODULE,
        )

        delta_buffer: list[str] = []
        delta_type: str | None = None
        last_flush_time = asyncio.get_event_loop().time()
        event_count = 0

        try:
            # 首先尝试获取第一个事件，确认 stream 正常工作
            Log.info(
                f"SSE._sse_generator: 开始 async for 迭代",
                module=_MODULE,
            )

            async for event in stream:
                event_count += 1
                event_type = _normalize_event_discriminator(event.type)

                Log.info(
                    f"SSE._sse_generator: 收到事件 #{event_count}, type={event_type}",
                    module=_MODULE,
                )

                # delta 类型事件（content_delta, reasoning_delta）合并发送
                if event_type in ("content_delta", "reasoning_delta"):
                    delta_text = str(event.payload or "")
                    if delta_text:
                        delta_buffer.append(delta_text)
                        # 优先使用 content_delta，因为 reasoning_delta 通常是思考内容
                        if delta_type is None or event_type == "content_delta":
                            delta_type = event_type

                        # 达到批量大小或超时，发送合并事件
                        now = asyncio.get_event_loop().time()
                        should_flush = (
                            len(delta_buffer) >= _DELTA_BATCH_SIZE or
                            (now - last_flush_time) * 1000 >= _DELTA_BATCH_TIMEOUT_MS
                        )

                        if should_flush and delta_buffer:
                            merged_text = "".join(delta_buffer)
                            data = json.dumps({
                                "type": delta_type or "content_delta",
                                "payload": merged_text,
                            }, ensure_ascii=False)
                            yield f"data: {data}\n\n"
                            delta_buffer = []
                            delta_type = None
                            last_flush_time = now
                else:
                    # 非 delta 事件，先发送已缓冲的 delta，然后发送当前事件
                    if delta_buffer:
                        merged_text = "".join(delta_buffer)
                        data = json.dumps({
                            "type": delta_type or "content_delta",
                            "payload": merged_text,
                        }, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                        delta_buffer = []
                        delta_type = None
                        last_flush_time = asyncio.get_event_loop().time()

                    # 发送当前事件（保持原有格式）
                    data = json.dumps(_build_sse_event_payload(event), ensure_ascii=False)
                    yield f"data: {data}\n\n"

            # 流结束时，发送剩余的 delta
            if delta_buffer:
                merged_text = "".join(delta_buffer)
                data = json.dumps({
                    "type": delta_type or "content_delta",
                    "payload": merged_text,
                }, ensure_ascii=False)
                yield f"data: {data}\n\n"

            Log.info(
                f"SSE._sse_generator: 流结束, total_events={event_count}",
                module=_MODULE,
            )

        except asyncio.CancelledError:
            Log.info(
                f"SSE._sse_generator: 被取消, total_events={event_count}",
                module=_MODULE,
            )
            raise

    @router.get("/runs/{run_id}/events")
    async def run_events(run_id: str):
        """订阅单个 run 的实时事件。"""

        try:
            stream = host_admin_service.subscribe_run_events(run_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        return StreamingResponse(
            _sse_generator(stream),
            media_type="text/event-stream",
        )

    @router.get("/sessions/{session_id}/events")
    async def session_events(session_id: str):
        """订阅 session 下所有 run 的实时事件。"""

        Log.info(
            f"events.session_events: 收到 SSE 连接请求, session_id={session_id}",
            module=_MODULE,
        )

        try:
            stream = host_admin_service.subscribe_session_events(session_id)
        except RuntimeError as exc:
            Log.warning(
                f"events.session_events: 订阅失败, session_id={session_id}, error={str(exc)}",
                module=_MODULE,
            )
            raise HTTPException(status_code=501, detail=str(exc)) from exc

        Log.info(
            f"events.session_events: SSE 连接建立, 开始生成事件流, session_id={session_id}",
            module=_MODULE,
        )

        return StreamingResponse(
            _sse_generator(stream),
            media_type="text/event-stream",
        )

    return router


__all__ = ["create_events_router"]