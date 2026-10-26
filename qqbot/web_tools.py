"""上网能力：抓网页正文、B 站搜索/热门、网页搜索。全部只读，返回给模型当参考。"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("qqbot.web")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

URL_RE = re.compile(r"https?://[^\s<>\"'）)】\]]+")


def find_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def _clean(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</(p|div|li|h[1-6]|tr)>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def fetch_text(url: str, max_chars: int = 2500) -> dict:
    """抓网页，返回 {ok, title, text, url}。"""
    import aiohttp

    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=25, allow_redirects=True) as r:
                raw = await r.text(errors="ignore")
                final = str(r.url)
        title = ""
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        if m:
            title = _clean(m.group(1))[:120]
        body = _clean(raw)
        # 去掉重复的导航噪声：取最长的连续段落区域
        return {"ok": True, "url": final, "title": title, "text": body[:max_chars]}
    except Exception as exc:
        log.warning("抓取失败 %s：%r", url, exc)
        return {"ok": False, "url": url, "error": repr(exc)}


async def bilibili_search(keyword: str, limit: int = 5) -> list[dict]:
    """B 站视频搜索，返回 [{title, url, author, play, duration}]。"""
    import aiohttp
    from urllib.parse import quote

    url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={quote(keyword)}"
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=20) as r:
                data = await r.json(content_type=None)
        items = ((data.get("data") or {}).get("result") or [])
        out = []
        for it in items[:limit]:
            title = re.sub(r"(?s)<[^>]+>", "", it.get("title") or "")
            bvid = it.get("bvid") or ""
            out.append(
                {
                    "title": title,
                    "url": f"https://www.bilibili.com/video/{bvid}" if bvid else it.get("arcurl", ""),
                    "author": it.get("author") or "",
                    "play": it.get("play") or 0,
                    "duration": it.get("duration") or "",
                }
            )
        return out
    except Exception as exc:
        log.warning("B 站搜索失败：%r", exc)
        return []


async def bilibili_hot(limit: int = 5) -> list[dict]:
    """B 站综合热门。"""
    import aiohttp

    url = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=20) as r:
                data = await r.json(content_type=None)
        items = ((data.get("data") or {}).get("list") or [])
        return [
            {
                "title": it.get("title") or "",
                "url": it.get("short_link_v2") or f"https://www.bilibili.com/video/{it.get('bvid','')}",
                "author": (it.get("owner") or {}).get("name", ""),
                "play": (it.get("stat") or {}).get("view", 0),
            }
            for it in items[:limit]
        ]
    except Exception as exc:
        log.warning("B 站热门失败：%r", exc)
        return []


async def bilibili_video_info(bvid: str) -> dict:
    """单个视频的标题/简介/播放数据，用来「看完说两句」。"""
    import aiohttp

    if not bvid:
        return {}
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=20) as r:
                data = await r.json(content_type=None)
        d = data.get("data") or {}
        if not d:
            return {}
        stat = d.get("stat") or {}
        return {
            "title": d.get("title") or "",
            "desc": (d.get("desc") or "")[:300],
            "author": (d.get("owner") or {}).get("name", ""),
            "duration": d.get("duration") or 0,
            "view": stat.get("view") or 0,
            "like": stat.get("like") or 0,
            "danmaku": stat.get("danmaku") or 0,
            "url": f"https://www.bilibili.com/video/{bvid}",
        }
    except Exception as exc:
        log.warning("B 站视频详情失败：%r", exc)
        return {}


async def bilibili_feed(keyword: str = "", limit: int = 6) -> list[dict]:
    """要分享时用：有关键词就搜，没有就取热门。"""
    items = await bilibili_search(keyword, limit=limit) if keyword else []
    if not items:
        items = await bilibili_hot(limit=limit)
    return items


def bvid_of(item: dict) -> str:
    url = item.get("url") or ""
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    return m.group(1) if m else ""


async def douyin_hot(limit: int = 10) -> list[dict]:
    """抖音热榜。两条线：抖音官方 billboard 接口 → 聚合站兜底。"""
    import aiohttp
    from urllib.parse import quote

    sources = [
        "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
        "https://api.codelife.cc/api/top/list?lang=cn&id=DpQvNABoNE",
    ]
    headers = {"User-Agent": UA, "Referer": "https://www.douyin.com/"}
    for url in sources:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers, timeout=20) as r:
                    data = await r.json(content_type=None)
        except Exception as exc:
            log.warning("抖音热榜取数失败（%s）：%r", url.split("/")[2], exc)
            continue
        items = data.get("word_list") or []
        if not items and isinstance(data.get("data"), list):
            items = data["data"]
        out = []
        for it in items[:limit]:
            word = (it.get("word") or it.get("title") or "").strip()
            if not word:
                continue
            out.append(
                {
                    "title": word,
                    "url": it.get("link") or f"https://www.douyin.com/search/{quote(word)}",
                    "hot": it.get("hot_value") or it.get("hotValue") or "",
                }
            )
        if out:
            return out
    return []


async def web_search(query: str, limit: int = 5) -> list[dict]:
    """DuckDuckGo HTML 版搜索，返回 [{title, url, snippet}]。"""
    import aiohttp
    from urllib.parse import quote, unquote

    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {"User-Agent": UA}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=25) as r:
                html = await r.text(errors="ignore")
        out = []
        for m in re.finditer(r'(?is)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html):
            href, title = m.group(1), _clean(m.group(2))
            if "uddg=" in href:
                href = unquote(href.split("uddg=")[1].split("&")[0])
            out.append({"title": title, "url": href})
            if len(out) >= limit:
                break
        return out
    except Exception as exc:
        log.warning("网页搜索失败：%r", exc)
        return []


def context_block(pages: list[dict], bili: list[dict] | None = None, search: list[dict] | None = None) -> str:
    """把工具结果压成给模型看的参考资料。"""
    lines = []
    if pages:
        lines.append("【网页内容】")
        for p in pages:
            if p.get("ok"):
                lines.append(f"- {p.get('title') or p['url']}（{p['url']}）\n{p['text'][:1200]}")
    if bili:
        lines.append("【B 站视频】")
        for v in bili:
            lines.append(f"- {v['title']} | UP:{v['author']} | 播放:{v['play']} | {v['url']}")
    if search:
        lines.append("【搜索结果】")
        for s in search:
            lines.append(f"- {s['title']} | {s['url']}")
    return "\n".join(lines)[:4000]
