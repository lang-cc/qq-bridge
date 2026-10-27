"""说话：edge-tts 合成 → silk → QQ 语音条。

edge-tts 用的是微软 Edge 的在线语音，不要 key、中文音色自然。
断网/被墙时返回 None，调用方退回文字，不影响聊天。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

log = logging.getLogger("qqbot.tts")

VOICES = {
    "cute": "zh-CN-XiaoyiNeural",
    "warm": "zh-CN-XiaoxiaoNeural",
    "boy": "zh-CN-YunxiNeural",
    "calm": "zh-CN-YunjianNeural",
}


async def volc_synth(text: str, appid: str, token: str, voice_type: str, cluster: str = "volcano_tts", timeout: int = 45) -> bytes | None:
    """火山引擎语音合成（大模型/普通都用这套 v1 接口），返回 mp3 字节。"""
    import base64
    import json
    import uuid

    import aiohttp

    if not appid or not token:
        log.warning("火山 TTS 缺 appid 或 token，跳过")
        return None
    payload = {
        "app": {"appid": str(appid), "token": token, "cluster": cluster or "volcano_tts"},
        "user": {"uid": "qq-bridge"},
        "audio": {"voice_type": voice_type, "encoding": "mp3", "speed_ratio": 1.0},
        "request": {"reqid": uuid.uuid4().hex, "text": text[:300], "text_type": "plain", "operation": "query"},
    }
    headers = {"Authorization": f"Bearer; {token}", "Content-Type": "application/json"}
    url = "https://openspeech.bytedance.com/api/v1/tts"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers, timeout=timeout) as r:
                data = await r.json(content_type=None)
    except Exception as exc:
        log.warning("火山 TTS 请求失败：%r", exc)
        return None
    code = data.get("code")
    if code != 3000:
        log.warning("火山 TTS 返回异常 code=%s msg=%s", code, (data.get("message") or "")[:120])
        return None
    try:
        raw = base64.b64decode(data.get("data") or "")
    except Exception:
        log.warning("火山 TTS 返回数据解不开")
        return None
    if len(raw) < 1000:
        log.warning("火山 TTS 音频过小：%d bytes", len(raw))
        return None
    return raw


async def synth(text: str, voice: str = "zh-CN-XiaoyiNeural", rate: str = "+0%", pitch: str = "+0Hz") -> str | None:
    """合成 mp3，返回文件路径。"""
    text = (text or "").strip()
    if not text:
        return None
    if voice in VOICES:
        voice = VOICES[voice]
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / f"tts-{int(time.time())}-{uuid.uuid4().hex[:6]}.mp3"
    try:
        import edge_tts

        comm = edge_tts.Communicate(text[:300], voice, rate=rate, pitch=pitch)
        await asyncio.wait_for(comm.save(str(dest)), timeout=45)
    except Exception as exc:
        log.warning("TTS 合成失败：%r", exc)
        return None
    if not dest.exists() or dest.stat().st_size < 1000:
        log.warning("TTS 产出为空：%s", dest)
        return None
    log.info("TTS 合成完成：%s（%d 字，%d KB）", dest.name, len(text), dest.stat().st_size // 1024)
    return str(dest)


def sapi_synth(text: str, out_wav: str | None = None) -> str | None:
    """本机离线语音（Windows System.Speech / SAPI5，中文一般有 Huihui）。

    edge-tts 走 speech.platform.bing.com，国内经常被掐（连上就 reset）；
    这时退回系统自带语音，音质差些但照样能发语音条。
    """
    import subprocess

    text = (text or "").strip()
    if not text:
        return None
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    dest = Path(out_wav) if out_wav else out_dir / f"sapi-{int(time.time())}-{uuid.uuid4().hex[:6]}.wav"
    dest = dest.resolve()
    txt_file = (out_dir / f"sapi-{uuid.uuid4().hex[:6]}.txt").resolve()
    txt_file.write_text(text, encoding="utf-8")

    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$v=$s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Culture.Name -like 'zh*'} | Select-Object -First 1;"
        "if($v){$s.SelectVoice($v.VoiceInfo.Name)};"
        f"$t=Get-Content -LiteralPath '{txt_file}' -Raw -Encoding UTF8;"
        f"$s.SetOutputToWaveFile('{dest}');"
        "$s.Speak($t);"
        "$s.Dispose()"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        log.warning("离线语音调用失败：%r", exc)
        return None
    finally:
        txt_file.unlink(missing_ok=True)
    if dest.exists() and dest.stat().st_size > 2000:
        log.info("离线语音合成完成：%s（%d 字，%d KB）", dest.name, len(text), dest.stat().st_size // 1024)
        return str(dest)
    log.warning("离线语音没产出：%s", (r.stderr or "")[:200])
    return None


async def to_silk(mp3: str) -> str:
    """mp3 → silk，丢线程里跑，别阻塞事件循环。"""
    from .voice import prepare

    return await asyncio.to_thread(prepare, mp3)


async def speak(text: str, voice: str = "zh-CN-XiaoyiNeural", cfg: dict | None = None) -> str | None:
    """一句话直接给出可发送的 silk 路径。cfg 里有 provider 就按其走。"""
    cfg = cfg or {}
    provider = (cfg.get("provider") or "edge").lower()
    mp3: str | None = None

    if provider == "volc":
        raw = await volc_synth(
            text,
            str(cfg.get("appid") or ""),
            str(cfg.get("token") or ""),
            str(cfg.get("voice_type") or voice),
            str(cfg.get("cluster") or "volcano_tts"),
        )
        if raw:
            out_dir = Path("tmp")
            out_dir.mkdir(exist_ok=True)
            dest = out_dir / f"volc-{int(time.time())}-{uuid.uuid4().hex[:6]}.mp3"
            dest.write_bytes(raw)
            log.info("火山 TTS 合成完成：%s（%d 字，%d KB）", dest.name, len(text), len(raw) // 1024)
            mp3 = str(dest)
        else:
            log.info("火山 TTS 不可用，退回 edge")

    if not mp3:
        mp3 = await synth(text, voice=cfg.get("voice") or voice)
    if not mp3:
        # edge 被掐时的离线兜底：系统自带语音，音质差但能发
        mp3 = await asyncio.to_thread(sapi_synth, text)
        if mp3:
            log.info("edge-tts 不可用，改用本机离线语音")
    if not mp3:
        return None
    silk = await to_silk(mp3)
    if not silk or not silk.lower().endswith((".silk", ".slk")):
        log.warning("silk 转码失败，语音这次跳过：%s", silk)
        return None
    return silk
