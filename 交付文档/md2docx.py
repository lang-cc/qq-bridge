# -*- coding: utf-8 -*-
"""把 docs 里的 Markdown 转成排版好的 DOCX（支持标题/表格/代码块/引用/列表/行内格式）。

用法：
    python md2docx.py docs\\任务单-AI部署.md 交付文档\\任务单-AI部署.docx
    python md2docx.py a.md b.md --outdir 交付文档
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "微软雅黑"
MONO = "Consolas"
CONTENT_W = 16.6  # cm，A4 减去左右各 2.2cm 页边距

INLINE = re.compile(r"(\*\*.+?\*\*)|(`[^`]+`)|(\[[^\]]+\]\([^)]+\))")


def set_font(run, name=FONT, size=None, bold=None, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    return run


def shade(p_or_cell, fill):
    el = p_or_cell._p if hasattr(p_or_cell, "_p") else p_or_cell._tc
    pPr = el.get_or_add_pPr() if hasattr(el, "get_or_add_pPr") else el.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)


def add_inline(p, text, base_bold=False, size=None, color=None):
    """解析 **粗体** / `代码` / [文字](链接)。"""
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            set_font(p.add_run(text[pos:m.start()]), size=size, bold=base_bold, color=color)
        tok = m.group(0)
        if tok.startswith("**"):
            set_font(p.add_run(tok[2:-2]), size=size, bold=True, color=color)
        elif tok.startswith("`"):
            set_font(p.add_run(tok[1:-1]), name=MONO, size=(size - 0.5) if size else 9.5,
                     bold=base_bold, color=(0x1F, 0x5F, 0xA8))
        else:
            label = re.match(r"\[([^\]]+)\]", tok).group(1)
            set_font(p.add_run(label), size=size, bold=base_bold, color=(0x1F, 0x5F, 0xA8))
        pos = m.end()
    if pos < len(text):
        set_font(p.add_run(text[pos:]), size=size, bold=base_bold, color=color)
    return p


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    line = line.replace("\\|", "\x00")
    return [c.strip().replace("\x00", "|") for c in line.split("|")]


def is_sep(line):
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def build_doc(md_path: Path, out_path: Path, title: str | None = None):
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.2)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(5)

    for name, size, color, before, after in (
        ("Heading 1", 16, (0x1F, 0x38, 0x64), 16, 6),
        ("Heading 2", 13, (0x2E, 0x54, 0x8C), 12, 4),
        ("Heading 3", 11.5, (0x33, 0x33, 0x33), 9, 3),
    ):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.bold = FONT, Pt(size), True
        st.font.color.rgb = RGBColor(*color)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True

    if title:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        set_font(p.add_run(title), size=22, bold=True, color=(0x1F, 0x38, 0x64))
        meta = doc.add_paragraph()
        meta.paragraph_format.space_after = Pt(12)
        set_font(meta.add_run(f"来源：{md_path.name}　｜　导出日期 2026-10-27"), size=9,
                 color=(0x80, 0x80, 0x80))

    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # --- 代码块 ---
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i].rstrip())
                i += 1
            i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.4)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.18
            shade(p, "F4F6F8")
            for k, ln in enumerate(buf):
                if k:
                    p.add_run().add_break()
                set_font(p.add_run(ln), name=MONO, size=8.8, color=(0x24, 0x29, 0x2E))
            continue

        # --- 表格 ---
        if stripped.startswith("|") and i + 1 < n and is_sep(lines[i + 1]):
            header = split_row(line)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            cols = len(header)
            t = doc.add_table(rows=1, cols=cols)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            t.autofit = False
            w = CONTENT_W / cols
            for c, h in enumerate(header):
                cell = t.rows[0].cells[c]
                cell.text = ""
                cp = cell.paragraphs[0]
                cp.paragraph_format.space_before = Pt(2)
                cp.paragraph_format.space_after = Pt(2)
                cp.paragraph_format.line_spacing = 1.2
                add_inline(cp, h, base_bold=True, size=9.5, color=(0xFF, 0xFF, 0xFF))
                shade(cell, "2E548C")
                cell.width = Cm(w) if c < cols - 1 else Cm(CONTENT_W - w * (cols - 1))
            for r in rows:
                cells = t.add_row().cells
                for c in range(cols):
                    cell = cells[c]
                    cell.text = ""
                    cp = cell.paragraphs[0]
                    cp.paragraph_format.space_before = Pt(2)
                    cp.paragraph_format.space_after = Pt(2)
                    cp.paragraph_format.line_spacing = 1.2
                    add_inline(cp, r[c] if c < len(r) else "", size=9.5)
                    cell.width = Cm(w)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # --- 空行 / 分隔线 ---
        if not stripped or re.fullmatch(r"[-*_]{3,}", stripped):
            i += 1
            continue

        # --- 标题 ---
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 3)
            h = doc.add_heading("", level=level)
            add_inline(h, m.group(2).strip())
            i += 1
            continue

        # --- 引用 ---
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(6)
            shade(p, "F7F7F5")
            for k, ln in enumerate([b for b in buf if b.strip()]):
                if k:
                    p.add_run().add_break()
                add_inline(p, ln, size=10)
            continue

        # --- 勾选框 ---
        m = re.match(r"^[-*]\s+\[( |x|X)\]\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            p.paragraph_format.space_after = Pt(3)
            set_font(p.add_run("☑  " if m.group(1).lower() == "x" else "□  "), size=11)
            add_inline(p, m.group(2))
            i += 1
            continue

        # --- 无序列表 ---
        m = re.match(r"^([-*+])\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.4
            add_inline(p, m.group(2))
            i += 1
            continue

        # --- 有序列表 ---
        m = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.first_line_indent = Cm(-0.8)
            p.paragraph_format.space_after = Pt(4)
            set_font(p.add_run(f"{m.group(1)}. "), bold=True)
            add_inline(p, m.group(2))
            i += 1
            continue

        # --- 普通段落 ---
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(5)
        add_inline(p, stripped)
        i += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--title", default=None)
    args = ap.parse_args(argv)
    results = []
    for src in args.inputs:
        p = Path(src)
        out = Path(args.outdir) / (p.stem + ".docx")
        results.append(build_doc(p, out, title=(args.title if len(args.inputs) == 1 else None)))
    for r in results:
        print("saved:", r)


if __name__ == "__main__":
    main()
