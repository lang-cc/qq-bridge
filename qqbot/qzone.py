"""QQ 空间说说：用 NapCat 当前登录态的 cookie 直接发。

登录态来源：NapCat 的 get_cookies（domain=user.qzone.qq.com，里面含 p_skey）。
g_tk 由 p_skey 算出，发布走 emotion_cgi_publish_v6。

注意：这是 QQ 空间的私有接口，不是官方开放能力。发在自己号上，
频率别高（一天一两条），否则可能被限流或删说说。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from .api_result import unwrap

log = logging.getLogger("qqbot.qzone")

PUBLISH_URL = (
    "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def parse_cookies(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out


def gtk(skey: str) -> int:
    h = 5381
    for ch in skey or "":
        h += (h << 5) + ord(ch)
    return h & 0x7FFFFFFF


def uin_of(cookies: dict[str, str]) -> str:
    u = cookies.get("uin") or cookies.get("p_uin") or cookies.get("pt2gguin") or ""
    return u[1:] if u.startswith("o") else u


async def fetch_cookies(bot, domain: str = "user.qzone.qq.com") -> dict[str, str]:
    """从协议端取当前登录态 cookie。"""
    try:
        res = await bot.call_api("get_cookies", domain=domain)
    except Exception as exc:
        log.error("取 cookie 失败：%r", exc)
        return {}
    data = unwrap(res) if isinstance(res, dict) else None
    raw = (data or {}).get("cookies") if isinstance(data, dict) else None
    return parse_cookies(raw or "")


def publish_sync(cookies: dict[str, str], content: str, timeout: int = 25) -> dict:
    """发一条纯文字说说，返回接口原始结果。"""
    skey = cookies.get("p_skey") or cookies.get("skey") or ""
    uin = uin_of(cookies)
    if not uin or not skey:
        return {"ok": False, "error": "没拿到登录态（缺 uin/p_skey）"}

    params = {
        "syn_tweet_verson": "1",
        "paramstr": "1",
        "who": "1",
        "con": content,
        "feedversion": "1",
        "ver": "1",
        "ugc_right": "1",
        "to_sign": "0",
        "hostuin": uin,
        "code_version": "1",
        "format": "json",
        "qzreferrer": f"https://user.qzone.qq.com/{uin}",
    }
    url = f"{PUBLISH_URL}?g_tk={gtk(skey)}"
    body = urllib.parse.urlencode(params, encoding="utf-8").encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "Referer": f"https://user.qzone.qq.com/{uin}",
            "Origin": "https://user.qzone.qq.com",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except Exception as exc:
        return {"ok": False, "error": repr(exc)[:200]}

    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "返回不是 JSON", "raw": raw[:300]}

    code = data.get("code")
    feedid = ((data.get("data") or {}) if isinstance(data.get("data"), dict) else {}).get("feedid") or data.get("feedid")
    ok = str(code) in ("0", "None") or bool(feedid)
    if not ok:
        return {"ok": False, "error": f"code={code} msg={data.get('message') or data.get('subcode')}", "raw": raw[:300]}
    return {"ok": True, "feedid": str(feedid or ""), "url": f"https://user.qzone.qq.com/{uin}/mood/{feedid}" if feedid else ""}


async def publish(bot, content: str) -> dict:
    cookies = await fetch_cookies(bot)
    if not cookies:
        return {"ok": False, "error": "拿不到 QQ 空间登录态，可能空间没开通或登录已失效"}
    import asyncio

    return await asyncio.get_event_loop().run_in_executor(None, publish_sync, cookies, content)
