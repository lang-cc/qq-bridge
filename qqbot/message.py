"""消息段构造：OneBot v11 的 message 支持「纯字符串」和「消息段数组」两种。

这里统一产出消息段数组，NapCat / Lagrange / LLOneBot 都认。
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any


def _uri(src: str) -> str:
    """本地路径转成 file:// 绝对路径；URL / base64 / file:// 原样返回。"""
    src = str(src)
    if src.startswith(("http://", "https://", "base64://", "file://")):
        return src
    return "file:///" + os.path.abspath(src).replace("\\", "/")


def _basename(src: str) -> str:
    return os.path.basename(str(src).replace("\\", "/").rstrip("/")) or "file"


# ---------------------------------------------------------------- 基础段
def text(content: Any) -> dict:
    return {"type": "text", "data": {"text": str(content)}}


def at(qq: Any) -> dict:
    return {"type": "at", "data": {"qq": str(qq)}}


def reply(message_id: Any) -> dict:
    return {"type": "reply", "data": {"id": str(message_id)}}


def image(src: str) -> dict:
    return {"type": "image", "data": {"file": _uri(src)}}


def image_bytes(data: bytes, fmt: str = "png") -> dict:
    b64 = base64.b64encode(data).decode()
    return {"type": "image", "data": {"file": f"base64://{b64}"}}


def record(src: str) -> dict:
    """语音。NapCat 需要 silk，多数版本会把本地音频自动转换。"""
    return {"type": "record", "data": {"file": _uri(src)}}


def video(src: str) -> dict:
    return {"type": "video", "data": {"file": _uri(src)}}


def file(src: str, name: str | None = None) -> dict:
    return {"type": "file", "data": {"file": _uri(src), "name": name or _basename(src)}}


def face(face_id: int) -> dict:
    return {"type": "face", "data": {"id": str(face_id)}}


def poke(qq: Any) -> dict:
    return {"type": "poke", "data": {"qq": str(qq)}}


def json_card(payload: dict | str) -> dict:
    data = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return {"type": "json", "data": {"data": data}}


# ---------------------------------------------------------------- 链接卡片
def link(url: str, title: str = "", desc: str = "", preview: str = "") -> dict:
    """发链接：做成 QQ 的结构化分享卡片（比纯文本链接好看，注意别高频发）。"""
    card = {
        "app": "com.tencent.structmsg",
        "desc": "新闻",
        "view": "news",
        "ver": "0.0.0.1",
        "prompt": f"[分享] {title or url}",
        "meta": {
            "news": {
                "title": title or url,
                "desc": desc or url,
                "jumpUrl": url,
                "preview": preview,
                "tag": "链接",
                "source": "qq-bridge",
            }
        },
    }
    return {"type": "json", "data": {"data": json.dumps(card, ensure_ascii=False)}}


def link_plain(url: str, title: str = "") -> dict:
    """最稳的链接发送方式：纯文本，QQ 会自动识别成卡片。"""
    return text(f"{title} {url}".strip())


# ---------------------------------------------------------------- 组装
def build(parts: Any) -> Any:
    """把 str / bytes / 单个段 / 段列表 统一成可直接发送的 message。"""
    if isinstance(parts, (str, dict)):
        return parts
    if isinstance(parts, (list, tuple)):
        return [p if isinstance(p, dict) else text(p) for p in parts]
    return text(parts)
