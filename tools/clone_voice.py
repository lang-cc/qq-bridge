"""在任意阿里云百炼账号下复刻一个音色，并（可选）直接写进 config.yaml。

用法：
    python3 tools/clone_voice.py --audio 参考音.wav --key sk-xxxx [--prefix xiaoling]
    python3 tools/clone_voice.py --audio 参考音.wav --key sk-xxxx --write-config config.yaml

音色是按账号走的：同一个参考音频，在不同百炼账号下复刻会得到不同的 voice_id。
所以给客户部署时，要么用你自己的 key（花你的钱），要么让客户用他自己的 key
把这个音色在他账号里复刻一遍。

参考音频要求：单声道人声、10~60 秒、无背景音乐、无他人说话，wav/mp3 都行。
"""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import sys
import urllib.request

ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


def create_voice(audio: pathlib.Path, key: str, prefix: str, target_model: str) -> dict:
    raw = audio.read_bytes()
    if len(raw) > 10 * 1024 * 1024:
        sys.exit(f"参考音频太大（{len(raw) // 1024}KB），请压到 10MB 以内")
    ext = audio.suffix.lower().lstrip(".") or "wav"
    mime = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4"}.get(ext, "audio/wav")
    body = {
        "model": "voice-enrollment",
        "input": {
            "action": "create_voice",
            "target_model": target_model,
            "prefix": prefix,
            "language_hints": ["zh"],
            "audio": f"data:{mime};base64,{base64.b64encode(raw).decode()}",
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def patch_config(path: pathlib.Path, voice: str, key: str, model: str) -> None:
    text = path.read_text(encoding="utf-8")

    def set_field(block: str, field: str, value: str) -> str:
        pat = re.compile(rf"^(\s*{field}:\s*).*$", re.M)
        return pat.sub(lambda m: f"{m.group(1)}{value}", block, count=1)

    start = text.find("\n  tts:")
    if start < 0:
        sys.exit("config.yaml 里没找到 tts 段")
    end = len(text)
    for nxt in re.finditer(r"\n  [a-z_]+:", text[start + 1 :]):
        end = start + 1 + nxt.start()
        break
    block = text[start:end]
    block = set_field(block, "provider", "aliyun")
    block = set_field(block, "model", model)
    block = set_field(block, "voice", voice)
    block = set_field(block, "api_key", key)
    block = set_field(block, "enabled", "true")
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="阿里云百炼音色复刻")
    ap.add_argument("--audio", required=True, help="参考音频路径（10~60 秒干净人声）")
    ap.add_argument("--key", required=True, help="百炼 API Key（sk-...）")
    ap.add_argument("--prefix", default="qqbot", help="音色名前缀，字母小写")
    ap.add_argument("--target-model", default="cosyvoice-v3.5-plus", help="目标语音模型")
    ap.add_argument("--write-config", help="把结果直接写进这个 config.yaml")
    args = ap.parse_args()

    audio = pathlib.Path(args.audio)
    if not audio.exists():
        sys.exit(f"找不到音频文件：{audio}")

    print(f"上传参考音频 {audio.name}（{audio.stat().st_size // 1024}KB）…")
    data = create_voice(audio, args.key, args.prefix, args.target_model)
    voice = (data.get("output") or {}).get("voice") or ""
    if not voice:
        print("复刻失败，接口返回：")
        print(json.dumps(data, ensure_ascii=False, indent=1)[:800])
        sys.exit(1)

    print(f"\n✅ 复刻成功\nvoice_id = {voice}\n模型 = {args.target_model}")
    if args.write_config:
        patch_config(pathlib.Path(args.write_config), voice, args.key, args.target_model)
        print(f"已写入 {args.write_config} 的 tts 段，记得重启服务")
    else:
        print("\n把下面三行填进 config.yaml 的 tts 段：")
        print(f"    provider: aliyun\n    model: {args.target_model}\n    voice: {voice}\n    api_key: {args.key}")


if __name__ == "__main__":
    main()
