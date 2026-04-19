"""Web UI CLI 子命令。

该模块实现 ``dayu web`` 子命令，启动 FastAPI Web 服务器。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from dayu.log import Log

_MODULE = "web_command"

# 包内 prompts 目录路径
_PACKAGE_PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"


def run_web_command(args: object) -> int:
    """执行 web 子命令。

    Args:
        args: 命令行参数对象。

    Returns:
        退出码，0 表示成功。

    Raises:
        无。
    """

    from dayu.cli.dependency_setup import (
        _prepare_cli_host_dependencies,
        _build_chat_service,
        _build_prompt_service,
        setup_paths,
        setup_loglevel,
    )
    import argparse

    setup_loglevel(args)
    paths_config = setup_paths(cast(argparse.Namespace, args))
    workspace_dir = paths_config.workspace_dir

    Log.info(f"工作目录: {workspace_dir}", module=_MODULE)

    # 解析参数
    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 9000)
    static_dir_str = getattr(args, "static_dir", None)
    reload = getattr(args, "reload", False)
    cors_origins_str = getattr(args, "cors_allow_origins", None)

    static_dir = Path(static_dir_str) if static_dir_str else None
    cors_allow_origins: tuple[str, ...] = ()
    if cors_origins_str:
        cors_allow_origins = tuple(cors_origins_str.split(","))
    else:
        # 开发环境默认允许前端端口
        cors_allow_origins = ("http://localhost:5175", "http://127.0.0.1:5175")

    # 装配依赖（Web 需要 event bus 支持 SSE）
    (
        workspace,
        _default_execution_options,
        scene_execution_acceptance_preparer,
        host_admin_service,
        fins_runtime,
    ) = _prepare_cli_host_dependencies(
        workspace_config=paths_config,
        execution_options=None,
        enable_event_bus=True,
    )

    chat_service = _build_chat_service(
        host=host_admin_service,
        scene_execution_acceptance_preparer=scene_execution_acceptance_preparer,
        fins_runtime=fins_runtime,
    )
    prompt_service = _build_prompt_service(
        host=host_admin_service,
        scene_execution_acceptance_preparer=scene_execution_acceptance_preparer,
        fins_runtime=fins_runtime,
    )

    # 构建 portfolio browsing service
    portfolio_browsing_service = _build_portfolio_browsing_service(workspace_dir)

    # 构建 scene config service
    scene_config_service = _build_scene_config_service(workspace_dir)

    # 构建 api key config service
    api_key_config_service = _build_api_key_config_service(workspace_dir)

    # 将已保存的 API keys 加载到环境变量（确保 ConfigLoader 能正确读取）
    loaded_keys = api_key_config_service.load_all_keys_to_environment()
    if loaded_keys > 0:
        Log.info(f"已从配置文件加载 {loaded_keys} 个 API keys 到环境变量", module=_MODULE)

    # 构建 fins service
    from dayu.services.fins_service import FinsService

    fins_service = FinsService(host=host_admin_service, fins_runtime=fins_runtime)

    # 构建 reply delivery service
    from dayu.services.reply_delivery_service import ReplyDeliveryService

    reply_delivery_service = ReplyDeliveryService(host=host_admin_service)

    # 创建 FastAPI 应用
    from dayu.web.fastapi_app import create_fastapi_app

    app = create_fastapi_app(
        chat_service=chat_service,
        prompt_service=prompt_service,
        fins_service=fins_service,
        host_admin_service=cast(Any, host_admin_service),
        reply_delivery_service=reply_delivery_service,
        portfolio_browsing_service=cast(Any, portfolio_browsing_service),
        scene_config_service=cast(Any, scene_config_service),
        api_key_config_service=cast(Any, api_key_config_service),
        static_dir=static_dir,
        cors_allow_origins=cors_allow_origins,
    )

    # 启动 uvicorn
    Log.info(f"启动 Web UI: http://{host}:{port}", module=_MODULE)

    try:
        import uvicorn  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        Log.error("未安装 uvicorn，无法启动 Web UI", module=_MODULE)
        return 1

    uvicorn.run(  # pyright: ignore[reportMissingImports]
        app,
        host=host,
        port=port,
        reload=reload,
    )

    return 0


def _build_portfolio_browsing_service(workspace_dir: Path) -> object:
    """构建 PortfolioBrowsingService 实例。

    Args:
        workspace_dir: 工作区根目录。

    Returns:
        PortfolioBrowsingService 实例。

    Raises:
        无。
    """

    from dayu.fins.storage import (
        FsCompanyMetaRepository,
        FsSourceDocumentRepository,
        FsProcessedDocumentRepository,
        FsDocumentBlobRepository,
        FsFilingMaintenanceRepository,
    )

    portfolio_root = workspace_dir / "portfolio"

    # 使用 repository factory 构建
    try:
        from dayu.fins.storage._fs_repository_factory import build_fs_repository_set
    except ImportError:
        # 回退方案：直接创建
        repository_set = None
    else:
        # 传入 workspace_dir 而非 portfolio_root，因为 FsStorageCore 会自动加 portfolio
        repository_set = build_fs_repository_set(workspace_root=workspace_dir)

    from dayu.services.portfolio_browsing_service import PortfolioBrowsingService

    return PortfolioBrowsingService(
        company_meta_repository=FsCompanyMetaRepository(
            workspace_dir,
            repository_set=repository_set,
        ),
        source_document_repository=FsSourceDocumentRepository(
            workspace_dir,
            repository_set=repository_set,
        ),
        processed_document_repository=FsProcessedDocumentRepository(
            workspace_dir,
            repository_set=repository_set,
        ),
        document_blob_repository=FsDocumentBlobRepository(
            workspace_dir,
            repository_set=repository_set,
        ),
        filing_maintenance_repository=FsFilingMaintenanceRepository(
            workspace_dir,
            repository_set=repository_set,
        ),
    )


def _build_api_key_config_service(workspace_dir: Path) -> object:
    """构建 ApiKeyConfigService 实例。

    Args:
        workspace_dir: 工作区根目录。

    Returns:
        ApiKeyConfigService 实例。

    Raises:
        无。
    """

    from dayu.services.api_key_config_service import ApiKeyConfigService

    dayu_dir = workspace_dir / ".dayu"
    return ApiKeyConfigService(dayu_dir=dayu_dir)


def _build_scene_config_service(workspace_dir: Path) -> object:
    """构建 SceneConfigService 实例。

    Args:
        workspace_dir: 工作区根目录。

    Returns:
        SceneConfigService 实例。

    Raises:
        无。
    """

    from dayu.services.internal.prompt_document_repository import PromptDocumentRepository
    from dayu.services.scene_config_service import SceneConfigService

    workspace_prompts_dir = workspace_dir / "config" / "prompts"

    # 构建 PromptDocumentRepository
    repository = PromptDocumentRepository(
        workspace_prompts_dir=workspace_prompts_dir if workspace_prompts_dir.exists() else None,
        package_prompts_dir=_PACKAGE_PROMPTS_DIR,
    )

    # 构建 PromptFragmentAssetStore（使用默认实现）
    asset_store = _DefaultPromptFragmentAssetStore(
        workspace_prompts_dir=workspace_prompts_dir if workspace_prompts_dir.exists() else None,
        package_prompts_dir=_PACKAGE_PROMPTS_DIR,
    )

    return SceneConfigService(
        prompt_asset_store=cast(Any, asset_store),
        prompt_document_repository=repository,
    )


class _DefaultPromptFragmentAssetStore:
    """默认 PromptFragmentAssetStore 实现。

    从工作区和包内 prompts 目录读取 fragment 模板与 scene manifest。
    """

    workspace_prompts_dir: Path | None
    package_prompts_dir: Path

    def __init__(
        self,
        *,
        workspace_prompts_dir: Path | None,
        package_prompts_dir: Path,
    ) -> None:
        """初始化资产仓储。"""

        self.workspace_prompts_dir = workspace_prompts_dir
        self.package_prompts_dir = package_prompts_dir

    def load_scene_manifest(self, scene_name: str) -> dict[str, object]:
        """读取 scene manifest JSON。"""

        import json

        manifest_path = f"manifests/{scene_name}.json"

        # 工作区优先
        if self.workspace_prompts_dir is not None:
            ws_path = self.workspace_prompts_dir / manifest_path
            if ws_path.exists():
                return json.loads(ws_path.read_text())

        # 回退到包内
        pkg_path = self.package_prompts_dir / manifest_path
        if pkg_path.exists():
            return json.loads(pkg_path.read_text())

        raise FileNotFoundError(f"未找到 scene manifest: {scene_name}")

    def load_fragment_template(
        self,
        fragment_path: str,
        *,
        required: bool = True,
    ) -> str | None:
        """读取 fragment 模板文件。"""

        # 工作区优先
        if self.workspace_prompts_dir is not None:
            ws_path = self.workspace_prompts_dir / fragment_path
            if ws_path.exists():
                return ws_path.read_text()

        # 回退到包内
        pkg_path = self.package_prompts_dir / fragment_path
        if pkg_path.exists():
            return pkg_path.read_text()

        if required:
            raise FileNotFoundError(f"未找到 fragment: {fragment_path}")
        return None


__all__ = ["run_web_command"]