# 部署②：Windows 本地一键部署（自己的电脑 / 远程帮别人装）

目标：在 Windows 10/11 上一台机器装好机器人，跑在这台机器上（QQ 必须在这台机器登录）。
支持两条路：**一条命令无人值守**（远程代装用）和 **双击安装 + 向导**（客户自己能点）。

---

## 一、一条命令装完（远程代装首选）

前提：机器上已经有 Python 3.10+（没有也行，脚本会用 winget 装）；
远程用 ToDesk / 向日葵 / RDP 连上客户电脑后，把 `qq-bridge-full.zip` 传过去、解压成安装目录，然后：

```powershell
Expand-Archive -Path D:\qq-bridge-full.zip -DestinationPath D:\qqbridge -Force
cd D:\qqbridge
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 `
    -InstallDir D:\qqbridge `
    -TicketPath D:\ticket.yaml
```

`ticket.yaml`（工单，含 QQ 号 / 白名单 / 模型三项 / 人格，模板见 `ticket.example.yaml`）：

```yaml
robot:
  qq: "10001"
allow:
  users: ["20002"]
  groups: []
city: "杭州"
api:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-你的密钥"
  model: "deepseek-chat"
persona:
  name: "小柚"
  age: 20
  prompt: |
    你是小柚，20 岁，在街角那家奶茶店做兼职……
```

不想写工单也可以把参数直接丢命令行（人格短的时候够用）：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1 -Qq 10001 -Users 20002 `
    -BaseUrl https://api.deepseek.com/v1 -ApiKey sk-xxx -Model deepseek-chat `
    -PersonaName 小柚 -PersonaAge 20 -PersonaWho "在奶茶店做兼职" -City 杭州
```

> 也可以一步到位让它自己解压：`powershell -ExecutionPolicy Bypass -File deploy.ps1 -ZipPath D:\qq-bridge-full.zip -TicketPath D:\ticket.yaml -InstallDir D:\qqbridge`（前提是手上已有 `deploy.ps1`）。

脚本会自己做完这些（幂等，重复跑不会重复下载、不覆盖已有配置和数据）：

| 步骤 | 内容 |
|---|---|
| 1 | 解压安装包到 `-InstallDir`（默认自动判断：包内 → 包目录，单独跑 → `C:\qqbridge`） |
| 2 | 找 Python（`py -3.12` / `py -3` / `python`），没有就用 winget 装 3.12 |
| 3 | 建 `.venv` |
| 4 | `pip install -r requirements.txt`（官方源失败自动切清华 / 阿里云镜像） |
| 5 | 下载并解压 NapCat（本地 zip 优先 → gitee → ghproxy → github） |
| 6 | 用参数生成 `ticket.yaml` → 跑 `autoconfig.py` 生成 `config.yaml` + `data\personas.yaml`，并写好端口和 `bot_qq` |
| 7 | 生成 `nb.env`（NoneBot2 运行配置：`DRIVER=~fastapi`，端口 8199） |
| 8 | 建桌面快捷方式「QQ机器人」 |
| 9 | 启动服务，等 `/status` 通，打印**远程验收报告** |

常用开关：

| 开关 | 用途 |
|---|---|
| `-SkipNapCat` | 这台机器已有协议端，只装机器人本体 |
| `-NoStart` | 只装环境不启动（先检查再启动） |
| `-NoShortcut` | 不建桌面图标（多开 / 测试） |
| `-DryRun` | 只打印计划，不动手（先确认参数） |
| `-Port 8199 -ApiPort 8088` | 换端口（一个机器装多个机器人时用） |
| `-InstallDir D:\qqbridge` | 指定安装目录 |

---

## 二、双击安装 + 向导（发给客户自己装）

1. 解压 `qq-bridge-full.zip`
2. 双击 **`安装.bat`**（内部跑 `install.ps1`：建环境、装依赖、准备 NapCat、生成配置、建桌面图标）
3. 会自动弹出设置向导（`setup_wizard.py`）：填机器人号 / 白名单 / 城市 → 模型三项 → 人格
4. 点「完成并启动」，需要时弹二维码，手机 QQ 扫码

以后双击桌面 **「QQ机器人」** 就打开网页配置台（`http://127.0.0.1:8088/admin`）：改模型 / 人设 / 行为、扫码登录、开掉线自愈、重启服务、保存备份、看记忆和日志。**整个机器人只有这一个后台**（另加 NapCat 面板 6099，只管扫码和网络）。

---

## 三、装完怎么验收

在这台机器上（PowerShell）：

```powershell
curl.exe http://127.0.0.1:8088/status
# {"ok": true, "adapter": "onebot11", "self_id": 10001, "connected": true, "plugins": 28}

.venv\Scripts\python.exe selfcheck.py
# 12 项全绿 = 交付状态
```

在 QQ 上给机器人发：

- `/nb` → 回 NoneBot2 版本 + 连接数 + 处理器数量（确认框架版在跑）
- `ping` → `pong 🏓`
- `help` → 指令列表

---

## 四、文件都在哪

| 位置 | 内容 |
|---|---|
| `config.yaml` | 全部配置：模型密钥、白名单、开关、语气（含密钥，别外传） |
| `data\personas.yaml` | 人格（改完保存即生效，代码每次调用都重读） |
| `data\personas\<id>\memory.db` | 各人格的记忆库（要备份就整目录拷走） |
| `nb.env` | 框架配置：`DRIVER=~fastapi` / `HOST` / `PORT` / access_token；删掉会自动按 config.yaml 重建 |
| `logs\nonebot.log` | 框架日志（连接、事件、报错） |
| `logs\qq-bridge.log` | 业务日志（聊天、记忆、语音、主动开聊） |
| `logs\watchdog.log` | 掉线自愈记录 |
| `napcat\` | 协议端（含登录态），换机器要一起拷 |

---

## 五、日常

| 想做什么 | 怎么做 |
|---|---|
| 启动 / 停止 | 双击桌面「QQ机器人」（不在跑会自动拉起）；停止用 `stop_all.bat` |
| 看它活着没 | `curl.exe http://127.0.0.1:8088/status` |
| 自己发消息（脚本化） | `POST http://127.0.0.1:8088/send` `{"group_id":123,"message":"你好"}` |
| 网页配置台 | 浏览器开 `http://127.0.0.1:8088/admin` |
| 改模型 | 配置台里改 → 「保存配置」（热重载，不用重启） |
| 换人格 | 改 `data\personas.yaml`，保存即生效 |
| 备份 | 配置台「保存备份」→ 导出 zip 到 `backups\`（记忆库 + 对话记录 + 配置 + 日志） |

---

## 六、常见问题

| 现象 | 处理 |
|---|---|
| 双击 `安装.bat` 一闪就退 | 右键用 PowerShell 跑 `install.ps1`，看报错；多为 Python 没装好 |
| `status` 里 `connected: false` | NapCat 没登录：配置台点「扫码登录」，或看 `napcat\logs` |
| 服务起不来 / 配置台打不开 | 看 `logs\stderr.log`；端口被占用会打印「端口可能被占用」；跑 `selfcheck.py` |
| 模型不回话 | `logs\qq-bridge.log` 搜「插件处理异常」；确认密钥/地址/模型名；白名单里有没有发消息的号 |
| 语音没声音 | 需要 Node.js 18+（`node -v`）；没有就自动退回文字 |
| 想回退老版（自研适配器） | `.venv\Scripts\python.exe main.py`；把 boot/watchdog/login_qr/run.bat/start_all.bat 里的 `main_nb.py` 改回 `main.py` |

---

## 七、远程代装的话术模板

> 我这边远程帮你装，你只要做两件事：
> 1. 电脑上装个 ToDesk/向日葵，把设备码和密码发我（装完你改掉密码）
> 2. 手机 QQ 准备好机器人小号的扫码登录（我会在那一步喊你）
>
> 装完你电脑上会多一个「QQ机器人」图标，双击就是网页配置台；
> 以后换模型、换人格、备份记忆都在里面点，不用回来找我。

**注意**：QQ 必须登录在客户这台机器上（协议端跑在本地），
所以客户**关机 / 断网机器人就下线**。要 24 小时在线就跑 Linux 服务器（见《部署①》）。
