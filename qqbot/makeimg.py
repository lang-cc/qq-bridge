"""她会发图：用 PIL 现场拼卡片——梗图、金句卡、心情图。

不用 AI 画图：不花钱、不用显卡、不联网。
"""

from __future__ import annotations

import logging
import random
import textwrap
from pathlib import Path

log = logging.getLogger("qqbot.makeimg")

FONT_CANDIDATES_BOLD = (
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
FONT_CANDIDATES_NORMAL = (
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
STICKER_DIR = Path("stickers")
OUT_DIR = Path("tmp/img")


def _font(size: int, bold: bool = True):
    from PIL import ImageFont

    order = (
        FONT_CANDIDATES_BOLD + FONT_CANDIDATES_NORMAL
        if bold
        else FONT_CANDIDATES_NORMAL + FONT_CANDIDATES_BOLD
    )
    for path in order:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    log.warning("没找到中文字体，图上文字可能显示成方块")
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in (text or "").split("\n"):
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=font) <= max_width:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    return [ln for ln in lines if ln.strip()] or [""]


def _sticker_bg(width: int = 720):
    from PIL import Image

    files = [p for p in STICKER_DIR.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif")]
    random.shuffle(files)
    for p in files[:40]:
        try:
            img = Image.open(p).convert("RGB")
        except Exception:
            continue
        if img.width < 120 or img.height < 120:
            continue
        scale = width / img.width
        img = img.resize((width, max(200, int(img.height * scale))), Image.LANCZOS)
        return img.crop((0, 0, width, min(img.height, 900)))
    return None


def meme(top: str, bottom: str = "", out: str | None = None) -> str | None:
    """经典梗图：底图 + 半透明字条 + 白字黑边（避免和原图自带的字撞在一起）。"""
    from PIL import Image, ImageDraw

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bg = _sticker_bg(720)
    if bg is None:
        bg = Image.new("RGB", (720, 720), (32, 32, 40))
    bg = bg.convert("RGBA")
    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    def paint(text: str, anchor_top: bool) -> None:
        if not (text or "").strip():
            return
        font = _font(max(30, int(bg.width / 13)))
        lines = _wrap(draw, text, font, bg.width - 60)
        lh = font.size + 8
        total = lh * len(lines)
        pad = 14
        y0 = pad if anchor_top else bg.height - total - pad * 3
        # 半透明黑条，压住底图原有的文字
        draw.rectangle([(0, y0 - 6), (bg.width, y0 + total + 6)], fill=(0, 0, 0, 135))
        yy = y0
        for ln in lines:
            w = draw.textlength(ln, font=font)
            x = (bg.width - w) / 2
            draw.text((x, yy), ln, font=font, fill=(255, 255, 255),
                      stroke_width=max(2, font.size // 12), stroke_fill=(0, 0, 0))
            yy += lh

    paint(top, True)
    paint(bottom, False)

    out_img = Image.alpha_composite(bg, overlay).convert("RGB")
    path = out or str(OUT_DIR / f"meme-{random.randint(1000, 9999)}.jpg")
    out_img.save(path, "JPEG", quality=88)
    return path


def quote(text: str, author: str = "小柚", out: str | None = None) -> str | None:
    """金句卡：深色渐变底 + 居中大字 + 落款。"""
    from PIL import Image, ImageDraw

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    W = 720
    font = _font(38)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines = _wrap(probe, text, font, W - 100)
    H = max(420, 140 + len(lines) * (font.size + 14))

    img = Image.new("RGB", (W, H), (18, 18, 24))
    draw = ImageDraw.Draw(img)
    # 竖向渐变，像一张卡片
    for y in range(H):
        t = y / max(1, H - 1)
        draw.line([(0, y), (W, y)], fill=(int(18 + 26 * t), int(18 + 20 * t), int(30 + 40 * t)))

    # 左上角一小段装饰线
    draw.rectangle([(48, 52), (48 + 56, 56)], fill=(240, 200, 220))

    y = (H - len(lines) * (font.size + 14)) // 2
    for ln in lines:
        draw.text((50, y), ln, font=font, fill=(245, 245, 250))
        y += font.size + 14

    draw.text((W - 150, H - 60), f"— {author}", font=_font(28, bold=False), fill=(190, 170, 200))
    path = out or str(OUT_DIR / f"quote-{random.randint(1000, 9999)}.jpg")
    img.save(path, "JPEG", quality=90)
    return path


def mood_card(mood: str, line: str, out: str | None = None) -> str | None:
    """心情卡：一句话 + 情绪标签，窄幅竖图。"""
    from PIL import Image, ImageDraw

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    W, H = 600, 760
    palettes = {
        "开心": ((255, 214, 224), (255, 168, 196), (120, 60, 80)),
        "难过": ((206, 216, 240), (150, 166, 205), (50, 60, 100)),
        "生气": ((255, 214, 200), (240, 150, 130), (110, 40, 30)),
        "困": ((222, 214, 245), (170, 160, 210), (60, 50, 100)),
        "平静": ((228, 236, 232), (180, 200, 190), (50, 70, 60)),
    }
    c1, c2, ink = palettes.get(mood, palettes["平静"])
    img = Image.new("RGB", (W, H), c1)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))

    draw.text((48, 90), f"今天有点{mood}", font=_font(34), fill=ink)
    font = _font(40)
    lines = _wrap(draw, line, font, W - 96)
    y = 220
    for ln in lines[:6]:
        draw.text((48, y), ln, font=font, fill=ink)
        y += font.size + 16
    draw.text((48, H - 90), "—— 小柚", font=_font(26, bold=False), fill=ink)

    path = out or str(OUT_DIR / f"mood-{random.randint(1000, 9999)}.jpg")
    img.save(path, "JPEG", quality=90)
    return path
