"""抖音：通过本机 Chrome（CDP）读推荐流，抓标题/作者/链接。

前提：Chrome 以 --remote-debugging-port=9222 --user-data-dir=data/browser-douyin 启动，
用户扫码登录过一次。签名接口（a_bogus）我们不碰，直接读渲染后的 DOM。
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from pathlib import Path
from urllib.parse import quote

from . import cdp

log = logging.getLogger("qqbot.douyin")

EXTRACT_JS = r"""
(() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="/video/"]').forEach(a => {
    const href = a.href.split('?')[0];
    if (!href || seen.has(href)) return;
    const card = a.closest('li') || a.closest('div');
    let title = (a.getAttribute('title') || a.innerText || '').trim();
    if (!title && card) title = (card.innerText || '').split('\n')[0].trim();
    const author = card ? ((card.innerText || '').match(/@[\u4e00-\u9fa5\w\-·]+/) || [''])[0] : '';
    if (title.length >= 4) { seen.add(href); out.push({title: title.slice(0, 60), url: href, author: author}); }
  });
  return JSON.stringify(out.slice(0, 30));
})()
"""


TEXT_JS = "document.body.innerText.slice(0, 4000)"


def parse_cards(text: str, limit: int = 10) -> list[dict]:
    """从推荐流文本里抠出「标题 + 作者」对，生成抖音搜索链接。

    页面结构（innerText）大致是：
        01:58
        5.5万
        这里是视频标题 #话题
        @作者名
        · 18小时前
    """
    lines = [x.strip() for x in (text or "").split("\n")]
    out: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        if not line.startswith("@") or len(line) < 2:
            continue
        author = line[1:].strip()
        title = ""
        for j in range(i - 1, max(-1, i - 5), -1):
            cand = lines[j]
            if not cand or cand.startswith("@") or cand.startswith("·"):
                continue
            if re.fullmatch(r"[\d.]+(万|亿|w)?|\d{1,2}:\d{2}(:\d{2})?|置顶|广告|热", cand):
                continue
            if len(cand) >= 6:
                title = cand
                break
        if not title or title in seen:
            continue
        seen.add(title)
        keyword = re.sub(r"#\S+", "", title)
        keyword = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9 ]", " ", keyword).strip()
        keyword = " ".join(keyword.split()[:6]) or title[:10]
        out.append(
            {
                "title": title[:60],
                "author": author[:20],
                "keyword": keyword,
                "url": "https://www.douyin.com/search/" + quote(keyword),
            }
        )
        if len(out) >= limit:
            break
    return out


def chrome_running(port: int = cdp.DEFAULT_PORT) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


_PROC = None


def _find_browser(prefer: str = "edge") -> str | None:
    edge = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    chrome = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    order = edge + chrome if prefer != "chrome" else chrome + edge
    for p in order:
        if Path(p).exists():
            return p
    return None


def launch_chrome(profile: str = "data/browser-douyin", url: str = "https://www.douyin.com/", port: int = cdp.DEFAULT_PORT, headless: bool = True, prefer: str = "edge") -> bool:
    global _PROC
    import subprocess

    exe = _find_browser(prefer)
    if not exe:
        log.error("找不到 Edge/Chrome，无法抓抖音")
        return False
    profile_dir = Path(profile).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,900",
        "--mute-audio",
        "--disable-blink-features=AutomationControlled",
    ]
    if headless:
        args.append("--headless=new")
        args.append("--disable-gpu")
    else:
        # 真窗口挪到屏幕外：抖音能识破无头模式，但看不出窗口在哪
        args.append("--window-position=-32000,-32000")
    args.append(url)
    try:
        _PROC = subprocess.Popen(args, close_fds=True)
    except Exception as exc:
        log.error("启动浏览器失败：%r", exc)
        return False
    log.info("已启动浏览器抓抖音（%s / %s，PID %s）", Path(exe).stem, "无头" if headless else "屏幕外窗口",
             getattr(_PROC, "pid", "?"))
    return True


def kill_browser() -> None:
    global _PROC
    if _PROC is not None:
        try:
            _PROC.terminate()
        except Exception:
            pass
        _PROC = None


async def _ready(headless: bool = True, prefer: str = "edge", port: int = cdp.DEFAULT_PORT,
                 probe_url: str = "https://www.douyin.com/?recommend=1") -> bool:
    """确保浏览器起来且能拿到真正渲染出来的内容；无头被识破就自动降级成屏幕外窗口。"""
    if not chrome_running(port):
        launch_chrome(headless=headless, prefer=prefer, port=port)
        await asyncio.sleep(11)
    sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        launch_chrome(headless=headless, prefer=prefer, port=port)
        await asyncio.sleep(11)
        sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        return False

    ok = False
    async with sess:
        try:
            await sess.send("Page.navigate", {"url": probe_url})
            await asyncio.sleep(5)
            txt = await sess.js("document.body.innerText") or ""
            ok = len(txt) > 50
            if not ok:
                log.warning("页面内容是空的（长度 %d），可能被识别", len(txt))
        except Exception as exc:
            log.warning("探测页面失败：%r", exc)

    if ok or not headless:
        return ok
    log.warning("无头模式取不到内容，降级为屏幕外窗口")
    kill_browser()
    await asyncio.sleep(3)
    launch_chrome(headless=False, prefer=prefer, port=port)
    await asyncio.sleep(12)
    return True


async def fetch_feed(limit: int = 10, scroll: int = 3, port: int = cdp.DEFAULT_PORT,
                     headless: bool = True, prefer: str = "edge") -> list[dict]:
    """打开推荐流，滚几下，抓视频卡片。"""
    if not await _ready(headless=headless, prefer=prefer, port=port):
        return []
    sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        return []

    items: list[dict] = []
    text = ""
    async with sess:
        try:
            await sess.send("Page.navigate", {"url": "https://www.douyin.com/?recommend=1"})
            await asyncio.sleep(6)
            for _ in range(max(1, scroll)):
                await sess.js("window.scrollBy(0, 1400)")
                await asyncio.sleep(2.2)
            text = await sess.js(TEXT_JS) or ""
        except Exception as exc:
            log.warning("抖音抓取失败：%r", exc)
            return []
    items = parse_cards(text, limit=limit)
    log.info("抖音抓到 %d 条推荐", len(items))
    return items[:limit]


async def search(keyword: str, limit: int = 8, port: int = cdp.DEFAULT_PORT) -> list[dict]:
    if not chrome_running(port):
        launch_chrome(port=port)
        await asyncio.sleep(9)
    sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        return []
    from urllib.parse import quote

    out: list[dict] = []
    text = ""
    async with sess:
        try:
            await sess.send("Page.navigate", {"url": f"https://www.douyin.com/search/{quote(keyword)}"})
            await asyncio.sleep(7)
            await sess.js("window.scrollBy(0, 1200)")
            await asyncio.sleep(2.5)
            text = await sess.js(TEXT_JS) or ""
        except Exception as exc:
            log.warning("抖音搜索失败：%r", exc)
    out = parse_cards(text, limit=limit)
    return out[:limit]


CARD_JS = r"""
(() => {
  const seen = new Set();
  const out = [];
  [...document.querySelectorAll('div,li,section')].forEach(e => {
    const t = (e.innerText || '');
    const r = e.getBoundingClientRect();
    if (!/\d{2}:\d{2}/.test(t) || t.length > 220) return;
    if (r.width < 220 || r.height < 140 || r.top < 70) return;
    const lines = t.split('\n').map(s => s.trim()).filter(Boolean);
    const title = lines.length >= 3 ? lines[2] : lines[lines.length - 1];
    if (!title || title.length < 5 || seen.has(title)) return;
    seen.add(title);
    out.push({
      title: title.slice(0, 60),
      author: (lines.find(l => l.startsWith('@')) || '').slice(0, 24),
      x: Math.round(r.left), y: Math.round(r.top),
      w: Math.round(r.width), h: Math.round(r.height),
    });
  });
  out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
  return JSON.stringify(out.slice(0, 12));
})()
"""


async def browse(path: str = "tmp/douyin.jpg", port: int = cdp.DEFAULT_PORT,
                 headless: bool = True, prefer: str = "edge", wait: float = 8) -> dict:
    """刷一遍抖音精选，列出卡片；并截其中一张卡片的图（画面与标题天然同源）。

    返回 {"items": [...], "pick": {...} 或 None, "shot": 路径或 None}
    """
    out: dict = {"items": [], "pick": None, "shot": None}
    if not await _ready(headless=headless, prefer=prefer, port=port):
        return out
    sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        return out

    async with sess:
        try:
            await sess.send("Page.navigate", {"url": "https://www.douyin.com/jingxuan"})
            await asyncio.sleep(wait)
            await sess.js("window.scrollBy(0, 300)")
            await asyncio.sleep(1.5)
            raw = await sess.js(CARD_JS)
            items = json.loads(raw) if raw else []
            out["items"] = items
            if items:
                pick = random.choice(items[:6])
                out["pick"] = pick
                clip = {
                    "x": max(0, pick["x"] - 4), "y": max(0, pick["y"] - 4),
                    "width": pick["w"] + 8, "height": min(pick["h"], 420) + 8, "scale": 1,
                }
                path = await sess.screenshot(path, clip=clip, quality=88)
                out["shot"] = path
        except Exception as exc:
            log.warning("抖音浏览失败：%r", exc)
    log.info("抖音浏览：%d 张卡片，选中「%s」，截图 %s",
             len(out["items"]), (out["pick"] or {}).get("title", "")[:20], "有" if out["shot"] else "无")
    return out


async def capture(path: str = "tmp/douyin.png", url: str = "https://www.douyin.com/?recommend=1", wait: float = 7,
                  scroll: int = 1, port: int = cdp.DEFAULT_PORT, headless: bool = True, prefer: str = "edge") -> str | None:
    """打开抖音推荐流并截屏，返回图片路径。"""
    if not await _ready(headless=headless, prefer=prefer, port=port, probe_url=url):
        return None
    sess = await cdp.open_session(port, match="douyin.com")
    if sess is None:
        return None
    async with sess:
        try:
            await sess.send("Page.navigate", {"url": url})
            await asyncio.sleep(wait)
            for _ in range(max(0, scroll)):
                await sess.js("window.scrollBy(0, 900)")
                await asyncio.sleep(2)
            return await sess.screenshot(path)
        except Exception as exc:
            log.warning("抖音截屏失败：%r", exc)
            return None


async def logged_in(port: int = cdp.DEFAULT_PORT) -> bool:
    return await cdp.douyin_logged_in(port)
