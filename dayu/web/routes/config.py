"""Config 配置 REST 端点。

该路由聚合 ``SceneConfigService`` 能力，向 UI 暴露配置浏览 API：
- scene × 模型矩阵
- prompt 文档浏览/编辑
- scene 拼接系统提示
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from dayu.services.protocols import SceneConfigServiceProtocol


def create_config_router(service: SceneConfigServiceProtocol) -> Any:
    """创建 config 配置路由。

    Args:
        service: scene 配置服务实例。

    Returns:
        FastAPI 路由对象。

    Raises:
        无。
    """

    router = APIRouter(prefix="/api/config", tags=["config"])

    # === 响应模型 ===

    class SceneModelOptionResponse(BaseModel):
        """scene 模型选项响应。"""

        model_name: str
        is_default: bool

    class SceneMatrixRowResponse(BaseModel):
        """scene 矩阵行响应。"""

        scene_name: str
        default_model: str
        allowed_models: list[SceneModelOptionResponse]

    class SceneMatrixResponse(BaseModel):
        """scene 矩阵响应。"""

        all_models: list[str]
        rows: list[SceneMatrixRowResponse]

    class PromptDocumentResponse(BaseModel):
        """prompt 文档摘要响应。"""

        category: str
        name: str
        relative_path: str
        size: int
        updated_at: str

    class PromptDocumentDetailResponse(BaseModel):
        """prompt 文档详情响应。"""

        document: PromptDocumentResponse
        content: str

    class ScenePromptCompositionResponse(BaseModel):
        """scene 拼接系统提示响应。"""

        scene_name: str
        composed_text: str
        fragments: list[str]

    class UpdatePromptRequest(BaseModel):
        """更新 prompt 请求体。"""

        content: str

    # === 转换函数 ===

    def _model_option_to_response(view: Any) -> SceneModelOptionResponse:
        """模型选项视图转响应。"""

        return SceneModelOptionResponse(
            model_name=view.model_name,
            is_default=view.is_default,
        )

    def _matrix_row_to_response(view: Any) -> SceneMatrixRowResponse:
        """矩阵行视图转响应。"""

        return SceneMatrixRowResponse(
            scene_name=view.scene_name,
            default_model=view.default_model,
            allowed_models=[_model_option_to_response(m) for m in view.allowed_models],
        )

    def _matrix_to_response(view: Any) -> SceneMatrixResponse:
        """矩阵视图转响应。"""

        return SceneMatrixResponse(
            all_models=list(view.all_models),
            rows=[_matrix_row_to_response(r) for r in view.rows],
        )

    def _document_to_response(view: Any) -> PromptDocumentResponse:
        """文档摘要视图转响应。"""

        return PromptDocumentResponse(
            category=view.category,
            name=view.name,
            relative_path=view.relative_path,
            size=view.size,
            updated_at=view.updated_at,
        )

    def _document_detail_to_response(view: Any) -> PromptDocumentDetailResponse:
        """文档详情视图转响应。"""

        return PromptDocumentDetailResponse(
            document=_document_to_response(view.document),
            content=view.content,
        )

    def _composition_to_response(view: Any) -> ScenePromptCompositionResponse:
        """composition 视图转响应。"""

        return ScenePromptCompositionResponse(
            scene_name=view.scene_name,
            composed_text=view.composed_text,
            fragments=list(view.fragments),
        )

    # === 路由端点 ===

    @router.get("/scenes/matrix", response_model=SceneMatrixResponse)
    async def get_scene_matrix() -> SceneMatrixResponse:
        """获取 scene × 模型矩阵。"""

        view = service.get_scene_matrix()
        return _matrix_to_response(view)

    @router.get("/prompts", response_model=list[PromptDocumentResponse])
    async def list_prompt_documents() -> list[PromptDocumentResponse]:
        """列出所有 prompt 文档。"""

        views = service.list_prompt_documents()
        return [_document_to_response(v) for v in views]

    @router.get(
        "/prompts/{relative_path:path}",
        response_model=PromptDocumentDetailResponse,
    )
    async def get_prompt_document(
        relative_path: str = Path(description="相对路径"),
    ) -> PromptDocumentDetailResponse:
        """获取 prompt 文档详情。"""

        try:
            view = service.get_prompt_document(relative_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return _document_detail_to_response(view)

    @router.put(
        "/prompts/{relative_path:path}",
        response_model=PromptDocumentDetailResponse,
    )
    async def update_prompt_document(
        relative_path: str = Path(description="相对路径"),
        body: UpdatePromptRequest = None,  # type: ignore[assignment]
    ) -> PromptDocumentDetailResponse:
        """更新 prompt 文档。"""

        try:
            view = service.update_prompt_document(relative_path, body.content)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _document_detail_to_response(view)

    @router.get(
        "/scenes/{scene_name}/composition",
        response_model=ScenePromptCompositionResponse,
    )
    async def get_scene_prompt_composition(
        scene_name: str = Path(description="scene 名称"),
    ) -> ScenePromptCompositionResponse:
        """获取 scene 拼接系统提示。"""

        try:
            view = service.get_scene_prompt_composition(scene_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _composition_to_response(view)

    return router


__all__ = ["create_config_router"]