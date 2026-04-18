"""Upload 路由测试。

按 §4.6 设计要求，覆盖：
- 路由端点注册
- 路由配置验证
"""

from __future__ import annotations

from typing import Any, AsyncIterator, cast

import pytest

from dayu.web.routes.upload import create_upload_router


async def _empty_event_stream() -> AsyncIterator[Any]:
    """返回空事件流。"""
    if False:
        yield cast(Any, None)


@pytest.mark.unit
def test_upload_router_registers_all_endpoints() -> None:
    """验证 upload 路由注册全部 3 个端点。"""

    class _FakeFinsService:
        def submit(self, request: Any) -> Any:
            return cast(Any, None)

    class _FakeHostService:
        def subscribe_run_events(self, run_id: str) -> Any:
            return _empty_event_stream()

    router = create_upload_router(
        cast(Any, _FakeFinsService()),
        cast(Any, _FakeHostService()),
    )
    assert router.prefix == "/api/upload"

    expected_paths = [
        "/api/upload/manual",
        "/api/upload/files",
        "/api/upload/progress/{run_id}",
    ]

    registered_paths = [r.path for r in router.routes if hasattr(r, 'path')]
    for expected in expected_paths:
        assert expected in registered_paths


@pytest.mark.unit
def test_manual_upload_route_is_post() -> None:
    """验证手动上传路由为 POST 方法。"""

    class _FakeFinsService:
        def submit(self, request: Any) -> Any:
            return cast(Any, None)

    class _FakeHostService:
        def subscribe_run_events(self, run_id: str) -> Any:
            return _empty_event_stream()

    router = create_upload_router(
        cast(Any, _FakeFinsService()),
        cast(Any, _FakeHostService()),
    )

    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/upload/manual":
            assert "POST" in route.methods
            break


@pytest.mark.unit
def test_files_upload_route_is_post() -> None:
    """验证文件上传路由为 POST 方法。"""

    class _FakeFinsService:
        def submit(self, request: Any) -> Any:
            return cast(Any, None)

    class _FakeHostService:
        def subscribe_run_events(self, run_id: str) -> Any:
            return _empty_event_stream()

    router = create_upload_router(
        cast(Any, _FakeFinsService()),
        cast(Any, _FakeHostService()),
    )

    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/upload/files":
            assert "POST" in route.methods
            break


@pytest.mark.unit
def test_progress_route_is_get() -> None:
    """验证进度路由为 GET 方法。"""

    class _FakeFinsService:
        def submit(self, request: Any) -> Any:
            return cast(Any, None)

    class _FakeHostService:
        def subscribe_run_events(self, run_id: str) -> Any:
            return _empty_event_stream()

    router = create_upload_router(
        cast(Any, _FakeFinsService()),
        cast(Any, _FakeHostService()),
    )

    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/upload/progress/{run_id}":
            assert "GET" in route.methods
            break


@pytest.mark.unit
def test_manual_upload_route_status_code() -> None:
    """验证手动上传路由返回 202 状态码。"""

    class _FakeFinsService:
        def submit(self, request: Any) -> Any:
            return cast(Any, None)

    class _FakeHostService:
        def subscribe_run_events(self, run_id: str) -> Any:
            return _empty_event_stream()

    router = create_upload_router(
        cast(Any, _FakeFinsService()),
        cast(Any, _FakeHostService()),
    )

    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/upload/manual":
            # status_code 在 route.status_code 属性
            if hasattr(route, 'status_code'):
                assert route.status_code == 202
            break


__all__ = [
    "test_upload_router_registers_all_endpoints",
    "test_manual_upload_route_is_post",
    "test_files_upload_route_is_post",
    "test_progress_route_is_get",
    "test_manual_upload_route_status_code",
]