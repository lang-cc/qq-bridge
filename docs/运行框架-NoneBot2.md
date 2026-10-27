# 运行框架：NoneBot2（替代自研适配器）

从 2026-10-26 起，机器人跑在 **NoneBot2** 上。业务功能（记忆 / 情绪 / 人格 / 语音 /
表情包 / 抖音 / 主动开聊 / 本机发送接口 / 网页配置台）全部保留，一行业务逻辑没动，
换掉的只是**连接与分发这一层**。

```
NapCat（协议端，管 QQ 连接）
        │  WebSocket   ws://127.0.0.1:8199/onebot/v11/ws
        ▼
NoneBot2 进程（框架）
   Driver（FastAPI 驱动：WS 监听、断线重连、生命周期）
        ▼
   Adapter · OneBot v11（原始 JSON → 统一 Event，附带 Bot 对象）
        ▼
   Matcher / Handler
        ├─ nb_sys          框架原生指令：/nb、/nbhelp
        └─ legacy_bridge   翻译成旧 Event → 交给老引擎（记忆 / 陪聊 …）
                     ▼
              你的模型接口（DeepSeek 等，由业务代码自己调）
```

## 文件在哪

| 文件 | 作用 |
|---|---|
| `main_nb.py` | **启动入口**（boot.py / watchdog.py / login_qr.py / open_console.vbs 拉起的都是它） |
| `nb.env` | 框架配置：`DRIVER=~fastapi`、`HOST`、`PORT`、`ONEBOT_ACCESS_TOKEN` |
| `nb/compat.py` | 唯一胶水层：NoneBot 事件 ⇄ 旧 Event，收发接口转接 |
| `nb/plugins/legacy_bridge.py` | 把 `qqbot/plugins/*` 挂到 NoneBot 事件管线（priority 10） |
| `nb/plugins/nb_sys.py` | 框架原生插件：`/nb` 看运行状态、`/nbhelp` |
| `qqbot/*` | 业务层，原样复用（记忆、人格、TTS、表情包、抖音…） |
| `qqbot/http_api.py` | 本机发送接口 + 网页配置台，仍在 `:8088` |

端口没有任何变化：**8199** 给 NapCat 反向 WS，**8088** 给本机 HTTP 接口/面板。

## 启动 / 停止

```bat
.venv\Scripts\python.exe main_nb.py      :: 前台跑，能看日志
```

平时双击桌面「QQ机器人」（会拉起服务并打开网页配置台 `8088/admin`），或者 `start_all.bat`；
`watchdog.py` 发现服务掉了会自动拉起 `main_nb.py`。

日志：`logs/nonebot.log`（框架侧）、`logs/qq-bridge.log`（业务侧）、`logs/watchdog.log`。

### 两层开关：功能 与 指令插件

网页配置台「插件」页上有两组，别混：

| 层 | 是什么 | 存在哪 | 代码 |
|---|---|---|---|
| **功能** | 引擎里的能力：心情、好感度、记忆、表情包、语音、画图、上网、抖音、主动开聊、日记、人格切换、白名单 | `config.yaml` → `autoreply.<名字>.enabled` | 清单在 `qqbot/features.py` |
| **指令插件** | `qqbot/plugins/*.py` 文件级的指令插件：help / ping / echo / send_tools / rules_demo、以及框架的 /nb | `config.yaml` → `plugins.disabled` | `qqbot/plugin_info.py` + `qqbot/toggles.py` |

功能开关改的是活着的引擎配置（`ENGINE.cfg`），拨一下就生效；指令插件是路由器派发前跳过，同样不用重启。

## 插件的开关（网页配置台「插件」页）

每个插件都能单独开 / 关，拨一下就生效，**不用重启**：

- 页面开关 → `POST /admin/plugins/toggle` → 写进 `config.yaml`：

```yaml
plugins:
  disabled:
    - qqbot.plugins.rules_demo
```

- 派发时 `qqbot/router.py` 直接跳过 `plugin` 在 disabled 里的处理器 —— 被关掉的插件等于没装
- 框架原生的 `/nb`、`/nbhelp` 用 `nonebot.rule.Rule` 挡：关掉后消息照常落到老引擎
- 「陪聊引擎」关掉 = 她不说话了；其它插件关掉只影响对应指令
- 页面上的名字和一句话说明在 `qqbot/plugin_info.py` 的 `NICE` 里维护

## 加新功能怎么写

两套写法可以并存：

1. **框架原生（推荐给新功能）** —— 在 `nb/plugins/` 里新建文件，用 `on_command` / `on_message`：

```python
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

echo2 = on_command("echo2", priority=3, block=True)

@echo2.handle()
async def _(bot: Bot, event: MessageEvent):
    await echo2.finish("框架原生回复")
```

   `priority` 小于 10 的指令会先于老引擎认领消息；老引擎在 priority 10 才接手，
   它自己内部仍按旧的 priority（5 / 10 / 50 / 850 / 900）排队。

2. **老写法** —— 继续在 `qqbot/plugins/` 里写 `setup(bot)` + `@bot.on_message(...)`，
   把模块名加到 `nb/plugins/legacy_bridge.py` 的 `LEGACY_PLUGINS` 列表即可。

## 想退回去

旧入口 `main.py`（自研 OneBot 适配器）还在，没删：

```bat
.venv\Scripts\python.exe main.py
```

把 `boot.py` / `watchdog.py` / `login_qr.py` / `run.bat` / `start_all.bat` 里的
`main_nb.py` 改回 `main.py` 就算完整回滚。

## 这次顺手修的三处

| 问题 | 修法 |
|---|---|
| `get_group_member_list` / `get_cookies` 返回值形状不统一，导致「群里 @ 真人」和「QQ 空间 cookie」静默失效 | 新增 `qqbot/api_result.py::unwrap()`，两种形状都能吃 |
| 看门狗锁端口 `listen(1)` 且从不 accept，连过一次后 backlog 塞满，自检误报「掉线监控未运行」 | 改成 `listen(16)` + 后台线程 accept 后立即关闭 |
| `pythonw` 下没有 stdout/stderr，日志库会抛异常 | `main_nb.py` 启动时兜底重定向到 `logs/stdout.log`、`logs/stderr.log` |

## 自测脚本

`tmp/mock_napcat.py` 可以假装成 NapCat 连上来发消息，用来验证收发链路
（不碰真实 QQ 账号）：

```bat
.venv\Scripts\python.exe tmp\mock_napcat.py ws://127.0.0.1:8199/onebot/v11/ws 462667371 "ping"
```
