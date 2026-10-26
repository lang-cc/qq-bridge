> ⚠️ **这份是旧版任务单（自研适配器 `main.py` 时代）。**
> 现在跑的是 NoneBot2 框架，请改用 **[`docs/任务单-AI部署.md`](任务单-AI部署.md)**（更全，含 Windows / Linux 两条线）。
> 本文仅作历史参考与极端情况下的手工回退说明。

---

# QQ 机器人 · 部署任务单

> **你（AI）的唯一任务：按这张单子把机器人装好、跑起来、验证通过。**
> 单子上填了什么就用什么，**不要再问单子上已经有的东西**。表里空着或写「默认」的，用默认值处理，并在最后报告里说明用了默认。

---

# ① 填写区（装机的人填这里，填完把整个文件发给 AI）

```
【机器人 QQ 号】
QQ号：____

【谁可以跟它聊天】（只有这些号会得到回复，其他号一概不回；多个用逗号隔开）
QQ号：____

【模型 API】（OpenAI 兼容接口，从你买 API 的后台复制）
接口地址：____          例：https://api.deepseek.com/v1
密钥：____              例：sk-xxxx
模型名：____            例：deepseek-chat

【她的性格】
名字：____              例：小柚
年龄：____              例：20
做什么的：____          例：在奶茶店做兼职
怎么说话：____          例：短句、爱用「呀」「啦」，会撒娇也会损人
和你什么关系：____      例：高中同学，她暗恋我三年但没说出口
没说破的事：____        例：她不知道我也喜欢她（没有就写「无」）
几点睡几点忙：____      例：1点睡，8-17在店里；不写就用默认

【天气提醒的城市】（可不填）
城市：____              例：杭州
```

填完 → 保存 → 把这个文件发给客户机上的 AI，说一句「按上面的任务单执行」。

---

# ② 给 AI 的执行规则（必读，5 条）

1. 你能执行命令、读写文件、下载、启动程序。**自己动手，不要指导用户手点。**
2. 按 ③ 的步骤顺序做，每步做完用「判据」检查；不通过就按「失败怎么办」处理，**不要跳到下一步**。
3. 只在**三处**停下来问人：手机扫码、人格写好后给对方确认、API 报错需要核对。其他一律自己做。
4. 所有路径固定用 `D:\qqbridge`，不要带中文和空格，不要放 OneDrive 目录。
5. 不要把 `config.yaml` / `ticket.yaml` 的内容（含密钥）外传，只写在本机文件里。

---

# ③ 执行步骤

## 第 1 步 · 拿到代码

**这个项目可以从公网直接下载（无需登录）**：`https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/qq-bridge-full.zip`（约 34MB，已内含 NapCat 协议端）。

```powershell
# 情况 A：本机已有安装包（D 盘根目录 / 下载目录）→ 直接用
$zip = (Get-ChildItem D:\, C:\Users\$env:USERNAME\Downloads -Filter "qq-bridge*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName

# 情况 B：没有就下载
if (-not $zip) {
    $zip = "D:\qq-bridge-full.zip"
    Invoke-WebRequest -Uri "https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/qq-bridge-full.zip" -OutFile $zip -UseBasicParsing -TimeoutSec 600
}

Expand-Archive -Path $zip -DestinationPath "D:\" -Force
$src = (Get-ChildItem D:\ -Directory | Where-Object { $_.Name -like "qq-bridge*" } | Select-Object -First 1).FullName
if ($src -ne "D:\qqbridge") { if (Test-Path D:\qqbridge) { Remove-Item D:\qqbridge -Recurse -Force }; Rename-Item $src "D:\qqbridge" }
Set-Location D:\qqbridge
```

判据：`Test-Path D:\qqbridge\main.py` 为 True，且 `D:\qqbridge\qqbot` 存在。

失败怎么办：Gitee 下载失败/超时 → 让操作员用浏览器打开 `https://gitee.com/wangcc111/qq-bridge-dist` 手动下载 `qq-bridge-full.zip` 放到 `D:\`，然后重复上面 `Expand-Archive` 之后的命令。

## 第 2 步 · 装环境（一条命令）

```powershell
Set-Location D:\qqbridge
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

它会：找/装 Python 3.12 → 建 `.venv` → 装依赖（失败自动换清华镜像）→ 下载 NapCat 到 `napcat\` → 生成配置和桌面图标 → 最后弹出一个设置向导。

**向导窗口一出现就关掉它**——你要用后面的任务单自动写配置，不点 GUI。

判据：

```powershell
Test-Path D:\qqbridge\.venv\Scripts\python.exe    # True
Test-Path D:\qqbridge\napcat\napcat.mjs           # True
Test-Path D:\qqbridge\config.yaml                 # True
```

失败怎么办：

| 现象 | 处理 |
|---|---|
| pip ConnectionError | `.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| NapCat 下载失败 | 换加速前缀重试：`https://ghproxy.net/https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip`，下完 `Expand-Archive .\NapCat.Shell.zip -DestinationPath .\napcat -Force`；仍失败则请对方手动下载并放到 `D:\qqbridge\` |
| Python 装不上 | `winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements`，然后重跑 install.ps1 |

## 第 3 步 · 把 ① 的内容写进工单

创建 `D:\qqbridge\ticket.yaml`，值全部照抄 ①（**不要用示例号**）：

```yaml
robot:
  qq: "①里的机器人QQ号"

allow:
  - "①里的白名单QQ号"

city: "①里的城市"          # 空着就留 ""

api:
  base_url: "①的接口地址"
  api_key: "①的密钥"
  model: "①的模型名"

persona:
  name: "①的名字"
  age: 20                    # ①的年龄，填数字
  who: "①做什么的"
  style: "①怎么说话"
  relation: "①和你什么关系 + ①没说破的事"
  prompt: |
    这里放你自己写的那段人格（见下）
  life: []                   # ①的作息；没写就留空，用默认
```

`prompt` 由你写：把 ① 里「名字/年龄/做什么/怎么说话/关系/没说破的事」揉成一段 **200-300 字、第二人称「你是…」开头**的中文人格。要求具体、有生活细节、有她心里没说出口的东西。写完把这段读给对方确认一次。

判据：`ticket.yaml` 里 `robot.qq`、`allow`、`api` 三项都非空。

## 第 4 步 · 自动生成配置

```powershell
Set-Location D:\qqbridge
.venv\Scripts\python.exe autoconfig.py --ticket ticket.yaml
```

判据：输出里有「已写入 config.yaml 和 data/personas.yaml」，且摘要中的 QQ 号、白名单、模型、人格、上下文条数都正确。缺项它会直接报缺哪个，回去补。

## 第 5 步 · 启动（需要人扫码）

```powershell
Start-Process -FilePath "D:\qqbridge\.venv\Scripts\pythonw.exe" -ArgumentList "boot.py" -WorkingDirectory "D:\qqbridge"
Start-Sleep -Seconds 25
(Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content
```

- 返回 `"connected": true` → 直接进第 6 步（登录态还在，不用扫）。
- 返回 `"connected": false` → 屏幕会弹出一个二维码窗口，**告诉对方**：
  > 屏幕上有个登录窗口，请用手机 QQ（登录机器人那个号）扫一下码，扫完窗口会自己关。

然后轮询，最多等 3 分钟：

```powershell
for ($i=0; $i -lt 18; $i++) { Start-Sleep 10; $s = (Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content; if ($s -match '"connected":\s*true') { "已连接"; break } }
```

判据：`connected: true`，且 `self_id` 等于 ① 里的机器人 QQ 号。

失败怎么办：二维码过期 → 关窗口，跑 `.venv\Scripts\python.exe login_qr.py` 重开；一直连不上 → 确认这台电脑的 QQ 是最新版。

## 第 6 步 · 自检 + 交付

```powershell
Set-Location D:\qqbridge
.venv\Scripts\python.exe selfcheck.py
```

判据：**12/12 全绿**。红项按它给的「处理」修完再跑。

再手工验三件：

1. 用**不在白名单**的号发消息 → 完全没回应。
2. 用白名单号发「在吗」→ 3-10 秒内有回复，像人说话，不是客服腔。
3. 双击桌面「QQ机器人」→ 点一次「自动修复」（开掉线监控）→ 点「保存备份」，桌面出现 zip。

最后把这段交给对方：

> 装好了。以后双击桌面「QQ机器人」就能启停；掉线了点「扫码登录」手机扫一下；想换模型或用备份都在那个面板里。

---

# ④ 交付报告（最后按这个格式输出）

```
安装结果：成功 / 失败（失败写卡在哪一步、报错原文）
安装目录：D:\qqbridge
机器人 QQ：____
白名单：____
模型：____ @ ____
人格：____（名字 / 身份 / 关系一句话）
自检：__/12
登录态：已连接（self_id ____）
用了默认值的项：____
下一步：双击桌面「QQ机器人」
```

---

# ⑤ 硬规矩

1. 不要重启对方电脑、不要改系统设置、不要卸载任何软件。
2. 不要把密钥、`config.yaml`、`ticket.yaml` 内容发到聊天里或任何外部位置。
3. 报错先看 `D:\qqbridge\logs\qq-bridge.log`，再看 `logs\boot.log`、`logs\watchdog.log`。
4. 想换人格/模型：改 `ticket.yaml` → 重跑第 4 步 → 杀掉 8088 端口进程 → 重跑第 5 步。
5. 对外打包只含代码和 `docs`；不要把 `.venv`、`napcat`、`data`、`logs` 发出去（含客户隐私）。
