#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置加载器
加载顺序：config.json → .env 文件 → 环境变量（最高优先级）
"""

import os
import json
from typing import Optional

from dotenv import load_dotenv

_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config: Optional[dict] = None


def load_config() -> dict:
    global _config

    config_path = os.path.join(_SERVICE_DIR, 'config.json')
    example_path = os.path.join(_SERVICE_DIR, 'config.example.json')

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    elif os.path.exists(example_path):
        print("[config] config.json 不存在，使用 config.example.json 默认值")
        with open(example_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        print("[config] 未找到配置文件，使用内置默认值")
        cfg = _builtin_defaults()

    for key, default in _builtin_defaults().items():
        if key not in cfg:
            cfg[key] = default
        elif isinstance(default, dict):
            for k, v in default.items():
                if k not in cfg[key]:
                    cfg[key][k] = v

    env_path = os.path.join(_SERVICE_DIR, '.env')
    load_dotenv(env_path, override=True)

    _apply_env_overrides(cfg)
    _resolve_paths(cfg)

    _config = cfg
    return cfg


def get_config() -> dict:
    global _config
    if _config is None:
        load_config()
    return _config


def get_service_dir() -> str:
    return _SERVICE_DIR


def _builtin_defaults() -> dict:
    return {
        "llm": {"provider": "openai", "base_url": "", "api_key": "", "model": "deepseek-chat"},
        "user": {"name": "主人"},
        "pet": {"name": "来福", "personality": "活泼、忠诚、有点粘人、偶尔调皮",
                "obedience": 60, "snark": 30},
        "tts": {"provider": "edge", "voice": "zh-CN-XiaoxiaoNeural"},
        "stt": {"provider": "whisper", "model": "small"},
        "image": {"provider": "siliconflow", "base_url": "https://api.siliconflow.cn/v1",
                  "api_key": "", "model": "black-forest-labs/FLUX.1-schnell"},
        "server": {"host": "127.0.0.1", "port": 18765},
        "paths": {"whisper_model": "", "embedding_model": "", "data_dir": "data",
                  "gpt_sovits_dir": "", "gpt_sovits_port": 9880},
    }


def _apply_env_overrides(cfg: dict) -> None:
    _override(cfg, "llm", "api_key", "LLM_API_KEY")
    _override(cfg, "image", "api_key", "IMAGE_API_KEY")
    _override(cfg, "server", "host", "PYTHON_HOST")
    _override_int(cfg, "server", "port", "PYTHON_PORT")
    _override(cfg, "paths", "whisper_model", "WHISPER_MODEL_PATH")
    _override(cfg, "paths", "embedding_model", "EMBEDDING_MODEL_PATH")
    _override(cfg, "paths", "gpt_sovits_dir", "GPT_SOVITS_DIR")
    _override_int(cfg, "paths", "gpt_sovits_port", "GPT_SOVITS_PORT")
    _override(cfg, "paths", "data_dir", "DATA_DIR")


def _override(cfg, section, key, env_var):
    val = os.getenv(env_var)
    if val:
        cfg[section][key] = val


def _override_int(cfg, section, key, env_var):
    val = os.getenv(env_var)
    if val:
        try:
            cfg[section][key] = int(val)
        except ValueError:
            pass


def _resolve_paths(cfg: dict) -> None:
    paths = cfg.get("paths", {})
    data_dir = paths.get("data_dir", "data")
    if data_dir and not os.path.isabs(data_dir):
        paths["data_dir"] = os.path.normpath(os.path.join(_SERVICE_DIR, data_dir))
    else:
        paths["data_dir"] = data_dir or os.path.join(_SERVICE_DIR, "data")
