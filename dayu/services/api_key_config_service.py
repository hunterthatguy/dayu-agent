"""API Key 配置服务。

该服务管理 API key 的存储、读取、设置和清空：
- 存储：`workspace/.dayu/api_keys.json`
- 读取优先级：JSON 文件 > 环境变量 > 空值
- 写入：同时写入 JSON 文件 + 设置当前进程环境变量
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dayu.services.contracts import ApiKeyStatusView, ModelApiKeyRequirementView

_API_KEY_FILE_NAME = "api_keys.json"

# 打码配置：显示前缀长度和后缀长度
_MASK_PREFIX_LEN = 4
_MASK_SUFFIX_LEN = 4
_MASK_MIN_LENGTH = 10  # key 长度小于此值时只显示 ****


def _mask_api_key(value: str) -> str:
    """生成打码后的 API key 显示值。

    规则：
    - 长度 < 10：只显示 `****`
    - 长度 >= 10：显示前4位 + `****` + 后4位

    Args:
        value: 完整 API key 值。

    Returns:
        打码后的显示值。
    """
    if not value:
        return ""
    if len(value) < _MASK_MIN_LENGTH:
        return "****"
    return f"{value[:_MASK_PREFIX_LEN]}****{value[-_MASK_SUFFIX_LEN:]}"

# 用户可配置的 API key 列表（按需求）
_CONFIGURABLE_KEYS: list[str] = [
    "MIMO_PLAN_API_KEY",
    "MIMO_API_KEY",
    "DEEPSEEK_API_KEY",
    "FMP_API_KEY",
    "TAVILY_API_KEY",
    "SERPER_API_KEY",
]

# API key 显示名称
_KEY_DISPLAY_NAMES: dict[str, str] = {
    "MIMO_PLAN_API_KEY": "Mimo Token Plan",
    "MIMO_API_KEY": "Mimo",
    "DEEPSEEK_API_KEY": "DeepSeek",
    "FMP_API_KEY": "FMP",
    "TAVILY_API_KEY": "Tavily",
    "SERPER_API_KEY": "Serper",
}

# API key 申请地址
_KEY_URLS: dict[str, str] = {
    "MIMO_PLAN_API_KEY": "https://platform.xiaomimimo.com/#/console/api-keys",
    "MIMO_API_KEY": "https://platform.xiaomimimo.com/#/console/api-keys",
    "DEEPSEEK_API_KEY": "https://platform.deepseek.com/api_keys",
    "FMP_API_KEY": "https://site.financialmodelingprep.com/developer/docs/dashboard",
    "TAVILY_API_KEY": "https://app.tavily.com/home",
    "SERPER_API_KEY": "https://serper.dev/",
}

# 模型 → 所需 API key 映射（从 llm_models.json 提取）
_MODEL_API_KEY_MAP: dict[str, str] = {
    # Mimo Token Plan 模型（需要 MIMO_PLAN_API_KEY）
    "mimo-v2-plan": "MIMO_PLAN_API_KEY",
    "mimo-v2-plan-thinking": "MIMO_PLAN_API_KEY",
    # Mimo 普通模型（需要 MIMO_API_KEY）
    "mimo-v2-pro": "MIMO_API_KEY",
    "mimo-v2-pro-thinking": "MIMO_API_KEY",
    "mimo-v2-flash": "MIMO_API_KEY",
    "mimo-v2-flash-thinking": "MIMO_API_KEY",
    # DeepSeek 模型
    "deepseek-chat": "DEEPSEEK_API_KEY",
    "deepseek-thinking": "DEEPSEEK_API_KEY",
    # Qwen 模型（需要 QWEN_API_KEY，暂不支持 WebUI 配置）
    "qwen3": "QWEN_API_KEY",
    "qwen3-thinking": "QWEN_API_KEY",
    "qwen3:30b-thinking": "QWEN_API_KEY",
    # 其他模型（需要对应 API Key，暂不支持 WebUI 配置）
    "gpt-5.4": "OPENAI_API_KEY",
    "claude-sonnet-4-6": "ANTHROPIC_API_KEY",
    "gemini-2.5-flash": "GEMINI_API_KEY",
    "glm-5": "GLM_API_KEY",
}


@dataclass(frozen=True)
class ApiKeyConfigService:
    """API Key 配置服务。

    Attributes:
        dayu_dir: `.dayu` 目录路径（通常为 `workspace/.dayu`）。
    """

    dayu_dir: Path

    def _get_keys_file_path(self) -> Path:
        """返回 API keys JSON 文件路径。"""
        return self.dayu_dir / _API_KEY_FILE_NAME

    def _read_keys_from_file(self) -> dict[str, str]:
        """从 JSON 文件读取已保存的 API keys。"""
        file_path = self._get_keys_file_path()
        if not file_path.exists():
            return {}
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return {}
            # 只返回字符串类型的值
            return {k: str(v) for k, v in data.items() if isinstance(v, str)}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_keys_to_file(self, keys: dict[str, str]) -> None:
        """将 API keys 写入 JSON 文件。"""
        file_path = self._get_keys_file_path()
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(keys, ensure_ascii=False, indent=2) + "\n"
        file_path.write_text(content, encoding="utf-8")

    def list_api_key_status(self) -> list[ApiKeyStatusView]:
        """返回所有可配置 API key 的状态列表。"""
        file_keys = self._read_keys_from_file()
        result: list[ApiKeyStatusView] = []
        for key_name in _CONFIGURABLE_KEYS:
            file_value = file_keys.get(key_name)
            env_value = os.environ.get(key_name)
            if file_value:
                # JSON 文件中有值
                result.append(ApiKeyStatusView(
                    key_name=key_name,
                    display_name=_KEY_DISPLAY_NAMES.get(key_name, key_name),
                    is_configured=True,
                    source="file",
                    masked_value=_mask_api_key(file_value),
                    url=_KEY_URLS.get(key_name, ""),
                ))
            elif env_value:
                # 环境变量中有值
                result.append(ApiKeyStatusView(
                    key_name=key_name,
                    display_name=_KEY_DISPLAY_NAMES.get(key_name, key_name),
                    is_configured=True,
                    source="env",
                    masked_value=_mask_api_key(env_value),
                    url=_KEY_URLS.get(key_name, ""),
                ))
            else:
                # 未配置
                result.append(ApiKeyStatusView(
                    key_name=key_name,
                    display_name=_KEY_DISPLAY_NAMES.get(key_name, key_name),
                    is_configured=False,
                    source="",
                    masked_value="",
                    url=_KEY_URLS.get(key_name, ""),
                ))
        return result

    def get_api_key(self, key_name: str) -> str | None:
        """获取指定 API key 的值。"""
        # 优先从文件读取
        file_keys = self._read_keys_from_file()
        if key_name in file_keys:
            return file_keys[key_name]
        # 其次从环境变量读取
        return os.environ.get(key_name)

    def set_api_key(self, key_name: str, value: str) -> None:
        """设置 API key。"""
        if key_name not in _CONFIGURABLE_KEYS:
            raise ValueError(f"不支持配置 {key_name}")
        if not value.strip():
            raise ValueError("API key 不能为空")
        # 读取现有 keys
        file_keys = self._read_keys_from_file()
        # 更新
        file_keys[key_name] = value.strip()
        # 写入文件
        self._write_keys_to_file(file_keys)
        # 设置环境变量（当前进程）
        os.environ[key_name] = value.strip()

    def clear_api_key(self, key_name: str) -> None:
        """清空 API key。"""
        if key_name not in _CONFIGURABLE_KEYS:
            raise ValueError(f"不支持配置 {key_name}")
        # 读取现有 keys
        file_keys = self._read_keys_from_file()
        # 删除
        if key_name in file_keys:
            del file_keys[key_name]
            self._write_keys_to_file(file_keys)
        # 清除环境变量（当前进程）
        if key_name in os.environ:
            del os.environ[key_name]

    def get_model_api_key_requirements(self) -> list[ModelApiKeyRequirementView]:
        """返回各模型的 API key 要求。"""
        result: list[ModelApiKeyRequirementView] = []
        for model_name, key_name in _MODEL_API_KEY_MAP.items():
            is_available = bool(self.get_api_key(key_name))
            result.append(ModelApiKeyRequirementView(
                model_name=model_name,
                required_key=key_name,
                key_display_name=_KEY_DISPLAY_NAMES.get(key_name, key_name),
                is_available=is_available,
            ))
        return result

    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用（是否配置了所需 API key）。"""
        key_name = _MODEL_API_KEY_MAP.get(model_name)
        if not key_name:
            # 模型不在映射中，假设可用（如本地模型）
            return True
        return bool(self.get_api_key(key_name))


__all__ = ["ApiKeyConfigService"]