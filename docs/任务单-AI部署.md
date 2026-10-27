# QQ 机器人 · 部署任务单（v3 · NoneBot2 框架）

> **你（AI）的任务：问清 3 件事 → 装好 → 跑通 → 验证 → 出报告。**
> 用户不需要填任何表格：你按 ① 的话术**主动问**（模型三项 / 人格 / 装在哪），然后全自动做完。
> 机器人号扫码后自动记录，白名单装完自动认领，系统类型你自己判断。
> **不要问 QQ 号、白名单、城市、端口** —— 用不着他操心。

---

# ① 开场：这些你去问用户（他不用填表）

用户手上不需要准备任何表格。**你先按下面这段话术问一遍**（一次问清，别来回问），拿到答案再开工：

```
我要开始装了，先问你 3 件事（直接回答就行）：

1）模型接口：网址、密钥、模型名，三个一起发我（例：
   https://api.deepseek.com/v1   sk-xxxx   deepseek-chat）

2）人格：她（他）是个什么样的人？叫什么、多大、干什么的、说话什么风格、
   跟你的关系 —— 想到什么就写什么，直接发一大段话给我也行，我照着写进去。

3）装在哪儿：这台电脑（关机会下线），还是你有台云服务器（24 小时在线）？
   有服务器的话把公网 IP 和 SSH 账号给我。
```

拿到回答后自己核对这几项，**缺哪项只补问哪项**：

| 要拿到的东西 | 从回答里取 |
|---|---|
| 模型网址 `base_url` | 形如 `https://.../v1` |
| API 密钥 `api_key` | `sk-` 开头那串 |
| 模型名 `model` | 形如 `deepseek-chat`、`gpt-4o-mini` |
| 人格 | 一整段文字（只给要点也行，见第 ⑥ 节，由你扩写） |
| 装在哪 | 这台电脑 / 云服务器（有公网 IP + SSH 账号） |

> **绝对不要问**：机器人 QQ 号、白名单、城市、端口、要不要开语音、各种参数。
> 这些都不用他操心：机器人号扫码后自动记录，白名单装完自动认领，城市不填就不报天气。

---

# ② 给 AI 的硬规矩（9 条，违反任何一条都算失败）

1. **自己动手执行命令**，不要教用户点按钮。需要人做的只有三件：手机扫码、发一句话（认领白名单）、云控制台放行端口。
2. **只问开场那 3 件事**（模型三项 / 人格 / 装在哪），其他一概不问：机器人 QQ 号（扫码后自动写入）、白名单（装完自动认领）、城市（不报天气也能用）、端口（固定 8199 / 8088）。
3. **不要改架构**：不换框架、不加插件、不改端口（8199 反向 WS / 8088 本机接口 / 6099 NapCat 面板）。
4. **不要跳步**：每步都有「判据」，不通过就按「失败怎么办」处理，修好再往下。
5. **路径固定**：Windows 一律 `D:\qqbridge`（无 D 盘用 `C:\qqbridge`），不带中文/空格/OneDrive；Linux 一律 `/opt/qqbridge`。
6. **密钥只落盘**：`ticket.yaml` / `config.yaml` 里的密钥不打印到聊天、不写进任何文档、不发外网。
7. **不动系统**：不卸载软件、不改系统设置、不重启机器（Linux 用 `systemctl restart qqbridge`）。
8. **人格照抄**：用户给的人格原样写进 `persona.prompt`，一个字都别改（只有他给的是一两句零散要点时才由你扩写，见第 ⑥ 节）。
9. **最后必须按第 ⑧ 节模板输出报告**，缺项视为没做完。

---

# ③ 第 0 步：确定部署方式（按用户回答 3 判断，别自己瞎猜）

```powershell
[System.Environment]::OSVersion.VersionString      # Windows
```

```bash
uname -a; cat /etc/os-release | head -3            # Linux
```

| 用户回答 | 走哪条 |
|---|---|
| 装了这台电脑 / 「就装我电脑上」 | 【④ 情况 A：本机部署】（机器人跑这台电脑，QQ 也登录在这台电脑） |
| 有云服务器并给了 IP + SSH | 【⑤ 情况 B：服务器部署】（24 小时在线，SSH 上去一条命令装完） |
| 说「要一直在线」但没服务器 | 告诉他本机方案关机会下线；他愿意就上云主机，不愿就先用【④】 |

> 如果当前这台机器本身就是那台云服务器（`uname` 是 Linux），直接走【⑤】，不用再 SSH。

---

# ④ 情况 A：Windows 本机部署

## A1 · 拿到安装包并解压

安装包 `qq-bridge-full.zip`（约 59MB，内含 NapCat 与表情包；解压出来就是安装目录）。

```powershell
$zip = (Get-ChildItem D:\, "$env:USERPROFILE\Downloads", "$env:USERPROFILE\Desktop" -Filter "qq-bridge*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $zip) {
    $zip = "D:\qq-bridge-full.zip"
    Invoke-WebRequest -Uri "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v2.0/qq-bridge-full.zip" -OutFile $zip -UseBasicParsing -TimeoutSec 600
}
Write-Host "包：$zip  $([math]::Round((Get-Item $zip).Length/1MB,1)) MB"

Expand-Archive -Path $zip -DestinationPath D:\qqbridge -Force
Test-Path D:\qqbridge\deploy.ps1     # 必须是 True
```

**判据**：`D:\qqbridge\deploy.ps1`、`D:\qqbridge\main_nb.py`、`D:\qqbridge\nb` 都存在。

**失败怎么办**：下载 404/超时 → 让用户用浏览器从 `https://gitee.com/wangcc111/qq-bridge-dist` 下 `qq-bridge-full.zip` 放 `D:\` 再解压；没有 D 盘就换 `C:\qqbridge`；`Expand-Archive` 报路径太长 → 用 `tar -xf $zip -C D:\qqbridge`。

## A2 · 写工单（只有 4 项）

把用户回答写进 `D:\ticket.yaml`（UTF-8，**人格整段照抄，每行前 4 个空格**）：

```yaml
api:
  base_url: "用户给的网址"
  api_key: "用户给的密钥"
  model: "用户给的模型名"

persona:
  prompt: |
    用户给的人格整段贴在这里
    第二行、第三行都保留
    每行前面 4 个空格（YAML 多行写法）
```

**判据**：`D:\ticket.yaml` 存在，`api` 三项非空，`persona.prompt` 字数 ≈ 用户给的那段。

> `robot.qq` 和 `allow` 都**不用写**：机器人号扫码时自动写入，白名单装完自动认领。

## A3 · 一条命令装完

```powershell
cd D:\qqbridge
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 -InstallDir D:\qqbridge -TicketPath D:\ticket.yaml
```

依次做（幂等，可重复跑）：找/装 Python 3.12 → 建 `.venv` → 装依赖（清华/阿里云镜像，官方源兜底）
→ 下载并解压 NapCat → 按工单生成 `config.yaml` + `data\personas.yaml` → 生成 `nb.env` → 建桌面图标
→ 启动服务 → 轮询 `/status` → 打印验收报告。

**判据**（报告末尾出现）：

```
框架     : NoneBot2 2.x（nonebot-adapter-onebot）
服务     : 在线
```

**失败怎么办**：

| 现象 | 处理 |
|---|---|
| pip 装不上 | `.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| NapCat 下载全失败 | 手动下 `NapCat.Shell.zip` 放 `D:\qqbridge\` 后重跑同一命令 |
| `/status` 120 秒没起来 | 看 `D:\qqbridge\logs\stderr.log`、`logs\nonebot.log`；端口占用先结束旧 `pythonw.exe` |
| 提示 `autoconfig 失败` | 只会是 `api.base_url / api_key / model` 三项没填 |

## A4 · 扫码登录（人工，一次）

```powershell
(Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content
```

- `"connected": true` → 登录态还在，直接进 A5。
- `"connected": false` → 让用户打开网页配置台扫码（也可以用命令）：

```powershell
Start-Process "http://127.0.0.1:8088/admin"       # 配置台里点「扫码登录」
# 等价的命令行方式：
Start-Process -FilePath "D:\qqbridge\.venv\Scripts\python.exe" -ArgumentList "login_qr.py" -WorkingDirectory "D:\qqbridge"
```

告诉用户：

> 浏览器里那个页面「动作」那一栏有个「扫码登录」按钮，点它，屏幕上会弹二维码窗口，用手机 QQ（登录机器人那个号）扫一下，扫完窗口自己会关。

轮询（最多 3 分钟）：

```powershell
for ($i=0; $i -lt 18; $i++) { Start-Sleep 10; $s = (Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content; if ($s -match '"connected":\s*true') { "已连接  $s"; break } }
```

**判据**：`connected: true`，`self_id` 是一串 QQ 号（**会自动写进 `config.yaml` 的 `bot_qq`，不用问用户**）。

## A5 · 认领白名单（自动，不用用户报号）

此刻白名单是空的 —— 谁发消息机器人都不回，但会把发信人写进日志：

1. 告诉用户：
   > 请用**你平时聊天的那个 QQ** 给机器人随便发一句话（比如「在吗」）。这会儿它不会回，正常，等我说好。
2. 确认日志留痕：

```powershell
Select-String -Path D:\qqbridge\logs\qq-bridge.log -Pattern "白名单外消息" | Select-Object -Last 3
```

3. 认领（加进白名单 + 热重载，不重启）：

```powershell
cd D:\qqbridge
.venv\Scripts\python.exe tools\claim.py --auto
```

输出应为：

```
· 加入白名单：<对方QQ>
· 已写入 D:\qqbridge\config.yaml
白名单    ：<对方QQ>
热重载    ：{'ok': True}
```

4. 让用户**再发一句「在吗」** → 应 3–10 秒内像人一样回话。

**判据**：`claim.py` 输出有「加入白名单」，第二次发消息有回复。

**失败怎么办**：

| 现象 | 处理 |
|---|---|
| 日志没有「白名单外消息」 | 消息没到机器人：`curl /status` 看 `connected`；确认发的是机器人号不是群；让用户重发 |
| 提示「发现多个 sender」 | `--add <对方QQ>` 手动指定（可给多个） |
| 加了白名单还是不回 | 看 `logs\qq-bridge.log` 的模型报错（密钥/余额/模型名），改 `config.yaml` 的 `autoreply.llm`，再 `tools\claim.py --status` 复查 |

## A6 · 验收

```powershell
cd D:\qqbridge
.venv\Scripts\python.exe selfcheck.py            # 要 12/12
.venv\Scripts\python.exe tools\claim.py --status
```

机器人号上再验：

1. `/nb` → 回 `NoneBot2 运行时 / 框架 nonebot2 x.x / 已连协议端 1 个`
2. `ping` → `pong 🏓`；`help` → 指令列表
3. **不在白名单**的另一个号发消息 → 完全没反应

---

# ⑤ 情况 B：Linux 服务器部署（阿里云，24 小时在线）

## B1 · 连上服务器

```bash
ssh root@<公网IP>
cat /etc/os-release | head -3
```

**判据**：显示 Ubuntu / Debian。
**失败怎么办**：连不上 → 让用户在云控制台确认「实例运行中 + 安全组放行 22」；密码错 → 控制台重置。

## B2 · 把人格写成文件（避免命令行转义）

```bash
cat > /root/persona.txt <<'PERSONA'
用户给的人格整段贴在这里
原样照抄，不用改
PERSONA
wc -c /root/persona.txt
```

## B3 · 一条命令部署

```bash
BASE_URL="用户给的网址" \
API_KEY="用户给的密钥" \
MODEL="用户给的模型名" \
PERSONA_FILE=/root/persona.txt \
bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
```

做的事：加 2G swap（内存 <3G）→ 装 python3 / Docker / 中文字体 → 下载代码到 `/opt/qqbridge` → `pip install`
→ 拉 NapCat 镜像 → 生成 `ticket.yaml`（含人格）→ `autoconfig` → 装 systemd（`qqbridge` + `qqbridge-watchdog`）
→ 起重 → 打 `/status`。

**判据**：末尾打印「部署完成」，且 `curl -s http://127.0.0.1:8088/status` 返回 `"ok": true`（此时 `connected` 还是 false，正常）。

**失败怎么办**：

| 现象 | 处理 |
|---|---|
| 代码下载失败 | 加前缀 `CODE_URL=<可访问 zip 地址>` 重跑；或先把 `qq-bridge-code.zip` 传到服务器，用 `CODE_URL=file:///root/qq-bridge-code.zip` |
| Docker 拉镜像全失败 | 云控制台取专属镜像加速器写进 `/etc/docker/daemon.json` 的 `registry-mirrors` → `systemctl restart docker` → 重跑 |
| `/status` 不通 | `journalctl -u qqbridge -n 80 --no-pager`；`ss -lntp \| grep -E '8088\|8199'` |

## B4 · 放行扫码端口（人工）

用户在阿里云控制台 → 安全组 → 入方向 → 加 `6099`（来源先 `0.0.0.0/0`）。扫完码建议收回或删除。

## B5 · 扫码登录（人工）

让用户浏览器打开 `http://<公网IP>:6099`，用手机 QQ 扫机器人号的码。

**判据**：面板显示已登录（能看到机器人昵称/头像）。

## B6 · 把 NapCat 接到机器人服务上（一条命令）

```bash
bash /opt/qqbridge/scripts/link-onebot.sh
```

自动做：找 NapCat 登录后生成的 `onebot11_<QQ>.json` → 写入反向 WS 指向 `ws://127.0.0.1:8199/onebot/v11/ws`
→ `docker restart napcat` → 等 `connected: true` → 把机器人号写进 `config.yaml` 的 `bot_qq`。

**判据**：输出「已连上机器人服务」；`curl -s http://127.0.0.1:8088/status` 里 `"connected": true`。

**失败怎么办**：提示「还没找到 onebot11_*.json」→ 扫码没成功，回 B5；「还没连上」→ `docker logs --tail 60 napcat`。

## B7 · 认领白名单（自动）

```bash
# 先让用户用自己聊天的 QQ 发一句「在吗」（此时不回，正常）
cd /opt/qqbridge
.venv/bin/python tools/claim.py --auto
```

然后让用户再发一句 → 应该有回复。

**判据**：输出「加入白名单」+「热重载 {'ok': True}」，第二次发消息有回复。

## B8 · 验收

```bash
systemctl is-active qqbridge qqbridge-watchdog                 # 两个都 active
/opt/qqbridge/.venv/bin/python /opt/qqbridge/selfcheck.py      # 12/12
cd /opt/qqbridge && .venv/bin/python tools/claim.py --status
```

机器人号上发 `/nb`、`ping`、`help`，判据同 A6 第 1–3 条。

---

# ⑥ 人格怎么处理

- 用户给的是**整段文字** → 原样写进 `persona.prompt`：不改写、不精简、不加设定。
- 用户只给了一两句要点（少见）→ 你扩写成 200–300 字、第二人称「你是…」开头的中文段落，
  保留对方所有细节，补上说话习惯（句子长短、口头禅、绝不说「作为AI」这类话），写完念一遍确认。
- **作息**可以不写（系统有默认）；**城市**不用问（不填就不报天气，不影响聊天）。

---

# ⑦ 验收清单（逐条打勾，缺一条不算交付）

- [ ] `curl /status` → `ok: true`、`connected: true`、`self_id` 是机器人号
- [ ] `selfcheck.py` **12/12**
- [ ] `/nb` 回框架信息（证明跑的是 NoneBot2）
- [ ] `ping` 回 `pong`；`help` 回指令列表
- [ ] 认领成功：`claim.py --auto` 输出「加入白名单」，用户第二次发消息**有回复**
- [ ] 白名单外的号发消息**完全没反应**
- [ ] Windows：桌面「QQ机器人」图标能打开网页配置台（`8088/admin`）；Linux：两个 systemd 服务都 active
- [ ] 日志无连续报错（`logs/nonebot.log`、`logs/qq-bridge.log`）

---

# ⑧ 交付报告（最后按这个格式输出，缺项视为没做完）

```
部署方式：A. Windows 本机 / B. Linux 服务器
安装目录：____
系统/版本：____（Windows 11 / Ubuntu 22.04）
Python：____        框架：NoneBot2 ____
模型：____ @ ____
机器人 QQ：____（从 /status 读出来的）
人格：____ 字，原样写入 ✅ / 改写过 ❌
接口：http://127.0.0.1:8088/status → connected=____ self_id=____
白名单（认领后）：____
自检：__/12
扫码：已完成 / 未完成（原因：____）
验收：/nb ✅/❌   ping ✅/❌   help ✅/❌   白名单外不回 ✅/❌
遗留问题：____（没有写「无」）
下一步：____（Windows：双击桌面「QQ机器人」；Linux：systemctl restart qqbridge）
```

---

# ⑨ 故障速查

| 症状 | 命令 |
|---|---|
| 不知道服务活着没 | `curl -s http://127.0.0.1:8088/status` |
| 机器人号 / 白名单现状 | `cd <安装目录> && .venv/Scripts/python.exe tools/claim.py --status`（Linux 用 `.venv/bin/python`） |
| 机器人不回话 | 先看 `connected`；再看 `logs/qq-bridge.log` 搜「插件处理异常」（多为密钥/模型名/余额）；确认号在白名单 |
| 掉线 | Windows：配置台点「扫码登录」（先点一次「开掉线自愈」以后自动重连）；Linux：重开 6099 面板扫码或 `docker restart napcat` |
| 端口被占用 | Windows `netstat -ano \| findstr :8088`；Linux `ss -lntp \| grep 8088` |
| 框架没起来 | Windows `logs\stderr.log`、`logs\nonebot.log`；Linux `journalctl -u qqbridge -n 80` |
| 改模型（不重启） | 网页配置台里改 → 「保存配置」；或改 `config.yaml` 的 `autoreply.llm` → `curl -X POST http://127.0.0.1:8088/admin/reload` |
| 改人格 | 改 `data/personas.yaml` → 保存即生效 |
| 回退老版（自研适配器） | 跑 `main.py` 而不是 `main_nb.py`；systemd/lib 里把 `ExecStart` 改回 `main.py` |

**文件地图**

| 位置 | 内容 |
|---|---|
| `config.yaml` | 全部配置（含密钥）：模型、白名单、开关、语气、`bot_qq` |
| `data/personas.yaml` | 人格（改完保存即生效） |
| `data/personas/*/memory.db` | 记忆库（备份整个目录拷走） |
| `nb.env` | 框架配置（`DRIVER=~fastapi`/`HOST`/`PORT`），删掉会按 config 自动重建 |
| `logs/nonebot.log` | 框架日志（连接、事件） |
| `logs/qq-bridge.log` | 业务日志（聊天、记忆、语音、白名单留痕） |
| `logs/watchdog.log` | 掉线自愈记录 |
| `backups/` | 配置台「保存备份」导出的 zip（记忆库 + 对话 + 配置 + 日志） |
| `napcat/`（Linux 为 Docker 容器） | 协议端 + 登录态 |

---

# ⑩ 附录：工具速查

## Windows：`deploy.ps1`（薄壳，真逻辑在 `scripts\remote-deploy.ps1`）

| 参数 | 说明 |
|---|---|
| `-TicketPath` | **推荐**：写好的 `ticket.yaml`（人格长文本走这里，避免命令行转义） |
| `-InstallDir` | 安装目录，建议 `D:\qqbridge` |
| `-ZipPath` | 安装包路径（手上已有 `deploy.ps1` 时可让它自己解压） |
| `-Qq -Users -Groups -City` | 不用工单时直接给（本题单不需要） |
| `-BaseUrl -ApiKey -Model` | 模型三项 |
| `-PersonaPrompt` | 整段人格（多行字符串） |
| `-Port 8199 -ApiPort 8088` | 换端口（一机多开） |
| `-SkipNapCat` / `-NoStart` / `-NoShortcut` / `-DryRun` | 跳过协议端 / 不启动 / 不建图标 / 只打印计划 |

## Linux：`deploy-linux.sh` 环境变量

`BASE_URL` `API_KEY` `MODEL` `PERSONA`（整段）或 `PERSONA_FILE`（文件）`TICKET_FILE`（已有工单）
可选：`QQ` `USERS` `GROUP` `CITY` `AT_ONLY` `HISTORY` `STAGE`(all/base) `SWAP_GB` `CODE_URL`

## 装完后的两个万能命令

```bash
python tools/claim.py --auto      # 认领白名单：谁刚发过消息就加谁（并热重载）
python tools/claim.py --status    # 看现状：服务 / 机器人号 / 白名单
```
