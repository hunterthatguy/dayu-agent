"""FastAPI Web UI 骨架。"""

from __future__ import annotations

from pathlib import Path

from dayu.services.protocols import (
    ApiKeyConfigServiceProtocol,
    ChatServiceProtocol,
    FinsServiceProtocol,
    HostAdminServiceProtocol,
    PortfolioBrowsingServiceProtocol,
    PromptServiceProtocol,
    ReplyDeliveryServiceProtocol,
    SceneConfigServiceProtocol,
)
from dayu.web.routes.sessions import create_session_router
from dayu.web.routes.runs import create_run_router
from dayu.web.routes.events import create_events_router
from dayu.web.routes.chat import create_chat_router
from dayu.web.routes.prompt import create_prompt_router
from dayu.web.routes.reply_outbox import create_reply_outbox_router
from dayu.web.routes.write import create_write_router
from dayu.web.routes.fins import create_fins_router
from dayu.web.routes.portfolio import create_portfolio_router
from dayu.web.routes.config import create_config_router
from dayu.web.routes.upload import create_upload_router
from dayu.web.routes.settings import create_settings_router


def create_fastapi_app(
    *,
    chat_service: ChatServiceProtocol,
    prompt_service: PromptServiceProtocol,
    fins_service: FinsServiceProtocol,
    host_admin_service: HostAdminServiceProtocol,
    reply_delivery_service: ReplyDeliveryServiceProtocol,
    portfolio_browsing_service: PortfolioBrowsingServiceProtocol,
    scene_config_service: SceneConfigServiceProtocol,
    api_key_config_service: ApiKeyConfigServiceProtocol,
    static_dir: Path | None = None,
    cors_allow_origins: tuple[str, ...] = (),
):
    """创建 FastAPI 应用骨架。

    Args:
        chat_service: 聊天服务实例。
        prompt_service: 单轮 prompt 服务实例。
        fins_service: 财报服务实例。
        host_admin_service: 宿主管理服务实例。
        reply_delivery_service: 回复投递服务实例。
        portfolio_browsing_service: portfolio 浏览服务实例。
        scene_config_service: scene 配置服务实例。
        api_key_config_service: API key 配置服务实例。
        static_dir: 前端构建产物目录；用于生产部署。
        cors_allow_origins: CORS 允许的 origins；用于开发环境。

    Returns:
        FastAPI 应用实例。

    Raises:
        RuntimeError: 未安装 fastapi 时抛出。
    """

    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover - 依赖是否安装由环境决定
        raise RuntimeError("未安装 fastapi，无法创建 Web UI 入口") from exc

    app = FastAPI(title="Dayu Web")

    # CORS 中间件（开发环境用）
    if cors_allow_origins:
        try:
            from fastapi.middleware.cors import CORSMiddleware
        except ImportError:  # pragma: no cover
            pass
        else:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=list(cors_allow_origins),
                allow_methods=["*"],
                allow_headers=["*"],
            )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """健康检查路由。"""

        return {"status": "ok"}

    # 挂载所有 API 路由（先于 static 挂载，避免被 catch-all 吞掉）
    app.include_router(create_session_router(host_admin_service))
    app.include_router(create_run_router(host_admin_service))
    app.include_router(create_events_router(host_admin_service))
    app.include_router(create_chat_router(chat_service, reply_delivery_service))
    app.include_router(create_prompt_router(prompt_service))
    app.include_router(create_reply_outbox_router(reply_delivery_service))
    app.include_router(create_write_router())
    app.include_router(create_fins_router(fins_service))
    app.include_router(create_portfolio_router(portfolio_browsing_service))
    app.include_router(create_config_router(scene_config_service))
    app.include_router(create_upload_router(fins_service, host_admin_service, portfolio_browsing_service))
    app.include_router(create_settings_router(api_key_config_service, scene_config_service))

    # 静态文件挂载（生产部署用）
    if static_dir is not None:
        try:
            from fastapi.staticfiles import StaticFiles
        except ImportError:  # pragma: no cover
            pass
        else:
            app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app


__all__ = ["create_fastapi_app"]
