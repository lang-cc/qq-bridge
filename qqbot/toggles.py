"""插件的开关状态（全局一份，改完立即生效，不用重启）。

配置写在 config.yaml：

    plugins:
      disabled:
        - qqbot.plugins.rules_demo

路由器派发前会问一句 ``is_enabled(插件id)``，被关掉的插件等于不存在。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

log = logging.getLogger("qqbot.toggles")

_disabled: set[str] = set()
_router: Any = None
_config: Any = None


def bind(router: Any, config: Any = None) -> None:
    """由 legacy_bridge 在挂载完老插件后调用，把路由器和配置交进来。"""
    global _router, _config
    _router = router
    if config is not None:
        _config = config
    load()


def load() -> set[str]:
    """从配置里读出被关掉的插件名单。"""
    global _disabled
    raw = dict(getattr(_config, "raw", {}) or {})
    ids = ((raw.get("plugins") or {}).get("disabled") or [])
    _disabled = {str(x) for x in ids if str(x).strip()}
    return _disabled


def disabled() -> set[str]:
    return set(_disabled)


def is_enabled(plugin_id: str) -> bool:
    return plugin_id not in _disabled


def set_disabled(ids: Iterable[str]) -> set[str]:
    global _disabled
    _disabled = {str(x) for x in ids if str(x).strip()}
    log.info("插件开关已更新｜关掉 %d 个：%s", len(_disabled), "、".join(sorted(_disabled)) or "无")
    return set(_disabled)


def toggle(plugin_id: str, enabled: bool) -> set[str]:
    ids = set(_disabled)
    if enabled:
        ids.discard(plugin_id)
    else:
        ids.add(plugin_id)
    return set_disabled(ids)
