"""RunEventBus 进程内多消费者事件总线。

适用于 Web / WeChat / GUI 等长驻进程。CLI 单命令进程不需要。
"""

from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator

from dayu.host.protocols import EventSubscription, RunEventBusProtocol, RunRegistryProtocol
from dayu.contracts.events import PublishedRunEventProtocol
from dayu.log import Log

MODULE = "HOST.EVENT_BUS"

# 每个 subscriber 的队列默认容量（增大以支持 thinking 模式的大量 reasoning_delta 事件）
_DEFAULT_QUEUE_MAX_SIZE = 4096


def _normalize_event_discriminator(value: object) -> str:
    """把事件判别字段规范化为稳定字符串。"""

    from enum import Enum

    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


class _Subscription:
    """单个订阅者的内部实现。"""

    def __init__(
        self,
        *,
        run_id: str | None,
        session_id: str | None,
        max_size: int = _DEFAULT_QUEUE_MAX_SIZE,
    ) -> None:
        """初始化 Subscription。

        Args:
            run_id: 按 run 过滤（精确匹配），None 表示不过滤。
            session_id: 按 session 过滤，None 表示不过滤。
            max_size: 队列最大容量。
        """

        self._run_id = run_id
        self._session_id = session_id
        self._queue: asyncio.Queue[PublishedRunEventProtocol | None] = asyncio.Queue(maxsize=max_size)
        self._closed = False

    @property
    def run_id(self) -> str | None:
        """返回过滤用的 run_id。"""

        return self._run_id

    @property
    def session_id(self) -> str | None:
        """返回过滤用的 session_id。"""

        return self._session_id

    @property
    def is_closed(self) -> bool:
        """返回订阅是否已关闭。"""

        return self._closed

    def close(self) -> None:
        """关闭订阅，向队列发送终止信号。"""

        if self._closed:
            return
        self._closed = True
        # 非阻塞放入 sentinel
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def try_put(self, event: PublishedRunEventProtocol) -> bool:
        """尝试向队列放入事件。

        Args:
            event: 应用事件。

        Returns:
            True 如果成功放入，False 如果队列已满（慢消费者）。
        """

        if self._closed:
            Log.debug(f"Subscription.try_put: 已关闭，跳过", module=MODULE)
            return False
        try:
            self._queue.put_nowait(event)
            Log.debug(f"Subscription.try_put: 成功放入事件，queue_size={self._queue.qsize()}", module=MODULE)
            return True
        except asyncio.QueueFull:
            # 慢消费者：丢弃最旧的，放入新的
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
            Log.warning(
                f"事件队列溢出，丢弃旧事件: session_id={self._session_id}, queue_size={self._queue.maxsize}",
                module=MODULE,
            )
            return False

    async def __aiter__(self) -> AsyncIterator[PublishedRunEventProtocol]:
        """异步迭代订阅事件。"""

        Log.info(
            f"Subscription.__aiter__: 开始迭代, session_id={self._session_id}, queue_size={self._queue.qsize()}",
            module=MODULE,
        )
        event_count = 0
        try:
            while True:
                # 使用超时避免客户端断开后无限等待
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # 30秒无事件，发送心跳保持连接
                    Log.info(
                        f"Subscription.__aiter__: 30s 无事件（心跳）, session_id={self._session_id}, consumed={event_count}",
                        module=MODULE,
                    )
                    continue

                if event is None:
                    # sentinel 表示订阅已关闭
                    Log.info(
                        f"Subscription.__aiter__: 收到 sentinel 结束, session_id={self._session_id}, consumed={event_count}",
                        module=MODULE,
                    )
                    break
                event_count += 1
                event_type = _normalize_event_discriminator(event.type)
                Log.info(
                    f"Subscription.__aiter__: yield #{event_count}, type={event_type}, session_id={self._session_id}",
                    module=MODULE,
                )
                yield event
        except asyncio.CancelledError:
            Log.info(
                f"Subscription.__aiter__: 被取消, session_id={self._session_id}, consumed={event_count}",
                module=MODULE,
            )
            raise


class AsyncQueueEventBus(RunEventBusProtocol):
    """基于 asyncio.Queue 的进程内多消费者事件总线。

    每个 subscriber 持有独立 queue，publish 时 fan-out 到所有匹配的 subscriber。
    """

    def __init__(
        self,
        run_registry: RunRegistryProtocol | None = None,
    ) -> None:
        """初始化 EventBus。

        Args:
            run_registry: 用于解析 run→session 关系（session_id 过滤时需要）。
        """

        self._run_registry = run_registry
        self._subscriptions: list[_Subscription] = []
        self._lock = threading.Lock()

    def publish(self, run_id: str, event: PublishedRunEventProtocol) -> None:
        """发布事件到指定 run 的所有匹配订阅者。"""

        with self._lock:
            subs = list(self._subscriptions)

        event_type = _normalize_event_discriminator(event.type)
        Log.info(
            f"EventBus.publish: 收到事件, run_id={run_id}, event_type={event_type}, total_subs={len(subs)}",
            module=MODULE,
        )

        session_id: str | None = None
        session_id_resolved = False
        matched_count = 0

        for sub in subs:
            if sub.is_closed:
                Log.debug(f"EventBus.publish: sub closed, skipping", module=MODULE)
                continue

            # 精确 run_id 匹配
            if sub.run_id is not None and sub.run_id != run_id:
                Log.debug(
                    f"EventBus.publish: run_id mismatch, sub.run_id={sub.run_id}, event.run_id={run_id}",
                    module=MODULE,
                )
                continue

            # session_id 匹配：需要通过 RunRegistry 解析
            if sub.session_id is not None:
                if not session_id_resolved:
                    session_id = self._resolve_session_id(run_id)
                    session_id_resolved = True
                if sub.session_id != session_id:
                    Log.info(
                        f"EventBus.publish: session不匹配, sub.session={sub.session_id}, resolved_session={session_id or 'None'}, run_id={run_id}",
                        module=MODULE,
                    )
                    continue

            matched_count += 1
            success = sub.try_put(event)
            Log.info(
                f"EventBus.publish: 事件放入队列成功, sub.session={sub.session_id}, matched_count={matched_count}",
                module=MODULE,
            )

        if matched_count == 0:
            Log.warning(
                f"EventBus.publish: 无匹配订阅者! run_id={run_id}, event_type={event_type}, total_subs={len(subs)}, resolved_session={session_id or '未解析'}",
                module=MODULE,
            )
        else:
            Log.info(
                f"EventBus.publish: 发布完成, run_id={run_id}, matched_subs={matched_count}",
                module=MODULE,
            )

    def subscribe(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> EventSubscription:
        """创建事件订阅。"""

        sub = _Subscription(run_id=run_id, session_id=session_id)
        with self._lock:
            self._subscriptions.append(sub)
            total = len(self._subscriptions)
        Log.info(
            f"EventBus.subscribe: 创建新订阅, session_id={session_id or 'None'}, run_id={run_id or 'None'}, total_subs={total}",
            module=MODULE,
        )
        return sub  # _Subscription 结构匹配 EventSubscription 协议

    def _cleanup_closed(self) -> None:
        """清理已关闭的订阅（内部维护用）。"""

        with self._lock:
            self._subscriptions = [s for s in self._subscriptions if not s.is_closed]

    def _resolve_session_id(self, run_id: str) -> str | None:
        """通过 RunRegistry 解析 run 所属 session_id。

        Args:
            run_id: 目标 run ID。

        Returns:
            关联的 session_id 或 None。
        """

        if self._run_registry is None:
            Log.warning(
                f"EventBus._resolve_session_id: run_registry 为 None! 无法解析 run_id={run_id}",
                module=MODULE,
            )
            return None
        run = self._run_registry.get_run(run_id)
        if run is None:
            Log.warning(
                f"EventBus._resolve_session_id: run_id={run_id} 不存在于 registry!",
                module=MODULE,
            )
            return None
        session_id = run.session_id
        Log.info(
            f"EventBus._resolve_session_id: 解析成功, run_id={run_id} -> session_id={session_id or 'None'}",
            module=MODULE,
        )
        return session_id


__all__ = ["AsyncQueueEventBus"]
