"""上网能力：抓网页正文、B 站搜索/热门、网页搜索。全部只读，返回给模型当参考。"""

from __future__ import annotations

import logging
import re
from html import unescape

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
    # 剩下的数字/命名实体（&ensp; &#0183; 之类）统一解码，不然摘要有乱码
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\u2000-\u200f\u2028-\u202f\u2060\ufeff]", " ", text)
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


def _abs(url: str, base: str = "") -> str:
    """补全协议相对 / 站点相对的链接。"""
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base.rstrip("/") + url
    return url


def _parse_bing(html: str, limit: int) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(r'(?is)<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', html):
        block = m.group(0)
        a = re.search(r'(?is)<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not a:
            continue
        p = re.search(r'(?is)<p[^>]*>(.*?)</p>', block)
        out.append({
            "title": _clean(a.group(2)),
            "url": _abs(a.group(1)),
            "snippet": _clean(p.group(1)) if p else "",
        })
        if len(out) >= limit:
            break
    return out


def _parse_so(html: str, limit: int) -> list[dict]:
    """360 搜索：a 标签带 data-mdurl 时优先用它（真实目标页）。"""
    out: list[dict] = []
    for m in re.finditer(r'(?is)<h3[^>]*class="res-title[^"]*"[^>]*>\s*<a([^>]*)>(.*?)</a>', html):
        attrs, inner = m.group(1), m.group(2)
        href = re.search(r'href="([^"]+)"', attrs)
        if not href:
            continue
        md = re.search(r'data-mdurl="([^"]+)"', attrs)
        out.append({
            "title": _clean(inner),
            "url": _abs(md.group(1) if md else href.group(1)),
            "snippet": "",
        })
        if len(out) >= limit:
            break
    return out


def _parse_sogou(html: str, limit: int) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(r'(?is)<h3 class="vr-title".*?</h3>', html):
        a = re.search(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', m.group(0))
        if not a:
            continue
        out.append({
            "title": _clean(a.group(2)),
            "url": _abs(a.group(1), "https://www.sogou.com"),
            "snippet": "",
        })
        if len(out) >= limit:
            break
    return out


def _parse_ddg(html: str, limit: int) -> list[dict]:
    from urllib.parse import unquote

    out: list[dict] = []
    for m in re.finditer(r'(?is)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html):
        href = m.group(1)
        if "uddg=" in href:
            href = unquote(href.split("uddg=")[1].split("&")[0])
        out.append({"title": _clean(m.group(2)), "url": _abs(href), "snippet": ""})
        if len(out) >= limit:
            break
    return out


# 按顺序试，第一个出结果的就用。DuckDuckGo 在国内基本连不上，放最后兜底。
SEARCH_ENGINES = (
    ("bing", "https://cn.bing.com/search?q={q}&setlang=zh-CN", _parse_bing),
    ("360", "https://www.so.com/s?q={q}", _parse_so),
    ("sogou", "https://www.sogou.com/web?query={q}", _parse_sogou),
    ("ddg", "https://html.duckduckgo.com/html/?q={q}", _parse_ddg),
)


async def web_search(query: str, limit: int = 5) -> list[dict]:
    """多源网页搜索，返回 [{title, url, snippet}]。

    以前只用 DuckDuckGo，国内连不上就静默返回空（等于「开了但空转」）。
    现在按 Bing(国内版) → 360 → 搜狗 → DuckDuckGo 顺序兜底，谁先出结果用谁。
    """
    import aiohttp
    from urllib.parse import quote

    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    async with aiohttp.ClientSession() as session:
        for name, tpl, parse in SEARCH_ENGINES:
            url = tpl.format(q=quote(query))
            try:
                async with session.get(url, headers=headers, timeout=12) as resp:
                    html = await resp.text(errors="ignore")
            except Exception as exc:
                log.warning("搜索源 %s 连不上：%r", name, exc)
                continue
            try:
                out = parse(html, limit)
            except Exception as exc:
                log.warning("搜索源 %s 解析失败：%r", name, exc)
                continue
            if out:
                log.info("网页搜索：%s 命中 %d 条（%s）", name, len(out), query[:20])
                return out
            log.warning("搜索源 %s 没解析出结果", name)
    log.warning("网页搜索：所有源都没结果（%s）", query[:30])
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
            snip = (s.get("snippet") or "").strip()
            lines.append(f"- {s['title']} | {s['url']}" + (f"\n  {snip[:160]}" if snip else ""))
    return "\n".join(lines)[:4000]
