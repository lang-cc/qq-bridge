"""OneBot API 返回值的统一拆包。

同一个 action，不同协议端/框架返回形状不一样：
    直接给数据：      [ {...} ]  或  {"cookies": "..."}
    整包给：           {"status": "ok", "retcode": 0, "data": [...] }
老适配器（自研）返回的是「数据本身」，NoneBot2 的 Bot.call_api 也是；
但有些协议端会把 data 再包一层。这里两种都吃，避免功能悄悄失效。
"""

from __future__ import annotations

from typing import Any


def unwrap(res: Any) -> Any:
    if isinstance(res, dict) and "data" in res:
        # 只有长成 OneBot「整包」的样子才拆（有 status/retcode，或者除 data 外没别的键）
        keys = set(res)
        if keys & {"status", "retcode", "msg", "wording"} or keys == {"data"}:
            return res.get("data")
    return res
