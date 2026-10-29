"""生活细节：让她活在**具体的**世界里，而且跨天不变。

为什么这条重要：「我有点困」是抽象话，「我手机还有 3% 电」「楼下那家麻辣烫今天
排到马路牙子」「我室友又把袜子扔洗衣机了」才是活人。模型默认只会说抽象话。

为什么必须"不变"：细节一致 = 她有历史；细节每次随机 = 她在更努力地演。
所以第一次用的时候按人格 id 定一批（md5 定种子，重启/换机器都一样），
存进这个人格的 memory.db（kv: __persona__ / world），之后只读不重抽。
想改就在 config.yaml 的 autoreply.world.fixed 里写死，或者后台改。

原则：一次只往 prompt 里挂一小段（十来项太多，模型会句句往生活上扯）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import random

log = logging.getLogger("qqbot.world")

KEY = "world"
KV_KEY = "world"


def _key(pid: str) -> str:
    """一个人格一份：老版本是所有人物格共用一个 memory.db，用 id 分开存才不会串。"""
    return f"{KV_KEY}:{pid or 'default'}"
KEEP = (
    "city", "area", "home", "shop", "boss", "roomie", "pet", "phone", "food",
)

# 每组都给「名字 + 一个具体特征」，光有名字没特征等于没写
CITIES = (
    ("成都", "武侯区", "老小区六楼，没电梯"),
    ("长沙", "岳麓区", "跟人合租的老房子，阳台朝西"),
    ("郑州", "金水区", "租的单间，隔壁天天打游戏"),
    ("合肥", "蜀山区", "老小区三楼，楼下有棵大樟树"),
    ("西安", "雁塔区", "城中村边上，晚上很吵"),
    ("昆明", "五华区", "单位分的老房子，暖气不太行"),
)
SHOPS = (
    ("楼下蜜雪冰城", "店长姓王，周末最忙"),
    ("商场三楼那家古茗", "下午两点到四点是空档"),
    ("街口的茶百道", "店长爱临时改班表"),
    ("学校后门的 coco", "学生一放学就排长队"),
    ("步行街的一点点", "隔壁是家炸鸡，油烟味很重"),
)
ROOMIES = (
    ("阿芸", "爱把袜子扔进洗衣机"),
    ("小雨", "半夜煮泡面，味道能飘一屋"),
    ("楠楠", "养了盆快死的绿萝，天天浇水"),
    ("二胖", "打游戏开语音，喊得整栋楼都听见"),
)
PETS = (
    ("团子", "橘猫，怕吸尘器"),
    ("芝麻", "黑猫，只认她一个人"),
    ("年糕", "柯基，一到点就扒门要出去"),
    ("灰灰", "同事寄养的兔子，会咬电线"),
)
PHONES = (
    "旧手机，电池撑不到晚上八点",
    "屏幕左上角裂了一道，贴了张膜凑合用",
    "64G 的，隔两天就得清一次相册",
    "充电线接触不良，得把线掰个角度才充得上",
)
FOODS = (
    "楼下麻辣烫，加两份宽粉",
    "便利店关东煮，最爱萝卜",
    "巷子里那家小面，二两微辣",
    "学校门口的煎饼，多加一个蛋",
    "夜市烤冷面，老板记得她不要香菜",
)


def _pick(seq, rng: random.Random):
    return seq[rng.randrange(len(seq))]


def seed(pid: str) -> dict:
    """按人格 id 定一批细节：同一台机器、换机器、重启，都是同一套。"""
    h = int(hashlib.md5(str(pid or "default").encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(h)
    city, area, home = _pick(CITIES, rng)
    shop, boss = _pick(SHOPS, rng)
    roomie, roomie_trait = _pick(ROOMIES, rng)
    pet, pet_trait = _pick(PETS, rng)
    return {
        "city": city,
        "area": area,
        "home": home,
        "shop": shop,
        "boss": boss,
        "roomie": f"{roomie}，{roomie_trait}",
        "pet": f"{pet}（{pet_trait}）",
        "phone": _pick(PHONES, rng),
        "food": _pick(FOODS, rng),
    }


def cfg_of(raw: dict | None) -> dict:
    c = {"enabled": True, "fixed": {}}
    for k, v in (raw or {}).items():
        if k in c:
            c[k] = v
    return c


def load(mem, pid: str, cfg: dict | None = None) -> dict:
    """取这个人格的生活细节：没存过就按 id 定一批存下去，之后不变。"""
    c = cfg_of(cfg)
    w: dict = {}
    try:
        raw = mem.kv_get("__persona__", _key(pid), "")
        if raw:
            d = json.loads(raw)
            if isinstance(d, dict):
                w = {k: str(v) for k, v in d.items() if k in KEEP and str(v).strip()}
    except Exception as exc:
        log.debug("读生活细节失败：%r", exc)
    fixed = c.get("fixed") or {}
    if isinstance(fixed, dict):
        for k, v in fixed.items():
            if k in KEEP and str(v).strip():
                w[k] = str(v).strip()
    if not w:
        w = seed(pid)
        save(mem, w, pid)
        log.info("生活细节已生成[%s]：%s %s", pid, w.get("city"), w.get("shop"))
    return w


def save(mem, world: dict, pid: str = "default") -> None:
    try:
        mem.kv_set("__persona__", _key(pid), json.dumps({k: str(v) for k, v in world.items() if k in KEEP}, ensure_ascii=False))
    except Exception as exc:
        log.warning("存生活细节失败：%r", exc)


def brief(world: dict, cfg: dict | None = None) -> str:
    """句前提醒用的短版本。

    为什么需要两份：flash 这类型号基本不读 system（实测问「你在哪上班」它答
    「我是 AI 助手」），真正管用的是贴在对方最后那句话前面的提醒。所以细节
    必须也进 brief，否则 system 里写了等于没写。
    """
    c = cfg_of(cfg)
    if not c.get("enabled", True) or not world:
        return ""
    bits = []
    if world.get("city"):
        bits.append("住" + world["city"])
    if world.get("shop"):
        bits.append("在" + world["shop"] + "上班")
    if world.get("roomie"):
        bits.append("室友" + str(world["roomie"]).split("，")[0])
    if world.get("pet"):
        bits.append("养了" + str(world["pet"]).split("（")[0])
    if not bits:
        return ""
    return "（你" + "、".join(bits) + "；这些是真的，别改口；跟身份设定冲突时以身份设定为准）"


def describe(world: dict, cfg: dict | None = None) -> str:
    """拼成 prompt 里的一段。"""
    c = cfg_of(cfg)
    if not c.get("enabled", True) or not world:
        return ""
    bits = []
    if world.get("city"):
        tail = ""
        if world.get("area"):
            tail += f" {world['area']}"
        if world.get("home"):
            tail += f"，{world['home']}"
        bits.append(f"你在{world['city']}{tail}")
    if world.get("shop"):
        bits.append("上班在" + world["shop"] + (f"（{world['boss']}）" if world.get("boss") else ""))
    if world.get("roomie"):
        bits.append("室友 " + world["roomie"])
    if world.get("pet"):
        bits.append("家里的 " + world["pet"])
    if world.get("phone"):
        bits.append("手机：" + world["phone"])
    if world.get("food"):
        bits.append("常吃：" + world["food"])
    if not bits:
        return ""
    return (
        "【你生活里的具体细节 —— 一直就是这些，别改口，也别编新的地名和人名】\n"
        + "；".join(bits)
        + "。\n说到这些的时候提起具体的那一样（哪家店、哪个名字），"
        "但别每句都往生活细节上扯，十次里提一两次就够。"
        "这些只是你生活的背景，跟你上面的身份设定冲突时以身份设定为准；用不上就当没这回事。"
    )
