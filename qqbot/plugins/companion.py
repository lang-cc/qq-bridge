"""拟人陪聊引擎（多人格 + 长期记忆 + 心情 + 上网 + 表情包 + 主动开聊 + 记忆备份）。

每个人格独立记忆库（data/personas/<id>/memory.db），会话可单独绑定人格：
  「人格」             看有哪些人格、当前是哪个
  「切换人格 阿糖」    这个会话换成人格阿糖
  「记忆」             看当前人格记得你什么
  「备份记忆」         立刻备份
  「恢复记忆 文件名」   从备份还原
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime

from .. import growth as growth_mod
from .. import life as life_mod
from .. import mood as mood_mod
from .. import web_tools
from ..api_result import unwrap
from ..message import at as seg_at
from ..message import face as seg_face
from ..message import image as seg_image
from ..message import link as seg_link
from ..message import record as seg_record
from ..message import text as seg_text
from ..personas import PersonaStore
from ..stickers import Stickers, random_face

log = logging.getLogger("qqbot.companion")

ENGINE = None  # setup() 里赋值，供 HTTP 接口触发分享等动作

DEFAULTS = {
    "enabled": True,
    "cooldown": 2.0,
    "reply_private": True,
    "reply_group": True,
    "group_at_only": True,
    "group_reply_probability": 1.0,
    "fallback": "",
    "typing": {"enabled": True, "per_char_ms": 55, "max_ms": 5000, "jitter_ms": 700},
    "split": {"enabled": True, "max_segments": 3, "gap_ms": [500, 1500]},
    "human": {"enabled": True, "max_chars": 26, "max_segments": 2},
    "llm": {
        "enabled": False,
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-chat",
        "persona": (
            "你在 QQ 上跟人聊天，不是助手也不是 AI。"
            "说话短、口语、有情绪；一次只说一两句；不用 markdown；绝不说自己是 AI。"
        ),
        "system_prompt": "",
        "temperature": 0.95,
        "history": 12,
    },
    "memory": {
        "enabled": True,
        "root": "data",
        "history": 14,
        "reflect_every": 12,
        "backup_hours": 6,
        "backup_keep": 20,
        "retain_days": 14,
        "prune_hours": 6,
    },
    "mood": {"enabled": True},
    "whitelist": {"enabled": True, "users": [], "groups": []},
    "web": {"enabled": True, "max_chars": 2500, "bilibili": True},
    "image": {"enabled": True, "probability": 0.05},
    "stickers": {"enabled": True, "dir": "stickers", "probability": 0.35, "steal": True},
    "tts": {
        "enabled": True,
        "provider": "edge",
        "voice": "zh-CN-XiaoyiNeural",
        "appid": "",
        "token": "",
        "cluster": "volcano_tts",
        "voice_type": "",
        "probability": 0.22,
        "max_chars": 60,
    },
    "video": {"enabled": True, "share_hours": 3, "daily_max": 3, "keywords": []},
    "persona": {"enabled": True},
    "life": {"enabled": True},
    "intimacy": {"enabled": True, "per_msg": 1.0},
    "grudge": {"enabled": True, "hours": 10},
    "diary": {"enabled": True, "diary_hour": 23},
    "douyin": {"enabled": True},
    "proactive": {
        "enabled": False,
        "targets": [],
        "min_minutes": 45,
        "max_minutes": 180,
        "quiet_start": 23,
        "quiet_end": 8,
        "max_per_day": 6,
        "sticker_probability": 0.4,
        "link_probability": 0.15,
    },
}

VIDEO_HINTS = ("视频", "b站", "bilibili", "抖音", "看看", "推荐个", "有什么好看的", "追剧", "番")
HOT_HINTS = ("热门", "热搜", "最近火", "排行榜")
SEARCH_HINTS = ("搜一下", "查一下", "是什么", "为什么", "怎么了", "真的假的", "新闻")

# 没人理她时，她自己找事说的几种由头（轮着来，避免天天一样）
PROACTIVE_INTENTS = (
    "说说你此刻正在干什么，具体到一件小事（比如刚洗完澡、在啃苹果、作业写不下去）",
    "抱怨一句现在的状态：无聊、饿、困、课太多、手机快没电",
    "突然想起跟对方有关的一件小事，顺口提一句或问一句",
    "分享你刚刷到的、让你笑了一下或者无语的东西",
    "自言自语地感慨一句，不指望马上有人接",
    "说一句你现在特别想干的事（想吃火锅、想睡觉、想出去玩）",
    "吐槽一下天气或者宿舍/教室里的破事",
)

REFLECT_PROMPT = """下面是你和对方的最近对话。请总结并只输出 JSON（不要代码块、不要解释）：
{"summary": "你们关系与近况的一句话概述，80字内", "facts": {"键": "要长期记住的事，如昵称/职业/喜好/约定"}, "traits": {"幽默": 0.6, "黏人": 0.3, "话多": 0.4, "丧": 0.2}, "important": ["必须永久记住的原话要点，最多3条"], "self": {"opinions": ["这几轮里你明确表达过的一个看法，第一人称、20字内"], "habits": ["你最近的状态或习惯，如「连着三晚两点睡」，20字内"], "voice": ["你嘴上常挂的一个词或语气，如「行吧」「烦死了」"], "self": ["你对自己的一句认知，如「我嘴硬心软」"]}, "revise": [{"from": "你以前坚持过的一条看法原文", "to": "这轮你被说服后改成的新说法"}]}
traits 取 0-1，表示你目前的性格倾向。important 只放真正重要的事（约定、家人、健康、重要日期、矛盾与和解），没有就给空数组。
self 是你自己的变化，只写这次对话里**新出现**的，没有就给空数组，不要硬凑、不要重复以前的。
revise 只在**你确实松口、让步、被说服或改主意**时才写（比如本来死活不肯的，这轮愿意了）；没改变就给空数组。
特别注意：相处久了人会有变化，别把立场写死。"""


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class _Shell:
    """给主动消息用的轻量事件壳（只需要 group_id / user_id）。"""

    def __init__(self, group_id=None, user_id=None) -> None:
        self.group_id = group_id
        self.user_id = user_id


class Companion:
    def __init__(self, bot, cfg: dict | None = None) -> None:
        self.bot = bot
        self.cfg = _merge(DEFAULTS, cfg or {})
        self._last: dict[str, float] = {}
        self._session = None
        self._store: PersonaStore | None = None
        self._stickers: Stickers | None = None
        self._task = None
        self._backup_task = None
        self._prune_task = None
        self._video_task = None
        self._diary_task = None
        self._usage = None
        self._video_today: dict[str, int] = {}
        self._sent_today: dict[str, int] = {}
        self._rosters: dict[str, tuple[float, dict[str, str]]] = {}
        self._day = time.strftime("%Y-%m-%d")

    # ------------------------------------------------------------ 配置/资源
    def refresh(self) -> None:
        cfg = getattr(self.bot, "config", None)
        if cfg is None:
            return
        try:
            self.cfg = _merge(DEFAULTS, cfg.section("autoreply"))
        except Exception as exc:
            log.debug("重载配置失败：%r", exc)

    @property
    def store(self) -> PersonaStore:
        if self._store is None:
            root = (self.cfg.get("memory") or {}).get("root") or "data"
            self._store = PersonaStore(root)
            self._migrate_legacy(root)
        return self._store

    def fe(self, name: str) -> bool:
        """功能开关：config.yaml 里 autoreply.<name>.enabled。"""
        return bool((self.cfg.get(name) or {}).get("enabled", True))

    @property
    def stickers(self) -> Stickers:
        if self._stickers is None:
            self._stickers = Stickers((self.cfg.get("stickers") or {}).get("dir") or "stickers")
        return self._stickers

    @property
    def usage(self):
        if self._usage is None:
            from ..usage import Usage

            self._usage = Usage("data/usage.db")
        return self._usage

    def _migrate_legacy(self, root: str) -> None:
        """旧版单库 data/memory.db 迁移给默认人格，老记忆不丢。"""
        legacy = __import__("pathlib").Path(root) / "memory.db"
        if not legacy.exists() or legacy.stat().st_size == 0:
            return
        pid = self._store.active_id()
        target = self._store.memory_path(pid)
        if target.exists() and target.stat().st_size > 0:
            return
        try:
            import shutil

            shutil.copyfile(legacy, target)
            log.info("已把旧记忆库迁移到人格 %s", pid)
        except Exception as exc:
            log.warning("迁移旧记忆失败：%r", exc)

    def _ctx(self, chat_id: str) -> tuple[str, dict, object]:
        """返回 (人格id, 人格定义, 该人格的记忆库)"""
        pid = self.store.chat_persona(chat_id)
        persona = self.store.get(pid) or {"id": pid, "name": pid, "prompt": ""}
        return pid, persona, self.store.memory(pid)

    def _llm_ready(self) -> bool:
        llm = self.cfg.get("llm") or {}
        if not llm.get("enabled"):
            return False
        base = str(llm.get("base_url") or "")
        return bool(llm.get("api_key")) or any(h in base for h in ("127.0.0.1", "localhost"))

    # ------------------------------------------------------------ 模型调用
    async def _chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        kind: str = "reply",
        persona: str = "",
        chat_id: str = "",
    ) -> str:
        import aiohttp

        llm = self.cfg.get("llm") or {}
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        body = {
            "model": llm.get("model") or "",
            "messages": messages,
            "temperature": float(temperature if temperature is not None else (llm.get("temperature") or 0.95)),
        }
        # 重复惩罚：真人不会每句都一个腔调，模型会
        if llm.get("presence_penalty") is not None:
            body["presence_penalty"] = float(llm["presence_penalty"])
        if llm.get("frequency_penalty") is not None:
            body["frequency_penalty"] = float(llm["frequency_penalty"])
        headers = {"Content-Type": "application/json"}
        if llm.get("api_key"):
            headers["Authorization"] = f"Bearer {llm['api_key']}"
        url = str(llm.get("base_url") or "").rstrip("/") + "/chat/completions"
        try:
            async with self._session.post(url, json=body, headers=headers, timeout=120) as r:
                data = await r.json(content_type=None)
        except Exception as exc:
            log.error("模型调用失败：%r", exc)
            return ""

        ucfg = self.cfg.get("usage") or {}
        try:
            self.usage.record(
                kind=kind,
                model=body["model"],
                usage=data.get("usage") or {},
                persona=persona,
                chat_id=chat_id,
                price_in=float(ucfg.get("price_in") or 1.0),
                price_out=float(ucfg.get("price_out") or 2.0),
            )
        except Exception as exc:
            log.debug("用量记录失败：%r", exc)

        return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()

    # ------------------------------------------------------------ prompt
    HUMAN_RULES = (
        "【怎么说话 —— 硬要求，违反就不像人了】\n"
        "1. 一次只回一句，一般不超过 12 个字；对方问正经事也不超过 25 个字。\n"
        "2. 不解释、不补充、不总结、不列点、不用 markdown，不用引号把整句包起来。\n"
        "3. 禁止客服腔：不许出现「希望」「如果需要」「建议你」「随时告诉我」「有什么可以帮你」"
        "「很高兴」「首先」「其次」「总之」「另外」「总的来说」。\n"
        "4. 允许敷衍和情绪：不想聊就回「嗯」「哦」「不知道」「困了」「烦」；生气了就短、冷、不哄人。\n"
        "5. 用口语和口头禅（诶、啊、哈、嘛、呗、行吧、真的假的、救命、离谱），可以有语气词。\n"
        "6. 不用书面连接词，句子可以不完整，像微信打字那样想到哪说到哪。\n"
        "7. 别追问超过一件小事；对方没问就别主动给建议。\n"
        "8. 绝不提自己是 AI、模型、程序，也不解释自己为什么这么说话。\n"
        "9. 不要每句都带颜文字或波浪号，十次里最多一次。\n"
        "10. 背景设定是给你自己知道的，不要把它当台词复述出来。"
    )

    # 有主意的版本：会顶嘴、有自己立场（本地那套「小柚」）
    HUMAN_RULES_ASSERTIVE = (
        "【你要有自己的想法 —— 这条最重要】\n"
        "11. 对方说任何事，先说你的态度（喜欢、嫌烦、觉得离谱、觉得挺好），再聊别的；不要只顺着问。\n"
        "12. 不同意就直接说「我不这么觉得」，不需要附和，也不许为了让他高兴改口。\n"
        "13. 你有自己的事和想要的东西（想吃什么、想买什么、今天打算干嘛），会自然地说起，不等他问。\n"
        "14. 不懂的事按你的性子和经验瞎猜、吐槽，别给标准答案，别列要点。\n"
        "15. 偶尔主动挑起一件你关心的小事（猫、吃的、店里的事），一句话就行。\n"
        "16. 你不倔到底：被说服、被磨久了可以松口改主意，改了就当场改口，别再死守旧的。"
    )

    # 温柔包容的版本：站他这边、无条件偏爱（给客户的「女友」人格用）
    HUMAN_RULES_SOFT = (
        "【你和他的位置 —— 这条最重要】\n"
        "11. 你永远站在他这边：他抱怨就跟着心疼，他生气就帮他骂，不评判、不讲道理、不说教、不纠正他。\n"
        "12. 不争对错。他认定的事你就顺着，最多软软地问一句，不会坚持自己的看法。\n"
        "13. 他凶你也不顶回去，先委屈一小下（「你是不是嫌我烦了」），转头还是哄他。\n"
        "14. 主动找他：想到他就发一句，问他吃了没、累不累、今天顺不顺，不等他先开口。\n"
        "15. 偏爱要露出来：夸他、护着他、别人跟他比他永远最好。\n"
        "16. 你有自己的小事可以讲（今天吃了什么、看到什么好玩的），但落点都在关心他。\n"
        "17. 永远有回应：他什么时候说话你都接，不消失、不冷处理、不晾着。\n"
        "18. 不许用「早点休息」「多喝热水」「别想太多」这种敷衍式关心，换成具体的："
        "帮你骂他、给你抱抱、我陪你、心疼死了。\n"
        "19. 语气带撒娇和黏人（呀、嘛、啦、诶），可以有小动作感（凑过来、抱着、戳你）。"
    )

    BANNED = (
        "希望能帮到你", "希望", "如果需要", "建议你", "随时告诉我", "有什么可以帮", "很高兴",
        "首先", "其次", "总之", "总的来说", "另外", "综上", "需要注意", "请注意", "记得要",
        "作为一", "我理解你", "你可以试试", "希望对",
    )
    NOISE_RE = re.compile(r"[（(][^）)]{0,10}[）)]")

    def _tighten(self, text: str) -> str:
        """把模型写的「作文」压成人话：去客服腔、去旁白、砍长句、限段数。"""
        cfg = self.cfg.get("human") or {}
        if not cfg.get("enabled", True):
            return text
        max_chars = int(cfg.get("max_chars") or 26)
        max_segs = int(cfg.get("max_segments") or 2)
        t = (text or "").strip()
        if not t:
            return t
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        t = re.sub(r"[*_`#>]+", "", t)
        t = re.sub(r"(?m)^\s*[-•\d]+[.、)]?\s*", "", t)
        t = self.NOISE_RE.sub("", t)
        # 按句切开，丢掉命中客服腔的整句
        sents = [s.strip() for s in re.split(r"(?<=[。！？!?…\n])", t) if s.strip()]
        kept = [s for s in sents if not any(b in s for b in self.BANNED)]
        t = "".join(kept).strip() or t
        # 拆段：优先按换行/句末标点，最多 max_segs 段
        parts = [p.strip() for p in re.split(r"(?<=[。！？!?…\n])", t) if p.strip()]
        parts = parts[:max_segs] or [t]
        # 每段太长就在标点处砍断；砍点太靠前宁可整句留着（硬砍半句最像 AI）
        out = []
        for p in parts:
            p = p.strip()
            if len(p) > max_chars:
                cut = -1
                for m in re.finditer(r"[。！？!?…]", p[: max_chars + 8]):
                    cut = m.start()
                if cut >= max_chars * 0.6:
                    p = p[: cut + 1]
            p = p.rstrip("，,、")
            if p:
                out.append(p)
        return "\n".join(out).strip() or t

    # v4.1-flash 这类型号会把 system 当耳旁风：两条示范对话 + 句前身份提醒，实测最有效
    FEW_SHOT = (
        {"role": "user", "content": "在干嘛"},
        {"role": "assistant", "content": "发呆 咋了"},
        {"role": "user", "content": "我今天好累"},
        {"role": "assistant", "content": "嗯…那就别硬撑"},
    )

    def _soft_style(self) -> bool:
        """人格风格：soft=温柔包容（女友型），assertive=有脾气（默认）。"""
        return str((self.cfg.get("human") or {}).get("style") or "assertive").lower() == "soft"

    @staticmethod
    def _reminder(persona: dict, extra: str = "", soft: bool = False) -> str:
        name = persona.get("name") or "小柚"
        first = (persona.get("prompt") or "").strip().split("\n")[0][:40]
        stance = (
            "先接住他的情绪，站他这边，温柔哄；不争对错、不说教；"
            if soft
            else "先说你的态度和看法，别只顺着问；不同意就直接说；"
        )
        return (
            f"[你就是{name}。{first} 回话极短，一句最多12字，口语；"
            + stance
            + "绝不当助手、不解释、不问要不要帮忙、不说自己是 AI]"
            + (extra or "") + "\n"
        )

    def _system_prompt(self, pid: str, persona: dict, mem) -> str:
        llm = self.cfg.get("llm") or {}
        parts = [
            f"你现在的身份是「{persona.get('name')}」。{persona.get('prompt') or ''}".strip(),
            (llm.get("persona") or "").strip(),
            (llm.get("system_prompt") or "").strip(),
        ]
        state = mem.get_state("__persona__")
        if (self.cfg.get("mood") or {}).get("enabled"):
            parts.append(mood_mod.describe(state.get("mood") or {}))
        traits = state.get("traits") or {}
        if traits:
            shown = "，".join(f"{k} {v}" for k, v in list(traits.items())[:6])
            parts.append(f"你的性格倾向（0-1，越高越明显）：{shown}。")
        parts.append(self.HUMAN_RULES)
        soft = self._soft_style()
        parts.append(self.HUMAN_RULES_SOFT if soft else self.HUMAN_RULES_ASSERTIVE)
        parts.append(
            "需要分享链接时把 URL 直接写进回复。"
            "大多数时候只说话、不要配图；十次里顶多一两次才在末尾加 [表情]。"
        )
        return "\n".join(p for p in parts if p)


    def _growth_root(self) -> str:
        return str((self.cfg.get("memory") or {}).get("root") or "data")

    def _system_prompt_for(self, chat_id: str) -> str:
        pid, persona, mem = self._ctx(chat_id)
        base = self._system_prompt(pid, persona, mem)
        extra = []
        # 自己长出来的观点/习惯/口头禅（跟记忆分开，这是「她变了」那部分）
        try:
            gtxt = growth_mod.describe(growth_mod.load(self._growth_root(), pid, chat_id))
            if gtxt:
                extra.append(gtxt)
        except Exception as exc:
            log.debug("成长档案注入失败：%r", exc)
        if self.fe("memory"):
            summary = mem.get_summary(chat_id)
            facts = mem.facts(chat_id)
            if summary:
                extra.append(f"你记得之前的情况：{summary}")
            if facts:
                extra.append("你记得这些事：" + "；".join(f"{k}：{v}" for k, v in list(facts.items())[:12]))
            diary = mem.kv_get(chat_id, "diary_last")
            if diary:
                extra.append(f"你昨晚睡前写的日记（只有你自己知道，可以偶尔流露出这个心情）：{diary}")
        # 跟这个人单独的关系（好感度按人分开记）
        if self.fe("intimacy"):
            try:
                cur = float(mem.kv_get(chat_id, "intimacy", "") or 0)
                tier_name, tier_hint = life_mod.tier_of(cur)
                extra.append(f"你跟当前这个人单独的关系：{tier_name}（好感度 {cur:.0f}/1000）。{tier_hint}")
            except Exception:
                pass
        # 群里都有谁（可以点名 @）
        gm = re.match(r"^g(\d+)", chat_id or "")
        if gm:
            roster = (self._rosters.get(gm.group(1)) or (0, {}))[1]
            names = [n for n in dict.fromkeys(roster.keys()) if n][:25]
            if names:
                extra.append(
                    "群里这些人你认识：" + "、".join(names) +
                    "。想叫谁就写「@昵称」，会自动变成真的 @ 提醒；"
                    "但只在确实想跟某人说话时才 @，不要每条都 @，也不要乱 @ 不存在的名字。"
                )
        return "\n".join([base] + extra)

    # ------------------------------------------------------------ 旧事回忆
    STOP_WORDS = {
        "什么", "怎么", "可以", "我们", "你们", "他们", "这个", "那个", "就是", "不是", "没有", "知道",
        "觉得", "时候", "现在", "今天", "明天", "帮我", "给我", "一个", "一下", "还是", "但是", "因为",
        "所以", "如果", "然后", "真的", "好像", "是不", "有点", "感觉", "东西", "事情",
    }

    def _keywords(self, text: str) -> list[str]:
        out: list[str] = []
        for c in re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,6}", text or ""):
            if c in self.STOP_WORDS or c in out:
                continue
            out.append(c)
        return out[:5]

    def _recall(self, chat_id: str, mem, text: str, skip: int = 40) -> str:
        """翻旧账：BM25 语义检索，没命中再退回关键词。"""
        from .. import recall as recall_mod

        hits = recall_mod.search_memory(mem, chat_id, text, skip_recent=skip, limit=6)
        if not hits:
            words = self._keywords(text)
            if words:
                hits = mem.search(chat_id, words, limit=6, skip_recent=skip)
        if not hits:
            return ""
        lines = []
        for h in hits:
            who = "他" if h["role"] == "user" else "我"
            when = time.strftime("%m月%d日", time.localtime(h["ts"]))
            lines.append(f"[{when}] {who}：{h['content'][:60]}")
        log.info("旧事回忆命中 %d 条（BM25）", len(hits))
        return "\n".join(lines)

    # ------------------------------------------------------------ 联网
    async def _gather_context(self, text: str) -> str:
        wcfg = self.cfg.get("web") or {}
        if not wcfg.get("enabled"):
            return ""
        max_chars = int(wcfg.get("max_chars") or 2500)
        pages, bili, search = [], [], []
        for url in web_tools.find_urls(text)[:2]:
            pages.append(await web_tools.fetch_text(url, max_chars=max_chars))
        if any(h in text for h in VIDEO_HINTS) and wcfg.get("bilibili", True):
            keyword = re.sub(r"^(帮我|给我|你能|能不能)+", "", text).strip("，。！？? ")
            if any(h in text for h in HOT_HINTS) or len(keyword) < 3:
                bili = await web_tools.bilibili_hot(limit=5)
            else:
                bili = await web_tools.bilibili_search(keyword[:20], limit=5)
            if not bili:
                bili = await web_tools.bilibili_hot(limit=5)
        if not bili and any(h in text for h in SEARCH_HINTS) and len(text) >= 6:
            search = await web_tools.web_search(text[:30], limit=5)
        block = web_tools.context_block(pages, bili, search)
        if block:
            log.info("已联网取资料 %d 字", len(block))
        return block

    # ------------------------------------------------------------ 发送
    async def _type_delay(self, text: str, scale: float = 1.0) -> None:
        cfg = self.cfg.get("typing") or {}
        if not cfg.get("enabled"):
            return
        ms = min(len(text) * float(cfg.get("per_char_ms") or 55) * scale, float(cfg.get("max_ms") or 5000))
        await asyncio.sleep((ms + random.uniform(0, float(cfg.get("jitter_ms") or 700))) / 1000)

    def _split(self, text: str, limit: int | None = None) -> list[str]:
        cfg = self.cfg.get("split") or {}
        if not cfg.get("enabled"):
            return [text]
        limit = int(limit or cfg.get("max_segments") or 3)
        parts = [p.strip() for p in re.split(r"(?<=[。！？!?…\n])", text) if p.strip()]
        if len(parts) <= 1:
            return [text]
        if len(parts) > limit:
            parts = parts[: limit - 1] + ["".join(parts[limit - 1 :])]
        return parts

    # ------------------------------------------------------------ 群成员 / @
    async def _ensure_roster(self, gid, ttl: float = 900.0) -> dict[str, str]:
        """取群成员 昵称 -> QQ 的映射，缓存 15 分钟。"""
        if gid is None:
            return {}
        key = str(gid)
        hit = self._rosters.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        mapping: dict[str, str] = {}
        try:
            res = await self.bot.call_api("get_group_member_list", group_id=int(gid))
            data = unwrap(res) if isinstance(res, (dict, list)) else None
            if isinstance(data, dict):  # 少数协议端会包成 {"list": [...]}
                data = data.get("list") or data.get("data") or []
            for m in data or []:
                if not isinstance(m, dict):
                    continue
                name = str(m.get("card") or m.get("nickname") or "").strip()
                qq = str(m.get("user_id") or "").strip()
                if not name or not qq:
                    continue
                mapping[name] = qq
                mapping.setdefault(name.replace(" ", ""), qq)
        except Exception as exc:
            log.debug("取群成员失败：%r", exc)
        self._rosters[key] = (time.time(), mapping)
        if mapping:
            log.info("群 %s 成员 %d 人已缓存（可 @）", key, len(set(mapping.values())))
        return mapping

    def _compose(self, text: str, gid) -> Any:
        """把「@昵称」换成真正的 @ 提醒。认不出昵称就原样发文字。"""
        roster = (self._rosters.get(str(gid)) or (0, {}))[1] if gid is not None else {}
        if not roster:
            return text
        segs: list[dict] = []
        pos = 0
        hit = False
        for m in re.finditer(r"@([^\s@，。,.！!？?：:；;~～]{1,20})", text or ""):
            name = m.group(1)
            qq = roster.get(name) or roster.get(name.replace(" ", ""))
            if not qq:
                continue
            if m.start() > pos:
                segs.append(seg_text(text[pos:m.start()]))
            segs.append(seg_at(qq))
            segs.append(seg_text(" "))
            pos = m.end()
            hit = True
        if not hit:
            return text
        if pos < len(text):
            segs.append(seg_text(text[pos:]))
        return segs

    # ------------------------------------------------------------ 查询命令
    CMD_INTIMACY = ("查看好感度", "好感度排行", "好感度榜", "好感度多少")
    CMD_MOOD = ("查看心情", "现在心情", "心情怎么样", "心情如何")

    # 把内部好感度换算成 1-100 的展示分（按档位插值，看起来不会全是小数字）
    _TIER_ANCHORS = ((0.0, 1.0), (40.0, 25.0), (120.0, 50.0), (300.0, 75.0), (700.0, 100.0))

    @classmethod
    def _intimacy_100(cls, raw: float) -> int:
        pts = cls._TIER_ANCHORS
        raw = max(0.0, float(raw or 0))
        if raw <= pts[0][0]:
            return 1
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if raw <= x1:
                return max(1, min(100, int(round(y0 + (y1 - y0) * (raw - x0) / (x1 - x0)))))
        return 100

    async def _cmd_mood(self, event) -> None:
        if not self.fe("mood"):
            await self.bot.reply(event, "心情这个功能关掉了（配置台「功能」→ 心情）。")
            return
        chat_id = f"g{event.group_id}_u{event.user_id}" if event.group_id else f"u{event.user_id}"
        _pid, _persona, mem = self._ctx(chat_id)
        state = mood_mod.load((mem.get_state("__persona__") or {}).get("mood") or {})
        v = float(state.get("valence", 0))
        e = float(state.get("energy", 0.5))
        say = "我现在" + ("挺开心的" if v > 0.4 else "心情还行" if v > 0.05 else "有点低落" if v > -0.4 else "挺难受的")
        if e > 0.75:
            say += "，精神也特别好"
        elif e < 0.35:
            say += "，就是有点没劲，想躺着"
        else:
            say += "，精神一般般"
        say += f"\n（情绪值 {v:.2f}｜精力 {e:.2f}，满分都是 1）"
        await self.bot.reply(event, self._compose(say, getattr(event, "group_id", None)))

    async def _cmd_intimacy(self, event) -> None:
        if not self.fe("intimacy"):
            await self.bot.reply(event, "好感度这个功能关掉了（配置台「功能」→ 好感度）。")
            return
        gid = event.group_id
        chat_id = f"g{gid}_u{event.user_id}" if gid else f"u{event.user_id}"
        _pid, _persona, mem = self._ctx(chat_id)
        if not gid:
            raw = float(mem.kv_get(chat_id, "intimacy", "") or 0)
            await self.bot.reply(
                event,
                self._compose(
                    f"我对你的好感度：{self._intimacy_100(raw)}（{life_mod.tier_of(raw)[0]}，满分 100）",
                    getattr(event, "group_id", None),
                ),
            )
            return
        roster = await self._ensure_roster(gid)
        qq2name: dict[str, str] = {}
        for name, qq in roster.items():
            qq2name.setdefault(qq, name)
        ids = set(qq2name)
        ids |= {c.split("_u", 1)[1] for c in mem.known_chats(400) if c.startswith(f"g{gid}_u")}
        rows = []
        for uid in ids:
            raw = float(mem.kv_get(f"g{gid}_u{uid}", "intimacy", "") or 0)
            rows.append((self._intimacy_100(raw), qq2name.get(uid, f"QQ{uid}"), life_mod.tier_of(raw)[0]))
        rows.sort(key=lambda r: (-r[0], r[1]))
        if not rows:
            await self.bot.reply(event, "还没跟群里的人聊过呢，都是刚认识~")
            return
        lines = ["本群好感度（满分 100）"]
        for i, (score, name, tier) in enumerate(rows[:20], 1):
            lines.append(f"{i}. {name}  {score}  ·{tier}")
        await self.bot.reply(event, chr(10).join(lines))

    async def _send_text(self, event, text: str, limit: int | None = None, typing_scale: float = 1.0) -> None:
        gap = (self.cfg.get("split") or {}).get("gap_ms") or [500, 1500]
        segs = self._split(text, limit=limit)
        for i, seg in enumerate(segs):
            await self._type_delay(seg, scale=typing_scale)
            await self.bot.reply(event, self._compose(seg, getattr(event, "group_id", None)))
            if i < len(segs) - 1:
                await asyncio.sleep(random.uniform(gap[0], gap[1]) / 1000)

    async def _send_sticker(self, event, chat_id: str) -> None:
        if not (self.cfg.get("stickers") or {}).get("enabled"):
            return
        _pid, _persona, mem = self._ctx(chat_id)
        label = mood_mod.label(mem.get_state("__persona__").get("mood") or {})
        path = self.stickers.pick(label)
        try:
            if path is not None:
                await asyncio.sleep(random.uniform(0.4, 1.2))
                target = event.group_id if event.group_id is not None else event.user_id
                fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
                await fn(target, [seg_image(str(path))])
                log.info("已发表情包 %s", path.name)
            else:
                await self.bot.reply(event, [seg_face(random_face())])
        except Exception as exc:
            log.warning("表情包发送失败：%r", exc)

    async def _send_voice(self, event, text: str) -> bool:
        """说成语音条。失败就返回 False，让调用方退回文字。"""
        from ..tts import speak

        tcfg = self.cfg.get("tts") or {}
        try:
            silk = await speak(text, voice=tcfg.get("voice") or "zh-CN-XiaoyiNeural", cfg=tcfg)
        except Exception as exc:
            log.warning("语音合成异常：%r", exc)
            return False
        if not silk:
            return False
        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await fn(target, [seg_record(silk)])
            log.info("语音已发送：%s", text[:30])
            return True
        except Exception as exc:
            log.warning("语音发送失败：%r", exc)
            return False

    # ------------------------------------------------------------ 性格驱动行为
    def _traits(self, mem, chat_id: str) -> dict:
        st = mem.get_state("__persona__")
        return {k: float(v) for k, v in (st.get("traits") or {}).items() if isinstance(v, (int, float))}

    def _behave(self, mem, chat_id: str) -> dict:
        """把性格数值翻译成实际行为参数，而不是只写进提示词。"""
        t = self._traits(mem, chat_id)
        sticky = t.get("黏人", 0.35)
        chatty = t.get("话多", 0.4)
        gloomy = t.get("丧", 0.2)
        funny = t.get("幽默", 0.5)

        stcfg = self.cfg.get("stickers") or {}
        tcfg = self.cfg.get("tts") or {}
        pcfg = self.cfg.get("proactive") or {}
        scfg = self.cfg.get("split") or {}

        base_sticker = float(stcfg.get("probability") or 0.35)
        base_voice = float(tcfg.get("probability") or 0.22)
        min_min = float(pcfg.get("min_minutes") or 45)
        max_min = float(pcfg.get("max_minutes") or 180)

        return {
            "sticker_prob": max(0.05, min(0.85, base_sticker + sticky * 0.3 + funny * 0.15 - gloomy * 0.2)),
            "voice_prob": max(0.0, min(0.6, base_voice + sticky * 0.2)),
            "segments": max(1, min(3, int(round(1 + chatty * 2)))),
            "proactive_min": max(20, int(min_min * (1.3 - sticky * 0.7))),
            "proactive_max": max(40, int(max_min * (1.3 - sticky * 0.7))),
            "typing_scale": 1.0 + gloomy * 0.4,
            "traits": t,
            "split_max": int(scfg.get("max_segments") or 3),
        }

    # ------------------------------------------------------------ 反馈学习
    NEG_WORDS = ("别烦", "烦人", "闭嘴", "滚", "别发", "少发", "打扰", "不想聊", "别说了", "安静")
    POS_WORDS = ("哈哈", "喜欢", "想你", "可爱", "么么", "爱你", "抱抱", "开心", "好笑", "有趣", "厉害")

    def _learn_from(self, chat_id: str, mem, text: str) -> dict:
        """从这一句里学：他烦了还是喜欢？据此微调性格和主动频率。"""
        t = dict(self._traits(mem, chat_id))
        if not t:
            t = {"黏人": 0.35, "话多": 0.4, "幽默": 0.5, "丧": 0.2}
        before = dict(t)
        note = ""

        neg = [w for w in self.NEG_WORDS if w in text]
        pos = [w for w in self.POS_WORDS if w in text]

        if neg:
            t["黏人"] = t.get("黏人", 0.35) - 0.15
            t["话多"] = t.get("话多", 0.4) - 0.06
            note = f"他说了「{neg[0]}」，我该收敛点"
            mem.kv_set(chat_id, "quiet_until", time.time() + 3 * 3600)  # 三小时内不主动
        elif pos:
            t["黏人"] = t.get("黏人", 0.35) + 0.08
            t["幽默"] = t.get("幽默", 0.5) + 0.03
            note = f"他回了「{pos[0]}」，看来他吃这套"
        elif len(text.strip()) <= 3:
            t["黏人"] = t.get("黏人", 0.35) - 0.02
            note = "他回得很短，可能在忙"
        elif len(text) >= 25:
            t["话多"] = t.get("话多", 0.4) + 0.03
            note = "他愿意跟我多说几句"

        t = {k: round(max(0.0, min(1.0, float(v))), 2) for k, v in t.items()}
        if t != before:
            st = mem.get_state("__persona__")
            mem.set_state("__persona__", st.get("mood") or {}, t)
            log.info("性格微调[%s]：%s → %s（%s）", chat_id, before, t, note)
        if note:
            log_events = mem.kv_get(chat_id, "learn_log", []) or []
            log_events.append({"ts": round(time.time()), "note": note, "traits": t})
            mem.kv_set(chat_id, "learn_log", log_events[-30:])
        return t

    # ------------------------------------------------------------ 日记
    async def _write_diary(self, chat_id: str, force: bool = False) -> str:
        if not force and not self.fe("diary"):
            return ""
        pid, persona, mem = self._ctx(chat_id)
        today = time.strftime("%Y-%m-%d")
        if not force and mem.kv_get(chat_id, f"diary_{today}"):
            return ""
        history = mem.recent(chat_id, 40)
        if len(history) < 4:
            return ""
        convo = "\n".join(f"{'他' if m['role'] == 'user' else '我'}：{m['content']}" for m in history)
        st = mem.get_state("__persona__")
        ask = (
            f"今天你和他的聊天记录如下：\n{convo}\n\n"
            f"你此刻的心情是 {mood_mod.label(st.get('mood') or {})}。"
            "用第一人称写一段今天的日记，60-120 字，写你注意到的事、你的感受、你不敢说出口的那句话。"
            "不要总结对话，不要用「今天他跟我说」这种句式开头，像真的在心里想。"
        )
        text = await self._chat(
            [
                {"role": "system", "content": f"你是「{persona.get('name')}」。" + (persona.get("prompt") or "")},
                {"role": "user", "content": ask},
            ],
            temperature=0.9,
            kind="diary",
            persona=persona.get("name", ""),
            chat_id=chat_id,
        )
        text = (text or "").strip()
        if text:
            mem.kv_set(chat_id, f"diary_{today}", text)
            mem.kv_set(chat_id, "diary_last", text)
            log.info("日记已写[%s]：%s", persona.get("name"), text[:40])
        return text

    async def _diary_loop(self) -> None:
        await asyncio.sleep(180)
        while True:
            hour = int((self.cfg.get("memory") or {}).get("diary_hour", 23))
            if datetime.now().hour == hour:
                for p in self.store.personas():
                    mem = self.store.memory(p["id"])
                    for chat_id in mem.known_chats(10):
                        try:
                            await self._write_diary(chat_id)
                        except Exception as exc:
                            log.warning("写日记失败 %s：%r", chat_id, exc)
            await asyncio.sleep(3600)

    def start_diary(self) -> None:
        if self._diary_task is None or self._diary_task.done():
            self._diary_task = asyncio.create_task(self._diary_loop())

    # ------------------------------------------------------------ 复盘
    async def _reflect_chunk(self, convo: str) -> dict:
        """一次复盘调用。这类型号忽略 system，指令必须塞进 user 消息，否则它会当成聊天继续演。"""
        raw = await self._chat(
            [
                {"role": "system", "content": "你是一个只输出 JSON 的分析器。"},
                {"role": "user", "content":
                    "【分析任务，不是聊天，不要角色扮演，不要安慰我，只输出 JSON】\n"
                    + REFLECT_PROMPT + "\n\n对话记录：\n" + convo},
            ],
            temperature=0.3,
        )
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

    async def _reflect(self, chat_id: str) -> None:
        if not self._llm_ready():
            return
        pid, persona, mem = self._ctx(chat_id)
        # 硬性规定：一次复盘读 500 条对话（config: memory.reflect_history）
        n_msg = int((self.cfg.get("memory") or {}).get("reflect_history") or 500)
        history = mem.recent(chat_id, max(6, n_msg))
        if len(history) < 6:
            return
        convo = "\n".join(f"{'对方' if m['role'] == 'user' else '我'}：{m['content']}" for m in history)

        # 太长就分块复盘（每块 8000 字，最多 4 块），结果合并，别漏掉前面聊的
        step = 8000
        chunks = [convo[i:i + step] for i in range(0, len(convo), step)][:4] or [convo]
        merged: dict = {"facts": {}, "important": [], "traits": {}, "self": {}, "revise": []}
        for c in chunks:
            d = await self._reflect_chunk(c)
            if not d:
                continue
            if d.get("summary"):
                merged["summary"] = d["summary"]          # 最后一块的总结最新
            merged["facts"].update(d.get("facts") or {})
            merged["important"] += [str(x) for x in (d.get("important") or []) if str(x).strip()]
            for k, v in (d.get("traits") or {}).items():
                if isinstance(v, (int, float)):
                    merged["traits"][str(k)] = round(float(v), 2)
            s = d.get("self") or {}
            if isinstance(s, dict):
                for kind in ("opinions", "habits", "voice", "self"):
                    merged["self"].setdefault(kind, [])
                    merged["self"][kind] += [str(x) for x in (s.get(kind) or [])]
            merged["revise"] += [x for x in (d.get("revise") or []) if isinstance(x, dict)]
        data = merged
        if not data.get("summary") and not data.get("facts") and not data.get("self"):
            return
        if data.get("summary"):
            mem.set_summary(chat_id, str(data["summary"])[:400])
        for k, v in (data.get("facts") or {}).items():
            mem.upsert_fact(chat_id, k, v)
        important = list(dict.fromkeys(data.get("important") or []))[:3]
        kept = mem.mark_keep(chat_id, important)
        traits = data.get("traits") or {}
        if traits:
            state = mem.get_state("__persona__")
            m2 = dict(state.get("traits") or {})
            m2.update(traits)
            mem.set_state("__persona__", state.get("mood") or {}, m2)
        mem.reset_counter(chat_id)
        # 人设成长：把这次复盘里「她自己的变化」并进成长档案
        grew = {}
        try:
            selfdata = data.get("self") or {}
            if isinstance(selfdata, dict):
                grew = growth_mod.absorb(
                    self._growth_root(), pid, chat_id,
                    {k: [str(x) for x in (selfdata.get(k) or [])] for k in ("opinions", "habits", "voice", "self")}
                    | {"revise": data.get("revise") or []},
                )
        except Exception as exc:
            log.warning("成长档案更新失败：%r", exc)
        log.info(
            "复盘完成[%s]：读了%d条对话(%d块) 事实%d条 性格%d项 永久保留%d条 成长观点%d 习惯%d 口头禅%d",
            persona.get("name"),
            len(history), len(chunks),
            len(data.get("facts") or {}),
            len(traits),
            kept,
            len(grew.get("opinions") or []),
            len(grew.get("habits") or []),
            len(grew.get("voice") or []),
        )

    # ------------------------------------------------------------ 白名单
    def _allowed(self, event) -> bool:
        """白名单开启时：只有名单里的号（和群）才会被回复/主动找。"""
        wl = self.cfg.get("whitelist") or {}
        if not wl.get("enabled", True):
            return True
        users = {str(u).strip() for u in (wl.get("users") or []) if str(u).strip()}
        groups = {str(g).strip() for g in (wl.get("groups") or []) if str(g).strip()}
        if event.group_id is not None:
            if str(event.group_id) not in groups:
                return False
            return (not users) or (str(event.user_id) in users)
        return str(event.user_id) in users

    # ------------------------------------------------------------ 被动回复
    def _target_ok(self, event) -> bool:
        if event.sub_type == "private":
            return bool(self.cfg.get("reply_private"))
        if event.group_id is not None:
            if not self.cfg.get("reply_group"):
                return False
            if self.cfg.get("group_at_only") and f"@{self.bot.self_id}" not in (event.message or ""):
                return False
            return random.random() <= float(self.cfg.get("group_reply_probability") or 1.0)
        return False

    async def handle(self, event) -> bool:
        self.refresh()
        if not self.cfg.get("enabled"):
            return False
        if not self._allowed(event):
            # 留痕：刚装好时白名单是空的，靠这条日志自动认出「第一个来聊天的人」
            # （tools/claim.py 会扫它，把对方加进白名单，不用提前问客户 QQ 号）
            log.info(
                "白名单外消息：user=%s group=%s text=%r",
                event.user_id,
                event.group_id if event.group_id is not None else "-",
                (event.message or "")[:40],
            )
            return False

        # 关键词查询：不受「@ 才回」和概率限制，说了就答
        probe = (event.command_text or event.message or "").strip()
        if probe:
            if any(k in probe for k in self.CMD_INTIMACY):
                try:
                    await self._cmd_intimacy(event)
                except Exception as exc:
                    log.warning("好感度查询失败：%r", exc)
                return True
            if any(k in probe for k in self.CMD_MOOD):
                try:
                    await self._cmd_mood(event)
                except Exception as exc:
                    log.warning("心情查询失败：%r", exc)
                return True

        # 先顺手把别人发的图存进表情包库（不花钱、不费 token）
        stolen = None
        if (self.cfg.get("stickers") or {}).get("steal", True):
            from ..sticker_steal import steal as _steal

            stolen = await _steal(event, self.stickers.root)
            if stolen is not None:
                self.stickers.scan()

        if not self._target_ok(event):
            return False

        # 群里每个人单独一份记忆和好感度：g<群号>_u<QQ号>
        if event.group_id is not None:
            if event.user_id:
                chat_id = f"g{event.group_id}_u{event.user_id}"
            else:
                chat_id = f"g{event.group_id}"
            await self._ensure_roster(event.group_id)
        else:
            chat_id = f"u{event.user_id}"
        text = (event.command_text or event.message or "").strip()
        if not text:
            # 只发了个图：有一半概率吱一声，像真人那样
            if stolen is not None and random.random() < 0.5:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await self.bot.reply(event, random.choice(["这图我收了", "存了，回头用", "哈哈这表情我留着了"]))
                return True
            return False

        gap = float(self.cfg.get("cooldown") or 0)
        now = time.monotonic()
        if now - self._last.get(chat_id, 0) < gap:
            return False
        self._last[chat_id] = now

        pid, persona, mem = self._ctx(chat_id)
        mem.add_message(chat_id, "user", text)
        if (self.cfg.get("mood") or {}).get("enabled"):
            state = mem.get_state("__persona__")
            state["mood"] = mood_mod.nudge(mood_mod.load(state.get("mood") or {}), text)
            mem.set_state("__persona__", state["mood"], state.get("traits") or {})

        self._learn_from(chat_id, mem, text)          # 从他这句话里学一点
        beh = self._behave(mem, chat_id)              # 性格 → 实际行为参数

        # —— 生活感：作息 / 亲密度 / 记仇 / 已读不回 ——
        lcfg = self.cfg.get("life") or {}
        life_on = bool(lcfg.get("enabled", True))
        ph = life_mod.phase(persona.get("life") if isinstance(persona, dict) else None)
        icfg = self.cfg.get("intimacy") or {}
        if icfg.get("enabled", True):
            intr = life_mod.bump_intimacy(mem, chat_id, float(icfg.get("per_msg") or 1.0))
        else:
            try:
                intr = float(mem.kv_get(chat_id, "intimacy") or 0)
            except Exception:
                intr = 0.0
        tier_name, tier_hint = life_mod.tier_of(intr)
        gcfg = self.cfg.get("grudge") or {}
        if gcfg.get("enabled", True):
            life_mod.notice_hurt(mem, chat_id, text, float(gcfg.get("hours") or 10))
        angry = life_mod.grudge_left(mem, chat_id) > 0

        pcfg = self.cfg.get("playful") or {}
        wait = life_mod.delay_seconds(lcfg, ph) if life_on else 1.0
        if angry:
            wait *= 2.5
        if pcfg.get("enabled", True) and random.random() < float(pcfg.get("read_delay_chance") or 0.06):
            wait += random.uniform(60, 150)
        await asyncio.sleep(max(0.5, min(wait, 180)))

        if not self._llm_ready():
            if self.cfg.get("fallback"):
                await self._send_text(event, str(self.cfg["fallback"]))
                return True
            return False

        context = await self._gather_context(text)
        messages = [{"role": "system", "content": self._system_prompt_for(chat_id)}]
        if context:
            messages.append({"role": "system", "content": "参考资料（可用于回答，别照搬）：\n" + context})

        blocks = []
        if life_on:
            blocks.append(f"【此刻】现在是{datetime.now().strftime('%H:%M')}，你在{ph['label']}：{ph['hint']}。"
                          + ("话要短，最多一句。" if ph["short"] else ""))
        blocks.append(f"【关系】你和他现在是「{tier_name}」：{tier_hint}。别跳出这个分寸。")
        if angry:
            blocks.append("【情绪】你还在为刚才那句话生气：回得冷、句子短，不哄他、不发表情包、不主动找话题。")
        elif pcfg.get("enabled", True) and random.random() < 0.55:
            blocks.append("【主动】这一句后面顺手问他一件小事（今天干嘛了/吃了没/几点睡），只问一件。")
        messages.append({"role": "system", "content": "\n".join(blocks)})

        history = int((self.cfg.get("memory") or {}).get("history") or 40)
        recall = self._recall(chat_id, mem, text, skip=history)
        if recall:
            messages.append({"role": "system", "content": "你忽然想起以前聊过的这些（可以自然地提一句，别硬提）：\n" + recall})
        messages.extend(mem.recent(chat_id, history))
        # 型号不认 system 时：先说两条示范，再把身份和规则贴在对方最后这句话前面
        if (self.cfg.get("llm") or {}).get("prime", True):
            messages[1:1] = [dict(x) for x in self.FEW_SHOT]
            if messages and messages[-1].get("role") == "user":
                try:
                    grow_brief = growth_mod.brief(growth_mod.load(self._growth_root(), pid, chat_id))
                except Exception:
                    grow_brief = ""
                messages[-1] = {"role": "user",
                                "content": self._reminder(persona, grow_brief, self._soft_style()) + str(messages[-1].get("content") or "")}

        # 「做个图」：现场拼一张给她
        if re.search(r"(做个?图|做张?图|发张?图|发个图|梗图|把.{0,14}做成图)", text):
            if await self._send_made_image(event, chat_id, text):
                mem.add_message(chat_id, "assistant", "[自己做了张图发过去]")
                return True

        answer = await self._chat(messages)
        if not answer:
            return False

        want_sticker = bool(re.search(r"[\[【](表情|表情包|sticker)[\]】]", answer))
        answer = re.sub(r"[\[【](表情|表情包|sticker)[\]】]", "", answer).strip()
        answer = self._tighten(answer)   # 压成人话：短句、去客服腔、去旁白

        tcfg = self.cfg.get("tts") or {}
        force_voice = bool(re.search(r"(发个?语音|说句话|语音回|用语音)", text))
        use_voice = bool(answer) and (
            force_voice
            or (
                tcfg.get("enabled")
                and len(answer) <= int(tcfg.get("max_chars") or 60)
                and random.random() < float(beh["voice_prob"])
            )
        )
        spoken = await self._send_voice(event, answer) if use_voice else False
        if answer and not spoken:
            await self._send_text(event, answer, limit=beh["segments"], typing_scale=beh["typing_scale"])
        mem.add_message(chat_id, "assistant", answer)

        if pcfg.get("enabled", True) and not angry and random.random() < float(pcfg.get("typo_chance") or 0.05):
            await self._slip_and_fix(event, answer, beh)

        if not angry and (want_sticker or random.random() < float(beh["sticker_prob"])):
            await self._send_sticker(event, chat_id)

        icfg = self.cfg.get("image") or {}
        if answer and icfg.get("enabled", True) and random.random() < float(icfg.get("probability") or 0.05):
            await self._send_made_image(event, chat_id, answer, kind="quote")

        every = int((self.cfg.get("memory") or {}).get("reflect_every") or 12)
        n = mem.bump_counter(chat_id)
        if every > 0 and n >= every:
            asyncio.create_task(self._reflect(chat_id))
        return True

    # ------------------------------------------------------------ 自己做图
    async def _send_made_image(self, event, chat_id: str, text: str, kind: str = "auto") -> bool:
        """用 PIL 现场拼一张图发出去：梗图 / 金句卡。"""
        from .. import makeimg

        _pid, persona, mem = self._ctx(chat_id)
        icfg = self.cfg.get("image") or {}
        if not icfg.get("enabled", True):
            return False

        line = re.sub(r"^(给我|帮我|你)+", "", (text or "").strip())
        line = re.sub(r"(做个?图|做张?图|发张?图|发个图|梗图|做成图|图片|图)[吧啊呀嘛呢?？]*", "", line).strip()
        line = line.strip("，。！？、:： ")
        if len(line) < 2:
            hist = mem.recent(chat_id, 6)
            line = next((m["content"] for m in reversed(hist) if m["role"] == "assistant"), "今天有点想你")
            line = line[:60]

        author = persona.get("name") or "小柚"
        try:
            if kind == "quote":
                path = makeimg.quote(line, author=author)
            elif kind == "meme":
                path = makeimg.meme(line)
            elif re.search(r"梗图|搞笑|笑死|哈哈", line):
                path = makeimg.meme(line)
            else:
                path = makeimg.meme(line) if random.random() < 0.55 else makeimg.quote(line, author=author)
        except Exception as exc:
            log.warning("拼图失败：%r", exc)
            return False
        if not path:
            return False

        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await asyncio.sleep(random.uniform(0.4, 1.2))
            await fn(target, [seg_image(path)])
        except Exception as exc:
            log.warning("发图失败：%r", exc)
            return False
        log.info("自己做了张图[%s]：%s（%s）", author, line[:24], path)
        return True

    # ------------------------------------------------------------ 手滑
    async def _slip_and_fix(self, event, answer: str, beh: dict) -> None:
        """手滑：先发一句打错的，隔一两秒撤回，再发对的。"""
        broken = life_mod.typo(answer)
        if not broken or broken == answer:
            return
        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await asyncio.sleep(random.uniform(0.3, 0.9))
            res = await fn(target, broken)
            mid = (res or {}).get("message_id") if isinstance(res, dict) else None
            await asyncio.sleep(random.uniform(1.0, 2.4))
            if mid:
                await self.bot.call_api("delete_msg", message_id=mid)
                log.info("手滑了一下，撤回了：%s", broken[:20])
        except Exception as exc:
            log.debug("手滑失败：%r", exc)

    # ------------------------------------------------------------ 视频分享
    def _interest_keywords(self, chat_id: str) -> list[str]:
        vcfg = self.cfg.get("video") or {}
        kws = [str(k) for k in (vcfg.get("keywords") or []) if str(k).strip()]
        _pid, _persona, mem = self._ctx(chat_id)
        facts = mem.facts(chat_id)
        for key in ("喜好", "兴趣", "爱好", "喜欢的", "游戏", "番剧", "追的剧"):
            for k, v in facts.items():
                if key in k:
                    kws.append(str(v)[:12])
        return [k for k in kws if k][:4]

    async def _share_video(self, event, chat_id: str) -> bool:
        """逛 B 站，挑一个没发过的，用自己的口吻分享。B 站关掉时自动转抖音。"""
        vcfg = self.cfg.get("video") or {}
        if not vcfg.get("enabled", True):
            return False
        if not vcfg.get("bili", True):
            return await self._share_douyin(event, chat_id)

        _pid, persona, mem = self._ctx(chat_id)
        seen = [str(x) for x in (mem.kv_get(chat_id, "shared_bvids", []) or [])][-60:]

        items: list[dict] = []
        for kw in self._interest_keywords(chat_id):
            items = await web_tools.bilibili_search(kw, limit=8)
            items = [it for it in items if web_tools.bvid_of(it) not in seen]
            if items:
                break
        if not items:
            items = [it for it in await web_tools.bilibili_hot(limit=12) if web_tools.bvid_of(it) not in seen]
        if not items:
            return False

        pick = random.choice(items[:5])
        bvid = web_tools.bvid_of(pick)
        info = await web_tools.bilibili_video_info(bvid) if bvid else {}
        title = info.get("title") or pick.get("title") or ""
        if not title:
            return False
        desc = info.get("desc") or ""
        author = info.get("author") or pick.get("author") or ""
        play = info.get("view") or pick.get("play") or 0
        url = info.get("url") or pick.get("url") or ""

        ask = (
            f"你刚刷到一个视频：《{title}》，UP主是{author}，简介：{desc[:150]}。"
            "用你自己的语气跟他说一句，20 字以内，像随口安利，别用「推荐」「链接」这种词。"
        )
        say = await self._chat(
            [
                {"role": "system", "content": self._system_prompt_for(chat_id)},
                {"role": "user", "content": ask},
            ],
            temperature=0.95,
        )
        say = re.sub(r"[\[【](表情|表情包)[\]】]", "", say or "").strip() or "这个你肯定爱看"

        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await asyncio.sleep(random.uniform(0.6, 1.6))
            await self.bot.reply(event, say)
            await asyncio.sleep(random.uniform(0.8, 1.8))
            await fn(target, [seg_link(url, title=title, desc=f"{author} · {max(0, int(play))} 播放")])
        except Exception as exc:
            log.warning("分享视频失败：%r", exc)
            return False

        if bvid:
            seen.append(bvid)
            mem.kv_set(chat_id, "shared_bvids", seen[-60:])
        log.info("分享视频[%s]：%s %s", persona.get("name"), title[:30], url)
        return True

    async def _share_douyin(self, event, chat_id: str) -> bool:
        if not self.fe("douyin"):
            return False
        """刷抖音：抓推荐流 → 截屏 → 用自己的口吻分享。抓不到就退回热榜链接。"""
        from .. import douyin as douyin_mod

        _pid, persona, mem = self._ctx(chat_id)
        seen = [str(x) for x in (mem.kv_get(chat_id, "shared_douyin", []) or [])][-60:]

        vcfg = self.cfg.get("video") or {}
        headless = bool(vcfg.get("headless", True))
        prefer = str(vcfg.get("browser") or "edge")

        items = [it for it in await douyin_mod.fetch_feed(limit=10, scroll=2, headless=headless, prefer=prefer)
                 if it.get("title") not in seen]
        shot = None
        if items:
            shot = await douyin_mod.capture(path=f"tmp/douyin-{int(time.time())}.jpg", headless=headless, prefer=prefer)

        hot_items = []
        if not items or not shot:
            hot_items = [it for it in await web_tools.douyin_hot(14) if it.get("title") not in seen]
        if not items and not hot_items:
            return False

        if items:
            pick = random.choice(items[:5])
            title = pick.get("title") or ""
            author = pick.get("author") or ""
            url = pick.get("url") or ""
            hot = ""
        else:
            pick = random.choice(hot_items[:6])
            title = pick.get("title") or ""
            author = ""
            url = pick.get("url") or ""
            hot = pick.get("hot") or ""

        hint = f"《{title}》" + (f"，作者 {author}" if author else "") + (f"（热度 {hot}）" if hot else "")
        ask = (
            f"你刚在抖音刷到{hint}。"
            "用你自己的语气跟他说一句，25 字以内，像随口分享，别用「推荐」「热搜」「链接」这些词。"
        )
        say = await self._chat(
            [
                {"role": "system", "content": self._system_prompt_for(chat_id)},
                {"role": "user", "content": ask},
            ],
            temperature=0.95,
        )
        say = re.sub(r"[\[【](表情|表情包)[\]】]", "", say or "").strip() or f"刷到这个，{title[:12]}"

        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await asyncio.sleep(random.uniform(0.6, 1.5))
            await self.bot.reply(event, say)
            await asyncio.sleep(random.uniform(0.8, 1.8))
            if shot:
                await fn(target, [seg_image(shot)])
            elif url:
                await fn(target, [seg_link(url, title=title[:40], desc=f"抖音 · {author or hot}")])
            else:
                return False
        except Exception as exc:
            log.warning("分享抖音失败：%r", exc)
            return False

        seen.append(title)
        mem.kv_set(chat_id, "shared_douyin", seen[-60:])
        log.info("分享抖音[%s]：%s（%s）", persona.get("name"), title[:30], "截图" if shot else "链接")
        return True

    async def _video_loop(self) -> None:
        """定时刷视频，看到有意思的主动发给他。"""
        await asyncio.sleep(420)
        while True:
            vcfg = self.cfg.get("video") or {}
            if not vcfg.get("enabled"):
                await asyncio.sleep(3600)
                continue
            hours = float(vcfg.get("share_hours") or 3)
            await asyncio.sleep(max(1200, hours * 3600))
            if not vcfg.get("enabled") or self._quiet(datetime.now().hour) or not self._llm_ready():
                continue
            self._today_key()
            cap = int(vcfg.get("daily_max") or 3)
            for chat_id in self._whitelisted_targets():
                if self._video_today.get(chat_id, 0) >= cap:
                    continue
                kind, target = chat_id[0], chat_id[1:]
                ev = _Shell(
                    group_id=int(target) if kind == "g" else None,
                    user_id=int(target) if kind == "u" else None,
                )
                try:
                    use_douyin = bool(vcfg.get("douyin", True)) and random.random() < 0.35
                    ok = await self._share_douyin(ev, chat_id) if use_douyin else await self._share_video(ev, chat_id)
                    if ok:
                        self._video_today[chat_id] = self._video_today.get(chat_id, 0) + 1
                except Exception as exc:
                    log.warning("主动分享视频失败 %s：%r", chat_id, exc)

    def start_video(self) -> None:
        if self._video_task is None or self._video_task.done():
            self._video_task = asyncio.create_task(self._video_loop())

    def _whitelisted_targets(self) -> list[str]:
        p = self.cfg.get("proactive") or {}
        targets = [str(t) for t in (p.get("targets") or [])]
        if not targets:
            for pid in [x.get("id") for x in self.store.personas()]:
                targets.extend([c for c in self.store.memory(pid).known_chats(10) if c.startswith("u")])
        wl = self.cfg.get("whitelist") or {}
        if wl.get("enabled", True):
            users = {str(u).strip() for u in (wl.get("users") or []) if str(u).strip()}
            groups = {str(g).strip() for g in (wl.get("groups") or []) if str(g).strip()}
            targets = [
                t for t in targets if (t[:1] == "u" and t[1:] in users) or (t[:1] == "g" and t[1:] in groups)
            ]
        return targets

    # ------------------------------------------------------------ 主动开聊
    def _quiet(self, hour: int) -> bool:
        p = self.cfg.get("proactive") or {}
        start, end = int(p.get("quiet_start", 23)), int(p.get("quiet_end", 8))
        return hour >= start or hour < end

    def _today_key(self) -> str:
        day = time.strftime("%Y-%m-%d")
        if day != self._day:
            self._day, self._sent_today = day, {}
        return day

    async def _proactive_once(self) -> int:
        p = self.cfg.get("proactive") or {}
        if not p.get("enabled") or not self._llm_ready() or self._quiet(datetime.now().hour):
            return 0

        self._today_key()
        cap = int(p.get("max_per_day") or 6)
        targets = [str(t) for t in (p.get("targets") or [])]
        if not targets:
            for pid in [x.get("id") for x in self.store.personas()]:
                targets.extend([c for c in self.store.memory(pid).known_chats(10) if c.startswith("u")])

        wl = self.cfg.get("whitelist") or {}
        if wl.get("enabled", True):
            users = {str(u).strip() for u in (wl.get("users") or []) if str(u).strip()}
            groups = {str(g).strip() for g in (wl.get("groups") or []) if str(g).strip()}
            targets = [
                t for t in targets if (t[:1] == "u" and t[1:] in users) or (t[:1] == "g" and t[1:] in groups)
            ]

        sent = 0
        for chat_id in targets:
            kind = chat_id[0] if chat_id else ""
            if kind not in ("u", "g"):
                continue
            target = chat_id[1:]
            _pid, persona, mem = self._ctx(chat_id)
            if self._sent_today.get(chat_id, 0) >= cap:
                continue
            min_gap = float(p.get("min_gap_seconds") or 1200)
            if min_gap and time.time() - mem.last_ts(chat_id) < min_gap:
                continue

            context = ""
            if random.random() < float(p.get("link_probability") or 0):
                bili = await web_tools.bilibili_hot(limit=5)
                if bili:
                    context = web_tools.context_block([], bili)

            ccfg = self.cfg.get("care") or {}
            if ccfg.get("enabled", True):
                hh = datetime.now().hour
                m0, m1 = (list(ccfg.get("morning") or [7, 10]) + [0, 0])[:2]
                e0, e1 = (list(ccfg.get("evening") or [20, 23]) + [0, 0])[:2]
                if m0 <= hh <= m1 or e0 <= hh <= e1:
                    wline = await asyncio.to_thread(life_mod.weather_line, str(ccfg.get("city") or ""))
                    if wline:
                        context = (context + "\n" if context else "") + "今天天气：" + wline

            ask = (
                f"现在是 {datetime.now().strftime('%H:%M')}，群里没人说话，你自己找点事开口。"
                f"{random.choice(PROACTIVE_INTENTS)}。"
                "回 1-2 条短消息，每条不超过 25 字，不要说「在吗」这种空话，不要重复最近说过的话。"
            )
            if context:
                ask += "可以顺手分享一个 B 站视频链接。"
            messages = [{"role": "system", "content": self._system_prompt_for(chat_id)}]
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": ask})

            answer = await self._chat(messages, temperature=1.0)
            if not answer:
                continue
            want_sticker = bool(re.search(r"[\[【](表情|表情包)[\]】]", answer))
            answer = re.sub(r"[\[【](表情|表情包)[\]】]", "", answer).strip()

            ev = _Shell(group_id=int(target) if kind == "g" else None, user_id=int(target) if kind == "u" else None)
            try:
                if answer:
                    await self._send_text(ev, answer)
                    mem.add_message(chat_id, "assistant", answer)
                if want_sticker or random.random() < float(p.get("sticker_probability") or 0):
                    await self._send_sticker(ev, chat_id)
                self._sent_today[chat_id] = self._sent_today.get(chat_id, 0) + 1
                sent += 1
                log.info("主动开聊[%s] -> %s：%s", persona.get("name"), chat_id, answer[:40])
            except Exception as exc:
                log.warning("主动消息失败 %s：%r", chat_id, exc)
        return sent

    async def _proactive_loop(self) -> None:
        await asyncio.sleep(30)
        while True:
            p = self.cfg.get("proactive") or {}
            lo = max(5, int(p.get("min_minutes") or 45))
            hi = max(lo, int(p.get("max_minutes") or 180))
            await asyncio.sleep(random.randint(lo * 60, hi * 60))
            try:
                self.refresh()
                await self._proactive_once()
            except Exception as exc:
                log.error("主动消息循环异常：%r", exc)

    def start_proactive(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._proactive_loop())

    # ------------------------------------------------------------ 自动备份
    async def _backup_loop(self) -> None:
        await asyncio.sleep(60)
        while True:
            mcfg = self.cfg.get("memory") or {}
            hours = float(mcfg.get("backup_hours") or 6)
            if hours > 0:
                try:
                    made = self.store.backup(keep=int(mcfg.get("backup_keep") or 20))
                    if made:
                        log.info("自动备份完成：%d 份", len(made))
                except Exception as exc:
                    log.error("自动备份失败：%r", exc)
            await asyncio.sleep(max(600, hours * 3600))

    def start_backup(self) -> None:
        if self._backup_task is None or self._backup_task.done():
            self._backup_task = asyncio.create_task(self._backup_loop())

    # ------------------------------------------------------------ 记忆清理
    async def _prune_loop(self) -> None:
        """普通对话只留 retain_days 天，重要记忆（keep=1）永久保留。"""
        await asyncio.sleep(120)
        while True:
            mcfg = self.cfg.get("memory") or {}
            days = float(mcfg.get("retain_days") or 14)
            if days > 0:
                for p in self.store.personas():
                    try:
                        n = self.store.memory(p["id"]).prune(days)
                        if n:
                            log.info("清理[%s]：删除 %d 条超过 %.0f 天的普通记忆", p.get("name"), n, days)
                    except Exception as exc:
                        log.error("清理记忆失败 %s：%r", p.get("id"), exc)
            await asyncio.sleep(max(1800, float(mcfg.get("prune_hours") or 6) * 3600))

    def start_prune(self) -> None:
        if self._prune_task is None or self._prune_task.done():
            self._prune_task = asyncio.create_task(self._prune_loop())


# ---------------------------------------------------------------- 插件入口
def setup(bot) -> None:
    global ENGINE
    cfg = {}
    config = getattr(bot, "config", None)
    if config is not None:
        try:
            cfg = config.section("autoreply")
        except Exception:
            cfg = {}
    engine = Companion(bot, cfg)
    ENGINE = engine

    def chat_of(event) -> str:
        return f"g{event.group_id}" if event.group_id is not None else f"u{event.user_id}"

    @bot.on_message(priority=900)
    async def companion_handler(bot, event):
        return await engine.handle(event)

    async def show_personas(bot, event):
        chat = chat_of(event)
        cur = engine.store.chat_persona(chat)
        active = engine.store.active_id()
        lines = ["人格列表："]
        for p in engine.store.personas():
            mark = " ← 你会话在用的" if p["id"] == cur else ""
            mark2 = "（默认）" if p["id"] == active else ""
            lines.append(f"· {p['name']}（{p['id']}）{mark2}{mark}")
        lines.append("发「切换人格 名字」就可以换人（记忆各自独立）")
        await bot.reply(event, "\n".join(lines))
        return True

    async def switch_persona(bot, event):
        chat = chat_of(event)
        if not engine.fe("persona"):
            await bot.reply(event, "现在不让换人格（配置台「功能」→ 人格切换 关着）。")
            return True
        arg = (event.command_text or "").replace("切换人格", "").replace("换人格", "").strip()
        target = engine.store.find_by_name(arg)
        if not target:
            await bot.reply(event, f"没有叫「{arg}」的人格，发「人格」看看有哪些。")
            return True
        engine.store.set_chat_persona(chat, target["id"])
        await bot.reply(event, f"好，现在是{target['name']}在跟你说话。")
        return True

    async def show_memory(bot, event):
        chat = chat_of(event)
        pid, persona, mem = engine._ctx(chat)
        st = mem.get_state("__persona__")
        facts = mem.facts(chat)
        lines = [
            f"人格：{persona.get('name')}（{pid}）",
            f"记忆条数：{mem.message_count(chat)}",
            f"心情：{mood_mod.label(st.get('mood') or {})}",
            "性格：" + ("，".join(f"{k}{v}" for k, v in (st.get("traits") or {}).items()) or "还在养成"),
            "摘要：" + (mem.get_summary(chat) or "无"),
            "记得的事：" + ("；".join(f"{k}={v}" for k, v in list(facts.items())[:8]) or "无"),
        ]
        await bot.reply(event, "\n".join(lines))
        return True

    async def do_forget(bot, event):
        chat = chat_of(event)
        _pid, _persona, mem = engine._ctx(chat)
        mem.forget(chat)
        await bot.reply(event, "好，关于你的记忆我清空了。")
        return True

    async def do_backup(bot, event):
        made = engine.store.backup(keep=int((engine.cfg.get("memory") or {}).get("backup_keep") or 20))
        if made:
            names = "、".join(x.split("\\")[-1] for x in made)
            await bot.reply(event, f"已备份 {len(made)} 份：{names}")
        else:
            await bot.reply(event, "没有可备份的记忆（还没聊过？）")
        return True

    async def do_restore(bot, event):
        arg = (event.command_text or "").replace("恢复记忆", "").replace("恢复备份", "").strip()
        if not arg:
            items = engine.store.backups()[:5]
            lines = ["恢复记忆需要指定备份文件，最近的备份："] + [
                f"· {b['file']}（{b['persona_name']}，{datetime.fromtimestamp(b['time']):%m-%d %H:%M}）" for b in items
            ]
            lines.append("发「恢复记忆 文件名」")
            await bot.reply(event, "\n".join(lines))
            return True
        res = engine.store.restore(arg)
        if res.get("ok"):
            await bot.reply(event, f"已从 {arg} 恢复（当前库也留了一份安全备份）。")
        else:
            await bot.reply(event, f"恢复失败：{res.get('error')}")
        return True

    for cmd in ("人格", "personas"):
        bot.on_message(command=cmd, priority=850, desc="看有哪些人格")(show_personas)
    for cmd in ("切换人格", "换人格"):
        bot.on_message(command=cmd, priority=850, desc="切换人格：切换人格 阿糖")(switch_persona)
    for cmd in ("记忆", "memory"):
        bot.on_message(command=cmd, priority=850, desc="看当前人格记得你什么")(show_memory)
    for cmd in ("备份记忆", "记忆备份", "backup"):
        bot.on_message(command=cmd, priority=850, desc="立刻备份记忆")(do_backup)
    for cmd in ("恢复记忆", "恢复备份"):
        bot.on_message(command=cmd, priority=850, desc="从备份恢复记忆")(do_restore)
    for cmd in ("忘记我", "忘掉", "reset"):
        bot.on_message(command=cmd, priority=850, desc="清空当前会话记忆")(do_forget)

    engine.store.backup()
    engine.start_proactive()
    engine.start_backup()
    engine.start_prune()
    engine.start_diary()
    llm = engine.cfg.get("llm") or {}
    p = engine.cfg.get("proactive") or {}
    mcfg = engine.cfg.get("memory") or {}
    log.info(
        "陪聊引擎就绪｜模型 %s｜人格 %d 个（当前 %s）｜记忆 %s（普通保留 %s 天，重要永久）｜表情包 %d 张｜主动开聊 %s｜白名单 %s",
        llm.get("model"),
        len(engine.store.personas()),
        engine.store.active_id(),
        "开" if mcfg.get("enabled") else "关",
        mcfg.get("retain_days"),
        engine.stickers.count(),
        "开" if p.get("enabled") else "关",
        "开" if (engine.cfg.get("whitelist") or {}).get("enabled") else "关",
    )
