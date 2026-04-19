"""scene 与 prompt 配置浏览/编辑服务。

该服务把 ``dayu.prompting`` 的 scene 解析能力与 prompt 文档仓储统一封装为
UI 友好的稳定 DTO，专门服务于配置控制台界面。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dayu.prompting.prompt_plan import PromptFragmentAssetStoreProtocol, build_prompt_assembly_plan
from dayu.prompting.scene_definition import (
    SceneDefinition,
    ScenePromptAssetStoreProtocol,
    load_scene_definition,
)
from dayu.services.contracts import (
    PromptDocumentDetailView,
    PromptDocumentView,
    SceneDefaultModelUpdateView,
    SceneMatrixRowView,
    SceneMatrixView,
    SceneModelOptionView,
    ScenePromptCompositionView,
)
from dayu.services.internal.prompt_document_repository import PromptDocumentRepository


_MANIFEST_CATEGORY = "manifests"
_PROMPT_FRAGMENT_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class SceneConfigService:
    """scene 与 prompt 配置浏览/编辑服务。

    该服务依赖 prompt 资产仓储读取 scene manifest，并依赖 prompt 文档仓储
    提供 prompt 文件枚举/读写能力。

    Attributes:
        prompt_asset_store: prompt 资产仓储（同时支持 manifest 与 fragment 模板）。
        prompt_document_repository: prompt 文档仓储（列出/读/写 prompt 文档）。
    """

    prompt_asset_store: PromptFragmentAssetStoreProtocol
    prompt_document_repository: PromptDocumentRepository

    def get_scene_matrix(self) -> SceneMatrixView:
        """读取 scene × 模型矩阵全量快照。"""

        documents = self.prompt_document_repository.list_documents()
        scene_names = self._collect_scene_names(documents)
        rows: list[SceneMatrixRowView] = []
        all_models: set[str] = set()
        for scene_name in scene_names:
            try:
                definition = load_scene_definition(self.prompt_asset_store, scene_name)
            except Exception:
                continue
            row = _build_matrix_row(definition)
            rows.append(row)
            all_models.update(option.model_name for option in row.allowed_models)
        return SceneMatrixView(
            all_models=tuple(sorted(all_models)),
            rows=tuple(rows),
        )

    def list_prompt_documents(self) -> list[PromptDocumentView]:
        """列出全部 prompt 文档。"""

        return self.prompt_document_repository.list_documents()

    def get_prompt_document(self, relative_path: str) -> PromptDocumentDetailView:
        """读取单份 prompt 文档详情。"""

        return self.prompt_document_repository.read_document(relative_path)

    def update_prompt_document(self, relative_path: str, content: str) -> PromptDocumentDetailView:
        """覆盖写入 prompt 文档原文。"""

        return self.prompt_document_repository.write_document(relative_path, content)

    def get_scene_prompt_composition(self, scene_name: str) -> ScenePromptCompositionView:
        """读取指定 scene 的拼接系统提示。"""

        normalized_name = scene_name.strip()
        if not normalized_name:
            raise FileNotFoundError("scene 名称不能为空")
        plan = build_prompt_assembly_plan(
            asset_store=self._narrow_fragment_asset_store(),
            scene_name=normalized_name,
        )
        sorted_fragments = sorted(plan.fragments, key=lambda fragment: fragment.order)
        composed_text = _PROMPT_FRAGMENT_SEPARATOR.join(fragment.template for fragment in sorted_fragments).strip()
        fragment_ids = tuple(fragment.id for fragment in sorted_fragments)
        return ScenePromptCompositionView(
            scene_name=normalized_name,
            composed_text=composed_text,
            fragments=fragment_ids,
        )

    def update_scene_default_model(self, scene_name: str, model_name: str) -> SceneDefaultModelUpdateView:
        """更新 scene 的默认模型。

        Args:
            scene_name: Scene 名称。
            model_name: 新默认模型名。

        Returns:
            更新结果视图。

        Raises:
            FileNotFoundError: scene manifest 不存在。
            ValueError: 模型不在 allowed_names 中。
        """
        normalized_scene = scene_name.strip()
        if not normalized_scene:
            raise FileNotFoundError("scene 名称不能为空")

        # 先检查当前定义
        try:
            definition = load_scene_definition(self.prompt_asset_store, normalized_scene)
        except Exception as exc:
            raise FileNotFoundError(f"scene {normalized_scene} 不存在: {exc}") from exc

        old_model = definition.model.default_name

        # 检查模型是否在 allowed_names 中
        if model_name not in definition.model.allowed_names:
            raise ValueError(f"模型 {model_name} 不在 scene {normalized_scene} 的 allowed_names 中")

        # 获取 manifest 文件路径并更新
        manifest_path = self._get_manifest_path(normalized_scene)
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest 文件不存在: {manifest_path}")

        # 读取并更新
        content = manifest_path.read_text(encoding="utf-8")
        data = json.loads(content)
        model_section = data.get("model")
        if not isinstance(model_section, dict):
            raise ValueError(f"manifest 格式错误: 缺少 model 配置")

        model_section["default_name"] = model_name
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        return SceneDefaultModelUpdateView(
            scene_name=normalized_scene,
            old_model=old_model,
            new_model=model_name,
        )

    def _get_manifest_path(self, scene_name: str) -> Path:
        """获取 scene manifest 文件路径（优先返回 workspace 版本）。"""
        repo = self.prompt_document_repository
        # 优先使用 workspace 目录（可写入）
        if repo.workspace_prompts_dir is not None:
            workspace_manifest = repo.workspace_prompts_dir / "manifests" / f"{scene_name}.json"
            if workspace_manifest.exists():
                return workspace_manifest
        # 回退到包内目录
        return repo.package_prompts_dir / "manifests" / f"{scene_name}.json"

    def _collect_scene_names(self, documents: Iterable[PromptDocumentView]) -> list[str]:
        """从文档列表中提取 scene 名（基于 manifests 目录）。"""

        scene_names: list[str] = []
        seen: set[str] = set()
        for view in documents:
            if view.category != _MANIFEST_CATEGORY:
                continue
            if view.name in seen:
                continue
            seen.add(view.name)
            scene_names.append(view.name)
        scene_names.sort()
        return scene_names

    def _narrow_asset_store(self) -> ScenePromptAssetStoreProtocol:
        """收窄 prompt_asset_store 为 scene manifest 协议。"""

        return self.prompt_asset_store

    def _narrow_fragment_asset_store(self) -> PromptFragmentAssetStoreProtocol:
        """收窄 prompt_asset_store 为 fragment + manifest 协议（运行时检查由调用方保证）。"""

        store = self.prompt_asset_store
        load_fragment = getattr(store, "load_fragment_template", None)
        if not callable(load_fragment):
            raise TypeError("prompt_asset_store 不支持 load_fragment_template，无法拼接 scene 系统提示")
        return _AssetStoreAdapter(store=store)


@dataclass(frozen=True)
class _AssetStoreAdapter:
    """把任意支持 ``load_scene_manifest`` + ``load_fragment_template`` 的 store 适配为
    ``PromptFragmentAssetStoreProtocol``。

    该 adapter 仅做协议形变，不增加业务逻辑。
    """

    store: ScenePromptAssetStoreProtocol

    def load_scene_manifest(self, scene_name: str):  # pyright: ignore[reportMissingTypeStubs]
        """读取 scene manifest。"""

        return self.store.load_scene_manifest(scene_name)

    def load_fragment_template(self, fragment_path: str, *, required: bool = True):  # pyright: ignore[reportMissingTypeStubs]
        """读取 fragment 模板。"""

        load_fragment = getattr(self.store, "load_fragment_template")
        return load_fragment(fragment_path, required=required)


def _build_matrix_row(definition: SceneDefinition) -> SceneMatrixRowView:
    """从 scene 定义构造 scene 矩阵单行视图。"""

    default_name = definition.model.default_name
    options = tuple(
        SceneModelOptionView(model_name=name, is_default=(name == default_name))
        for name in definition.model.allowed_names
    )
    return SceneMatrixRowView(
        scene_name=definition.name,
        default_model=default_name,
        allowed_models=options,
    )


__all__ = ["SceneConfigService"]
