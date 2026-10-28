# DeepSeek Harness（dsh）下载 / 安装 / 首次使用 · 完整教程

> 适用：Windows 10/11、macOS 13+。文档基于官方站点与仓库说明整理（2026-10 版），DeepSeek Harness 处于**开发者预览**阶段，版本迭代快，命令以 `--help` 输出为准。
>
> 官方入口：
> - 产品页：https://www.deepseek.com/harness/
> - 下载页：https://www.deepseek.com/download/
> - 源码仓库：https://github.com/deepseek-ai/deepseek-harness
> - 官方文档：https://deepseek-harness.github.io/deepseek-harness/
> - 许可证：MIT

---

## 0. 先选路线：三条安装方式对比

| 方式 | 适合谁 | 需要准备 | 特点 |
|---|---|---|---|
| **A. 桌面端安装包** | 普通用户、只想用起来 | 无（下载即装） | 双击安装，图形界面，支持后台运行、本地文件读写，自动更新 |
| **B. `npx` 启动 Web UI** | 有 Node 环境的开发者 | Node.js（建议 24 LTS+） | 一条命令启动本地网页版，无需装包，升级=换版本号 |
| **C. 源码安装** | 要改代码 / 写插件 / 二次开发 | Node.js ≥ 24.9、pnpm、git | 可调试、可自定义构建，占空间大 |

三者跑的是同一套 harness，能力基本一致；区别在分发方式和可定制程度。

---

## 1. 方式 A：桌面端（最省事）

### 1.1 下载

打开 https://www.deepseek.com/download/ ，按系统选择：

- **Windows（x64）**：直接下载
  `https://download.deepseek.com/desktop/dsh-latest-windows-x64.exe`
- **macOS（Apple 芯片，macOS 13 或更高）**：
  `https://download.deepseek.com/desktop/dsh-latest-macos-arm64.dmg`

> 文件名里的 `latest` 表示始终指向最新版，收藏该链接即可当"永远下最新版"的入口。

### 1.2 安装（Windows）

1. 双击 `dsh-latest-windows-x64.exe`。
2. 若弹出 **"Windows 已保护你的电脑"**（SmartScreen）：点「更多信息」→「仍要运行」。
   原因是安装包较新、下载量尚未积累签名信誉，并非文件损坏。
3. 选择安装位置（默认即可）→ 下一步 → 安装 → 完成。
4. 首次启动如出现防火墙提示，允许其访问**专用网络**即可（Web UI/本地服务需要回环访问）。

### 1.3 安装（macOS）

1. 双击 `dsh-latest-macos-arm64.dmg`，把图标拖进「应用程序」。
2. 首次打开若提示"无法验证开发者"：**右键 App → 打开 → 打开**（或在「系统设置 → 隐私与安全性」里点「仍要打开」）。
3. Intel Mac 目前官网只提供 Apple 芯片包；Intel 机型建议走方式 B。

### 1.4 首次启动后必做两件事

1. **配置模型**：设置 → 模型 → 在 DeepSeek 卡片填入 API 密钥 → 保存。
   密钥申请地址：https://platform.deepseek.com/
   （也支持第三方提供商 / 自定义 OpenAI 兼容端点、Anthropic Messages 端点。）
2. **选择工作区**：点「选择工作区」，添加你要操作的项目文件夹并选中。
   **没选中工作区时，输入框是不可用的**，这一步最容易漏。

密钥存在 `%USERPROFILE%\.dsh\.credentials.yaml`（macOS/Linux 为 `~/.dsh/`），settings 里只留引用；界面只会显示脱敏信息。

### 1.5 升级 / 卸载

- **升级**：下载页重新下载覆盖安装即可（会话与配置在 `.dsh` 目录，不受影响）。
- **卸载**：Windows「设置 → 应用 → 已安装的应用」卸载；macOS 把 App 拖到废纸篓。
- **彻底清除个人数据**（谨慎）：删除 `C:\Users\<你>\.dsh` —— 会一并清掉登录凭据、会话历史、插件与自定义配置。

---

## 2. 方式 B：`npx` 启动 Web UI（推荐开发者，本机已具备条件）

> 你机器上 `node v24.21.0`、`npm 11.19.0` **已满足要求**，可跳过 2.1。

### 2.1 装 Node.js（还没有的话）

到 https://nodejs.org/ 下载 LTS 版（建议 24.x 或更高）。装完开新终端验证：

```powershell
node -v     # 期望 v24.x 或更高
npm -v
```

### 2.2 一条命令启动

```powershell
npx @deepseek-ai/dsh web
```

行为说明：

- 默认在 `http://127.0.0.1:3080` 起 Web UI，并**自动用默认浏览器打开**；
- 通过 SSH / 远程会话启动时只打印宿主机 URL（本地转发由 SSH 客户端或编辑器负责）；
- 加 `--no-open` 只起服务、不弹浏览器：

```powershell
npx @deepseek-ai/dsh web --no-open
```

- 首次运行会下载依赖包，几十秒到几分钟属正常；之后再启动会用 npm 缓存，快很多。
- **进程就是服务**：关掉终端窗口 / Ctrl+C 就等于关掉 Web UI。

### 2.3 打开后的三步

1. 浏览器访问终端里打印的地址（默认 `http://127.0.0.1:3080`）。
2. 设置 → 模型 → 填 DeepSeek API 密钥 → 保存（立即生效，不用重启）。
3. 选择工作区 = **你启动 `npx` 命令时所在的那个目录**（dsh 以启动目录为默认文件系统位置），添加并选中后再开新会话。

> 想指定别的目录作为工作区：先 `cd` 到目标目录再启动，或在界面里手动添加该目录。

### 2.4 可选：全局安装（日常反复用更方便）

```powershell
npm install -g @deepseek-ai/dsh
dsh web                 # 之后直接这样启动
dsh web --no-open
```

查看版本 / 帮助：

```powershell
npm view @deepseek-ai/dsh version
dsh --help
dsh web --help          # 端口等参数以这里为准
```

升级 / 卸载：

```powershell
npm update -g @deepseek-ai/dsh      # 升级
npm uninstall -g @deepseek-ai/dsh   # 卸载
```

### 2.5 无界面（headless）跑一个任务

```powershell
dsh --profile headless "fetch https://example.com and tell me the page title"
```

适合放进脚本、CI、定时任务。

### 2.6 国内网络加速（可选）

`npx`/`npm` 下载慢时换镜像：

```powershell
npm config set registry https://registry.npmmirror.com
# 需要回滚时：
npm config set registry https://registry.npmjs.org
```

---

## 3. 方式 C：源码安装（定制 / 开发）

> 前置：**Node.js ≥ 24.9.0**、**pnpm**（仓库锁定 `pnpm@11.28.5`）、**git**。
> 你机器上目前缺 `git` 和 `pnpm`，先补这两样。

### 3.1 装 git 与 pnpm

```powershell
# git：https://git-scm.com/download/win 下载安装，或 winget
winget install --id Git.Git -e

# pnpm：Node 自带 corepack，最省事
corepack enable
corepack prepare pnpm@11.28.5 --activate
pnpm -v
# 备选：npm install -g pnpm
```

### 3.2 克隆并构建

```powershell
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web
```

要点：

- `pnpm run build` 负责准备仓库产物（耗时较久，属正常）；
- `pnpm dsh web` **直接使用已构建产物**，不会重新构建；
- 改源码开发时用 `pnpm run dev:web`：一个终端里完成构建 + 启动 + 源改变时重建前端 bundle；
- `make help` 可列出 Web 与 Desktop 相关的构建目标（Windows 无 make 时按 `package.json` 的 `scripts` 走）。

### 3.3 常见构建问题

| 现象 | 处理 |
|---|---|
| `pnpm: 无法将"pnpm"项识别为…` | 没执行 `corepack enable`，或当前终端未刷新 PATH，重开终端 |
| 构建报 Node 版本过低 | 升级到 Node ≥ 24.9.0 |
| 安装依赖卡住 / 大量超时 | 换 npm 镜像：`pnpm config set registry https://registry.npmmirror.com` |
| 内存不足中断 | 关闭其他大程序；构建脚本已按较大堆内存设置，必要时提高系统虚拟内存 |

---

## 4. 通用配置

### 4.1 数据目录 `DSH_HOME`

默认 `~/.dsh`（你这台机器：`C:\Users\wang\.dsh`），存放：

- `profiles/<profile>/cordis.patch.yml` —— 该 profile 的配置覆盖（如 `web`）
- `.credentials.yaml` —— 模型密钥（敏感，勿外传）
- 会话日志、插件、`.env` 等

要换位置就设环境变量后再启动：

```powershell
$env:DSH_HOME = "D:\dsh-home"
npx @deepseek-ai/dsh web
```

### 4.2 代理（模型调用 / 网页抓取 / HTTP MCP 都走它）

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
$env:HTTP_PROXY  = "http://127.0.0.1:7890"
$env:NO_PROXY    = "internal.example.com,.corp.example.com"
```

也可以把这几行写进 `C:\Users\<你>\.dsh\.env`（与 API key 放一起）。

关键提醒：

- **不支持 SOCKS**（`socks5://` 会被跳过并报错），请填代理软件的 **HTTP 端口**；
- 代理软件的"系统代理"开关浏览器认，**命令行工具不认**；要么导出环境变量，要么开 TUN 模式；
- 企业 TLS 拦截代理需要：`$env:NODE_EXTRA_CA_CERTS = "C:\path\corp-ca.pem"`（必须在启动 dsh **之前**设置）；
- 想确认是否生效，让 agent 抓一个页面，同时看代理软件的连接日志。

### 4.3 扩展能力（插件）

- 官方插件市场：https://deepseek-harness.github.io/deepseek-harness/guide/plugin-market
- 社区插件：GitHub 话题 https://github.com/topics/dsh-plugin
- 可以在「创造模式」里通过对话直接生成插件

---

## 5. 快速验收清单

装完后按顺序确认：

1. `node -v` ≥ 24（源码路线 ≥ 24.9）
2. 命令能起来：桌面端能打开窗口 / `dsh web` 打印出 `http://127.0.0.1:3080`
3. 浏览器能打开该地址，设置 → 模型里 DeepSeek 卡片显示已保存（脱敏）
4. **已选中工作区**，输入框可用
5. 发一句 `总结一下这个仓库并列出主要包`，能正常流式返回并调用工具

---

## 6. FAQ / 排错

**Q1：`npx @deepseek-ai/dsh web` 报 `EPERM ... npm-cache`**
npm 缓存目录不可写（常见于受限账户、沙箱、杀软锁定）。处理：

```powershell
npm cache clean --force
# 或把缓存挪到可写目录
npm config set cache "D:\npm-cache"
```

**Q2：端口 3080 被占用**
先 `npx @deepseek-ai/dsh web --help` 看当前版本支持的端口/主机参数，或先结束占用进程：

```powershell
Get-NetTCPConnection -LocalPort 3080 | Select-Object OwningProcess
```

**Q3：终端关了就没了？**
Web UI 由该进程承载。想常驻：桌面端（本来就后台运行），或用计划任务/终端复用器托管 `dsh web`。

**Q4：模型报 `MISSING_CREDENTIAL`**
密钥没保存或环境变量缺失 → 到 设置 → 模型 重新填写保存。

**Q5：模型报 `UNKNOWN_MODEL`**
当前选中的模型不在已配置列表里 → 在模型菜单重新选，或给自定义提供商补上模型 ID。

**Q6：网关地址、密钥都对，但每个请求都被拒**
多半是请求形状不兼容（自建/中转网关常见）：在 `cordis.patch.yml` 里给该路由加

```yaml
compat:
  supportsDeveloperRole: false
  maxTokensField: max_tokens
```

**Q7：`CLIENT_UPGRADE_REQUIRED`**
新模型要求更新的客户端 → 升级到提示中写明的版本（桌面端重下安装包 / `npm update -g`）。

**Q8：我该选桌面端还是 Web UI？**
只想干活 → 桌面端；要接自己的脚本、跑在服务器、或开发插件 → `npx dsh web` / 源码。

**Q9：预览版能用于生产吗？**
官方明确说明处于开发者预览，**会有破坏性变更**；关键流程请锁版本并留意升级说明。

**Q10：会把我的文件传上去吗？**
文件读写发生在本地工作区，模型只看到你实际发出去的内容与工具返回结果；权限策略触发的敏感操作会先向你申请审批。

---

## 7. 命令速查

```powershell
# 方式 B
npx @deepseek-ai/dsh web                 # 起 Web UI（默认 3080，自动开浏览器）
npx @deepseek-ai/dsh web --no-open       # 只起服务
npm install -g @deepseek-ai/dsh          # 全局安装
dsh web                                  # 全局安装后启动
dsh --profile headless "任务描述"        # 无界面跑一次
npm view @deepseek-ai/dsh version        # 看最新版本
npm update -g @deepseek-ai/dsh           # 升级
npm uninstall -g @deepseek-ai/dsh        # 卸载

# 方式 C
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web
pnpm run dev:web                         # 开发模式（改源码自动重建）

# 环境变量
$env:DSH_HOME      = "D:\dsh-home"
$env:HTTPS_PROXY   = "http://127.0.0.1:7890"
$env:HTTP_PROXY    = "http://127.0.0.1:7890"
$env:NODE_EXTRA_CA_CERTS = "C:\path\corp-ca.pem"

# npm 镜像
npm config set registry https://registry.npmmirror.com
```

---

## 8. 官方链接汇总

| 用途 | 地址 |
|---|---|
| 产品介绍 | https://www.deepseek.com/harness/ |
| 桌面端下载 | https://www.deepseek.com/download/ |
| GitHub 仓库 | https://github.com/deepseek-ai/deepseek-harness |
| 文档（含 Web UI / 模型 / 代理 / 插件） | https://deepseek-harness.github.io/deepseek-harness/ |
| DeepSeek API 密钥 | https://platform.deepseek.com/ |
| 插件市场 | https://deepseek-harness.github.io/deepseek-harness/guide/plugin-market |
| 社区插件话题 | https://github.com/topics/dsh-plugin |
| 讨论 / 反馈 | https://github.com/deepseek-ai/deepseek-harness/discussions |
