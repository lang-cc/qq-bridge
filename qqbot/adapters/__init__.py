from __future__ import annotations

from typing import Any

from .base import Adapter


def get_adapter(name: str, cfg: dict | None = None) -> Adapter:
    """按名字挑适配器。新增平台就在这里注册。"""
    from .official import OfficialAdapter
    from .onebot11 import OneBot11Adapter

    registry: dict[str, Any] = {
        "onebot11": OneBot11Adapter,
        "official": OfficialAdapter,
    }
    key = (name or "").strip().lower()
    if key not in registry:
        raise ValueError(f"未知适配器 {name!r}，可选: {', '.join(registry)}")
    return registry[key](cfg or {})


__all__ = ["Adapter", "get_adapter"]
