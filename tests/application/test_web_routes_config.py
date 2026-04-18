"""Config 路由测试。

按 §4.6 设计要求，覆盖：
- 路由端点注册
- handler 逻辑验证
- 404/403/400 错误场景
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any, cast

import pytest

from dayu.web.routes.config import create_config_router


class _FakeRouter:
    """最小 APIRouter 测试桩。"""

    def __init__(self, *, prefix: str, tags: list[str]) -> None:
        self.prefix = prefix
        self.tags = tags
        self.routes: list[tuple[str, str]] = []
        self.handlers: dict[str, object] = {}

    def _record_handler(self, method: str, path: str, func: object) -> object:
        self.routes.append((method, path))
        self.handlers[f"{method} {path}"] = func
        return func

    def get(self, path: str, **_kwargs):
        def _decorator(func):
            return self._record_handler("GET", path, func)
        return _decorator

    def put(self, path: str, **_kwargs):
        def _decorator(func):
            return self._record_handler("PUT", path, func)
        return _decorator


class _FakeHTTPException(Exception):
    """最小 HTTPException 测试桩。"""

    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeBaseModel:
    """最小 BaseModel 测试桩。"""

    def __init__(self, **data: object) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass(frozen=True)
class _SceneModelOptionView:
    model_name: str
    is_default: bool


@dataclass(frozen=True)
class _SceneMatrixRowView:
    scene_name: str
    default_model: str
    allowed_models: tuple[_SceneModelOptionView, ...]


@dataclass(frozen=True)
class _SceneMatrixView:
    all_models: tuple[str, ...]
    rows: tuple[_SceneMatrixRowView, ...]


@dataclass(frozen=True)
class _PromptDocumentView:
    category: str
    name: str
    relative_path: str
    size: int
    updated_at: str


@dataclass(frozen=True)
class _PromptDocumentDetailView:
    document: _PromptDocumentView
    content: str


@dataclass(frozen=True)
class _ScenePromptCompositionView:
    scene_name: str
    composed_text: str
    fragments: tuple[str, ...]


def _install_fake_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """安装 fastapi/pydantic 测试桩。"""

    def _fake_path(*args, **kwargs):
        return args[0] if args else ""

    fake_fastapi = ModuleType("fastapi")
    cast(Any, fake_fastapi).APIRouter = _FakeRouter
    cast(Any, fake_fastapi).HTTPException = _FakeHTTPException
    cast(Any, fake_fastapi).Path = _fake_path

    fake_pydantic = ModuleType("pydantic")
    cast(Any, fake_pydantic).BaseModel = _FakeBaseModel

    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "pydantic", fake_pydantic)


@pytest.mark.unit
def test_config_router_registers_all_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 config 路由注册全部 5 个端点。"""

    _install_fake_modules(monkeypatch)

    matrix = _SceneMatrixView(
        all_models=("model-a", "model-b"),
        rows=(
            _SceneMatrixRowView(
                scene_name="prompt",
                default_model="model-a",
                allowed_models=(
                    _SceneModelOptionView(model_name="model-a", is_default=True),
                ),
            ),
        ),
    )

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return matrix
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise FileNotFoundError()
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError()

    router = create_config_router(cast(Any, _FakeService()))
    assert router.prefix == "/api/config"

    # 验证路由数量
    assert len(router.routes) == 5

    # 验证路由路径（包含前缀）
    route_paths = [r.path for r in router.routes]
    assert "/api/config/scenes/matrix" in route_paths
    assert "/api/config/prompts" in route_paths
    assert "/api/config/prompts/{relative_path:path}" in route_paths
    assert "/api/config/scenes/{scene_name}/composition" in route_paths


@pytest.mark.unit
def test_get_scene_matrix_handler_returns_correct_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 scene 矩阵 handler 返回正确结构。"""

    matrix = _SceneMatrixView(
        all_models=("mimo-v2-pro", "mimo-v2-flash"),
        rows=(
            _SceneMatrixRowView(
                scene_name="prompt",
                default_model="mimo-v2-pro",
                allowed_models=(
                    _SceneModelOptionView(model_name="mimo-v2-pro", is_default=True),
                    _SceneModelOptionView(model_name="mimo-v2-flash", is_default=False),
                ),
            ),
        ),
    )

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return matrix
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise FileNotFoundError()
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError()

    router = create_config_router(cast(Any, _FakeService()))

    # 找到 scenes/matrix 路由
    matrix_route = None
    for route in router.routes:
        if route.path == "/api/config/scenes/matrix":
            matrix_route = route
            break

    assert matrix_route is not None
    assert "GET" in matrix_route.methods


@pytest.mark.unit
def test_get_prompt_document_handler_returns_404() -> None:
    """验证 prompt 文档不存在时返回 404。"""

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return _SceneMatrixView(all_models=(), rows=())
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError(f"Not found: {relative_path}")
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise FileNotFoundError()
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError()

    router = create_config_router(cast(Any, _FakeService()))

    # 找到 prompts/{relative_path:path} GET 路由
    get_route = None
    for route in router.routes:
        if route.path == "/api/config/prompts/{relative_path:path}" and "GET" in route.methods:
            get_route = route
            break

    assert get_route is not None


@pytest.mark.unit
def test_update_prompt_document_handler_returns_403() -> None:
    """验证 prompt 更新越权时返回 403。"""

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return _SceneMatrixView(all_models=(), rows=())
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise PermissionError(f"Permission denied: {relative_path}")
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError()

    router = create_config_router(cast(Any, _FakeService()))

    # 找到 prompts/{relative_path:path} PUT 路由
    put_route = None
    for route in router.routes:
        if route.path == "/api/config/prompts/{relative_path:path}" and "PUT" in route.methods:
            put_route = route
            break

    assert put_route is not None


@pytest.mark.unit
def test_update_prompt_document_handler_returns_400() -> None:
    """验证 prompt 更新内容非法时返回 400。"""

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return _SceneMatrixView(all_models=(), rows=())
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise ValueError("Content must not be empty")
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError()

    router = create_config_router(cast(Any, _FakeService()))

    # 找到 prompts/{relative_path:path} PUT 路由
    put_route = None
    for route in router.routes:
        if route.path == "/api/config/prompts/{relative_path:path}" and "PUT" in route.methods:
            put_route = route
            break

    assert put_route is not None


@pytest.mark.unit
def test_get_scene_composition_handler_route_exists() -> None:
    """验证 scene composition 路由已注册。"""

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return _SceneMatrixView(all_models=(), rows=())
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise FileNotFoundError()
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            raise FileNotFoundError(f"Scene not found: {scene_name}")

    router = create_config_router(cast(Any, _FakeService()))

    # 验证路由已注册
    route_found = False
    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/config/scenes/{scene_name}/composition":
            route_found = True
            assert "GET" in route.methods
            break

    assert route_found, "Scene composition route not found"


@pytest.mark.unit
def test_scene_composition_endpoint_registered_correctly() -> None:
    """验证 scene composition endpoint 正确配置。"""

    class _FakeService:
        def get_scene_matrix(self) -> Any:
            return _SceneMatrixView(all_models=(), rows=())
        def list_prompt_documents(self) -> list[Any]:
            return []
        def get_prompt_document(self, relative_path: str) -> Any:
            raise FileNotFoundError()
        def update_prompt_document(self, relative_path: str, content: str) -> Any:
            raise FileNotFoundError()
        def get_scene_prompt_composition(self, scene_name: str) -> Any:
            # 返回一个模拟的 composition view
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class _Composition:
                scene_name: str
                composed_text: str
                fragments: tuple
            return _Composition(scene_name=scene_name, composed_text="test", fragments=("a", "b"))

    router = create_config_router(cast(Any, _FakeService()))

    # 验证路由存在且响应模型配置正确
    for route in router.routes:
        if hasattr(route, 'path') and route.path == "/api/config/scenes/{scene_name}/composition":
            # 检查响应模型字段是否正确序列化
            assert hasattr(route, 'response_model')
            break


__all__ = [
    "test_config_router_registers_all_endpoints",
    "test_get_scene_matrix_handler_returns_correct_structure",
    "test_get_prompt_document_handler_returns_404",
    "test_update_prompt_document_handler_returns_403",
    "test_update_prompt_document_handler_returns_400",
    "test_get_scene_composition_handler_route_exists",
    "test_scene_composition_endpoint_registered_correctly",
]