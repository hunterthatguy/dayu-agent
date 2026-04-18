"""Portfolio 路由测试。

按 §4.6 设计要求，覆盖：
- 路由端点注册
- handler 逻辑验证

遵循 test_web_routes.py 的同步测试模式。
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from dayu.web.routes.portfolio import create_portfolio_router


@pytest.mark.unit
def test_portfolio_router_registers_all_endpoints() -> None:
    """验证 portfolio 路由注册全部 7 个端点。"""

    class _FakeService:
        def list_companies(self) -> list[Any]:
            return []
        def list_filings(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_filing_detail(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def get_filing_processed(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def list_processed_artifacts(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_portfolio_health(self, ticker: str) -> Any:
            return object()
        def read_filing_file(self, ticker: str, document_id: str, filename: str) -> Any:
            raise FileNotFoundError()

    router = create_portfolio_router(cast(Any, _FakeService()))
    assert router.prefix == "/api/portfolio"

    expected_paths = [
        "/api/portfolio/companies",
        "/api/portfolio/companies/{ticker}/filings",
        "/api/portfolio/companies/{ticker}/filings/{document_id}",
        "/api/portfolio/companies/{ticker}/filings/{document_id}/processed",
        "/api/portfolio/companies/{ticker}/processed",
        "/api/portfolio/companies/{ticker}/health",
        "/api/portfolio/companies/{ticker}/filings/{document_id}/files/{filename}",
    ]

    registered_paths = [r.path for r in router.routes if hasattr(r, 'path')]
    for expected in expected_paths:
        assert expected in registered_paths


@pytest.mark.unit
def test_list_companies_route_method() -> None:
    """验证 list_companies 路由方法为 GET。"""

    class _FakeService:
        def list_companies(self) -> list[Any]:
            return []
        def list_filings(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_filing_detail(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def get_filing_processed(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def list_processed_artifacts(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_portfolio_health(self, ticker: str) -> Any:
            return object()
        def read_filing_file(self, ticker: str, document_id: str, filename: str) -> Any:
            raise FileNotFoundError()

    router = create_portfolio_router(cast(Any, _FakeService()))

    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/portfolio/companies":
            assert "GET" in route.methods
            break


@pytest.mark.unit
def test_filing_detail_route_exists() -> None:
    """验证 filing 详情路由存在。"""

    class _FakeService:
        def list_companies(self) -> list[Any]:
            return []
        def list_filings(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_filing_detail(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def get_filing_processed(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def list_processed_artifacts(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_portfolio_health(self, ticker: str) -> Any:
            return object()
        def read_filing_file(self, ticker: str, document_id: str, filename: str) -> Any:
            raise FileNotFoundError()

    router = create_portfolio_router(cast(Any, _FakeService()))

    found = False
    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/portfolio/companies/{ticker}/filings/{document_id}":
            assert "GET" in route.methods
            found = True
            break

    assert found


@pytest.mark.unit
def test_file_download_route_exists() -> None:
    """验证文件下载路由存在。"""

    class _FakeService:
        def list_companies(self) -> list[Any]:
            return []
        def list_filings(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_filing_detail(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def get_filing_processed(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def list_processed_artifacts(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_portfolio_health(self, ticker: str) -> Any:
            return object()
        def read_filing_file(self, ticker: str, document_id: str, filename: str) -> Any:
            raise FileNotFoundError()

    router = create_portfolio_router(cast(Any, _FakeService()))

    found = False
    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/portfolio/companies/{ticker}/filings/{document_id}/files/{filename}":
            assert "GET" in route.methods
            found = True
            break

    assert found


@pytest.mark.unit
def test_health_route_exists() -> None:
    """验证健康度路由存在。"""

    class _FakeService:
        def list_companies(self) -> list[Any]:
            return []
        def list_filings(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_filing_detail(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def get_filing_processed(self, ticker: str, document_id: str) -> Any:
            raise FileNotFoundError()
        def list_processed_artifacts(self, ticker: str, **kwargs) -> list[Any]:
            return []
        def get_portfolio_health(self, ticker: str) -> Any:
            return object()
        def read_filing_file(self, ticker: str, document_id: str, filename: str) -> Any:
            raise FileNotFoundError()

    router = create_portfolio_router(cast(Any, _FakeService()))

    found = False
    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/portfolio/companies/{ticker}/health":
            assert "GET" in route.methods
            found = True
            break

    assert found


__all__ = [
    "test_portfolio_router_registers_all_endpoints",
    "test_list_companies_route_method",
    "test_filing_detail_route_exists",
    "test_file_download_route_exists",
    "test_health_route_exists",
]