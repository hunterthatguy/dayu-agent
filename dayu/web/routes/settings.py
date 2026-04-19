"""Settings REST 端点。

该路由封装 API Key 配置与模型管理能力：
- API Key 配置：列出状态、设置、清空
- 模型管理：列出模型与 API key 要求、更新 scene 默认模型
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel

from dayu.services.contracts import (
    ApiKeyStatusView,
    ModelApiKeyRequirementView,
    SceneDefaultModelUpdateView,
)
from dayu.services.protocols import ApiKeyConfigServiceProtocol, SceneConfigServiceProtocol


# === 请求/响应模型 ===

class ApiKeyStatusResponse(BaseModel):
    """API key 状态响应。"""

    key_name: str
    display_name: str
    is_configured: bool
    source: str
    masked_value: str
    url: str


class SetApiKeyRequest(BaseModel):
    """设置 API key 请求。"""

    value: str


class ModelRequirementResponse(BaseModel):
    """模型 API key 要求响应。"""

    model_name: str
    required_key: str
    key_display_name: str
    is_available: bool


class UpdateSceneModelRequest(BaseModel):
    """更新 scene 默认模型请求。"""

    model_name: str


class SceneModelUpdateResponse(BaseModel):
    """更新 scene 默认模型响应。"""

    scene_name: str
    old_model: str
    new_model: str


def _key_status_to_response(view: ApiKeyStatusView) -> ApiKeyStatusResponse:
    """API key 状态视图转响应。"""
    return ApiKeyStatusResponse(
        key_name=view.key_name,
        display_name=view.display_name,
        is_configured=view.is_configured,
        source=view.source,
        masked_value=view.masked_value,
        url=view.url,
    )


def _model_req_to_response(view: ModelApiKeyRequirementView) -> ModelRequirementResponse:
    """模型要求视图转响应。"""
    return ModelRequirementResponse(
        model_name=view.model_name,
        required_key=view.required_key,
        key_display_name=view.key_display_name,
        is_available=view.is_available,
    )


def _model_update_to_response(view: SceneDefaultModelUpdateView) -> SceneModelUpdateResponse:
    """模型更新视图转响应。"""
    return SceneModelUpdateResponse(
        scene_name=view.scene_name,
        old_model=view.old_model,
        new_model=view.new_model,
    )


def create_settings_router(
    api_key_service: ApiKeyConfigServiceProtocol,
    scene_config_service: SceneConfigServiceProtocol,
) -> Any:
    """创建 settings 路由。

    Args:
        api_key_service: API key 配置服务实例。
        scene_config_service: Scene 配置服务实例。

    Returns:
        FastAPI 路由对象。
    """

    router = APIRouter(prefix="/api/settings", tags=["settings"])

    # === API Key 端点 ===

    @router.get("/api-keys", response_model=list[ApiKeyStatusResponse])
    async def list_api_keys() -> list[ApiKeyStatusResponse]:
        """列出所有 API key 配置状态。"""
        views = api_key_service.list_api_key_status()
        return [_key_status_to_response(v) for v in views]

    @router.put(
        "/api-keys/{key_name}",
        response_model=ApiKeyStatusResponse,
    )
    async def set_api_key(
        key_name: str = Path(description="API key 变量名"),
        body: SetApiKeyRequest = Body(...),
    ) -> ApiKeyStatusResponse:
        """设置 API key。"""
        try:
            api_key_service.set_api_key(key_name, body.value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # 返回更新后的状态
        views = api_key_service.list_api_key_status()
        for view in views:
            if view.key_name == key_name:
                return _key_status_to_response(view)
        raise HTTPException(status_code=500, detail="设置成功但无法获取状态")

    @router.delete("/api-keys/{key_name}")
    async def clear_api_key(
        key_name: str = Path(description="API key 变量名"),
    ) -> dict[str, str]:
        """清空 API key。"""
        try:
            api_key_service.clear_api_key(key_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "cleared", "key_name": key_name}

    # === 模型端点 ===

    @router.get("/models", response_model=list[ModelRequirementResponse])
    async def list_model_requirements() -> list[ModelRequirementResponse]:
        """列出各模型的 API key 要求。"""
        views = api_key_service.get_model_api_key_requirements()
        return [_model_req_to_response(v) for v in views]

    @router.put(
        "/scenes/{scene_name}/default-model",
        response_model=SceneModelUpdateResponse,
    )
    async def update_scene_default_model(
        scene_name: str = Path(description="Scene 名称"),
        body: UpdateSceneModelRequest = Body(...),
    ) -> SceneModelUpdateResponse:
        """更新 scene 的默认模型。"""
        try:
            view = scene_config_service.update_scene_default_model(scene_name, body.model_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _model_update_to_response(view)

    return router


__all__ = ["create_settings_router"]