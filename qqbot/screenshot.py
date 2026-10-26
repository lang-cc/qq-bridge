"""截屏：桌面截屏（Pillow）与网页截屏（Playwright，可选）。"""

from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("qqbot.screenshot")

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "shots")


def _ensure_dir() -> str:
    os.makedirs(SHOT_DIR, exist_ok=True)
    return SHOT_DIR


def _path(prefix: str) -> str:
    return os.path.join(_ensure_dir(), f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}.png")


def capture_desktop(path: str | None = None, bbox: tuple[int, int, int, int] | None = None) -> str:
    """截本机屏幕，返回 png 路径。bbox=(left, top, right, bottom) 可只截一块。"""
    from PIL import ImageGrab

    target = path or _path("screen")
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    img.save(target, "PNG")
    log.info("桌面截屏完成: %s (%sx%s)", target, img.width, img.height)
    return target


def capture_url(url: str, path: str | None = None, width: int = 1280, height: int = 800, wait_ms: int = 800) -> str:
    """网页截屏，需要先 pip install playwright && playwright install chromium。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "网页截屏需要 Playwright：pip install playwright 然后 playwright install chromium"
        ) from exc

    target = path or _path("web")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)
        page.screenshot(path=target, full_page=False)
        browser.close()
    log.info("网页截屏完成: %s <- %s", target, url)
    return target
