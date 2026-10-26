# 部署指令（交给 AI 执行）

你（AI）现在在客户的 Windows 电脑上，任务是把这个 QQ 机器人装好并跑起来。
**你能执行命令、读写文件、下载、启动程序。** 严格按下面顺序做，每步做完用「判据」自检；不通过就按「失败怎么办」处理，不要跳到下一步。

只在这三处停下来问人：**① 手机扫码 ② 确认人格对不对 ③ 确认 API 有余额**。其他全部自己完成。

---

## 第 0 步：确认手里有什么

```powershell
# 1) 有没有现成的安装包（最常见：操作员已经把 qq-bridge.zip 放在 D 盘根目录）
Get-ChildItem D:\, C:\Users\$env:USERNAME\Downloads -Filter "qq-bridge*.zip" -ErrorAction SilentlyContinue
# 2) 有没有网
Test-NetConnection api.github.com -Port 443 -InformationLevel Quiet
Test-NetConnection gitee.com -Port 443 -InformationLevel Quiet
# 3) 有没有 Python
py -3.12 -c "print('py ok')" ; python -c "print('python ok')"
```

判据：**至少有一样能拿到代码**（本地 zip 或 gitee 可达）。

失败怎么办：

- 找不到 zip 且 gitee 不通 → 停下来告诉操作员：「请把 qq-bridge.zip 传到这台电脑的 D 盘根目录，然后回复我继续」。
- 没有 Python → 走第 2 步的 winget 安装。

---

## 第 1 步：放代码

```powershell
# 情况 A：本地已有 zip
$zip = (Get-ChildItem D:\, C:\Users\$env:USERNAME\Downloads -Filter "qq-bridge*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if (-not $zip) { throw "没有找到安装包" }
Expand-Archive -Path $zip -DestinationPath "D:\" -Force -ErrorAction Stop
# 解压后目录名可能是 qq-bridge-main 或 qq-bridge，统一成 D:\qqbridge
$src = (Get-ChildItem D:\ -Directory | Where-Object { $_.Name -like "qq-bridge*" } | Select-Object -First 1).FullName
if ($src -ne "D:\qqbridge") { if (Test-Path D:\qqbridge) { Remove-Item D:\qqbridge -Recurse -Force }; Rename-Item $src "D:\qqbridge" }
Set-Location D:\qqbridge

# 情况 B：没有 zip、gitee 可达 → 从链接下载（把 <URL> 换成操作员给的地址）
# Invoke-WebRequest -Uri "<URL>" -OutFile D:\qq-bridge.zip ; 然后重复情况 A
```

判据：

```powershell
Test-Path D:\qqbridge\main.py        # True
Test-Path D:\qqbridge\qqbot           # True
```

> 路径必须是 `D:\qqbridge`，且**不含中文和空格**。不要放在 OneDrive 同步目录。

---

## 第 2 步：装环境（一条命令）

```powershell
Set-Location D:\qqbridge
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

它会：找/装 Python 3.12 → 建 `.venv` → 装依赖（失败自动换清华镜像）→ 下载 NapCat 到 `napcat\` → 生成 `config.yaml`、`data\personas.yaml` → 建桌面图标 → 打开设置向导。

**看到设置向导窗口弹出时，直接关掉它**（你要用工单自动配置，不点 GUI）。

判据：

```powershell
Test-Path D:\qqbridge\.venv\Scripts\python.exe    # True
Test-Path D:\qqbridge\napcat\napcat.mjs           # True
Test-Path D:\qqbridge\config.yaml                 # True
```

失败怎么办：

| 现象 | 处理 |
|---|---|
| pip 报 ConnectionError | 手动跑：`.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| NapCat 下载失败（GitHub 被墙） | 依次试这些前缀拼原链接：`https://ghproxy.net/` + `https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip`；成功后解压到 `D:\qqbridge\napcat`。仍失败 → 请操作员手动下载 `NapCat.Shell.zip` 放到 `D:\qqbridge\`，然后 `Expand-Archive .\NapCat.Shell.zip -DestinationPath .\napcat -Force` |
| Python 装不上 | `winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements`，完成后重跑 install.ps1 |

---

## 第 3 步：问人，拿三样东西（照这段话问，一次问完）

> 我需要你提供三样东西，其余我全自动：
> ① **机器人的 QQ 号**（建议用不常用的小号）+ 等会儿要你**手机扫码**登录它
> ② **允许跟它聊天的 QQ 号**（只有这些号它才回复）
> ③ **模型 API**：接口地址（一般以 /v1 结尾）、密钥、模型名 —— 你买的哪家就在后台复制
>
> 另外 6 个问题决定她的性格：
> 1. 她叫什么？几岁？
> 2. 她是做什么的？（学生 / 上班 / 开店 / 待在家）
> 3. 她怎么说话？（话多话少、爱用什么语气词、会不会撒娇或损人）
> 4. 你和她什么关系？（朋友 / 暧昧 / 前任 / 暗恋 / 在一起）
> 5. 有没有「没说破」的事？（例如她暗恋你但装没事）
> 6. 她几点睡、几点忙？（不说就用默认：1-8 睡，8-17 忙，17-22 闲，22-1 熬夜）
>
> 最后告诉我所在城市（天气提醒用，可不填）。

拿到答案后，**自己把人格答案写成一段完整 prompt**（不要只堆字段）：第二人称「你是…」开头，200-300 字，写清她的身份、说话习惯、和对方的关系、心里没说出口的东西。写好后给操作员看一眼确认。

---

## 第 4 步：写工单

在 `D:\qqbridge\ticket.yaml` 写这个文件（把内容换成实际值，**别照抄示例号**）：

```yaml
robot:
  qq: "机器人QQ号"

allow:
  - "允许聊天的QQ号"

city: "杭州"

api:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-xxx"
  model: "deepseek-chat"

persona:
  name: "小柚"
  age: 20
  who: "在奶茶店做兼职"
  style: "短句、口语，爱用「呀」「啦」，会撒娇也会损人"
  relation: "高中同学。你暗恋他三年没说出口，毕业后断了联系，最近刚联系上"
  prompt: |
    把第 3 步写好的那段人格贴这里
```

判据：文件存在，`robot.qq`、`allow`、`api` 三项都非空。

---

## 第 5 步：自动生成配置

```powershell
Set-Location D:\qqbridge
.venv\Scripts\python.exe autoconfig.py --ticket ticket.yaml
```

判据：输出里有「已写入 config.yaml 和 data/personas.yaml」，且摘要中的 QQ 号、白名单、模型、人格都正确。有缺项它会直接告诉你缺哪个，回去补工单再跑。

可选：如果人格写得不够满意，加 `--polish` 让模型润色（`persona.notes` 里放要点）。

---

## 第 6 步：启动 + 扫码（要人）

```powershell
Start-Process -FilePath "D:\qqbridge\.venv\Scripts\pythonw.exe" -ArgumentList "boot.py" -WorkingDirectory "D:\qqbridge"
Start-Sleep -Seconds 25
(Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content
```

- 如果返回里 `"connected": true` → 直接进第 7 步（登录态还在，不用扫）。
- 如果是 `"connected": false` → 屏幕上会弹出一个二维码窗口，**告诉操作员**：
  > 屏幕上有个登录窗口，请用手机 QQ（登录的是刚才那个机器人号）扫一下码。扫完窗口会自己关。

之后轮询直到成功（最多等 3 分钟）：

```powershell
for ($i=0; $i -lt 18; $i++) { Start-Sleep 10; $s = (Invoke-WebRequest http://127.0.0.1:8088/status -UseBasicParsing).Content; if ($s -match '"connected":\s*true') { "已连接"; break } }
```

判据：`connected: true` 且 `self_id` 等于机器人 QQ 号。

失败怎么办：二维码过期 → 关掉那个窗口，重跑 `login_qr.py`（`.venv\Scripts\python.exe login_qr.py`）；一直连不上 → 确认电脑上装的 QQ 是最新版。

---

## 第 7 步：自检并交付

```powershell
Set-Location D:\qqbridge
.venv\Scripts\python.exe selfcheck.py
```

判据：**12/12 全绿**。有红色项，按它给的「处理」提示修完再跑一次。

再手工验三件（自检查不到）：

1. 用**没列入白名单**的号发一条消息 → 应该完全没有回应。
2. 用白名单号发「在吗」→ 3-10 秒内回，且像人说话。
3. 双击桌面「QQ机器人」→ 点一次「自动修复」（开掉线监控）→ 再点「保存备份」，桌面应出现 zip。

最后给操作员这段交付说明：

> 装好了，以后这样用：
> 1. 桌面「QQ机器人」双击打开，能启动 / 扫码登录 / 停止。
> 2. 掉线了不用慌：点「扫码登录」，手机扫一下就好。
> 3. 想换模型或改性格，还是这个面板点「模型设置」，或者找我。
> 4. 桌面「保存备份」会把记忆和聊天记录打成一个包，换电脑能还原。

---

## 交付报告（最后输出这一段给操作员）

```
安装结果：成功 / 失败（失败写卡在哪一步）
安装目录：D:\qqbridge
机器人 QQ：xxx
白名单：xxx
模型：xxx @ xxx
人格：名字 / 身份 / 关系一句话
自检：12/12
登录态：已连接（self_id xxx）
下一步：双击桌面「QQ机器人」
```

---

## 硬规矩

1. **不要**重启客户电脑、不要改系统设置、不要卸载软件。
2. **不要**把 `config.yaml` / `ticket.yaml` 的内容外传或写进聊天记录（含 API 密钥）。
3. 每一步都要按判据自检，不要跳步；报错先看 `D:\qqbridge\logs\qq-bridge.log`。
4. 客户改主意要换人格/模型：改 `ticket.yaml` 后重跑第 5 步，再重启服务（`taskkill` 掉 8088 端口进程后重跑第 6 步启动命令）。
5. 装完不要把 `.venv`、`napcat`、`data`、`logs` 打包外发；只有 `stickers` 和 `data\personas` 属于客户隐私数据。
