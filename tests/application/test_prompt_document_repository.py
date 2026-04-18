"""PromptDocumentRepository 单元测试。

测试覆盖 prompt 文档仓储的边界场景：
- 列表合并两个目录（工作区优先）
- 读取优先返回工作区版本
- 写入只写工作区目录
- 路径校验拒绝越界
- workspace_prompts_dir 为 None 时禁止写入
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dayu.services.contracts import PromptDocumentDetailView, PromptDocumentView
from dayu.services.internal.prompt_document_repository import PromptDocumentRepository


def test_list_documents_merges_workspace_and_package(tmp_path: Path) -> None:
    """list_documents 应合并两个目录，工作区文件优先。"""

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

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    documents = repository.list_documents()

    assert len(documents) == 3
    manifests = [doc for doc in documents if doc.category == "manifests"]
    scenes = [doc for doc in documents if doc.category == "scenes"]
    assert len(manifests) == 2
    assert len(scenes) == 1
    analyze_manifest = next(doc for doc in manifests if doc.name == "analyze")
    assert analyze_manifest.relative_path == "manifests/analyze.json"


def test_list_documents_workspace_file_prioritized_for_same_path(tmp_path: Path) -> None:
    """list_documents 应优先返回工作区版本（同名文件）。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"package_version": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"workspace_version": true}')

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    documents = repository.list_documents()

    assert len(documents) == 1
    assert documents[0].relative_path == "manifests/analyze.json"


def test_read_document_workspace_priority(tmp_path: Path) -> None:
    """read_document 应优先返回工作区版本。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"package": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"workspace": true}')

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    detail = repository.read_document("manifests/analyze.json")

    assert '{"workspace": true}' in detail.content


def test_read_document_fallback_to_package(tmp_path: Path) -> None:
    """read_document 应在无工作区版本时回退到包内版本。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"package": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    detail = repository.read_document("manifests/analyze.json")

    assert '{"package": true}' in detail.content


def test_read_document_raises_for_missing_file(tmp_path: Path) -> None:
    """read_document 应在文件不存在时抛 FileNotFoundError。"""

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=tmp_path,
    )

    with pytest.raises(FileNotFoundError, match="未找到"):
        repository.read_document("manifests/missing.json")


def test_write_document_creates_in_workspace(tmp_path: Path) -> None:
    """write_document 应在工作区目录创建文件。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text("{}")

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    result = repository.write_document("manifests/analyze.json", '{"updated": true}')

    assert '{"updated": true}' in result.content
    assert (workspace_dir / "manifests" / "analyze.json").exists()
    assert (workspace_dir / "manifests" / "analyze.json").read_text() == '{"updated": true}'


def test_write_document_does_not_modify_package(tmp_path: Path) -> None:
    """write_document 不应修改包内目录的文件。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text('{"original": true}')

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "manifests").mkdir()
    (workspace_dir / "manifests" / "analyze.json").write_text('{"original": true}')

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    repository.write_document("manifests/analyze.json", '{"updated": true}')

    package_content = (package_dir / "manifests" / "analyze.json").read_text()
    assert '{"original": true}' in package_content


def test_write_document_rejects_empty_content(tmp_path: Path) -> None:
    """write_document 应拒绝空白内容。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text("{}")

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=package_dir,
    )

    with pytest.raises(ValueError, match="内容不能为空白"):
        repository.write_document("manifests/analyze.json", "   ")


def test_write_document_rejects_path_traversal() -> None:
    """write_document 应拒绝路径越界。"""

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=Path("/fake/package"),
    )

    with pytest.raises(PermissionError, match="非法"):
        repository.write_document("../outside.json", "content")


def test_write_document_rejects_invalid_category() -> None:
    """write_document 应拒绝非法分类。"""

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=Path("/fake/package"),
    )

    with pytest.raises(PermissionError, match="非法"):
        repository.write_document("invalid/some.md", "content")


def test_write_document_rejects_empty_path() -> None:
    """write_document 应拒绝空路径。"""

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=Path("/fake/package"),
    )

    with pytest.raises(PermissionError, match="不能为空"):
        repository.write_document("", "content")


def test_write_document_rejects_when_no_workspace_dir() -> None:
    """workspace_prompts_dir 为 None 时 write_document 应抛 PermissionError。"""

    package_dir = Path("/fake/package/prompts")
    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=package_dir,
    )

    with pytest.raises(PermissionError, match="禁止写入"):
        repository.write_document("manifests/analyze.json", "content")


def test_write_document_raises_for_missing_source(tmp_path: Path) -> None:
    """write_document 应在源文件不存在时抛 FileNotFoundError。"""

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)

    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_dir,
        package_prompts_dir=tmp_path / "package",
    )

    with pytest.raises(FileNotFoundError, match="未找到"):
        repository.write_document("manifests/missing.json", "content")


def test_list_documents_ignores_invalid_categories(tmp_path: Path) -> None:
    """list_documents 应忽略非法分类目录。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "analyze.json").write_text("{}")
    (package_dir / "invalid").mkdir()
    (package_dir / "invalid" / "some.md").write_text("invalid")

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=package_dir,
    )

    documents = repository.list_documents()

    assert len(documents) == 1
    assert documents[0].category == "manifests"


def test_list_documents_sorts_by_category_and_name(tmp_path: Path) -> None:
    """list_documents 应按 (category, name) 排序。"""

    package_dir = tmp_path / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "manifests").mkdir()
    (package_dir / "manifests" / "z_manifest.json").write_text("{}")
    (package_dir / "manifests" / "a_manifest.json").write_text("{}")
    (package_dir / "scenes").mkdir()
    (package_dir / "scenes" / "b_scene.md").write_text("# b")
    (package_dir / "scenes" / "a_scene.md").write_text("# a")

    repository = PromptDocumentRepository(
        workspace_prompts_dir=None,
        package_prompts_dir=package_dir,
    )

    documents = repository.list_documents()

    assert [doc.relative_path for doc in documents] == [
        "manifests/a_manifest.json",
        "manifests/z_manifest.json",
        "scenes/a_scene.md",
        "scenes/b_scene.md",
    ]