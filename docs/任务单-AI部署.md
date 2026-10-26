# QQ 机器人 · 部署任务单（v2 · NoneBot2 框架）

> **你（AI）的任务：把这份单子执行完——装好、跑通、验证、出报告。**
> 单子里已填写的信息直接照用，**不要再问**。空着的按默认值处理，并在报告里注明用了默认值。
> 只在第 ② 节列的四处停下来找人（扫码、人格确认、密钥或防火墙需要本人操作、系统层面必须重启）。

---

# ① 填写区（人填，填完把整份文件发给 AI）

```
【部署到哪】选一个，填 A 或 B，另一个写「不适用」
  A. Windows 本地  —— 机器人跑在这台 Windows 电脑上（QQ 也登录在这台电脑，关机就下线）
  B. Linux 服务器 —— 阿里云/腾讯云等云主机（24 小时在线）

【B 时必填】服务器公网 IP：________    SSH 账号：________    密码或密钥：________

【机器人 QQ 号】________            （建议小号；扫码登录用）
【谁可以跟它聊天】
  私聊 QQ 号：________            （多个用逗号隔开；只有这些号会得到回复）
  群号：________                  （可不填；填了默认只在群里被 @ 时才回）
【模型 API】OpenAI 兼容接口
  接口地址：________              例：https://api.deepseek.com/v1
  密钥：________                  例：sk-xxxxxxxx
  模型名：________                例：deepseek-chat
【她的性格】
  名字：________                  例：小柚
  年龄：________                  例：20
  做什么的：________              例：在奶茶店做兼职
  怎么说话：________              例：短句、爱用「呀」「啦」，会撒娇也会损人
  和你什么关系：________          例：高中同学，她暗恋我三年没说出口
  没说破的事：________            例：她不知道我也喜欢她（没有写「无」）
  作息：________                  例：1 点睡，8-17 在店里（不写用默认）
【天气城市】________              例：杭州（可不填）
```

---

# ② 给 AI 的硬规矩（8 条，违反任何一条都算失败）

1. **自己动手执行命令**，不要教用户点按钮；需要人做的只有扫码、确认人格、解安全组。
2. **不要改架构**：不要换框架、不要装额外插件、不要动端口（8199 反向 WS / 8088 本机接口 / 6099 NapCat 面板）。
3. **不要跳步**：每步都有「判据」，不通过就按「失败怎么办」处理，修好再往下。
4. **路径固定**：Windows 一律 `D:\qqbridge`（没有 D 盘用 `C:\qqbridge`），不带中文、空格、OneDrive；Linux 一律 `/opt/qqbridge`。
5. **密钥只落盘**：`config.yaml` / `ticket.yaml` 里的密钥不打印到聊天、不写进任何文档、不发外网。
6. **不动系统**：不卸载软件、不改系统设置、不重启服务器（Linux 用 `systemctl restart qqbridge` 即可）。
7. **只在四处停下来找人**：
   - 手机 QQ 扫码登录（第一步登录必须人工）
   - 把你自己写的人格念给对方确认（就一次）
   - Linux 安全组放行 6099（如果对方不给云控制台权限，就提示他自己点，然后等他回「好了」）
   - 任何一处判据连续失败 2 次以上，把**报错原文**发回给人，不要瞎试
8. **最后必须按第 ⑧ 节模板输出报告**，缺项视为没做完。

---

# ③ 情况 A：Windows 本地部署（机器人跑在这台电脑上）

## A1 · 拿到安装包

安装包：`qq-bridge-full.zip`（约 59MB，已内含 NapCat 协议端与表情包）。

```powershell
$zip = (Get-ChildItem D:\, "$env:USERPROFILE\Downloads", "$env:USERPROFILE\Desktop" -Filter "qq-bridge*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $zip) {
    $zip = "D:\qq-bridge-full.zip"
    Invoke-WebRequest -Uri "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v2.0/qq-bridge-full.zip" -OutFile $zip -UseBasicParsing -TimeoutSec 600
}
Write-Host "包：$zip   $([math]::Round((Get-Item $zip).Length/1MB,1)) MB"
```

**判据**：打印出的文件存在且 > 30MB。

**失败怎么办**：
- 下载 404 / 超时 → 让操作员用浏览器打开 `https://gitee.com/wangcc111/qq-bridge-dist` 手动下载 `qq-bridge-full.zip` 放到 `D:\`，然后重跑上面的 `$zip` 判断。
- 机器没有 D 盘 → 全程换成 `C:\`，安装目录用 `C:\qqbridge`。

## A2 · 写工单（含人格）

先按 ① 的内容，把人格写成一段 200–300 字的中文 prompt（规范见第 ⑤ 节），
**念给对方确认一次**，然后写文件 `D:\ticket.yaml`（UTF-8）：

```yaml
robot:
  qq: "①里的机器人QQ号"

allow:
  users:
    - "①里的私聊QQ号"
    - "有多个就多写几行"
  groups:
    - "①里的群号（没有就写 [] 这一行删掉）"

city: "①里的城市"          # 没填就留 ""

api:
  base_url: "①的接口地址"
  api_key: "①的密钥"
  model: "①的模型名"

persona:
  name: "①的名字"
  age: 20
  prompt: |
    这里贴你写的那段人格（多行，每行前面 4 个空格）
```

**判据**：`D:\ticket.yaml` 存在，且 `robot.qq`、`allow.users`、`api` 三项都非空。

## A3 · 一条命令装完

```powershell
$zip = "D:\qq-bridge-full.zip"      # A1 得到的路径
powershell -NoProfile -ExecutionPolicy Bypass -File deploy.ps1 -ZipPath $zip -InstallDir D:\qqbridge -TicketPath D:\ticket.yaml
```

> 如果解压后已经在目录里（`D:\qqbridge\deploy.ps1` 存在），改成：
> `cd D:\qqbridge; powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 -InstallDir D:\qqbridge -TicketPath D:\ticket.yaml`

它会依次做（幂等，可重复跑）：解压 → 找/装 Python 3.12 → 建 `.venv` → 装依赖（官方源失败自动切清华/阿里云镜像）
→ 下载并解压 NapCat → 按工单生成 `config.yaml` + `data\personas.yaml` → 生成 `nb.env` → 建桌面图标
→ 启动服务 → 轮询 `/status` → 打印报告。

**判据**（报告末尾应出现）：

```
框架     : NoneBot2 2.x（nonebot-adapter-onebot）
服务     : 在线
```

**失败怎么办**：

| 现象 | 处理 |
|---|---|
| 提示「缺少参数」 | 用了 `-TicketPath` 就不用传 `-Qq/-Users/...`；没用工单文件才需要补齐 |
| pip 装不上 | `.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| NapCat 下载全失败 | 让操作员手动下 `NapCat.Shell.zip` 放 `D:\qqbridge\` 后重跑同一命令 |
| 120 秒 `/status` 没起来 | 看 `D:\qqbridge\logs\stderr.log`、`logs\nonebot.log`；端口被占用就先结束旧的 `pythonw.exe` 再跑 |
| Python 装不上 | `winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements` 后重跑 |

## A4 · 扫码登录（必须人工）

```powershell
(Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content
```

- 返回 `"connected": true` → 登录态还在，直接进 A5。
- 返回 `"connected": false` → 拉起扫码：

```powershell
Start-Process -FilePath "D:\qqbridge\.venv\Scripts\python.exe" -ArgumentList "login_qr.py" -WorkingDirectory "D:\qqbridge"
```

告诉对方：

> 屏幕上会出现登录窗口，请用手机 QQ（登录机器人号那个）扫一下码，扫完窗口会自己关。

然后轮询（最多 3 分钟）：

```powershell
for ($i=0; $i -lt 18; $i++) { Start-Sleep 10; $s = (Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content; if ($s -match '"connected":\s*true') { "已连接  $s"; break } }
```

**判据**：`connected: true`，且 `self_id` = ①里的机器人 QQ 号。

## A5 · 验收

```powershell
Set-Location D:\qqbridge
.venv\Scripts\python.exe selfcheck.py
```

**判据**：**12/12 全绿**（红项按它给的「处理」修完重跑）。

再验三件事：

1. 机器人号上发 `/nb` → 必须回 `NoneBot2 运行时 / 框架 nonebot2 x.x / 已连协议端 1 个`
2. 发 `ping` → 回 `pong 🏓`；发 `help` → 回指令列表
3. 用**不在白名单**的号发消息 → 完全没反应；用白名单号发「在吗」→ 3–10 秒内像人一样回话

---

# ④ 情况 B：Linux 服务器部署（阿里云，24 小时在线）

## B1 · 连上服务器

```bash
ssh root@<公网IP>        # 有密钥就 ssh -i 路径 root@IP
```

**判据**：能执行 `cat /etc/os-release` 看到 Ubuntu / Debian。

**失败怎么办**：连不上 → 让对方在云控制台确认「实例运行中 + 安全组放行 22」；密码错 → 控制台重置密码。

## B2 · 一条命令部署（含系统依赖 / Docker / NapCat / systemd）

```bash
QQ=10001 \
USERS=20002,20003 \
CITY=杭州 \
BASE_URL=https://api.deepseek.com/v1 \
API_KEY=sk-你的密钥 \
MODEL=deepseek-chat \
PNAME=小柚 AGE=20 WHO="在奶茶店做兼职" \
STYLE="短句、口语，爱用「呀」「啦」" \
RELATION="高中同学，最近刚重新联系上" \
bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
```

可选：`GROUP=群号,群号`（群聊）、`AT_ONLY=false`（群里不用 @）、`HISTORY=100`（上下文条数）、
`STAGE=base`（只装环境不装 Docker）。

它做的事：加 2G swap（内存 <3G 时）→ 装 python3/venv/Docker/中文字体 → 下载代码到 `/opt/qqbridge`
→ `pip install` → 拉 NapCat 镜像 → 预置 OneBot 反向 WS 指向 `127.0.0.1:8199` → 生成 `ticket.yaml`
→ 跑 `autoconfig.py` 生成配置 → 装 systemd（`qqbridge` + `qqbridge-watchdog`）→ 起重 → 打 `/status`。

**判据**：末尾打印「部署完成」，且 `curl -s http://127.0.0.1:8088/status` 返回 `"ok": true`（此时 `connected` 还是 false，正常）。

**失败怎么办**：

| 现象 | 处理 |
|---|---|
| 代码下载失败 | 用 `CODE_URL=<可访问的 zip 地址>` 前缀重跑；或让操作员把 `qq-bridge-code.zip` 发到服务器上再 `CODE_URL=file:///root/qq-bridge-code.zip`（脚本需能 curl 到该地址） |
| Docker 拉镜像全失败 | 云控制台取专属镜像加速器写入 `/etc/docker/daemon.json` 的 `registry-mirrors` 再 `systemctl restart docker`，然后 `STAGE=all` 重跑 |
| pip 慢/失败 | 脚本已用阿里云镜像；仍失败 `curl -I https://mirrors.aliyun.com` 看网络 |
| `/status` 不通 | `journalctl -u qqbridge -n 80 --no-pager` 看报错；`ss -lntp \| grep -E '8088\|8199'` 看端口 |

## B3 · 放行扫码端口（人工，一次性）

让对方在阿里云控制台 → 安全组 → 入方向 → 添加 `6099`（来源先 `0.0.0.0/0`）。
扫完码后建议收回成「仅自己 IP」或删除该规则。

## B4 · 扫码登录（必须人工）

让对方浏览器打开 `http://<公网IP>:6099`，用手机 QQ 扫机器人号的码。

```bash
for i in $(seq 1 18); do sleep 10; s=$(curl -s http://127.0.0.1:8088/status); echo "$s"; echo "$s" | grep -q '"connected": *true' && break; done
```

**判据**：`"connected": true` 且 `"self_id": ①的机器人QQ号`。

## B5 · 验收

```bash
systemctl is-active qqbridge qqbridge-watchdog        # 两个都是 active
/opt/qqbridge/.venv/bin/python /opt/qqbridge/selfcheck.py   # 12/12
```

机器人号上发 `/nb` / `ping` / `help`，判据同 A5 第 1、2 条；
白名单外的号发消息应无任何回应。

---

# ⑤ 人格 prompt 写作规范（AI 自己写，别问）

写成 **200–300 字**、第二人称「你是…」开头的中文段落，必须包含：

1. 名字、年龄、身份/工作（具体到「哪家店、什么班」这种细节）
2. 说话风格（句子长短、口头禅、用不用表情/省略号、绝不说什么——比如「作为AI」「有什么可以帮你」）
3. 与对方的关系和来历（怎么认识的、现在什么状态）
4. 心里没说出口的那点事（暗恋/别扭/在意），这条决定她说话的分寸
5. 边界：不解释自己是程序、不主动提敏感话题、不知道的事就顺着聊

示例（可直接用，也可改写）：

```
你是小柚，20 岁，在街角那家「甜啦啦」做兼职，晚班到十点。
说话短、口语，爱用「呀」「啦」「嘛」，偶尔损人但没恶意；
不用书面语，不列点，不说「作为AI」「有什么可以帮你」这种话。
你和他高中同学三年，暗恋他没说出口，毕业后断了联系，最近刚重新加上。
你会在意他回消息快不快，但不会直接问；
他半天不回你会说「你是不是又忙忘了」，语气像抱怨又像撒娇。
你不知道的事就顺着聊，不装懂；不主动提你自己是程序。
```

---

# ⑥ 验收清单（逐条打勾，缺一条不算交付）

- [ ] `curl /status` 返回 `ok: true`，`connected: true`，`self_id` 正确
- [ ] `selfcheck.py` **12/12**
- [ ] `/nb` 回框架信息（证明跑的是 NoneBot2）
- [ ] `ping` 回 `pong`；`help` 回指令列表
- [ ] 白名单号聊天有像人回复；白名单外的号完全没反应
- [ ] 桌面快捷方式「QQ机器人」能打开控制面板（Windows）
- [ ] `systemctl is-active qqbridge qqbridge-watchdog` 都是 active（Linux）
- [ ] 日志里没有连续报错：`logs/qq-bridge.log`、`logs/nonebot.log`

---

# ⑦ 故障速查（按症状查命令）

| 症状 | 命令 |
|---|---|
| 不知道服务活着没 | `curl -s http://127.0.0.1:8088/status` |
| 机器人不回话 | 先看 `/status` 的 connected；再看 `logs/qq-bridge.log` 搜「插件处理异常」；确认发消息的号在白名单 |
| 掉线了 | Windows：面板「扫码登录」；Linux：重开 6099 面板扫码，或 `docker restart napcat` |
| 端口被占用 | Windows `netstat -ano \| findstr :8088`；Linux `ss -lntp \| grep 8088` |
| 框架没起来 | Windows 看 `logs\stderr.log`、`logs\nonebot.log`；Linux `journalctl -u qqbridge -n 80` |
| 语音没声音 | 需要 Node.js 18+（`node -v`），没有会自动退回文字 |
| 想换模型 | 改 `config.yaml` 的 `autoreply.llm` → 重启服务；Windows 也可在面板「模型设置」热改 |
| 想换人格 | 改 `data/personas.yaml`（立即生效，不用重启） |
| 想回退老版（自研适配器） | 启动 `main.py` 而不是 `main_nb.py`；systemd/lib 里把 `ExecStart` 改回 `main.py` |

**文件地图**

| 位置 | 内容 |
|---|---|
| `config.yaml` | 全部配置（含密钥）：模型、白名单、开关、语气 |
| `data/personas.yaml` | 人格（改完保存即生效） |
| `data/personas/*/memory.db` | 记忆库（备份就整个目录拷走） |
| `nb.env` | 框架配置（`DRIVER=~fastapi`/`HOST`/`PORT`），删掉会自动按 config 重建 |
| `logs/nonebot.log` | 框架日志（连接、事件） |
| `logs/qq-bridge.log` | 业务日志（聊天、记忆、语音） |
| `logs/watchdog.log` | 掉线自愈记录 |
| `napcat/`（Linux 为容器） | 协议端 + 登录态，换机器要一起迁 |

---

# ⑧ 交付报告（最后按这个格式输出，缺项视为没做完）

```
部署方式：A. Windows 本地 / B. Linux 服务器
安装目录：____
系统/版本：____（Windows 11 / Ubuntu 22.04）
Python：____       框架：NoneBot2 ____
机器人 QQ：____     白名单：____（群：____）
模型：____ @ ____
人格：____（名字 / 身份 / 关系，一句话）
接口：http://127.0.0.1:8088/status → connected=____ self_id=____
自检：__/12
扫码：已完成 / 未完成（原因：____）
验收：/nb ✅/❌   ping ✅/❌   help ✅/❌   白名单外不回 ✅/❌
用了默认值的项：____
遗留问题：____（没有写「无」）
下一步：____（Windows：双击桌面「QQ机器人」；Linux：systemctl restart qqbridge）
```

---

# ⑨ 附录：参数速查

## Windows：`scripts\remote-deploy.ps1`（或根目录 `deploy.ps1`）

| 参数 | 说明 |
|---|---|
| `-ZipPath` | 安装包路径（给了会自动解压到 `-InstallDir`） |
| `-InstallDir` | 安装目录，默认自动判断，建议 `D:\qqbridge` |
| `-TicketPath` | 已写好的 `ticket.yaml`（**推荐**：人格长文本走这个，避免命令行转义） |
| `-Qq -Users -Groups -City` | 不用工单时直接在命令行给 |
| `-BaseUrl -ApiKey -Model` | 模型三项 |
| `-PersonaName -PersonaAge -PersonaWho -PersonaStyle -PersonaRelation` | 人格字段（短的话可用） |
| `-PersonaPrompt` | 整段人格（多行字符串） |
| `-Port 8199 -ApiPort 8088` | 换端口（一机多开时） |
| `-SkipNapCat` | 这台机器已有协议端 |
| `-NoStart` | 只装环境不启动 |
| `-NoShortcut` | 不建桌面图标 |
| `-DryRun` | 只打印计划 |

## Linux：`deploy-linux.sh` 环境变量

`QQ` `USERS` `GROUP` `CITY` `BASE_URL` `API_KEY` `MODEL` `PNAME` `AGE` `WHO` `STYLE` `RELATION`
`AT_ONLY` `HISTORY` `STAGE`(all/base) `SWAP_GB` `CODE_URL`

## 一次性装完之后的常用运维

```bash
# Linux
systemctl status qqbridge; systemctl restart qqbridge
journalctl -u qqbridge -n 100 -f
tail -f /opt/qqbridge/logs/nonebot.log

# Windows
curl.exe http://127.0.0.1:8088/status
.venv\Scripts\python.exe selfcheck.py
Get-Content .\logs\nonebot.log -Tail 50 -Wait
```
