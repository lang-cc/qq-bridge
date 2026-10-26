"""按工单自动生成配置：AI / 装机的人不用点 GUI，也不用手写 yaml。

用法：
    python autoconfig.py                        # 读 ticket.yaml
    python autoconfig.py --ticket 张三.yaml
    python autoconfig.py --polish               # 让模型把 persona.notes 润色成完整人格
    python autoconfig.py --dry-run              # 只打印，不写文件
    python autoconfig.py --config x.yaml --personas y.yaml

做的事：
    1. 读工单 → 写 config.yaml（模型、白名单、城市、主动性等）
    2. 生成 data/personas.yaml（人格 + 作息）
    3. 打印摘要（密钥打码）与下一步命令
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LIFE_DEFAULT = [
    {"key": "sleep", "from": 1, "to": 8, "label": "睡觉",
     "hint": "你还在睡，被消息吵醒时句子很短、有点迷糊", "delay": [15, 60], "short": True},
    {"key": "work", "from": 8, "to": 17, "label": "忙",
     "hint": "你在忙自己的事，回得慢、话短", "delay": [12, 45], "short": True},
    {"key": "free", "from": 17, "to": 22, "label": "空闲",
     "hint": "你闲下来了，最有空聊天，话最多也最有耐心", "delay": [1, 6], "short": False},
    {"key": "night", "from": 22, "to": 1, "label": "夜里",
     "hint": "夜里了，你有点困但还想聊，情绪比白天软", "delay": [3, 12], "short": False},
]

PROMPT_TMPL = """{head}
{rel}
【你怎么说话】
{style}

硬性规则：
1. 一次只说一两句，像真人打字，不用书面语，不用列表和小标题。
2. 不要自称 AI、助手、模型，不要解释自己在做什么。
3. 不要每句都追问；对方不想聊的时候，你就安静一点。
4. 不知道的事就说不知道，别编；记不清的旧事可以问一句。
5. 偶尔会打错字、改口、发一半——你是人，不是完美的。
"""

POLISH_ASK = """把下面这些要点写成一段中文人格设定，第二人称「你是…」开头，200-300 字。
要求：具体、有细节、有生活感，写出她说话的习惯和心里没说出口的东西；不要罗列条目，要像一个人在描述另一个人。
要点：
{notes}
只输出这段话本身，不要任何解释。"""

# 客户没给性格时的兜底人格（够自然，不油腻，也不像客服）
DEFAULT_PERSONA = {
    "name": "小柚",
    "age": 22,
    "who": "在写字楼上班，做的是普通的文职",
    "style": "短句、口语，爱用「嗯」「哈哈」「嘛」，被人逗会损回去，不装可爱也不冷淡",
    "relation": "认识一段时间的朋友，聊得来，但还没到无话不说",
}


def _head(persona: dict) -> str:
    name = str(persona.get("name") or "小柚").strip()
    bits = [f"你叫{name}"]
    age = str(persona.get("age") or "").strip()
    who = str(persona.get("who") or "").strip()
    if age:
        bits.append(f"{age} 岁")
    if who:
        bits.append(who)
    return "，".join(bits) + "。"


def build_prompt(persona: dict) -> str:
    given = str(persona.get("prompt") or "").strip()
    if given:
        return given
    rel = str(persona.get("relation") or "").strip()
    style = str(persona.get("style") or "").strip() or "短句、口语，不说书面语"
    head = _head(persona)
    rel_block = ""
    if rel:
        lines = [ln.strip() for ln in rel.replace("。", "。\n").split("\n") if ln.strip()]
        rel_block = "\n【你和对方的关系】\n" + "\n".join(lines) + "\n"
    return PROMPT_TMPL.format(head=head, rel=rel_block, style=style)


def polish(notes: str, api: dict, timeout: int = 120) -> str:
    body = json.dumps({
        "model": api["model"],
        "messages": [{"role": "user", "content": POLISH_ASK.format(notes=notes)}],
        "temperature": 0.8,
    }).encode()
    req = urllib.request.Request(
        api["base_url"].rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api['api_key']}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def yaml_dump(data, path: Path, header: str = "") -> None:
    import yaml

    class Block(str):
        pass

    def _rep(d, v):
        return d.represent_scalar("tag:yaml.org,2002:str", v, "|" if "\n" in v else None)

    def conv(o):
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        return Block(o) if isinstance(o, str) else o

    yaml.add_representer(Block, _rep, Dumper=yaml.SafeDumper)
    text = yaml.safe_dump(conv(data), allow_unicode=True, sort_keys=False, width=200)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((header + text) if header else text, encoding="utf-8")


def main(argv=None) -> int:
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", default="ticket.yaml")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--personas", default="data/personas.yaml")
    ap.add_argument("--polish", action="store_true", help="用模型润色 persona.notes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    tp = Path(args.ticket)
    if not tp.exists():
        print(f"找不到工单 {tp}，先照着 ticket.example.yaml 填一份")
        return 2
    ticket = yaml.safe_load(tp.read_text(encoding="utf-8")) or {}

    robot = ticket.get("robot") or {}
    api = ticket.get("api") or {}
    persona = dict(ticket.get("persona") or {})
    tuning = ticket.get("tuning") or {}
    group_cfg = ticket.get("group") or {}

    # 没给的字段用兜底人格补齐（客户"没有性格"也能跑得自然）
    for k, v in DEFAULT_PERSONA.items():
        if not str(persona.get(k) or "").strip():
            persona[k] = v

    # allow 支持两种写法：
    #   allow: ["20002"]                                   → 只私聊
    #   allow: {users: ["20002"], groups: ["123456789"]}    → 私聊 + 群聊
    allow_raw = ticket.get("allow") or []
    if isinstance(allow_raw, dict):
        users = [str(u).strip() for u in (allow_raw.get("users") or []) if str(u).strip()]
        groups = [str(g).strip() for g in (allow_raw.get("groups") or []) if str(g).strip()]
    else:
        users = [str(u).strip() for u in allow_raw if str(u).strip()]
        groups = [str(g).strip() for g in (ticket.get("groups") or []) if str(g).strip()]
    qq = str(robot.get("qq") or "").strip()

    problems = []
    if not qq:
        problems.append("robot.qq 没填（机器人 QQ 号）")
    if not users and not groups:
        problems.append("allow 没填（至少一个允许聊天的 QQ 号或群号）")
    for k in ("base_url", "api_key", "model"):
        if not str(api.get(k) or "").strip():
            problems.append(f"api.{k} 没填")
    if problems:
        print("工单有缺项，先补上：")
        for p in problems:
            print("  -", p)
        return 2

    # 人格 prompt
    if args.polish and str(persona.get("notes") or "").strip() and not str(persona.get("prompt") or "").strip():
        try:
            persona["prompt"] = polish(str(persona["notes"]), api)
            print("已用模型润色人格 prompt（%d 字）" % len(persona["prompt"]))
        except Exception as exc:
            print(f"润色失败，改用字段拼装：{exc}")
    prompt = build_prompt(persona)
    phases = persona.get("life") or LIFE_DEFAULT

    # ---- config.yaml ----
    cfg_path = Path(args.config)
    cfg = {}
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    ar = cfg.setdefault("autoreply", {})
    llm = ar.setdefault("llm", {})
    llm.update({"enabled": True, "base_url": str(api["base_url"]).strip(),
                "api_key": str(api["api_key"]).strip(), "model": str(api["model"]).strip()})
    ar["whitelist"] = {"enabled": True, "users": users, "groups": groups}
    if groups:
        ar["reply_group"] = True
        ar["group_at_only"] = bool(group_cfg.get("at_only", True))
        ar["group_reply_probability"] = float(group_cfg.get("probability") or 1.0)
    pro = ar.setdefault("proactive", {})
    targets = [f"u{u}" for u in users] + [f"g{g}" for g in groups]
    pro.update({"enabled": bool(tuning.get("proactive_min_minutes", 1)),
                "targets": targets,
                "min_minutes": int(tuning.get("proactive_min_minutes") or 45),
                "max_minutes": int(tuning.get("proactive_max_minutes") or 180),
                "max_per_day": int(tuning.get("proactive_max_per_day") or 6)})
    ar.setdefault("care", {})["city"] = str(ticket.get("city") or "").strip()
    ar.setdefault("memory", {})["history"] = int(tuning.get("history") or 100)
    ar.setdefault("tts", {})["probability"] = float(tuning.get("tts_probability") or 0.25)
    ar.setdefault("stickers", {})["probability"] = float(tuning.get("sticker_probability") or 0.35)
    if int(tuning.get("max_rounds") or 0) > 0:
        ar["max_rounds"] = int(tuning["max_rounds"])

    # ---- personas.yaml ----
    pd = {
        "active": "main",
        "personas": [{
            "id": "main",
            "name": str(persona.get("name") or "小柚").strip(),
            "prompt": prompt,
            "life": {"phases": phases},
        }],
    }

    print("\n===== 将写入的配置 =====")
    print(f"机器人 QQ    : {qq}")
    print(f"私聊白名单   : {', '.join(users) if users else '(无)'}")
    print(f"群白名单     : {', '.join(groups) if groups else '(无)'}")
    if groups:
        print(f"群里怎么回   : {'只在被@时回' if ar.get('group_at_only') else '会主动插话'}"
              f"（概率 {ar.get('group_reply_probability')}）")
    print(f"城市         : {ticket.get('city') or '(不报天气)'}")
    print(f"模型         : {api['model']} @ {api['base_url']}")
    print(f"密钥         : {str(api['api_key'])[:8]}…{str(api['api_key'])[-4:]}")
    print(f"上下文条数   : {ar['memory']['history']}")
    print(f"人格         : {persona.get('name')}，{persona.get('age')} 岁，{prompt[:40]}…")
    print(f"作息段数     : {len(phases)}")

    if args.dry_run:
        print("\n[--dry-run] 未写文件")
        return 0

    yaml_dump(cfg, cfg_path, header="# 由 autoconfig.py 生成，可手改；含密钥，勿提交\n")
    yaml_dump(pd, Path(args.personas), header="# 由 autoconfig.py 生成，可手改\n")
    print(f"\n已写入 {cfg_path} 和 {args.personas}")
    print("\n下一步：")
    print("  1) 启动：.venv\\Scripts\\pythonw.exe boot.py   （需要扫码时会自动弹二维码）")
    print("  2) 验收：.venv\\Scripts\\python.exe selfcheck.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
