"""SceneConfigService 单元测试。

测试构造 fake 资产仓储与文档仓储，验证服务把 scene 定义正确聚合为 UI DTO，
覆盖 manifest 解析、prompt 文档枚举/读写、composition 拼接等场景。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

from dayu.services.contracts import (
    PromptDocumentDetailView,
    PromptDocumentView,
    SceneMatrixView,
    ScenePromptCompositionView,
)
from dayu.services.internal.prompt_document_repository import PromptDocumentRepository
from dayu.services.scene_config_service import SceneConfigService


@dataclass
class _FakePromptAssetStore:
    """内存 prompt 资产仓储。"""

    manifests: dict[str, dict[str, Any]] = field(default_factory=dict)
    fragments: dict[str, str] = field(default_factory=dict)

    def load_scene_manifest(self, scene_name: str) -> dict[str, Any]:
        """读取 scene manifest。"""

        if scene_name not in self.manifests:
            raise FileNotFoundError(f"未找到 scene manifest: {scene_name}")
        return dict(self.manifests[scene_name])

    def load_fragment_template(self, fragment_path: str, *, required: bool = True) -> str | None:
        """读取 fragment 模板。"""

        if fragment_path not in self.fragments:
            if required:
                raise FileNotFoundError(f"未找到 fragment: {fragment_path}")
            return None
        return self.fragments[fragment_path]


@dataclass
class _FakePromptDocumentRepository:
    """内存 prompt 文档仓储。"""

    documents: list[PromptDocumentView] = field(default_factory=list)
    document_details: dict[str, PromptDocumentDetailView] = field(default_factory=dict)

    def list_documents(self) -> list[PromptDocumentView]:
        """列出所有 prompt 文档。"""

        return list(self.documents)

    def read_document(self, relative_path: str) -> PromptDocumentDetailView:
        """读取单份 prompt 文档详情。"""

        if relative_path not in self.document_details:
            raise FileNotFoundError(f"未找到 prompt 文档: {relative_path}")
        return self.document_details[relative_path]

    def write_document(self, relative_path: str, content: str) -> PromptDocumentDetailView:
        """覆盖写入 prompt 文档。"""

        if relative_path not in self.document_details:
            raise FileNotFoundError(f"未找到 prompt 文档: {relative_path}")
        existing = self.document_details[relative_path]
        updated = PromptDocumentDetailView(document=existing.document, content=content)
        self.document_details[relative_path] = updated
        return updated


def _make_scene_manifest(
    scene_name: str,
    *,
    default_model: str = "claude-opus-4-7",
    allowed_models: tuple[str, ...] | None = None,
    fragments: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """构造 scene manifest dict。"""

    resolved_allowed = allowed_models or (default_model, "claude-sonnet-4-6")
    resolved_fragments = fragments or (
        {"id": "base", "type": "SCENE", "path": f"scenes/{scene_name}.md", "order": 0},
        {"id": "user", "type": "USER", "path": "base/user.md", "order": 1},
    )
    return {
        "scene": scene_name,
        "version": "v1",
        "description": f"{scene_name} scene",
        "model": {
            "default_name": default_model,
            "allowed_names": list(resolved_allowed),
            "temperature_profile": "default",
        },
        "fragments": list(resolved_fragments),
    }


def _build_service(
    *,
    asset_store: _FakePromptAssetStore,
    document_repository: _FakePromptDocumentRepository | None = None,
    workspace_prompts_dir: Path | None = None,
    package_prompts_dir: Path | None = None,
) -> SceneConfigService:
    """组装服务实例。"""

    if document_repository is not None:
        repository: PromptDocumentRepository = cast(Any, document_repository)
    else:
        if package_prompts_dir is None:
            package_prompts_dir = Path("/fake/package/prompts")
        repository = PromptDocumentRepository(
            workspace_prompts_dir=workspace_prompts_dir,
            package_prompts_dir=package_prompts_dir,
        )
    return SceneConfigService(
        prompt_asset_store=cast(Any, asset_store),
        prompt_document_repository=repository,
    )


def _make_prompt_document_view(
    category: str,
    name: str,
    relative_path: str,
) -> PromptDocumentView:
    """构造 prompt 文档视图。"""

    return PromptDocumentView(
        category=category,
        name=name,
        relative_path=relative_path,
        size=100,
        updated_at="2026-04-18T10:00:00+00:00",
    )


def test_get_scene_matrix_aggregates_default_and_allowed_models() -> None:
    """get_scene_matrix 应聚合多 scene 的 default/allowed_models。"""

    asset_store = _FakePromptAssetStore(
        manifests={
            "analyze": _make_scene_manifest(
                "analyze",
                default_model="claude-opus-4-7",
                allowed_models=("claude-opus-4-7", "claude-sonnet-4-6"),
            ),
            "chat": _make_scene_manifest(
                "chat",
                default_model="claude-sonnet-4-6",
                allowed_models=("claude-sonnet-4-6", "claude-haiku-4-5"),
            ),
        },
    )
    document_repository = _FakePromptDocumentRepository(
        documents=[
            _make_prompt_document_view("manifests", "analyze", "manifests/analyze.json"),
            _make_prompt_document_view("manifests", "chat", "manifests/chat.json"),
        ],
    )
    service = _build_service(asset_store=asset_store, document_repository=document_repository)

    matrix = service.get_scene_matrix()

    assert set(matrix.all_models) == {"claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"}
    assert len(matrix.rows) == 2
    analyze_row = next(row for row in matrix.rows if row.scene_name == "analyze")
    assert analyze_row.default_model == "claude-opus-4-7"
    assert {opt.model_name for opt in analyze_row.allowed_models} == {
        "claude-opus-4-7",
        "claude-sonnet-4-6",
    }
    chat_row = next(row for row in matrix.rows if row.scene_name == "chat")
    assert chat_row.default_model == "claude-sonnet-4-6"


def test_list_prompt_documents_workspace_overrides_package(tmp_path: Path) -> None:
    """list_prompt_documents 应合并两目录，工作区优先。"""

    asset_store = _FakePromptAssetStore()
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text("{}")
    (package_dir / "scenes").mkdir()
    (package_dir / "scenes" / "analyze.md").write_text("# analyze")

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"override": true}')
    (workspace_dir / "manifests" / "chat.json").write_text("{}")

    service = _build_service(
        asset_store=asset_store,
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    documents = service.list_prompt_documents()

    assert len(documents) == 3
    manifests = [doc for doc in documents if doc.category == "manifests"]
    scenes = [doc for doc in documents if doc.category == "scenes"]
    assert len(manifests) == 2
    assert len(scenes) == 1
    analyze_manifest = next(doc for doc in manifests if doc.name == "analyze")
    assert analyze_manifest.relative_path == "manifests/analyze.json"


def test_get_prompt_document_workspace_priority_return(tmp_path: Path) -> None:
    """get_prompt_document 应优先返回工作区版本。"""

    asset_store = _FakePromptAssetStore()
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"package": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"workspace": true}')

    service = _build_service(
        asset_store=asset_store,
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    detail = service.get_prompt_document("manifests/analyze.json")

    assert '{"workspace": true}' in detail.content


def test_update_prompt_document_writes_to_workspace_only(tmp_path: Path) -> None:
    """update_prompt_document 应只写工作区目录，不污染包内。"""

    asset_store = _FakePromptAssetStore()
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"original": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"original": true}')

    service = _build_service(
        asset_store=asset_store,
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    updated = service.update_prompt_document("manifests/analyze.json", '{"updated": true}')

    assert '{"updated": true}' in updated.content
    package_content = (package_dir / "manifests" / "analyze.json").read_text()
    assert '{"original": true}' in package_content


def test_update_prompt_document_rejects_empty_content(tmp_path: Path) -> None:
    """update_prompt_document 应拒绝空白内容。"""

    asset_store = _FakePromptAssetStore()
    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text("{}")

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)

    service = _build_service(
        asset_store=asset_store,
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    with pytest.raises(ValueError, match="内容不能为空白"):
        service.update_prompt_document("manifests/analyze.json", "   ")


def test_update_prompt_document_rejects_path_traversal() -> None:
    """update_prompt_document 应拒绝路径越界。"""

    asset_store = _FakePromptAssetStore()
    service = _build_service(asset_store=asset_store)

    with pytest.raises(PermissionError, match="非法"):
        service.update_prompt_document("../outside.json", "content")


def test_update_prompt_document_rejects_when_no_workspace_dir() -> None:
    """workspace_prompts_dir 为 None 时 update_prompt_document 应抛 PermissionError。"""

    asset_store = _FakePromptAssetStore()
    package_dir = Path("/fake/package/prompts")
    service = _build_service(
        asset_store=asset_store,
        workspace_prompts_dir=None,
        package_prompts_dir=package_dir,
    )

    with pytest.raises(PermissionError, match="禁止写入"):
        service.update_prompt_document("manifests/analyze.json", "content")


def test_get_scene_prompt_composition_joins_by_order() -> None:
    """get_scene_prompt_composition 应按 fragment.order 拼接模板。"""

    asset_store = _FakePromptAssetStore(
        manifests={
            "analyze": _make_scene_manifest(
                "analyze",
                fragments=(
                    {"id": "user", "type": "USER", "path": "base/user.md", "order": 10},
                    {"id": "scene", "type": "SCENE", "path": "scenes/analyze.md", "order": 5},
                    {"id": "tools", "type": "TOOLS", "path": "base/tools.md", "order": 0},
                ),
            ),
        },
        fragments={
            "base/tools.md": "Tools header",
            "scenes/analyze.md": "Analyze scene body",
            "base/user.md": "User context",
        },
    )
    service = _build_service(asset_store=asset_store)

    composition = service.get_scene_prompt_composition("analyze")

    assert composition.scene_name == "analyze"
    assert composition.fragments == ("tools", "scene", "user")
    assert composition.composed_text == "Tools header\n\nAnalyze scene body\n\nUser context"


def test_get_scene_prompt_composition_raises_for_empty_scene_name() -> None:
    """get_scene_prompt_composition 应拒绝空 scene 名。"""

    asset_store = _FakePromptAssetStore()
    service = _build_service(asset_store=asset_store)

    with pytest.raises(FileNotFoundError, match="不能为空"):
        service.get_scene_prompt_composition("")


def test_get_scene_prompt_composition_raises_for_missing_scene() -> None:
    """get_scene_prompt_composition 应在 scene 不存在时抛 FileNotFoundError。"""

    asset_store = _FakePromptAssetStore()
    service = _build_service(asset_store=asset_store)

    with pytest.raises(FileNotFoundError):
        service.get_scene_prompt_composition("missing_scene")