"""本地生成简易表情包（不依赖任何图片 API）。

生成 400x400 PNG，圆脸 + 简单五官 + 中文口头语，按心情分目录：
  stickers/开心、stickers/日常、stickers/难过、stickers/生气、stickers/困

用法： .venv\\Scripts\\python.exe tools\\make_stickers.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stickers"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]

# (目录, 文件名, 颜色, 表情类型, 文案)
SPECS = [
    ("开心", "haha", (255, 205, 66), "laugh", "哈哈"),
    ("开心", "xing", (255, 205, 66), "thumb", "行吧"),
    ("开心", "xihuan", (255, 160, 190), "heart", "喜欢"),
    ("开心", "naicha", (200, 170, 130), "sip", "喝奶茶"),
    ("日常", "wuyu", (215, 220, 230), "flat", "…"),
    ("日常", "zaizai", (180, 220, 255), "wave", "在呢"),
    ("日常", "haode", (180, 240, 200), "thumb", "好"),
    ("难过", "wuwu", (170, 200, 240), "cry", "呜呜"),
    ("生气", "heng", (255, 170, 170), "angry", "哼"),
    ("困", "kun", (190, 190, 230), "sleep", "困死了"),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_face(d: ImageDraw.ImageDraw, kind: str, w: int) -> None:
    cx, cy, r = w // 2, int(w * 0.42), int(w * 0.30)
    dark = (40, 40, 48)
    # 眼睛
    ex = int(r * 0.42)
    ey = cy - int(r * 0.12)
    if kind in ("laugh",):
        d.arc([cx - ex - 12, ey - 14, cx - ex + 14, ey + 14], 200, 340, fill=dark, width=6)
        d.arc([cx + ex - 14, ey - 14, cx + ex + 12, ey + 14], 200, 340, fill=dark, width=6)
    elif kind == "sleep":
        d.line([cx - ex - 12, ey, cx - ex + 12, ey], fill=dark, width=6)
        d.line([cx + ex - 12, ey, cx + ex + 12, ey], fill=dark, width=6)
        f = font(int(r * 0.5))
        d.text((cx + r, cy - r), "Z", font=f, fill=dark)
    elif kind == "cry":
        d.ellipse([cx - ex - 9, ey - 12, cx - ex + 9, ey + 16], fill=dark)
        d.ellipse([cx + ex - 9, ey - 12, cx + ex + 9, ey + 16], fill=dark)
        d.ellipse([cx - ex - 6, ey + 24, cx - ex + 6, ey + 70], fill=(90, 160, 240))
        d.ellipse([cx + ex - 6, ey + 24, cx + ex + 6, ey + 70], fill=(90, 160, 240))
    elif kind == "angry":
        d.line([cx - ex - 13, ey - 14, cx - ex + 11, ey - 4], fill=dark, width=6)
        d.line([cx + ex - 11, ey - 4, cx + ex + 13, ey - 14], fill=dark, width=6)
        d.ellipse([cx - ex - 7, ey + 4, cx - ex + 7, ey + 18], fill=dark)
        d.ellipse([cx + ex - 7, ey + 4, cx + ex + 7, ey + 18], fill=dark)
    else:
        d.ellipse([cx - ex - 8, ey - 10, cx - ex + 8, ey + 10], fill=dark)
        d.ellipse([cx + ex - 8, ey - 10, cx + ex + 8, ey + 10], fill=dark)

    # 嘴
    my = cy + int(r * 0.42)
    if kind == "laugh":
        d.chord([cx - 34, my - 26, cx + 34, my + 26], 0, 180, fill=(120, 40, 40))
    elif kind == "flat":
        d.line([cx - 22, my, cx + 22, my], fill=dark, width=6)
    elif kind == "cry":
        d.arc([cx - 26, my, cx + 26, my + 34], 200, 340, fill=dark, width=6)
    elif kind == "angry":
        d.arc([cx - 24, my + 8, cx + 24, my + 34], 190, 350, fill=dark, width=6)
    elif kind == "sleep":
        d.ellipse([cx - 12, my - 8, cx + 12, my + 12], fill=(120, 60, 60))
    else:
        d.arc([cx - 26, my - 14, cx + 26, my + 20], 20, 160, fill=dark, width=6)

    # 装饰
    if kind == "heart":
        for dx in (-78, 78):
            hx, hy = cx + dx, cy - int(r * 0.6)
            d.ellipse([hx - 12, hy - 12, hx, hy], fill=(240, 90, 120))
            d.ellipse([hx, hy - 12, hx + 12, hy], fill=(240, 90, 120))
            d.polygon([(hx - 12, hy - 4), (hx + 12, hy - 4), (hx, hy + 16)], fill=(240, 90, 120))
    if kind == "thumb":
        d.rounded_rectangle([cx + 60, cy - 10, cx + 96, cy + 50], 12, fill=(255, 235, 180), outline=dark, width=3)
    if kind == "sip":
        d.rounded_rectangle([cx - 40, cy + 40, cx + 40, cy + 120], 14, fill=(240, 235, 225), outline=dark, width=3)
        d.line([cx + 12, cy + 54, cx + 44, cy + 24], fill=dark, width=6)
    if kind == "wave":
        d.arc([cx + 40, cy - 30, cx + 90, cy + 20], 300, 60, fill=dark, width=5)


def make_one(bucket: str, name: str, color: tuple, kind: str, caption: str) -> Path:
    W = 400
    img = Image.new("RGBA", (W, W), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    # 白色贴纸外轮廓 + 彩色圆脸
    d.ellipse([26, 26, W - 26, W - 26], fill=(255, 255, 255))
    d.ellipse([40, 40, W - 40, W - 40], fill=color, outline=(45, 45, 55), width=5)
    draw_face(d, kind, W)
    # 文案
    f = font(56)
    tw = d.textlength(caption, font=f)
    d.text(((W - tw) / 2, W - 108), caption, font=f, fill=(45, 45, 55))

    folder = OUT / bucket
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.png"
    img.save(path)
    return path


def main() -> None:
    made = [make_one(*spec) for spec in SPECS]
    for p in made:
        print("已生成", p.relative_to(ROOT))
    print(f"共 {len(made)} 张 -> {OUT}")


if __name__ == "__main__":
    main()
