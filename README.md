# qq-bridge

把一个 QQ 号变成会聊天的「人」：有记忆、有作息、有脾气，会发语音、发图、发自己写的日记。

本地跑（NapCat + OneBot v11），不依赖任何云服务，聊天只走你自己的模型接口。

运行框架：**NoneBot2**（`nonebot2` + `nonebot-adapter-onebot`）。启动入口 `main_nb.py`，
端口没变（8199 给 NapCat 反向 WS，8088 给本机接口/面板）。细节见
[`docs/运行框架-NoneBot2.md`](docs/运行框架-NoneBot2.md)。旧的 `main.py`（自研适配器）保留可随时回滚。

---

## 它能做什么

| 能力 | 说明 |
|---|---|
| **像人聊天** | 短句、分段、打字延迟、口语，不说「作为 AI」 |
| **记忆** | 摘要 + 事实 + 最近 100 条上下文 + BM25 旧事回忆 + 每晚日记 |
| **性格会变** | 你的语气反馈会慢慢改变她（更黏 / 更丧 / 更话多） |
| **生活感** | 人格自带作息：忙时回得慢、困了句子短；亲密度分五档换语气；说重话会记仇，哄好才回来 |
| **主动找你** | 按间隔自己开聊，避开深夜，天冷会提醒你穿衣服 |
| **语音 / 表情包 / 自制图** | edge-tts 转 silk 语音；206 张表情包还会偷别人的；PIL 现场拼梗图和金句卡 |
| **白名单** | 只回你指定的人，其他人一概不理 |
| **后台** | 网页配置台 `http://127.0.0.1:8088/admin`（6 个标签：概览 / 模型与人格 / 行为 / 记忆 / 日志 / 试聊；扫码登录、掉线自愈、重启、备份都在「概览」里）。只有这一个后台，另加 NapCat 面板 6099 管扫码和网络 |

---

## 环境要求

- Windows 10 / 11 x64
- Python 3.10+（安装脚本会尝试自动装 3.12）
- QQ 客户端（官方版，最新）
- 一个可用的 OpenAI 兼容模型接口（DeepSeek / 中转站 / 本地 Ollama 都行）
- 可选：Node.js 18+（只有语音功能需要）

---

## 部署（两条线，都有一键脚本）

| 场景 | 一键入口 | 文档 |
|---|---|---|
| **A. Windows 本地**（QQ 登录在这台电脑） | `powershell -File deploy.ps1 -ZipPath D:\qq-bridge-full.zip -TicketPath D:\ticket.yaml` | [docs/部署②-Windows本地.md](docs/部署②-Windows本地.md) |
| **B. Linux 服务器 / 阿里云**（24h 在线） | `QQ=... USERS=... bash <(curl -fsSL .../deploy-linux.sh)` | [docs/部署①-Linux服务器-阿里云.md](docs/部署①-Linux服务器-阿里云.md) |
| 远程代装（发给客户的 AI 自己跑） | 把任务单发过去 | **[docs/任务单-AI部署.md](docs/任务单-AI部署.md)** |
| 自己远程操作别人电脑 | 同上，照着操作手一页纸 | [docs/远程代装-操作手一页纸.md](docs/远程代装-操作手一页纸.md) |

打包给别人（自动剔除 `config.yaml` / `nb.env` / `data/` / `logs/` / `.venv` / `napcat/`）：

```bash
.venv\Scripts\python.exe tools\make_dist.py --all --with-assets --with-napcat
# → dist/qq-bridge-code.zip（0.3MB，Linux 用）、dist/qq-bridge-full.zip（59MB，Windows 用）
```

---

## 安装（手动双击版）

1. 下载本仓库（Code → Download ZIP）并解压到任意目录，路径别带特殊符号。
2. 双击 **`安装.bat`**，等它跑完（约 2-3 分钟）。
3. 自动弹出设置向导，填 4 页：
   - 机器人的 QQ 号、允许聊天的 QQ 号、所在城市
   - 模型接口地址 / 密钥 / 模型名（点「测试连接」验证）
   - 人格：名字、年龄、身份、说话风格、和对方的关系
4. 点「完成并启动」。需要时弹出二维码，用手机 QQ 扫码。
5. 桌面上会有三个图标：**「QQ机器人」**（双击 = 拉起服务并打开后台）、**「机器人后台」**（`127.0.0.1:8088/admin`）、**「NapCat 面板」**（`127.0.0.1:6099`，扫码用）。

想验收是否装好：

```bash
.venv\Scripts\python.exe selfcheck.py
```

12 项全绿即为交付状态（含模型连通性、QQ 连接、白名单、记忆库、掉线监控）。

机器人里发 `/nb` 能看到当前框架版本、连接数、处理器数量（确认 NoneBot2 在跑）。

---

## 日常使用

- **双击桌面「QQ机器人」** → 网页配置台：改模型 / 人设、扫码登录、开掉线自愈、重启服务、保存备份、看记忆和日志、试聊
- **换模型** → 配置台里改模型地址/密钥/名字，点「保存配置」，热重载，不用重启
- **换人格 / 调作息** → 改 `data/personas.yaml`，保存即生效（代码里每次调用都重读）
- **备份** → 配置台「保存备份」，导出一个 zip：记忆库＋可读对话记录＋配置＋日志
- **掉线** → 不用管：看门狗会自动重启 NapCat，实在不行会自己弹二维码

---

## 目录说明

```
config.yaml            配置（含密钥，已被 .gitignore 排除）
data/personas.yaml     人格设定（名字、prompt、作息）
data/personas/*/       每个人格一个 SQLite 记忆库
stickers/              表情包素材
napcat/                QQ 协议端（第三方，安装脚本下载）
logs/                  运行日志
qqbot/                 主体代码
  plugins/companion.py 陪聊引擎（记忆、性格、主动、语音、发图）
  life.py              作息 / 亲密度 / 记仇 / 手滑 / 天气
  recall.py            BM25 旧事回忆
  makeimg.py           梗图与金句卡
  memory.py            SQLite 记忆层
open_console.vbs       桌面图标：拉起服务并打开网页配置台
boot.py                启动器（服务 + NapCat + 看门狗 + 掉线自动扫码）
watchdog.py            掉线监控
login_qr.py            扫码登录工具
selfcheck.py           交付自检
setup_wizard.py        首次设置向导
```

---

## 常见问题

**扫码后一会儿又掉线？**
NapCat 的登录态和 QQ 版本相关。配置台点一次「开掉线自愈」让看门狗常开，掉线会自动重登；频繁掉线通常是 QQ 在别处登录或版本更新。

**语音没声音？**
语音走 edge-tts（需联网）+ Node 转 silk。没装 Node 或网络不通时会自动退回文字，不影响聊天。

**模型报错 / 换 API？**
配置台里填地址、密钥、模型名 → 「拉取可用模型 / 测试连接」→ 「保存配置」。

**会不会乱回别人？**
白名单开着的时候只回列表里的 QQ，其他人完全不回应（连提示都没有）。

---

## 注意

- 本项目的 QQ 接入依赖 [NapCatQQ](https://github.com/NapNeko/NapCatQQ)（第三方，AGPL-3.0），请遵守其许可与腾讯的服务条款。
- 用自动化账号存在被风控的可能，建议使用小号，不要用于批量加好友/群发。
- 模型调用按量计费。100 条上下文约为每次 4k tokens；给客户部署时请设置日限额。

## License

MIT（本仓库自有代码）。NapCat 与 QQ 客户端遵循各自许可。
