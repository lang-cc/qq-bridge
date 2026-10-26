from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # 没装 PyYAML 时退化为 JSON 配置
    yaml = None

DEFAULTS: dict[str, Any] = {
    "adapter": "onebot11",
    "log_level": "INFO",
    "onebot11": {
        "mode": "reverse_ws",
        "access_token": "",
        "api_timeout": 20,
        "reverse": {"host": "0.0.0.0", "port": 8199, "path": "/onebot/v11/ws", "strict_path": False},
        "forward": {"url": "ws://127.0.0.1:3001"},
        "http": {"base_url": "http://127.0.0.1:3000"},
    },
    "http_api": {"enabled": True, "host": "127.0.0.1", "port": 8088, "token": ""},
    "official": {"app_id": "", "app_secret": "", "intents": 1 << 25, "sandbox": False},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    raw: dict = field(default_factory=dict)

    @property
    def adapter(self) -> str:
        return str(self.raw.get("adapter") or "onebot11")

    @property
    def log_level(self) -> str:
        return str(self.raw.get("log_level") or "INFO")

    def section(self, name: str) -> dict:
        return self.raw.get(name) or {}

    def reload(self, path: str | Path = "config.yaml") -> None:
        """从磁盘重读配置（控制台改完配置后调用，机器人无需重启）。"""
        fresh = load_config(path)
        self.raw.clear()
        self.raw.update(fresh.raw)

    def override(self, **kwargs: Any) -> None:
        """命令行覆盖，例如 adapter=official / onebot11.mode=forward_ws。"""
        for key, value in kwargs.items():
            if value is None:
                continue
            target = self.raw
            parts = key.split(".")
            for p in parts[:-1]:
                target = target.setdefault(p, {})
            target[parts[-1]] = value


def load_config(path: str | Path = "config.yaml") -> Config:
    path = Path(path)
    data: dict = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            if yaml is None:
                raise RuntimeError("读取 YAML 配置需要 PyYAML，请 pip install PyYAML 或改用 config.json")
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text or "{}")
    else:
        logging.getLogger("qqbot").warning("配置文件 %s 不存在，使用默认配置", path)
    return Config(_deep_merge(DEFAULTS, data))
