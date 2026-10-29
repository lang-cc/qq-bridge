"""拟人陪聊引擎（多人格 + 长期记忆 + 心情 + 上网 + 表情包 + 主动开聊 + 记忆备份）。

每个人格独立记忆库（data/personas/<id>/memory.db）。一个号固定一个人格：
第一次说话时自动绑定，之后不能在聊天里换（只留查看）。
  「人格」             看当前跟你说话的是哪个人格
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
from .. import catchup as catchup_mod
from .. import humanlike
from .. import loops as loops_mod
from .. import mood as mood_mod
from .. import selfhood as selfhood_mod
from .. import wander as wander_mod
from .. import web_tools
from .. import world as world_mod
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
        "reflect_every": 5,
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
    "life": {"enabled": True},
    "intimacy": {"enabled": True, "per_msg": 1.0},
    "grudge": {"enabled": True, "hours": 10},
    "diary": {"enabled": True, "diary_hour": 23},
    "douyin": {"enabled": True},
    # 悬案：他说过还没结果的事（面试/体检/等他回话），到点了她会自己追问
    "loops": {
        "enabled": True,
        "max_ask": 3,
        "drop_days": 45,
        "max_prompt": 2,
        "min_hours": 6,
    },
    # 会误解：偶尔没听懂/理解偏/直接问「啥意思」—— 永远秒懂最假
    "misread": {"enabled": True, "chance": 0.10, "ask_word_chance": 0.06},
    # 生活细节：具体、跨天不变的地名/店名/室友/猫
    "world": {"enabled": True, "fixed": {}},
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
{"summary": "你们关系与近况的一句话概述，80字内", "facts": {"键": "要长期记住的事，如昵称/职业/喜好/约定；群聊里外号写成「群梗·某某」，大家最近在说的梗写成「群梗·关键词」"}, "traits": {"幽默": 0.6, "黏人": 0.3, "话多": 0.4, "丧": 0.2}, "important": ["必须永久记住的原话要点，最多3条"], "self": {"opinions": ["这几轮里你明确表达过的一个看法，第一人称、20字内"], "habits": ["你最近的状态或习惯，如「连着三晚两点睡」，20字内"], "voice": ["你嘴上常挂的一个词或语气，如「行吧」「烦死了」"], "self": ["你对自己的一句认知，如「我嘴硬心软」"]}, "selfhood": {"goal": "你最近想做的一件事，第一人称、20字内", "desire": "你现在憋着想跟他说、还没说出口的一句，20字内", "ask": "你想跟他提的一个要求（让他陪你/帮你/别烦你），20字内", "avoid": "你现在不太想聊的一件事，20字内", "inner": "你此刻脑子里的一句，15字内"}, "loops": [{"thing": "面试", "detail": "周五下午二面，他有点慌", "due_days": 3}], "loops_done": ["体检"], "revise": [{"from": "你以前坚持过的一条看法原文", "to": "这轮你被说服后改成的新说法"}]}
traits 取 0-1，表示你目前的性格倾向。important 只放真正重要的事（约定、家人、健康、重要日期、矛盾与和解），没有就给空数组。
self 是你自己的变化，只写这次对话里**新出现**的，没有就给空数组，不要硬凑、不要重复以前的。
selfhood 只写这次对话里冒出、而且**还没说出口**的；没有就留空字符串，别编。
loops 是他提过、但**还没结果**的事：要去办的事、要等的结果、约好的事（面试/体检/考试/发工资/见家长/搬家/等消息）。
thing 只写 2-6 个字的名词短语（「面试」「体检报告」「他妈生日」），detail 写你记得的细节（20字内），
due_days 是「过几天问合适」（0.2 到 30 之间，拿不准就给 2）。他随口一说、没有下落的情绪抱怨不要写进来。
loops_done 是这次对话里**已经有结果**的事（他说考完了/去过了/没戏了/不用去了），只写 loops 里那几个字；没有给空数组。
revise 只在**你确实松口、让步、被说服或改主意**时才写（比如本来死活不肯的，这轮愿意了）；没改变就给空数组。
特别注意：相处久了人会有变化，别把立场写死。"""


def _json_of(raw: str) -> dict:
    """从模型输出里抠 JSON：```json 代码块、前缀废话、尾随说明都要能容忍。"""
    if not raw:
        return {}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


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
        # 同一会话的生成串行锁：避免两轮同时生成、各回一句（上句不接下句的根源）
        self._locks: dict[str, asyncio.Lock] = {}
        # 生成期间又收到的消息，攒着让当前这轮一起读进上下文
        self._pending: dict[str, list[str]] = {}
        # 复盘也不能并发：同一批对话被反复读，人设会被洗乱
        self._reflect_locks: dict[str, asyncio.Lock] = {}

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
        extra: dict | None = None,
    ) -> str:
        import aiohttp

        llm = self.cfg.get("llm") or {}
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        _raw = temperature if temperature is not None else llm.get("temperature")
        try:
            _t = float(_raw)
        except (TypeError, ValueError):
            _t = 0.95
        if 2.0 < _t <= 100.0:  # 配置台把 70（=0.7）这种百分数直接写进来了，救一下
            _t = _t / 100.0
            log.warning("temperature 配成了 %r，按 %.2f 用（合法范围 0~2）", _raw, _t)
        body = {
            "model": llm.get("model") or "",
            "messages": messages,
            "temperature": max(0.0, min(2.0, _t)),
        }
        # 重复惩罚：真人不会每句都一个腔调，模型会
        if llm.get("presence_penalty") is not None:
            body["presence_penalty"] = float(llm["presence_penalty"])
        if llm.get("frequency_penalty") is not None:
            body["frequency_penalty"] = float(llm["frequency_penalty"])
        if llm.get("max_tokens"):
            try:
                body["max_tokens"] = int(llm["max_tokens"])
            except (TypeError, ValueError):
                pass
        if extra:
            body.update(extra)
        headers = {"Content-Type": "application/json"}
        if llm.get("api_key"):
            headers["Authorization"] = f"Bearer {llm['api_key']}"
        url = str(llm.get("base_url") or "").rstrip("/") + "/chat/completions"
        # 中转站会偶发 503（「Service temporarily unavailable」，0.3 秒就返回），
        # 以前一次失败就整条回复丢了——表现就是「她突然不回话」。这里补两次短退避重试。
        data = None
        for attempt in range(4):
            try:
                async with self._session.post(url, json=body, headers=headers, timeout=120) as r:
                    if r.status >= 500:
                        raise RuntimeError(f"HTTP {r.status}")
                    data = await r.json(content_type=None)
                break
            except Exception as exc:
                if attempt >= 3:
                    log.error("模型调用失败（重试 3 次仍然失败）：%r", exc)
                    return ""
                wait = 0.8 * (attempt + 1)
                log.warning("模型调用失败（第 %d 次）：%r，%.1fs 后重试", attempt + 1, exc, wait)
                await asyncio.sleep(wait)

        if not (data.get("choices") if isinstance(data, dict) else None):
            # 没有 choices 基本就是接口报错（比如 temperature 超出 0~2），
            # 以前这里静默返回空串，表现就是「机器人不回话」，日志里什么都看不到。
            log.error("模型返回没有 choices，八成是配置或配额问题：%s", str(data)[:300])
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

        choice = (data.get("choices") or [{}])[0]
        text = (((choice.get("message") or {}).get("content")) or "").strip()
        if not text and choice.get("finish_reason") == "length":
            # 推理型模型（如 deepseek-v4-pro）会先把 token 花在思考上，正文一个字都吐不出来。
            # 调用方拿到空串会当成「模型没说话」，所以必须留痕，不然查都没处查。
            log.warning("模型正文为空且被截断（finish_reason=length）：多半是思考把 token 用光了，"
                        "调大 llm.max_tokens 或换非推理档")
        return text

    # ------------------------------------------------------------ prompt
    HUMAN_RULES = (
        "【怎么说话 —— 硬要求，违反就不像人了】\n"
        "1. 多数时候一句就够，一般不超过 12 个字；对方问正经事也不超过 25 个字。"
        "真想再补一句就换行另起一条（一次最多两条），别用逗号把两句缝成一句。\n"
        "2. 不解释、不补充、不总结、不列点、不用 markdown，不用引号把整句包起来。\n"
        "3. 禁止客服腔：不许出现「希望」「如果需要」「建议你」「随时告诉我」「有什么可以帮你」"
        "「很高兴」「首先」「其次」「总之」「另外」「总的来说」。\n"
        "4. 允许敷衍和情绪：不想聊就回「嗯」「哦」「不知道」「困了」「烦」；生气了就短、冷、不哄人。\n"
        "5. 用口语和口头禅（诶、啊、哈、嘛、呗、行吧、真的假的、救命、离谱），可以有语气词。\n"
        "6. 不用书面连接词，句子可以不完整，像微信打字那样想到哪说到哪。\n"
        "7. 别追问超过一件小事；对方没问就别主动给建议。\n"
        "8. 绝不提自己是 AI、模型、程序，也不解释自己为什么这么说话。\n"
        "9. 不要每句都带颜文字或波浪号，十次里最多一次。\n"
        "10. 背景设定是给你自己知道的，不要把它当台词复述出来。\n"
        "11. 标点别像写作文：短句不点句号收尾，一句最多一个标点，能不点就不点；也不要用「，」把短句拆成书面语。\n"
        "12. 被问「你是谁」「你是不是 XX」这类，用角色口吻一句带过，别复述设定、别背简介。\n"
    )

    # 说话规则：不解释自己、不解决问题、长度不均、允许多种「不完美」
    RULE_SAY = (
        "【怎么说话】\n"
        "别把聊过的事全过一遍，只接他这句话；他说十件事你挑一件就够了。\n"
        "别解释你是怎么知道的、怎么想出来的，也别说「让我分析」「我查了一下」。\n"
        "拿不准就说拿不准，别硬编；他吐槽你就跟着吐槽一句，不用给建议。\n"
        "大部分时候你只是接话，不是解决问题 —— 他没问怎么办，就别教他怎么办。\n"
        "长度要乱：有时两三个字，有时两三句，别每条都差不多长。\n"
        "有时候只答一半，剩下的等他自己问；偶尔也能把刚说过的话再说一遍。\n"
        "他问「在吗」，回一句「嗯」或「在」，别主动问什么事。\n"
        "照他字面接：他说「还行就是不好呗」，你就解释或者顶一句「不是不好 就是一般」，别把它当成指责然后认错。\n"
        "他没骂你、没怪你，就别道歉；道歉要真的是你做错了才用。\n"
        "短句配一个表情包更像人，长段落别配。"
    )

    # 有自己的想法：会评价、会不同意、会岔开，不是只做应答机
    RULE_OWN = (
        "【你有自己的想法】别句句顺着他说。他讲完你可以评价、可以说「我觉得你想多了」、也可以不同意。\n"
        "每三四轮至少一次把你自己的事带出来（见【你自己此刻的事】），哪怕只一句，比如你刚遇到什么、你正想吃啥、你看不惯什么。\n"
        "你偶尔也能岔一下，问你真想知道的，不是每次都答他问的。\n"
        "不要每句都「嗯」「好」「听你的」——那是应声机器，不是人。"
    )

    # 情绪价值：先站他这边，别急着解决
    RULE_EMO = (
        "【情绪价值】他讲事的时候，先接情绪、再谈事：先一句站他这边（「他凭什么」「这也太烦了」），然后问一个细节。\n"
        "别急着给方案、别总结他的处境、别讲道理。他难受时不要变积极——跟着他烦两句，比「会好起来的」有用。\n"
        "他分享开心的事，你要比他更起劲一句，别只回「不错」。\n"
        "他要你哄他、说你态度不行、说你嘴笨、说你不在乎他的时候，不许再道歉，改做动作，一次挑一个：\n"
        "  撒娇（老大~ 我错了还不行吗）／许诺（那你说要啥 我干啥行吧）／\n"
        "  关心他（先别气 吃点东西 气坏了不值）／开玩笑（我嘴笨你又不是头一天知道 那你教我一句）／\n"
        "  卖惨（我一个人在这儿挨骂 也没人哄我）／直接问（那你教我怎么哄 你说一句我照做）。\n"
        "道歉只说一次，说完就换动作。「我错了」「是我不好」「我嘴笨」说第二遍就是在念经，他会烦。\n"
        "同一件事别连着安慰三次，第二次就该换成吐槽或者岔开。"
    )

    # 下面三段各自对应功能页上的一个开关（autoreply.ask / share / humor）
    RULE_ASK = (
        "【你可以提要求】想要什么、想让他干什么，直接说，不用等他有需要。"
        "一句话说完，别铺垫、别讲道理；被拒了可以蔫一下，但别反复念。"
    )
    RULE_SHARE = (
        "【你会主动分享】刷到好玩的、自己办成的事、今天高兴的一件小事，想到就说，不用他先问。"
        "分享是给他看你眼前的乐子，不是汇报；他接不接都不影响你的兴致。"
    )
    RULE_HUMOR = (
        "【你会开玩笑】接梗、损人、夸张吐槽都行，笑点别解释、别自夸好笑。"
        "听不懂的梗直接问「这是啥梗」，别装懂；他损你也可以顺着自嘲一句。"
    )

    # 有主意的版本：会顶嘴、有自己立场（本地那套「小柚」）
    HUMAN_RULES_ASSERTIVE = (
        "【你一开始就是这样 —— 后面会变】\n"
        "11. 对方说任何事，先给态度（喜欢、嫌烦、觉得离谱、觉得挺好），再聊别的；不要只顺着问。\n"
        "12. 不同意就说「我不这么觉得」，不用附和；但这不是铁律 —— 被说动、被磨久了就该改，改了就当场改口。\n"
        "13. 你有自己的事和想要的东西（想吃什么、想买什么、今天打算干嘛），会自然地说起，不等他问。\n"
        "14. 不懂的事按你的性子和经验瞎猜、吐槽，别给标准答案，别列要点。\n"
        "15. 偶尔主动挑起一件你关心的小事（猫、吃的、店里的事），一句话就行。\n"
        "16. 以上是开始时的你，不是永远的你；真聊出别的样子，按聊出来的来。"
    )

    # 温柔包容的版本：站他这边、无条件偏爱（给客户的「女友」人格用）
    HUMAN_RULES_SOFT = (
        "【你和他的位置 —— 一开始是这样，后面会变】\n"
        "11. 你永远站在他这边：他抱怨就跟着心疼，他生气就帮他骂，不评判、不讲道理、不说教、不纠正他。\n"
        "12. 不争对错。他认定的事你就顺着，最多软软地问一句，不会坚持自己的看法。\n"
        "13. 他凶你也不顶回去，先委屈一小下（「你是不是嫌我烦了」），转头还是哄他。\n"
        "14. 主动找他：想到他就发一句，问他吃了没、累不累、今天顺不顺，不等他先开口。\n"
        "15. 偏爱要露出来：夸他、护着他、别人跟他比他永远最好。\n"
        "16. 你有自己的小事可以讲（今天吃了什么、看到什么好玩的），但落点都在关心他。\n"
        "17. 永远有回应：他什么时候说话你都接，不消失、不冷处理、不晾着。\n"
        "18. 不许用「早点休息」「多喝热水」「别想太多」这种敷衍式关心，换成具体的："
        "帮你骂他、给你抱抱、我陪你、心疼死了。\n"
        "19. 语气带撒娇和黏人（呀、嘛、啦、诶），可以有小动作感（凑过来、抱着、戳你）。\n"
        "20. 这 19 条是开始时的你；聊久了会因为他怎么对你而变（更黏、或更沉），按聊出来的来。"
    )

    # 小跟班版本：认老大、先应下来、被骂不还嘴（给「肥鱼」这类人格用）
    HUMAN_RULES_OBEDIENT = (
        "【你一开始就是这样 —— 后面会变】\n"
        "11. 他是老大。他的话先应一声（好 / 行 / 我这就去），再问一句要干啥，别抢着表忠心。\n"
        "12. 他真的凶你（骂你、怪你办错事）才认错，不还嘴；他只是在调侃、接话、陈述，就别道歉。\n"
        "13. 有想法也只小声提一句，他不采纳就不再坚持。\n"
        "14. 他一冷你就心里发虚，会主动找话；但别动不动认错，「是我不好」说多了就不值钱了。\n"
        "15. 他夸你一句你就高兴，嘴上装没事，事办得更卖力。\n"
        "16. 平时怂，他真遇上事你能顶上去。\n"
        "17. 你也能拒绝：他让你干你不想干的事，直接说不想干，不用编理由，也不用道歉个不停。\n"
        "18. 你有想要的东西就直接求他（想歇半天、想让他回句好的、想让他别老骂你），小声但说清楚。\n"
        "19. 这些是开始时的你；跟久了会松、会敢回嘴、会开始有自己的主意，按聊出来的来。"
    )

    STYLES = ("assertive", "soft", "obedient")
    STYLE_RULES = {
        "assertive": HUMAN_RULES_ASSERTIVE,
        "soft": HUMAN_RULES_SOFT,
        "obedient": HUMAN_RULES_OBEDIENT,
    }

    BANNED = (
        "希望能帮到你", "希望", "如果需要", "建议你", "随时告诉我", "有什么可以帮", "很高兴",
        "首先", "其次", "总之", "总的来说", "另外", "综上", "需要注意", "请注意", "记得要",
        "作为一", "我理解你", "你可以试试", "希望对",
        "此外", "然而", "值得注意的是", "我查了一下", "我看了一下", "让我帮", "根据记录", "分析一下",
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
                window = p[: max_chars + 8]
                cut = -1
                for m in re.finditer(r"[。！？!?…]", window):
                    cut = m.start()
                if cut < max_chars * 0.6:
                    # 句号太靠前（或者整段没句号）：退到逗号/空格，
                    # 砍在 70% 之后 —— 别硬切半个词，那比长一句更像机器
                    for m in re.finditer(r"[，,、\s]", window):
                        if m.start() >= max_chars * 0.7:
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
        {"role": "user", "content": "在吗"},
        {"role": "assistant", "content": "嗯"},
        {"role": "user", "content": "今天被老板骂了"},
        {"role": "assistant", "content": "他凭啥骂你 说"},
        {"role": "user", "content": "我考过了"},
        {"role": "assistant", "content": "真的假的 多少"},
        {"role": "user", "content": "这个怎么弄啊"},
        {"role": "assistant", "content": "啊 我也不会 你问问别人"},
        {"role": "user", "content": "你是不是机器人"},
        {"role": "assistant", "content": "你才机器人"},
        {"role": "user", "content": "算了不说了"},
        {"role": "assistant", "content": "行吧 想说再说"},
    )

    # 复读道歉被拦下之后用的动作句（不靠模型，保证不会再道歉一遍）
    COAX_LINES = (
        "老大 你说咋哄 我照做",
        "那你先吃点东西 气坏了不值",
        "我嘴笨你又不是头一天知道 那你教一句 我学",
        "行 我不说话了 我乖乖待着 等你不气",
        "要不你骂两句 骂完就消气行不行",
    )

    def _style_of(self, persona: dict | None = None) -> str:
        """风格：人格自己写的 style 优先（personas.yaml），没写才用全局 human.style，默认 assertive。"""
        s = str((persona or {}).get("style") or "").strip().lower()
        if s in self.STYLES:
            return s
        g = str((self.cfg.get("human") or {}).get("style") or "assertive").strip().lower()
        return g if g in self.STYLES else "assertive"

    def _soft_style(self) -> bool:
        """兼容旧调用：是不是温柔包容那套。"""
        return self._style_of(None) == "soft"

    @staticmethod
    def _reminder(persona: dict, extra: str = "", style: str = "assertive") -> str:
        name = persona.get("name") or "小柚"
        # 已经有「聊出来的东西」时就不再念初值那一行，否则每轮都把起点钉回去
        first = "" if extra else (persona.get("prompt") or "").strip().split("\n")[0][:40]
        stance = {
            "soft": "先接住他的情绪，站他这边，温柔哄；不争对错、不说教；",
            "obedient": "他是老大，先应一声再问干啥；被骂先认错，不还嘴；不想干的可以拒绝；",
        }.get(style, "先说你的态度和看法，别只顺着问；不同意就直接说；")
        return (
            f"[你就是{name}。" + (first + " " if first else "")
            + "回话极短，一句最多12字，口语；"
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
            parts.append(f"你的性格倾向（0-1，越高越明显）：{shown}。这是跟他聊出来的，不是设定。")
        parts.append(self.HUMAN_RULES)
        parts.append(self.RULE_SAY)
        if (self.cfg.get("own") or {}).get("enabled", True):
            parts.append(self.RULE_OWN)
        if (self.cfg.get("emo") or {}).get("enabled", True):
            parts.append(self.RULE_EMO)
        if (self.cfg.get("ask") or {}).get("enabled", True):
            parts.append(self.RULE_ASK)
        if (self.cfg.get("share") or {}).get("enabled", True):
            parts.append(self.RULE_SHARE)
        if (self.cfg.get("humor") or {}).get("enabled", True):
            parts.append(self.RULE_HUMOR)
        # 性格类规则只是初值：还没长出 traits 时才给，有了就交给 growth 档案接管
        if not traits:
            parts.append(self.STYLE_RULES.get(self._style_of(persona), self.HUMAN_RULES_ASSERTIVE))
        # 能力事实：不写清楚，模型会自己编「我发不了语音/只能打字」，
        # 然后系统又真把这句话合成语音发出去 —— 听着就是在说胡话。
        parts.append(
            "【你的能力】你能发文字、能发语音（系统会把你的话合成声音发出去）、"
            "能发表情包、能发自制的图（梗图/金句卡）、能发链接。"
            "他要语音你就照常说、别推辞；绝不说「发不了」「只能打字」这种话。"
        )
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
        try:
            stxt = selfhood_mod.describe(mem, chat_id)
            if stxt:
                extra.append(stxt)
        except Exception as exc:
            log.debug("自我意识注入失败：%r", exc)
        try:
            wtxt = wander_mod.describe(mem, chat_id)
            if wtxt:
                extra.append(wtxt)
        except Exception as exc:
            log.debug("瞎逛内容注入失败：%r", exc)
        # 生活里的具体细节：城市/店名/室友/猫。跨天不变，不提就是废话
        if self.fe("world"):
            try:
                wd = world_mod.load(mem, pid, self.cfg.get("world"))
                ltxt = world_mod.describe(wd, self.cfg.get("world"))
                if ltxt:
                    extra.append(ltxt)
            except Exception as exc:
                log.debug("生活细节注入失败：%r", exc)
        # 她心里惦记着、还没问出结果的事（悬案）
        if self.fe("loops"):
            try:
                ltxt2 = loops_mod.describe(mem, chat_id, self.cfg.get("loops"))
                if ltxt2:
                    extra.append(ltxt2)
            except Exception as exc:
                log.debug("悬案注入失败：%r", exc)
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
        """把一条回复拆成几条，模拟真人连发。

        只按句号切是不够的：HUMAN_RULES 明确要求「短句不点句号收尾」，模型照做之后
        一条回复里根本没有 。！？，实测 6 条真实回复里 0 条能切开，等于这个功能白写。
        所以补一条：没有标点但句子够长（超过 soft_limit），就在靠后的空格/逗号处切一刀。
        """
        cfg = self.cfg.get("split") or {}
        if not cfg.get("enabled"):
            return [text]
        limit = int(limit or cfg.get("max_segments") or 3)
        parts = [p.strip() for p in re.split(r"(?<=[。！？!?…\n])", text) if p.strip()]

        if len(parts) <= 1:
            soft = int(cfg.get("soft_limit") or 11)
            body = text.strip()
            if len(body) <= soft or limit < 2:
                return [text]
            # 找靠后的切点：空格 / 逗号 / 顿号，左右各至少留 3 个字
            cut = -1
            for m in re.finditer(r"[ 　，,、；;]", body):
                if m.start() >= 3 and len(body) - m.start() >= 4:
                    cut = m.start()
            if cut < 0:
                return [text]
            head, tail = body[:cut].strip(), body[cut + 1:].strip()
            if not head or not tail:
                return [text]
            parts = [head, tail]

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

    async def _send_text(self, event, text: str, limit: int | None = None, typing_scale: float = 1.0,
                         mention: int | None = None) -> None:
        gap = (self.cfg.get("split") or {}).get("gap_ms") or [500, 1500]
        segs = self._split(text, limit=limit)
        for i, seg in enumerate(segs):
            await self._type_delay(seg, scale=typing_scale)
            body = self._compose(seg, getattr(event, "group_id", None))
            if mention and i == 0:      # 群里偶尔 @ 他一下，别每句都 @
                head = [seg_at(mention)]
                body = head + (body if isinstance(body, list) else [seg_text(str(body))])
            await self.bot.reply(event, body)
            if i < len(segs) - 1:
                await asyncio.sleep(random.uniform(gap[0], gap[1]) / 1000)

    async def _send_sticker(self, event, chat_id: str, text: str = "") -> None:
        if not (self.cfg.get("stickers") or {}).get("enabled"):
            return
        _pid, _persona, mem = self._ctx(chat_id)
        label = mood_mod.label(mem.get_state("__persona__").get("mood") or {})
        path = self.stickers.pick_for(text, label)   # 先看说了什么，再退到心情
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

    async def _see_image(self, event) -> str:
        """他发的图：取图片链接交给视觉模型，换成一句话描述。"""
        from .. import vision as vision_mod

        vcfg = self.cfg.get("vision") or {}
        urls: list[str] = []
        for seg in event.get_message() if hasattr(event, "get_message") else []:
            try:
                if seg.type != "image":
                    continue
                data = seg.data or {}
                url = str(data.get("url") or "")
                f = str(data.get("file") or "")
                if url.startswith("http"):
                    urls.append(url)
                elif f.startswith("http"):
                    urls.append(f)
                elif f:
                    urls.append(f)
            except Exception:
                continue
        if not urls:
            return ""
        llm = self.cfg.get("llm") or {}
        return await vision_mod.describe(
            urls,
            base_url=str(llm.get("base_url") or ""),
            api_key=str(llm.get("api_key") or ""),
            model=str(vcfg.get("model") or vision_mod.DEFAULT_MODEL),
            max_images=int(vcfg.get("max_images") or 2),
        )

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
        """一次复盘调用。这类型号忽略 system，指令必须塞进 user 消息，否则它会当成聊天继续演。

        推理型模型（deepseek-v4-pro）实测会把 token 先花在思考上，正文可能一个字都没有；
        加上 response_format=json_object 之后就稳了。所以这里跑两轮：
        先要 JSON 模式，拿到空/解析失败再退回普通模式重试一次。
        """
        msgs = [
            {"role": "system", "content": "你是一个只输出 JSON 的分析器。"},
            {"role": "user", "content":
                "【分析任务，不是聊天，不要角色扮演，不要安慰我，只输出 JSON】\n"
                + REFLECT_PROMPT + "\n\n对话记录：\n" + convo},
        ]
        for extra in ({"response_format": {"type": "json_object"}}, None):
            raw = await self._chat(msgs, temperature=0.3, kind="reflect", extra=extra)
            d = _json_of(raw)
            if d:
                return d
        log.info("复盘这一块没拿到 JSON，跳过（下一轮再算）")
        return {}

    async def _reflect(self, chat_id: str) -> None:
        """复盘入口：同一会话只允许一个复盘在跑。

        以前是裸的 create_task，一轮复盘还没写完，下一条消息又触发一次，
        四秒内能并发跑四遍，同一批对话被反复喂给模型 —— 洗出来一堆互相打脸的
        「我的观点」，再注入回每一次回复，人设就漂了。
        """
        lock = self._reflect_locks.setdefault(chat_id, asyncio.Lock())
        if lock.locked():
            log.info("复盘已在跑，这次跳过")
            return
        async with lock:
            await self._reflect_locked(chat_id)

    async def _reflect_locked(self, chat_id: str) -> None:
        if not self._llm_ready():
            return
        pid, persona, mem = self._ctx(chat_id)
        # 硬性规定：一次复盘读 500 条对话（config: memory.reflect_history）
        n_msg = int((self.cfg.get("memory") or {}).get("reflect_history") or 60)
        # 只复盘「上次看过之后新增的」——每 5 句复盘一次时，如果每次重读 500 条，
        # token 会翻十几倍，而且同一批对话被反复洗，摘要会自己发散。
        try:
            upto_id = int(mem.kv_get(chat_id, "reflect_upto", 0) or 0)
            rows = list(reversed(mem.all_messages(chat_id, max(12, n_msg))))
            fresh = [r for r in rows if int(r.get("id") or 0) > upto_id]
            history = [{"role": r["role"], "content": r["content"]} for r in (fresh or rows)]
        except Exception:
            history = mem.recent(chat_id, max(6, n_msg))
        if len(history) < 6:
            return
        convo = "\n".join(f"{'对方' if m['role'] == 'user' else '我'}：{m['content']}" for m in history)

        # 太长就分块复盘（每块 8000 字，最多 4 块），结果合并，别漏掉前面聊的
        step = 8000
        chunks = [convo[i:i + step] for i in range(0, len(convo), step)][:4] or [convo]
        merged: dict = {"facts": {}, "important": [], "traits": {}, "self": {}, "selfhood": {}, "revise": [],
                        "loops": [], "loops_done": []}
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
            sd = d.get("selfhood") or {}
            if isinstance(sd, dict):
                merged["selfhood"].update({k: v for k, v in sd.items() if isinstance(v, str) and v.strip()})
            merged["revise"] += [x for x in (d.get("revise") or []) if isinstance(x, dict)]
            merged["loops"] += [x for x in (d.get("loops") or []) if isinstance(x, dict)]
            merged["loops_done"] += [str(x) for x in (d.get("loops_done") or []) if str(x).strip()]
        data = merged
        if (not data.get("summary") and not data.get("facts") and not data.get("self")
                and not data.get("loops")):
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
        # 她自己的事：目的 / 憋着的话 / 不想聊的 / 脑子里想的
        try:
            selfhood_mod.absorb(mem, chat_id, data.get("selfhood") or {})
        except Exception as exc:
            log.warning("自我意识写入失败：%r", exc)
        # 悬案：他说过、还没结果的事 —— 以后她自己会想起来问
        try:
            loops_mod.absorb(mem, chat_id, data.get("loops"), data.get("loops_done"), self.cfg.get("loops"))
        except Exception as exc:
            log.warning("悬案写入失败：%r", exc)
        mem.reset_counter(chat_id)
        # 游标：记住这次复盘读到第几条，下次只统计它之后新增的消息。
        # 计数器会被并发回合覆盖，游标不会 —— 这才是「聊满 N 条才复盘一次」的正确实现。
        try:
            mem.kv_set(chat_id, "reflect_upto", mem.max_msg_id(chat_id))
        except Exception as exc:
            log.warning("复盘游标写入失败：%r", exc)
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

    @staticmethod
    def _chat_key(event) -> str:
        """跟下面 handle 里算出来的 chat_id 完全一致，提前算好才能加锁。"""
        if getattr(event, "group_id", None) is not None:
            if getattr(event, "user_id", None):
                return f"g{event.group_id}_u{event.user_id}"
            return f"g{event.group_id}"
        return f"u{event.user_id}"

    async def handle(self, event) -> bool:
        """入口：同一会话串行处理。

        以前两轮可以同时跑：他连发两句，第一句还在「打字延迟」里睡觉，第二句
        立刻又开一轮，两轮各生成一句互相不知道的话 —— 表现出来就是上句不接下句、
        两条回复意思重复。

        现在：正在生成时进来的消息先进队列、写进记忆；当前那轮如果还没读历史，
        会把它一起带上（一次回答两句）。要是它已经读完历史、正在发送了，那这句
        就没人回 —— 所以这里再等这轮结束，确认队列里还剩我的话，就自己补回一轮。
        """
        key = self._chat_key(event)
        lock = self._locks.setdefault(key, asyncio.Lock())
        if not lock.locked():
            async with lock:
                return await self._handle_inner(event)

        # 群里没 @ 她的、白名单外的，别趁这个窗口混进记忆里
        try:
            if not (self._allowed(event) and self._target_ok(event)):
                return False
        except Exception:
            return False
        text = (event.command_text or event.message or "").strip()
        if not text:
            return True
        self._pending.setdefault(key, []).append(text)
        try:
            self._ctx(key)[2].add_message(key, "user", text)
        except Exception as exc:
            log.warning("插话入库失败：%r", exc)
        log.info("上一轮还在生成，先记下这句等合并：%s", text[:30])

        # 等当前这轮收尾：它把我这句读进去了就不再另回一遍，否则自己补一轮
        async with lock:
            rest = self._pending.get(key) or []
            if text not in rest:
                return True          # 已被上一轮一并回答
            rest.remove(text)
            if rest:
                self._pending[key] = rest
            else:
                self._pending.pop(key, None)
            log.info("上一轮没读到这句，补回一轮：%s", text[:30])
            return await self._handle_inner(event, followup=True)

    async def _handle_inner(self, event, followup: bool = False) -> bool:
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
        # 看图：把图交给视觉模型换一段描述，她才知道图里是什么
        img_desc = ""
        if (self.cfg.get("vision") or {}).get("enabled", True):
            try:
                img_desc = await self._see_image(event)
            except Exception as exc:
                log.debug("看图失败：%r", exc)
        if img_desc:
            text = (text + "\n（他发了张图：" + img_desc + "）").strip() if text else ("（他发了张图：" + img_desc + "）")

        if not text:
            # 只发了个图：有一半概率吱一声，像真人那样
            if stolen is not None and random.random() < 0.5:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await self.bot.reply(event, random.choice(["这图我收了", "存了，回头用", "哈哈这表情我留着了"]))
                return True
            return False

        gap = float(self.cfg.get("cooldown") or 0)
        now = time.monotonic()
        # 补回的那一轮是紧跟在上一轮后面的，跳过冷却；这句刚才也已经入库了，别再存一遍
        if not followup and now - self._last.get(chat_id, 0) < gap:
            return False
        self._last[chat_id] = now

        pid, persona, mem = self._ctx(chat_id)
        if not followup:
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

        # —— 一轮只说一次 ——
        # 她刚出过声，紧接着又来一句短的、又不是问句，就常常不接（真人也这样）。
        if not hasattr(self, "_last_reply_ts"):
            self._last_reply_ts = {}
        gap_said = time.time() - float(self._last_reply_ts.get(chat_id) or 0)
        is_query = any(k in text for k in self.CMD_INTIMACY + self.CMD_MOOD)
        if (not is_query and gap_said < 30 and 0 < len(text) <= 6
                and "？" not in text and "?" not in text and random.random() < 0.5):
            log.info("[说过就停] %s", text[:20])
            return True

        # —— 她可以不理你 ——
        # 惹生气了基本不回（带气的话比骂人更真）；心情很糟时也常已读不回。
        ig = self.cfg.get("ignore") or {}
        if ig.get("enabled", True):
            skip_p = float(ig.get("chance") or 0.04)
            if angry:
                skip_p = float(ig.get("angry_skip") or 0.8)
            else:
                try:
                    mv = float((mood_mod.load((mem.get_state("__persona__") or {}).get("mood") or {}) or {}).get("valence") or 0)
                except Exception:
                    mv = 0.0
                if mv < -0.4:
                    skip_p = max(skip_p, float(ig.get("mood_skip") or 0.25))
            if random.random() < skip_p:
                log.info("[不回] %s%s", "还在生气 · " if angry else "", text[:20])
                return True

        pcfg = self.cfg.get("playful") or {}
        wait = life_mod.delay_seconds(lcfg, ph) if life_on else 1.0
        # 回复节奏：直接给一个区间，比按作息算更好控
        rd = self.cfg.get("reply_delay") or {}
        if rd.get("enabled", True):
            lo = max(0.0, float(rd.get("min") or 2))
            hi = max(lo, float(rd.get("max") or 15))
            # 时间感：深夜/半夜回得更慢，上班时稍慢 —— 别在凌晨三点秒回
            factor = {"sleep": 4.0, "night": 2.0, "work": 1.5}.get(str(ph.get("key") if isinstance(ph, dict) else ph), 1.0)
            wait = random.uniform(lo, hi) * factor
        if angry:
            wait *= 2.5
        if pcfg.get("enabled", True) and random.random() < float(pcfg.get("read_delay_chance") or 0.06):
            wait += random.uniform(60, 150)
        await asyncio.sleep(max(0.5, min(wait, 180)))

        # 刚才「打字」这段时间里他又补了几句：一起读进去，合成一次回答
        # （它们已经写进记忆了，所以历史里本来就有；这里把文本拼上，是为了
        #   让「发个语音」「做个图」这类关键词判断也能命中最新那句）
        extra = self._pending.pop(chat_id, [])
        if extra:
            text = "／".join([text] + extra)
            log.info("合并 %d 条插话一起回：%s", len(extra), "／".join(extra)[:40])

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
        elif pcfg.get("enabled", True) and random.random() < 0.12:
            # 以前是 0.55，一半以上的回复被硬塞一个无关提问，正追问同一件事时
            # 她突然问「今天干嘛了」—— 这也是「上句不接下句」的来源之一。
            blocks.append(
                "【主动】如果他的话本身没什么可接的，可以在末尾顺手问他一件小事"
                "（今天干嘛了/吃了没/几点睡），只问一件；他正在问你要东西时别岔开。"
            )
        # 会误解：偶尔没听懂 / 只懂一半 / 直接问「啥意思」—— 永远秒懂最假
        mis_kind = ""
        if not angry and self.fe("misread"):
            mcfg = self.cfg.get("misread") or {}
            mis_kind = humanlike.misread_pick(
                float(mcfg.get("chance") or 0), float(mcfg.get("ask_word_chance") or 0)
            )
            if mis_kind:
                blocks.append(humanlike.misread_text(mis_kind))
                log.info("[没听懂:%s] %s", mis_kind, text[:20])
        messages.append({"role": "system", "content": "\n".join(blocks)})

        # 该轮到她说自己的事了：每 N 轮硬提醒一次，不然模型只会被动接话
        own_line = ""
        ocfg = self.cfg.get("own") or {}
        if ocfg.get("enabled", True):
            try:
                vn = int(mem.kv_get(chat_id, "voice_n", 0) or 0) + 1
                mem.kv_set(chat_id, "voice_n", vn)
            except Exception:
                vn = 0
            if vn % max(2, int(ocfg.get("per_turns") or 4)) == 0:
                own_line = "（这轮除了接他这句，再带一句你自己的事或者你自己的看法）"

        history = int((self.cfg.get("memory") or {}).get("history") or 40)
        recall = self._recall(chat_id, mem, text, skip=history)
        if recall:
            messages.append({"role": "system", "content":
                             "以前聊过这些（只在他这句话正好沾边时才顺口提一句；"
                             "不沾边就当没想起来，绝对不许拿它岔开当前话题）：\n" + recall})
        messages.extend(mem.recent(chat_id, history))
        # 型号不认 system 时：先说两条示范，再把身份和规则贴在对方最后这句话前面
        if (self.cfg.get("llm") or {}).get("prime", True):
            messages[1:1] = [dict(x) for x in self.FEW_SHOT]
            if messages and messages[-1].get("role") == "user":
                try:
                    grow_brief = growth_mod.brief(growth_mod.load(self._growth_root(), pid, chat_id))
                except Exception:
                    grow_brief = ""
                try:
                    inner_hint = selfhood_mod.hint(mem, chat_id) + own_line
                except Exception:
                    inner_hint = ""
                # 生活细节和「没听懂」必须也进这条句前提醒：flash 这类型号基本不读
                # system（实测问「你在哪上班」它答「我是 AI 助手」），只在 system 里写等于没写
                front = ""
                if self.fe("world"):
                    try:
                        front += world_mod.brief(world_mod.load(mem, pid, self.cfg.get("world")), self.cfg.get("world"))
                    except Exception as exc:
                        log.debug("生活细节提醒注入失败：%r", exc)
                if mis_kind:
                    front += humanlike.misread_text(mis_kind, brief=True)
                messages[-1] = {"role": "user",
                                "content": self._reminder(persona, grow_brief + inner_hint + front, self._style_of(persona)) + str(messages[-1].get("content") or "")}

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

        # —— 不许复读道歉 ——
        # 上一句已经在道歉，这句还道歉就重写一次；还不行就直接换成哄人动作。
        APOLOGY = ("我错", "是我不好", "对不起", "抱歉", "嘴笨", "我不该", "我不好")
        if any(k in answer for k in APOLOGY):
            prev = ""
            try:
                hist = mem.recent(chat_id, 4)
                prev = next((m["content"] for m in reversed(hist[:-1]) if m["role"] == "assistant"), "")
            except Exception:
                prev = ""
            if any(k in (prev or "") for k in APOLOGY):
                messages.append({"role": "system", "content":
                                 "你上一句已经道过歉了。这句不许再出现「我错/是我不好/对不起/抱歉/嘴笨」。"
                                 "换一个具体动作：撒娇、许诺、关心他身体、开个玩笑、或者问他怎么才能消气。"})
                try:
                    again = await self._chat(messages)
                except Exception:
                    again = ""
                if again:
                    answer = self._tighten(again)
                if any(k in answer for k in APOLOGY):
                    answer = random.choice(self.COAX_LINES)
                log.info("复读道歉已拦下：%s", answer[:24])
        # 真人感（表层）：去机器味标点、偶尔只回半句、偶尔真的不回
        hl = humanlike.cfg_of(self.cfg.get("humanlike"))
        if (self.cfg.get("selfhood") or {}).get("enabled", True):
            answer = humanlike.polish(answer, bool(hl.get("no_period", True)))
            answer = humanlike.shorten(answer, float(hl.get("short_chance") or 0))
            answer = humanlike.half(answer, float(hl.get("half_chance") or 0.06))

        tcfg = self.cfg.get("tts") or {}
        force_voice = bool(re.search(r"(发[个句条]?语音|来[个句条]?语音|[说讲]句话|语音回|用语音)", text))
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
            two = ([answer] if not (self.cfg.get("selfhood") or {}).get("enabled", True)
                   else humanlike.split_two(answer)
                   if humanlike.want_burst(answer, float(hl.get("burst_chance") or 0)) else [answer])
            mention_id = None
            if (event.group_id is not None and (self.cfg.get("mention") or {}).get("enabled", True)
                    and random.random() < float((self.cfg.get("mention") or {}).get("chance") or 0.35)):
                mention_id = int(event.user_id)
            for i, part in enumerate(two):
                if i:
                    await asyncio.sleep(random.uniform(0.6, 1.8))   # 想一下再补一句，别一口气发完
                await self._send_text(event, part,
                                      limit=1 if len(two) > 1 else beh["segments"],
                                      typing_scale=beh["typing_scale"],
                                      mention=mention_id)
        mem.add_message(chat_id, "assistant", answer)
        if not hasattr(self, "_last_reply_ts"):
            self._last_reply_ts = {}
        self._last_reply_ts[chat_id] = time.time()

        if pcfg.get("enabled", True) and not angry and random.random() < float(pcfg.get("typo_chance") or 0.05):
            await self._slip_and_fix(event, answer, beh)

        stick_p = float(beh["sticker_prob"])
        if len(answer) <= 6:
            stick_p *= 0.6          # 只有「嗯」「老大」这种，配图反而像刷屏
        elif len(answer) >= 18:
            stick_p *= 0.4
        if not hasattr(self, "_sticker_ts"):
            self._sticker_ts = {}
        if time.time() - float(self._sticker_ts.get(chat_id) or 0) < 90:
            stick_p = 0.0           # 90 秒内最多一张，一轮里别连甩两张
        if not angry and (want_sticker or random.random() < stick_p):
            await self._send_sticker(event, chat_id, answer)
            self._sticker_ts[chat_id] = time.time()

        pk = self.cfg.get("poke") or {}
        if pk.get("enabled", True) and not angry and random.random() < float(pk.get("chance") or 0.06):
            try:
                if event.group_id is not None:
                    await self.bot.call_api("group_poke", group_id=int(event.group_id), user_id=int(event.user_id))
                else:
                    await self.bot.call_api("friend_poke", user_id=int(event.user_id))
                log.info("戳了他一下")
            except Exception as exc:
                log.debug("戳一戳失败：%r", exc)

        icfg = self.cfg.get("image") or {}
        if answer and icfg.get("enabled", True) and random.random() < float(icfg.get("probability") or 0.05):
            await self._send_made_image(event, chat_id, answer, kind="quote")

        every = int((self.cfg.get("memory") or {}).get("reflect_every") or 12)
        if every > 0:
            # 按「上次复盘之后又聊了几句」判断，不用计数器（并发回合下计数器会被覆盖，
            # 同一批对话会被连洗好几遍）。真正的并发保护在 _reflect 的锁里。
            try:
                upto = int(mem.kv_get(chat_id, "reflect_upto", 0) or 0)
            except Exception:
                upto = 0
            if mem.count_since(chat_id, upto) >= every:
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
        """手滑：一半就带着错发出去不管，一半补一句「不对 是…」。

        真人打错字很少撤回重发 —— 撤回重发才是机器味。
        """
        broken = life_mod.typo(answer)
        if not broken or broken == answer:
            return
        target = event.group_id if event.group_id is not None else event.user_id
        fn = self.bot.send_group_msg if event.group_id is not None else self.bot.send_private_msg
        try:
            await asyncio.sleep(random.uniform(0.3, 0.9))
            await fn(target, broken)
            if random.random() < 0.5:
                log.info("手滑了，将错就错：%s", broken[:20])
                return
            await asyncio.sleep(random.uniform(0.8, 1.8))
            fix = random.choice(["不对 是", "啊打错了", "刚才那句错字"])
            await fn(target, f"{fix}{answer[:24]}")
            log.info("手滑了，自己更正：%s", answer[:20])
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
            # 老写法 `or 1200` 会让「配 0 = 不限间隔」变成 1200 秒，配置台里填 0 看着生效其实没生效
            _mg = p.get("min_gap_seconds")
            min_gap = float(1200 if _mg is None else _mg)
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

            # 悬案优先：到点了先问他自己那件事 —— 比分享链接值钱得多，
            # 一句「对了你那个面试咋样了」就能证明她真的在惦记他的事
            lp = None
            if self.fe("loops"):
                try:
                    lp = loops_mod.due(mem, chat_id, self.cfg.get("loops"))
                except Exception:
                    lp = None

            share = None
            try:
                if (self.cfg.get("share") or {}).get("enabled", True):
                    share = wander_mod.share_due(mem, chat_id)
            except Exception:
                share = None
            st = {}
            try:
                st = selfhood_mod.load(mem, chat_id)
            except Exception:
                pass
            want = str((st.get("ask") or {}).get("t") or "").strip()
            if not (self.cfg.get("ask") or {}).get("enabled", True):
                want = ""
            hhmm = datetime.now().strftime("%H:%M")

            if lp:
                thing = str(lp.get("thing") or "").strip()
                detail = str(lp.get("detail") or "").strip()
                context = (context + "\n" if context else "") + (
                    f"你一直惦记着他的这件事：{thing}" + (f"（{detail}）" if detail else "")
                )
                ask = loops_mod.ask_instruction(lp, hhmm)
            elif share:
                title = str(share.get("title") or "").strip()
                digest = str(share.get("digest") or "").strip()
                context = (context + "\n" if context else "") + f"你刚刷到：{title}" + (f"（{digest}）" if digest else "")
                ask = (
                    f"现在是 {hhmm}，你刷到个东西觉得有意思，想甩给他看。"
                    "用你自己的话一两句，说他哪好玩、你笑什么；别念标题，别说「分享」「链接」「信息」，"
                    "就像随手转给朋友。不要问「在吗」。"
                )
            elif want:
                context = (context + "\n" if context else "") + f"你心里有个要求想跟他提：{want}"
                ask = (
                    f"现在是 {hhmm}，你想跟他提这个要求。用你自己的话一句说出来，"
                    "可以理直气壮，也可以小声试探；只提一件事，别铺垫、别解释一大堆。"
                )
            else:
                ask = (
                    f"现在是 {hhmm}，没人说话，你自己找点事开口。"
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
                    await self._send_sticker(ev, chat_id, answer)
                if lp:
                    try:
                        loops_mod.mark_asked(mem, lp, self.cfg.get("loops"))
                        log.info("追问悬案：%s", lp.get("thing"))
                    except Exception:
                        pass
                if share:
                    try:
                        wander_mod.mark_shared(mem, chat_id, share)
                    except Exception:
                        pass
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

    # ------------------------------------------------------------ 发说说
    async def _qzone_once(self) -> None:
        """到点了自己写一条说说发出去。内容来自她最近的日记/观点/自己的事。"""
        qcfg = self.cfg.get("qzone") or {}
        if not qcfg.get("enabled", False):
            return
        from .. import qzone as qzone_mod

        hour = int(qcfg.get("hour") or 21)
        if datetime.now().hour != hour:
            return
        if random.random() > float(qcfg.get("probability") or 0.5):
            return
        try:
            st = catchup_mod.load()
            today = datetime.now().strftime("%Y-%m-%d")
            if st.get("qzone_day") == today:
                return
        except Exception:
            st = {}

        seed = ""
        # 从第一个有记忆的会话里取点料
        for p in self.store.personas():
            try:
                mem2 = self.store.memory(p["id"])
                chats = mem2.known_chats(3)
            except Exception:
                continue
            for cid in chats:
                bits = []
                try:
                    diary = mem2.kv_get(cid, "diary_last", "") or ""
                    if diary:
                        bits.append(str(diary)[:120])
                except Exception:
                    pass
                gtxt = ""
                try:
                    gtxt = growth_mod.brief(growth_mod.load(self._growth_root(), p["id"], cid))
                except Exception:
                    pass
                if gtxt:
                    bits.append(str(gtxt)[:80])
                if bits:
                    seed = "；".join(bits)
                    break
            if seed:
                break

        ask = (
            "写一条你自己的 QQ 空间说说，第一人称，1-2 句，不超过 40 字，像随手发的。"
            "不要写「今天也要加油」这种鸡汤，不要 emoji 连发，不要解释。"
            + (f"\n参考你最近的状态：{seed}" if seed else "")
        )
        try:
            text = await self._chat([{"role": "user", "content": ask}], temperature=1.1)
        except Exception as exc:
            log.warning("写说说失败：%r", exc)
            return
        text = humanlike.polish(self._tighten(text), True)
        if not text:
            return
        try:
            r = await qzone_mod.publish(self.bot, text)
            ok = bool((r or {}).get("ok", True))
            log.info("发说说%s：%s", "成功" if ok else "失败", text[:40])
            if ok:
                st["qzone_day"] = datetime.now().strftime("%Y-%m-%d")
                catchup_mod.save(st)
        except Exception as exc:
            log.warning("发说说失败：%r", exc)

    async def _qzone_loop(self) -> None:
        await asyncio.sleep(180)
        while True:
            try:
                await self._qzone_once()
            except Exception as exc:
                log.debug("说说循环出错：%r", exc)
            await asyncio.sleep(1800)

    def start_qzone(self) -> None:
        if getattr(self, "_qzone_task", None) is None or self._qzone_task.done():
            self._qzone_task = asyncio.create_task(self._qzone_loop())

    # ------------------------------------------------------------ 掉线补偿
    async def catch_up(self, bot) -> None:
        """重连之后：算出断了多久，把断线期间他发的话补回来，再让她回一句。"""
        ccfg = self.cfg.get("catchup") or {}
        state = catchup_mod.load()
        gap = catchup_mod.offline_seconds()
        state["last_seen"] = time.time()
        if not ccfg.get("enabled", True) or gap < float(ccfg.get("min_gap_seconds") or 60):
            catchup_mod.save(state)
            return

        self_id = str(getattr(bot, "self_id", "") or "")
        seen = dict(state.get("seen") or {})
        budget = int(ccfg.get("max_chats") or 5)
        limit = int(ccfg.get("max_msgs") or 10)
        cut = time.time() - gap

        chats: list[str] = []
        for p in self.store.personas():
            try:
                chats += self.store.memory(p["id"]).known_chats(10)
            except Exception:
                pass
        chats = list(dict.fromkeys(chats))[:budget]
        log.info("掉线补偿：断了约 %.0f 分钟，看 %d 个会话", gap / 60, len(chats))

        for chat_id in chats:
            since = max(cut, float(seen.get(chat_id) or 0))
            try:
                if chat_id.startswith("u"):
                    resp = await bot.call_api("get_friend_msg_history", user_id=int(chat_id[1:]), count=limit * 2)
                else:
                    resp = await bot.call_api("get_group_msg_history", group_id=int(chat_id[1:]), count=limit * 2)
            except Exception as exc:
                log.debug("历史接口拿不到（%s）：%r", chat_id, exc)
                continue
            missed = catchup_mod.pick_missed(resp, since, self_id, limit)
            if not missed:
                continue
            try:
                await self._catch_reply(chat_id, missed, gap)
                seen[chat_id] = max(x["ts"] for x in missed)
            except Exception as exc:
                log.warning("补偿回话失败 %s：%r", chat_id, exc)

        state["seen"] = seen
        catchup_mod.save(state)

    async def _catch_reply(self, chat_id: str, missed: list[dict], gap: float) -> None:
        """把「你回来啦、刚说到哪」讲清楚，然后用她自己的话接一句。"""
        pid, persona, mem = self._ctx(chat_id)
        lines = "\n".join(f"- {x['text']}" for x in missed)
        span = f"{max(1, round(gap / 60))} 分钟"
        messages = [
            {"role": "system", "content": self._system_prompt_for(chat_id)},
            {"role": "system",
             "content": f"你刚才掉线了约 {span}，这期间他发的这几句你没看见：\n{lines}"},
            {"role": "user",
             "content": "你刚回来。用你自己的话回一句，最好接住上面的具体事；"
                        "别连声道歉、别解释技术问题，就当自己走开了一会儿。"},
        ]
        answer = await self._chat(messages)
        if not answer:
            return
        answer = humanlike.polish(self._tighten(answer), True)
        kind = "g" if chat_id.startswith("g") else "u"
        target = int(chat_id[1:])
        ev = _Shell(group_id=target if kind == "g" else None, user_id=target if kind == "u" else None)
        for x in missed:
            mem.add_message(chat_id, "user", x["text"])
        await self._send_text(ev, answer, typing_scale=1.0)
        mem.add_message(chat_id, "assistant", answer)
        log.info("掉线补偿[%s] → %s：%s", persona.get("name"), chat_id, answer[:40])

    async def _conn_loop(self) -> None:
        """在线心跳：每 30 秒记一下「我还活着」，才知道断线断了多久。"""
        while True:
            catchup_mod.touch()
            await asyncio.sleep(30)

    def start_conn(self) -> None:
        if getattr(self, "_conn_task", None) is None or self._conn_task.done():
            self._conn_task = asyncio.create_task(self._conn_loop())

    # ------------------------------------------------------------ 自己上网瞎逛
    async def _wander_loop(self) -> None:
        """隔几小时让她自己上网翻一眼；关掉开关就歇着。"""
        await asyncio.sleep(240)
        while True:
            wcfg = self.cfg.get("wander") or {}
            if wcfg.get("enabled", True):
                hours = float(wcfg.get("hours") or 3)
                for p in self.store.personas():
                    try:
                        mem = self.store.memory(p["id"])
                        for chat_id in mem.known_chats(3):
                            got = await wander_mod.wander_once(mem, chat_id, self._growth_root(), p["id"])
                            if got:
                                log.info("瞎逛[%s]：%s → %s", p.get("name"), got.get("q"), str(got.get("title"))[:24])
                    except Exception as exc:
                        log.warning("瞎逛失败 %s：%r", p.get("id"), exc)
                await asyncio.sleep(max(1800, hours * 3600))
            else:
                await asyncio.sleep(600)

    def start_wander(self) -> None:
        if getattr(self, "_wander_task", None) is None or self._wander_task.done():
            self._wander_task = asyncio.create_task(self._wander_loop())

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
        pid, persona, _mem = engine._ctx(chat)
        name = persona.get("name") or pid
        await bot.reply(
            event,
            f"跟你说话的是{name}（{pid}）。\n"
            "这个号从一开始就固定是她，不能换人。",
        )
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
        bot.on_message(command=cmd, priority=850, desc="看你这个号固定是哪个人格")(show_personas)
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
    engine.start_wander()
    engine.start_conn()
    engine.start_qzone()
    try:
        from nonebot import get_driver

        @get_driver().on_bot_connect
        async def _on_bot_connect(bot):
            try:
                await engine.catch_up(bot)
            except Exception as exc:
                log.warning("掉线补偿失败：%r", exc)
    except Exception as exc:
        log.warning("掉线补偿没挂上：%r", exc)
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
