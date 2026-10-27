"""说话：edge-tts 合成 → silk → QQ 语音条。

正常走 edge-tts（微软 Edge 在线语音，不要 key、中文音色自然）；
国内经常被 reset，则依次降级：百度翻译 TTS → 本机系统语音（SAPI）。
三层都失败才退回文字，不影响聊天。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from urllib.parse import quote

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


async def aliyun_synth(text: str, api_key: str, voice: str = "Cherry", model: str = "qwen3-tts-flash") -> str | None:
    """阿里云百炼语音合成（Qwen-TTS / CosyVoice），国内直连、音质接近真人。"""
    import aiohttp

    text = (text or "").strip()
    if not text:
        return None
    text = text[:600]  # 接口上限 600 字
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    payload = {
        "model": model,
        "input": {"text": text, "voice": voice, "language_type": "Chinese"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # 网关对裸请求比较挑，带上 SDK 标识更稳
        "x-dashscope-sdk-client": "python-sdk/2.0.1/audio2",
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers,
                              timeout=aiohttp.ClientTimeout(total=40)) as r:
                body = await r.json(content_type=None)
            audio_url = (((body or {}).get("output") or {}).get("audio") or {}).get("url")
            if not audio_url:
                log.warning("阿里云 TTS 没返回音频：%s", str(body)[:200])
                return None
            async with s.get(audio_url, timeout=aiohttp.ClientTimeout(total=40)) as r2:
                raw = await r2.read()
    except Exception as exc:
        log.warning("阿里云 TTS 失败：%r", exc)
        return None
    if len(raw) < 3000:
        log.warning("阿里云 TTS 音频过小：%d bytes", len(raw))
        return None
    dest = out_dir / f"aliyun-{int(time.time())}-{uuid.uuid4().hex[:6]}.wav"
    dest.write_bytes(raw)
    log.info("阿里云 TTS 合成完成：%s（%d 字，%d KB，%s）", dest.name, len(text), len(raw) // 1024, voice)
    return str(dest)


async def baidu_synth(text: str) -> str | None:
    """百度翻译的免费 TTS（无需密钥），音质比系统离线语音自然。

    edge-tts 的 speech.platform.bing.com 在国内会被 reset 时用这条顶上。
    """
    import aiohttp

    text = (text or "").strip()
    if not text:
        return None
    # 接口对长文本不友好，语音条本来就短，截一下
    text = text[:180]
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / f"baidu-{int(time.time())}-{uuid.uuid4().hex[:6]}.mp3"
    url = (
        "https://fanyi.baidu.com/gettts?lan=zh&spd=5&source=web&text="
        + quote(text)
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status != 200:
                    log.warning("百度 TTS 返回 %s", r.status)
                    return None
                raw = await r.read()
    except Exception as exc:
        log.warning("百度 TTS 失败：%r", exc)
        return None
    if len(raw) < 3000:
        log.warning("百度 TTS 音频过小：%d bytes", len(raw))
        return None
    dest.write_bytes(raw)
    log.info("百度 TTS 合成完成：%s（%d 字，%d KB）", dest.name, len(text), len(raw) // 1024)
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
    """一句话直接给出可发送的 silk 路径。

    优先级：阿里云（有 key 时）→ 火山（provider=volc）→ edge-tts → 百度 → 本机离线。
    任何一层挂了自动往下走，保证语音不断。
    """
    cfg = cfg or {}
    provider = (cfg.get("provider") or "edge").lower()
    api_key = str(cfg.get("api_key") or "").strip()
    mp3: str | None = None

    # 1) 阿里云百炼（音质最好，国内直连）
    if api_key and provider in ("aliyun", "qwen", "bailian", "edge", "auto"):
        mp3 = await aliyun_synth(
            text,
            api_key,
            voice=str(cfg.get("voice") or "Cherry"),
            model=str(cfg.get("model") or "qwen3-tts-flash"),
        )
        if mp3:
            log.info("语音走阿里云（%s）", cfg.get("voice") or "Cherry")

    # 2) 火山引擎（要 appid + token）
    if not mp3 and provider == "volc":
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

    # 3) edge-tts（微软在线语音）
    if not mp3:
        mp3 = await synth(text, voice=cfg.get("voice") or voice)
    # 4) 百度翻译（免费，音质一般但通）
    if not mp3:
        mp3 = await baidu_synth(text)
        if mp3:
            log.info("改用百度 TTS 兜底")
    # 5) 本机离线语音（最后一道）
    if not mp3:
        mp3 = await asyncio.to_thread(sapi_synth, text)
        if mp3:
            log.info("在线 TTS 都不可用，改用本机离线语音")
    if not mp3:
        return None
    silk = await to_silk(mp3)
    if not silk or not silk.lower().endswith((".silk", ".slk")):
        log.warning("silk 转码失败，语音这次跳过：%s", silk)
        return None
    return silk
