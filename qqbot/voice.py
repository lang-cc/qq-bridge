"""语音转码：QQ 只吃 silk(v3)。

链路：ffmpeg 解出 24k 单声道 PCM → silk-wasm（node）编码 → .silk
装到的东西：
  tools/ffmpeg/bin/ffmpeg.exe      音频解码
  tools/silk/encode.mjs + node     PCM → silk（silk-wasm，免编译）
找不到就原样发送，让协议端自己试。
"""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile

log = logging.getLogger("qqbot.voice")

SILK_EXT = (".silk", ".slk")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SILK_SCRIPT = os.path.join(ROOT, "tools", "silk", "encode.mjs")


def _find(explicit: str | None, names: list[str], extra_dirs: list[str]) -> str | None:
    if explicit and os.path.isfile(explicit):
        return explicit
    for name in names:
        hit = shutil.which(name)
        if hit:
            return hit
    for folder in extra_dirs:
        for name in names:
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                return path
    return None


def ffmpeg_path(cfg: dict | None = None) -> str | None:
    cfg = cfg or {}
    return _find(
        cfg.get("ffmpeg"),
        ["ffmpeg.exe", "ffmpeg"],
        [os.path.join(ROOT, "tools", "ffmpeg", "bin"), os.path.join(ROOT, "tools", "ffmpeg")],
    )


def node_path(cfg: dict | None = None) -> str | None:
    cfg = cfg or {}
    found = _find(
        cfg.get("node"),
        ["node.exe", "node"],
        [os.path.join(ROOT, "tools", "node"), os.path.join(ROOT, "napcat")],
    )
    if found:
        return found
    # NapCat 自带的 node 也能用
    for pattern in (
        os.path.join(ROOT, "napcat", "**", "node.exe"),
        os.path.join(ROOT, "napcat", "node.exe"),
    ):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    return None


def silk_encoder(cfg: dict | None = None) -> str | None:
    """原生 silk 编码器（可选，没有就用 silk-wasm）。"""
    cfg = cfg or {}
    return _find(
        cfg.get("silk_encoder"),
        ["silk_v3_encoder.exe", "silk_v3_encoder"],
        [os.path.join(ROOT, "tools", "silk"), os.path.join(ROOT, "tools", "ffmpeg", "bin")],
    )


def _measure_levels(ffmpeg: str, src: str) -> tuple[float | None, float | None]:
    """量峰值与平均电平（dB），决定提多少响度。"""
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", src, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception:
        return None, None
    err = r.stderr or ""
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", err)
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", err)
    return (float(peak.group(1)) if peak else None,
            float(mean.group(1)) if mean else None)


def _ffmpeg_to_pcm(ffmpeg: str, src: str, pcm: str) -> None:
    """转 24k 单声道 PCM，顺便把「听着偏小」的语音顶响一些。

    做法：先压峰值留出余量，再整体提电平，把平均响度拉到 -4dB 左右
    （QQ 语音条在手机上大多是外放/小音量，平均电平比峰值更重要）。
    """
    peak, mean = _measure_levels(ffmpeg, src)
    filters = ["highpass=f=60"]
    if mean is not None and mean < -6.0:
        gain = min(-4.0 - mean, 9.0)
        filters += ["alimiter=limit=0.45", f"volume={gain:.1f}dB"]
        log.info("语音响度：平均 %.1fdB（峰值 %.1fdB），提升 %.1fdB", mean, peak if peak is not None else 0, gain)
    subprocess.run(
        [ffmpeg, "-y", "-i", src, "-af", ",".join(filters),
         "-ar", "24000", "-ac", "1", "-f", "s16le", pcm],
        check=True,
        capture_output=True,
    )


def prepare(src: str, cfg: dict | None = None) -> str:
    """把任意音频转成 silk 路径；做不到就原样返回。"""
    src = str(src)
    if src.startswith(("http://", "https://", "base64://")):
        return src
    if src.lower().endswith(SILK_EXT):
        return src

    ffmpeg = ffmpeg_path(cfg)
    if not ffmpeg:
        log.warning("没有 ffmpeg，无法转码语音，直接发送原文件：%s", src)
        return src

    workdir = tempfile.mkdtemp(prefix="qqbridge-silk-")
    pcm = os.path.join(workdir, "voice.pcm")
    out = os.path.join(workdir, "voice.silk")
    try:
        _ffmpeg_to_pcm(ffmpeg, src, pcm)
    except subprocess.CalledProcessError as exc:
        log.warning("ffmpeg 解码失败（%s），直接发送原文件", exc.stderr[-200:] if exc.stderr else exc)
        return src

    # 首选 silk-wasm（node）
    node = node_path(cfg)
    if node and os.path.isfile(SILK_SCRIPT):
        try:
            subprocess.run([node, SILK_SCRIPT, pcm, "24000", out], check=True, capture_output=True)
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                log.info("语音已转 silk（silk-wasm）：%s", out)
                return out
        except subprocess.CalledProcessError as exc:
            log.warning("silk-wasm 编码失败：%s", exc.stderr[-200:] if exc.stderr else exc)

    # 备选：原生编码器
    encoder = silk_encoder(cfg)
    if encoder:
        for args in (
            [encoder, pcm, out, "-Fs_API", "24000", "-quiet"],
            [encoder, pcm, out, "-Fs_API", "24000"],
            [encoder, pcm, out],
        ):
            try:
                subprocess.run(args, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                continue
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                log.info("语音已转 silk（原生编码器）：%s", out)
                return out

    log.warning("silk 编码不可用（缺 node 或 silk-wasm），直接发送原文件：%s", src)
    return src
