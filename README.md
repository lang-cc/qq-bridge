# qq-bridge

把一个 QQ 号变成会聊天的「人」：有记忆、有作息、有脾气，会发语音、发图、发自己写的日记、自己上网刷梗。

框架 **NoneBot2**（`nonebot2` + `nonebot-adapter-onebot`），入口 `main_nb.py`。
端口：**8199** 给协议端反向 WS，**8088** 是网页控制台 / 本机 HTTP 接口。

---

## 两套部署形态（同一份代码）

| | **本地（Windows）** | **服务器（Linux / 阿里云）** |
|---|---|---|
| 协议端 | **SnowLuma**（注入本机 QQNT 客户端） | **SnowLuma 官方 Docker 镜像**（容器里跑 Linux QQ，原生支持 x64/arm64） |
| QQ 登录 | 本机 QQ 客户端已登录机器人号 | 网页 noVNC（`6081`）里扫码，WebUI 在 `5099` |
| 启动方式 | `boot.py` 拉起 SnowLuma + 服务 | `docker run snowluma` + systemd `qqbridge` |
| 控制台 | `http://127.0.0.1:8088/admin`（桌面图标就是它） | `http://<IP>:8088/admin` 或 SSH 隧道 |
| 需要 Node.js | 是（语音转 silk） | 是（语音转 silk） |

### ⚠️ 哪些文件是 Windows 专用

**Python 代码本身跨平台**，Linux 上照常跑。下列文件只在 Windows 流程里用到，**Linux 部署时直接忽略**：

```
snowluma/          整目录（Windows QQ 注入用的运行时、.bat、node.exe）
*.bat              安装.bat 更新.bat run.bat start_all.bat stop_all.bat
*.ps1 / *.vbs      install.ps1 open_console.vbs
qqbot/proto.py     只有 boot.py 在 Windows 下拉起 QQ/协议端时才用；Linux 用 main_nb.py 不导入
```

**跨平台、Linux 也要用的：**

```
qqbot/  nb/  stickers/  static/  assets/  tools/  scripts/
main_nb.py  boot.py  login_qr.py  watchdog.py  selfcheck.py  autoconfig.py
config.example.yaml  personas.example.yaml  requirements.txt
```

---

## 环境要求

- Windows 10/11 x64 **或** Ubuntu 20.04+ / Debian 11+
- Python 3.10+（推荐 3.12）
- **Node.js 18+**（语音转 silk 必需，`tools/silk/encode.mjs` 用它）
- `ffmpeg`（语音/音频处理）
- 一个 OpenAI 兼容的模型接口（DeepSeek / 中转站 / 本地 Ollama 都行；看图功能需要支持图片的模型）
- 协议端：**SnowLuma**（Windows 本机/Qt 注入；Linux 服务器用官方 Docker 镜像，自带 Xvfb + noVNC 扫码）

---

## 快速开始

### A. Windows 本地（SnowLuma）

```powershell
git clone https://github.com/lang-cc/qq-bridge.git D:\qqbridge
cd D:\qqbridge
powershell -ExecutionPolicy Bypass -File install.ps1     # 建 .venv + 装依赖 + 生成 config.yaml
cd snowluma && .\setup_medium.bat                        # 部署 SnowLuma（需要运行时 zip）
cd .. && .\.venv\Scripts\python.exe boot.py              # 启动
```

### B. Linux 服务器（SnowLuma 官方 Docker 镜像）

```bash
apt update && apt install -y python3 python3-venv python3-pip git ffmpeg nodejs npm docker.io
git clone https://github.com/lang-cc/qq-bridge.git /opt/qqbridge && cd /opt/qqbridge
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
cp config.example.yaml config.yaml && cp personas.example.yaml data/personas.yaml

# 协议端：容器里带 QQ + Xvfb + noVNC，三个参数不能省
docker run -d --name snowluma --restart unless-stopped \
  --shm-size=1g --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --add-host=host.docker.internal:host-gateway \
  -p 6081:6081 -p 5099:5099 \
  -v qq-gateway-data:/app/data -v qq-client-config:/app/.config -v qq-client-data:/app/.local/share \
  motricseven7/snowluma:latest

.venv/bin/python main_nb.py        # 生产环境用 systemd 托管
```

- **扫码**：浏览器开 `http://<服务器IP>:6081/`（noVNC），密码在 `docker logs snowluma | grep 远程桌面密码`
- **WebUI**：`http://<服务器IP>:5099/`，临时密码在 `docker logs snowluma | grep 临时密码`
- WebUI 里新增 **OneBot v11 反向 WebSocket** → `ws://host.docker.internal:8199/onebot/v11/ws`

## 更新到新版本

更新只换代码，配置 / 密钥 / 记忆 / 协议端 / 表情包 / 虚拟环境全都不动，**不用重新扫码**。

- **Windows**：双击安装目录里的 `更新.bat`（= `scripts\update.ps1`）→ 自动下载最新代码、备份旧代码到 `backups\`、覆盖代码、跑自检 → 到后台概览页点「重启」。
  远程无人值守：`powershell -ExecutionPolicy Bypass -File scripts\update.ps1 -NoPause`
- **Linux 服务器**：`git pull && .venv/bin/pip install -r requirements.txt && systemctl restart qqbridge`
- **确认生效**：后台顶栏右侧的版本小字（`v0.2.0 · main@提交号 · 更新于 …`），提交号或时间变了就是新版；`/status` 接口里也有同样的 `version` 字段。
- **回滚**：把 `backups\code-before-update-<时间>.zip` 解压覆盖回安装目录，再重启。

更新源是 GitHub `main` 分支；官方源太慢时会自动换加速镜像。

## 它能做什么

| 能力 | 说明 |
|---|---|
| **像人聊天** | 短句、分段、打字延迟、口语，不说「作为 AI」 |
| **记忆** | 摘要 + 事实 + 最近 100 条上下文 + BM25 旧事回忆 + 每晚日记；每 5 条消息增量归档 |
| **性格会变** | 你的语气反馈会慢慢改变她（更黏 / 更丧 / 更话多） |
| **生活感** | 人格自带作息：忙时回得慢、困了句子短；亲密度分五档换语气；说重话会记仇，哄好才回来 |
| **主动性** | 按间隔自己开聊、分享刷到的东西、跟你说自己的事、向你提要求 |
| **看图 / 画图** | 你发的图她会描述（视觉模型）；也能自己拼梗图、金句卡 |
| **语音 / 表情包** | edge-tts 转 silk 发语音条；200+ 表情包按回复内容挑图，还会偷别人的 |
| **掉线补偿** | 断线重连后会把没看到的消息补上再接着聊 |
| **白名单** | 只回你指定的人，其他人一概不理 |
| **控制台** | `http://<host>:8088/admin`：概览 / 模型 / 人格 / 功能 / 记忆 / 日志，23 个功能开关、节奏与时间参数、记忆备份与导出 |

---

## 配置要点

`config.yaml`（从 `config.example.yaml` 复制，**不要提交到仓库**）：

```yaml
protocol_backend: snowluma      # 服务器改成 napcat
onebot11:
  reverse: {host: 0.0.0.0, port: 8199, path: /onebot/v11/ws}
http_api:
  host: 127.0.0.1               # 要让手机/公网访问改 0.0.0.0，并把 token 设成随机串
  port: 8088
  token: '<随机串>'
autoreply:
  reply_private: true
  reply_group: true
  group_at_only: true
  llm:
    base_url: <OpenAI 兼容地址>
    api_key: <密钥>
    model: <模型名>
    prime: true                 # 这个型号会忽略 system prompt，必须开
  whitelist: {enabled: true, users: [<QQ 号>]}
```

人格在 `data/personas.yaml`：`name` + `style`（`assertive` 强势 / `soft` 温柔 / `obedient` 小跟班）+ `prompt` + 可选 `examples`（示范对话最有效）。

---

## 目录说明

```
qqbot/                 主体代码
  plugins/companion.py 陪聊引擎（记忆、性格、主动、语音、发图、看图）
  memory.py            SQLite 记忆层
  life.py              作息 / 亲密度 / 记仇 / 手滑 / 天气
  recall.py            BM25 旧事回忆
  selfhood.py          自我意识（目的、憋着的话、想提的要求）
  wander.py            自主上网刷梗
  humanlike.py         去机器味（句号、拆句、只说半句）
  catchup.py           掉线补偿
  vision.py            看图
  http_api.py / admin_page.py   控制台（8088）
nb/                    NoneBot2 适配层
stickers/              表情包素材（随仓库分发）
snowluma/              Windows 协议端（服务器忽略）
scripts/deploy-linux.sh, watch_linux.py   Linux 部署与看门狗
tools/                 silk 编码、重启、隧道等运行时工具
main_nb.py             启动入口（跨平台）
boot.py                Windows 一键启动（拉起协议端 + 服务 + 扫码）
install.ps1 / 安装.bat  Windows 安装
```

---

## 常见问题

**服务器上跑起来报找不到 node？**
语音转 silk 需要 Node.js：`apt install -y nodejs npm`，然后 `.venv/bin/python -c "import qqbot.tts"` 自检。

**扫码后一会儿又掉线？**
SnowLuma 的登录态和 QQ 版本相关；先在手机上正常登录一次机器人号再扫，并确认内存够（2C4G 起）。

**语音没声音？**
语音走 edge-tts（需联网）+ Node 转 silk；缺任一条件会自动退回文字，不影响聊天。

**会不会乱回别人？**
白名单开着时只回列表里的 QQ，其他人完全不回应。

---

## 注意

- QQ 接入依赖第三方互操作运行时 **SnowLuma**（[文档](https://snowluma.github.io/zh/) / [GitHub](https://github.com/SnowLuma/SnowLuma)），请遵守其许可与腾讯服务条款。
- 自动化账号存在风控风险，建议用小号，不要批量加好友/群发。
- 模型按量计费：100 条上下文约 4k tokens/次；对外部署请设日限额。

## License

MIT（本仓库自有代码）。SnowLuma / QQ 客户端遵循各自许可。
