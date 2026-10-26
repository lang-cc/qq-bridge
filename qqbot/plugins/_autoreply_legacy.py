"""像真人的自动回复。

拟人化手段：
  1. 人设 system prompt（可改）
  2. 打字延迟：按字数估算，带抖动，不秒回
  3. 分段发送：长句拆成 2-3 条，中间有停顿
  4. 上下文记忆：每个会话独立保存最近 N 轮
  5. 概率回复：群聊可设概率，私聊默认必回
  6. 关键词规则优先（配置了就先命中规则，省钱）
支持任何 OpenAI 兼容接口：DeepSeek / 通义 / 智谱 / 本地 Ollama(127.0.0.1:11434/v1)
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time

log = logging.getLogger("qqbot.autoreply")

DEFAULTS = {
    "enabled": True,
    "cooldown": 2.0,
    "reply_private": True,
    "reply_group": True,
    "group_at_only": True,
    "group_reply_probability": 1.0,
    "fallback": "",
    "rules": [],
    "typing": {"enabled": True, "per_char_ms": 55, "max_ms": 5000, "jitter_ms": 700},
    "split": {"enabled": True, "max_segments": 3, "gap_ms": [500, 1500]},
    "llm": {
        "enabled": False,
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-chat",
        "system_prompt": "",
        "persona": (
            "你是在 QQ 上聊天的普通人，不是助手也不是 AI。"
            "说话短、口语、带点情绪，像微信打字那样；"
            "一次只说一两句，不用 markdown、不列条目、不写总结、不解释自己是模型。"
            "别人问你是谁就随口答，别端着。"
        ),
        "temperature": 0.9,
        "history": 8,
        "fallback": "",
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class AutoReply:
    def __init__(self, bot, cfg: dict | None = None) -> None:
        self.cfg = _merge(DEFAULTS, cfg or {})
        self.bot = bot
        self._last: dict[str, float] = {}
        self._history: dict[str, list[dict]] = {}
        self._session = None

    # ------------------------------------------------------------ 判断
    def _target_ok(self, event) -> bool:
        if event.sub_type == "private":
            return bool(self.cfg["reply_private"])
        if event.group_id is not None:
            if not self.cfg["reply_group"]:
                return False
            if self.cfg["group_at_only"] and f"@{self.bot.self_id}" not in (event.message or ""):
                return False
            prob = float(self.cfg.get("group_reply_probability") or 1.0)
            return random.random() <= prob
        return False

    def _cooldown_ok(self, key: str) -> bool:
        gap = float(self.cfg.get("cooldown") or 0)
        now = time.monotonic()
        if now - self._last.get(key, 0) < gap:
            return False
        self._last[key] = now
        return True

    def _match_rule(self, text: str) -> str | None:
        low = text.lower()
        for rule in self.cfg.get("rules") or []:
            keys = rule.get("match") or []
            if isinstance(keys, str):
                keys = [keys]
            if any(str(k).lower() in low for k in keys):
                return str(rule.get("reply") or "")
        return None

    # ------------------------------------------------------------ 拟人化发送
    async def _type_delay(self, text: str) -> None:
        cfg = self.cfg.get("typing") or {}
        if not cfg.get("enabled"):
            return
        ms = min(len(text) * float(cfg.get("per_char_ms") or 55), float(cfg.get("max_ms") or 5000))
        ms += random.uniform(0, float(cfg.get("jitter_ms") or 700))
        await asyncio.sleep(ms / 1000)

    def _split(self, text: str) -> list[str]:
        cfg = self.cfg.get("split") or {}
        if not cfg.get("enabled"):
            return [text]
        limit = int(cfg.get("max_segments") or 3)
        parts = [p.strip() for p in re.split(r"(?<=[。！？!?…\n])", text) if p.strip()]
        if len(parts) <= 1:
            return [text]
        if len(parts) > limit:  # 合并到 limit 段
            head = parts[: limit - 1]
            tail = "".join(parts[limit - 1 :])
            parts = head + [tail]
        return parts

    async def _send_humanized(self, event, text: str) -> None:
        segments = self._split(text)
        gap_cfg = (self.cfg.get("split") or {}).get("gap_ms") or [500, 1500]
        for i, seg in enumerate(segments):
            await self._type_delay(seg)
            try:
                await self.bot.reply(event, seg)
            except Exception as exc:
                log.error("发送失败：%r", exc)
                return
            if i < len(segments) - 1:
                await asyncio.sleep(random.uniform(gap_cfg[0], gap_cfg[1]) / 1000)

    # ------------------------------------------------------------ AI
    def _llm_ready(self) -> bool:
        llm = self.cfg.get("llm") or {}
        if not llm.get("enabled"):
            return False
        base = str(llm.get("base_url") or "")
        local = any(h in base for h in ("127.0.0.1", "localhost", "::1"))
        return bool(llm.get("api_key")) or local

    async def _ask_llm(self, key: str, text: str) -> str | None:
        if not self._llm_ready():
            return None
        import aiohttp

        llm = self.cfg["llm"]
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        history = self._history.setdefault(key, [])
        history.append({"role": "user", "content": text})
        keep = int(llm.get("history") or 8) * 2
        self._history[key] = history[-keep:]

        system = (llm.get("persona") or "") + "\n" + (llm.get("system_prompt") or "")
        body = {
            "model": llm.get("model") or "deepseek-chat",
            "messages": [{"role": "system", "content": system.strip()}] + self._history[key],
            "temperature": float(llm.get("temperature") or 0.9),
        }
        url = str(llm.get("base_url") or "").rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if llm.get("api_key"):
            headers["Authorization"] = f"Bearer {llm['api_key']}"
        try:
            async with self._session.post(url, json=body, headers=headers, timeout=90) as r:
                data = await r.json(content_type=None)
            answer = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            answer = (answer or "").strip()
            if answer:
                self._history[key].append({"role": "assistant", "content": answer})
                return answer
            log.warning("AI 返回为空：%s", str(data)[:200])
        except Exception as exc:
            log.error("调用 AI 失败：%r", exc)
        return None

    # ------------------------------------------------------------ 主流程
    def _refresh(self) -> None:
        """每来一条消息都重读配置，网页上改完立刻生效。"""
        config = getattr(self.bot, "config", None)
        if config is None:
            return
        try:
            self.cfg = _merge(DEFAULTS, config.section("autoreply"))
        except Exception as exc:
            log.debug("重载配置失败：%r", exc)

    async def handle(self, event) -> bool:
        self._refresh()
        if not self.cfg.get("enabled"):
            return False
        if not self._target_ok(event):
            return False

        key = f"g{event.group_id}" if event.group_id is not None else f"u{event.user_id}"
        if not self._cooldown_ok(key):
            return False

        text = (event.command_text or event.message or "").strip()
        if not text:
            return False

        rule_reply = self._match_rule(text)
        if rule_reply:
            log.info("[%s] 规则命中：%r", key, text[:30])
            await self._send_humanized(event, rule_reply)
            return True

        answer = await self._ask_llm(key, text)
        if answer:
            log.info("[%s] AI 回复：%r", key, answer[:40])
            await self._send_humanized(event, answer)
            return True

        fallback = (self.cfg.get("llm") or {}).get("fallback") or self.cfg.get("fallback")
        if fallback:
            await self._send_humanized(event, fallback)
            return True
        return False


def setup(bot) -> None:
    cfg = {}
    config = getattr(bot, "config", None)
    if config is not None:
        try:
            cfg = config.section("autoreply")
        except Exception:
            cfg = {}
    engine = AutoReply(bot, cfg)

    @bot.on_message(priority=900)
    async def auto(bot, event):
        return await engine.handle(event)

    llm = engine.cfg.get("llm") or {}
    log.info(
        "自动回复已启用｜规则 %d 条｜AI %s（%s）｜拟人：打字%s/分段%s",
        len(engine.cfg.get("rules") or []),
        "开" if llm.get("enabled") else "关",
        llm.get("model") or "-",
        "开" if (engine.cfg.get("typing") or {}).get("enabled") else "关",
        "开" if (engine.cfg.get("split") or {}).get("enabled") else "关",
    )
