"""Prompt 文档仓储。

该模块负责按目录布局枚举、读取、写入 ``dayu/config/prompts`` 与工作区
``workspace/config/prompts`` 下的 manifest / scene / base / task 文档，
并把工作区目录视为高优先级覆盖。

仓储只关心字节与路径，不解析 manifest 语义；scene 语义解析仍走
``dayu.prompting``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from dayu.services.contracts import PromptDocumentDetailView, PromptDocumentView


_PROMPTS_ROOT_NAME = "prompts"
_VALID_CATEGORIES: tuple[str, ...] = ("manifests", "scenes", "base", "tasks")
_TEXT_ENCODING = "utf-8"
_BLOCKED_PATH_TOKENS: tuple[str, ...] = ("..", "")


@dataclass(frozen=True)
class PromptDocumentRepository:
    """prompt 文档仓储。

    Attributes:
        workspace_prompts_dir: 工作区 prompts 目录；用于覆盖与写回。
            ``None`` 表示当前部署只用包内默认 prompts。
        package_prompts_dir: 包内默认 prompts 目录。
    """

    workspace_prompts_dir: Path | None
    package_prompts_dir: Path

    def list_documents(self) -> list[PromptDocumentView]:
        """列出所有 prompt 文档。

        遍历两个目录的 ``manifests / scenes / base / tasks`` 子目录，按相对路径去重，
        工作区版本优先。

        Returns:
            文档视图列表，按 ``(category, name)`` 排序。

        Raises:
            OSError: 目录扫描失败时抛出。
        """

        seen: dict[str, PromptDocumentView] = {}
        for source_dir in self._read_source_dirs():
            for category in _VALID_CATEGORIES:
                category_dir = source_dir / category
                if not category_dir.is_dir():
                    continue
                for path in sorted(category_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = self._relative_path_for(category, category_dir, path)
                    if relative_path in seen:
                        continue
                    seen[relative_path] = self._build_view(category, relative_path, path)
        return sorted(seen.values(), key=lambda view: (view.category, view.name))

    def read_document(self, relative_path: str) -> PromptDocumentDetailView:
        """读取单份 prompt 文档原文。

        Args:
            relative_path: 相对 prompts 根目录的路径。

        Returns:
            包含原文文本的详情视图。

        Raises:
            FileNotFoundError: 文档不存在时抛出。
            PermissionError: 路径越界（试图访问 prompts 根目录之外）时抛出。
        """

        category = self._validate_relative_path(relative_path)
        for source_dir in self._read_source_dirs():
            file_path = source_dir / relative_path
            if file_path.is_file():
                content = file_path.read_text(encoding=_TEXT_ENCODING)
                view = self._build_view(category, relative_path, file_path)
                return PromptDocumentDetailView(document=view, content=content)
        raise FileNotFoundError(f"未找到 prompt 文档: {relative_path}")

    def write_document(self, relative_path: str, content: str) -> PromptDocumentDetailView:
        """覆盖写入 prompt 文档。

        Args:
            relative_path: 相对 prompts 根目录的路径。
            content: 待写入的全量文本。

        Returns:
            写入后的详情视图。

        Raises:
            FileNotFoundError: 文档不存在于任何一层时抛出。
            PermissionError: 路径越界，或部署不允许写入（无 workspace_prompts_dir）时抛出。
            ValueError: 内容为空或仅含空白时抛出。
        """

        category = self._validate_relative_path(relative_path)
        if not content.strip():
            raise ValueError("prompt 文档内容不能为空白")
        write_dir = self.workspace_prompts_dir
        if write_dir is None:
            raise PermissionError("当前部署未配置 workspace prompts 目录，禁止写入")
        if not self._document_exists(relative_path):
            raise FileNotFoundError(f"未找到 prompt 文档: {relative_path}")
        target_path = write_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding=_TEXT_ENCODING)
        view = self._build_view(category, relative_path, target_path)
        return PromptDocumentDetailView(document=view, content=content)

    def _document_exists(self, relative_path: str) -> bool:
        """判断指定文档是否在任一来源目录下存在。"""

        return any((source_dir / relative_path).is_file() for source_dir in self._read_source_dirs())

    def _read_source_dirs(self) -> Iterable[Path]:
        """返回按优先级排序的 prompts 源目录列表。"""

        if self.workspace_prompts_dir is not None:
            yield self.workspace_prompts_dir
        yield self.package_prompts_dir

    def _relative_path_for(self, category: str, category_dir: Path, file_path: Path) -> str:
        """计算文件相对 prompts 根目录的路径。"""

        relative_in_category = file_path.relative_to(category_dir)
        return f"{category}/{relative_in_category.as_posix()}"

    def _build_view(self, category: str, relative_path: str, file_path: Path) -> PromptDocumentView:
        """构造 prompt 文档摘要视图。"""

        stat = file_path.stat()
        return PromptDocumentView(
            category=category,
            name=Path(relative_path).stem,
            relative_path=relative_path,
            size=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        )

    def _validate_relative_path(self, relative_path: str) -> str:
        """校验相对路径合法且分类合法，返回 category。"""

        normalized = relative_path.strip().lstrip("/")
        if not normalized:
            raise PermissionError("prompt 文档路径不能为空")
        for token in normalized.split("/"):
            if token in _BLOCKED_PATH_TOKENS:
                raise PermissionError(f"非法 prompt 文档路径: {relative_path}")
        category = normalized.split("/", 1)[0]
        if category not in _VALID_CATEGORIES:
            raise PermissionError(f"非法 prompt 文档分类: {category}")
        return category


__all__ = ["PromptDocumentRepository"]
