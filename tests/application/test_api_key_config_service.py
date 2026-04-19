"""ApiKeyConfigService 单测。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dayu.services.api_key_config_service import ApiKeyConfigService


@pytest.fixture
def temp_dayu_dir(tmp_path: Path) -> Path:
    """创建临时 .dayu 目录。"""
    dayu_dir = tmp_path / ".dayu"
    dayu_dir.mkdir(parents=True)
    return dayu_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理测试可能影响的 API key 环境变量。"""
    for key in [
        "MIMO_PLAN_API_KEY",
        "MIMO_API_KEY",
        "DEEPSEEK_API_KEY",
        "FMP_API_KEY",
        "TAVILY_API_KEY",
        "SERPER_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
def test_load_all_keys_to_environment_loads_from_file(
    temp_dayu_dir: Path,
    clean_env: None,
) -> None:
    """load_all_keys_to_environment 应从 JSON 文件加载 keys 到 os.environ。"""

    # 写入测试 keys 文件
    keys_file = temp_dayu_dir / "api_keys.json"
    test_keys = {
        "MIMO_PLAN_API_KEY": "test_mimo_plan_key_12345",
        "DEEPSEEK_API_KEY": "test_deepseek_key_abcdef",
    }
    keys_file.write_text(json.dumps(test_keys))

    # 创建 service
    service = ApiKeyConfigService(dayu_dir=temp_dayu_dir)

    # 验证环境变量未设置
    assert os.environ.get("MIMO_PLAN_API_KEY") is None
    assert os.environ.get("DEEPSEEK_API_KEY") is None

    # 加载 keys
    loaded_count = service.load_all_keys_to_environment()

    # 验证加载结果
    assert loaded_count == 2
    assert os.environ.get("MIMO_PLAN_API_KEY") == "test_mimo_plan_key_12345"
    assert os.environ.get("DEEPSEEK_API_KEY") == "test_deepseek_key_abcdef"


@pytest.mark.unit
def test_load_all_keys_to_environment_skips_empty_values(
    temp_dayu_dir: Path,
    clean_env: None,
) -> None:
    """load_all_keys_to_environment 应跳过空值。"""

    keys_file = temp_dayu_dir / "api_keys.json"
    test_keys = {
        "MIMO_PLAN_API_KEY": "",
        "DEEPSEEK_API_KEY": "   ",  # 空白字符串
    }
    keys_file.write_text(json.dumps(test_keys))

    service = ApiKeyConfigService(dayu_dir=temp_dayu_dir)
    loaded_count = service.load_all_keys_to_environment()

    assert loaded_count == 0


@pytest.mark.unit
def test_load_all_keys_to_environment_skips_unknown_keys(
    temp_dayu_dir: Path,
    clean_env: None,
) -> None:
    """load_all_keys_to_environment 应跳过不在 _CONFIGURABLE_KEYS 中的 key。"""

    keys_file = temp_dayu_dir / "api_keys.json"
    test_keys = {
        "MIMO_PLAN_API_KEY": "valid_key",
        "UNKNOWN_API_KEY": "should_be_skipped",
    }
    keys_file.write_text(json.dumps(test_keys))

    service = ApiKeyConfigService(dayu_dir=temp_dayu_dir)
    loaded_count = service.load_all_keys_to_environment()

    assert loaded_count == 1
    assert os.environ.get("MIMO_PLAN_API_KEY") == "valid_key"
    assert os.environ.get("UNKNOWN_API_KEY") is None


@pytest.mark.unit
def test_load_all_keys_to_environment_returns_zero_when_no_file(
    temp_dayu_dir: Path,
    clean_env: None,
) -> None:
    """文件不存在时应返回 0。"""

    # 不创建 keys 文件
    service = ApiKeyConfigService(dayu_dir=temp_dayu_dir)
    loaded_count = service.load_all_keys_to_environment()

    assert loaded_count == 0