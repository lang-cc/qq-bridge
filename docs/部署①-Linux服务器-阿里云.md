# 部署①：Linux 服务器（阿里云）一键部署

目标：一台**全新的**阿里云 Ubuntu/Debian 服务器（2 核 2G 起），一条命令装完，
剩最后一步手机扫码。跑起来之后是 24 小时在线的机器人，跟你的电脑没关系。

架构：NapCat（Docker 容器）→ WebSocket 127.0.0.1:8199 → NoneBot2 服务（systemd）→ 你的模型接口

---

## 一、准备（3 分钟，在阿里云控制台做）

| 项 | 怎么做 |
|---|---|
| 服务器 | Ubuntu 22.04 / Debian 12，**2 核 2G** 起（1 核 1G 也能跑，脚本会自动加 2G swap） |
| 安全组 | 放行 **6099**（NapCat 扫码面板，来源先填 `0.0.0.0/0`，扫完码改回来）；22 端口给 SSH |
| 登录 | `ssh root@<公网IP>`（Windows 用 PowerShell 直接 ssh，或用阿里云网页终端） |

不需要预装任何东西：Python、Docker、中文字体、swap 全由脚本处理。

---

## 二、一条命令部署

**最省事：只给 4 项**（网址 / 密钥 / 模型 / 人格整段）。人格先写成文件，免得命令行转义：

```bash
cat > /root/persona.txt <<'PERSONA'
她是小柚，20 岁，在街角那家奶茶店做兼职……
（整段原样粘贴）
PERSONA

BASE_URL=https://api.deepseek.com/v1 \
API_KEY=sk-你的密钥 \
MODEL=deepseek-chat \
PERSONA_FILE=/root/persona.txt \
bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
```

如果知道机器人号 / 白名单，也可以顺手带上（不带也行，装完会自动记录 + 自动认领）：

```bash
QQ=10001 USERS=20002,20003 GROUP=123456789 CITY=杭州 \
BASE_URL=... API_KEY=... MODEL=... PERSONA_FILE=/root/persona.txt \
bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
```

参数说明：

| 变量 | 必填 | 说明 |
|---|---|---|
| `BASE_URL` `API_KEY` `MODEL` | ✅ | OpenAI 兼容接口三项 |
| `PERSONA_FILE` / `PERSONA` | ✅（人格） | 人格整段：文件路径，或直接给字符串（多行建议用文件） |
| `TICKET_FILE` | 可选 | 已经有一份 `ticket.yaml` 时直接指过去 |
| `QQ` | 可选 | 机器人号；不填就等扫码后自动写入 `config.yaml` 的 `bot_qq` |
| `USERS` `GROUP` | 可选 | 白名单；不填就装完用 `tools/claim.py --auto` 自动认领 |
| `CITY` | 可选 | 天气关怀用，留空不报天气 |
| `PNAME` `AGE` | 可选 | 人格显示名/年龄（人格走 prompt 时不重要） |
| `AT_ONLY` `HISTORY` | 可选 | 群里是否只被 @ 才回 / 上下文条数 |
| `STAGE=base` | 可选 | 只装环境不装 Docker（想用自己的协议端时） |
| `CODE_URL` | 可选 | 代码包地址（默认拉 gitee 上的 `qq-bridge-code.zip`） |

脚本做的事：加 swap → 装系统依赖 → 下载代码 → `pip install` → 装 Docker + 拉 NapCat →
生成 `ticket.yaml`（含人格）→ `autoconfig` → 装 systemd（`qqbridge` + `qqbridge-watchdog`）→ 等 `/status` 通 → 打印验收报告。
（`QQ` 给了就顺手预置 OneBot 反向 WS；没给就在扫码后跑 `scripts/link-onebot.sh` 自动配。）

---

## 三、最后一步：扫码登录（必须人工）

1. 浏览器打开 `http://<公网IP>:6099`
2. 用手机 QQ 扫机器人号的码
3. 扫码成功后，把 NapCat 接到机器人服务上（一条命令，自动配 WS + 记机器人号）：

```bash
bash /opt/qqbridge/scripts/link-onebot.sh
curl -s http://127.0.0.1:8088/status
# {"ok": true, "adapter": "onebot11", "self_id": 10001, "connected": true, "plugins": 28}
```

`connected: true` 就通了。然后**认领白名单**（此刻白名单是空的，谁发都不回，但会记日志）：

```bash
# 让客户用自己要聊天的 QQ 给机器人发一句「在吗」，然后：
cd /opt/qqbridge && .venv/bin/python tools/claim.py --auto
```

它会把刚发消息那个号写进白名单并热重载，客户再发一句就有回复了。

接着在 QQ 上验：

- `/nb` → 回 NoneBot2 版本、连接数、处理器数量（**确认跑的是框架版**）
- `ping` → 回 `pong 🏓`
- `help` → 回指令列表

> 扫完码记得把安全组的 6099 收回内网/关掉。

---

## 四、日常运维

```bash
systemctl status qqbridge            # 服务状态
systemctl restart qqbridge           # 重启机器人
journalctl -u qqbridge -n 100 -f     # 实时日志（systemd 侧）
tail -f /opt/qqbridge/logs/nonebot.log    # 框架日志
tail -f /opt/qqbridge/logs/qq-bridge.log  # 业务日志
cd /opt/qqbridge && .venv/bin/python selfcheck.py   # 12 项自检
```

升级代码（保留配置和记忆库）：

```bash
# 把新包放到任意可访问地址，或直接传上去
CODE_URL=https://.../qq-bridge-code.zip bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
```

改人格 / 换模型：改 `/opt/qqbridge/config.yaml`（模型在白名单 `autoreply.llm`）→ `systemctl restart qqbridge`；
或直接开网页配置台 `http://127.0.0.1:8088/admin`（要 SSH 端口转发：`ssh -L 8088:127.0.0.1:8088 root@<IP>`）。

---

## 五、常见问题

| 现象 | 处理 |
|---|---|
| `/status` 一直 `connected: false` | NapCat 没登录 / 没连上：`docker logs --tail 50 napcat`，重开 6099 面板扫码 |
| 扫不了码（6099 打不开） | 安全组没放行 6099，或 `docker ps` 看容器是否在跑 |
| 依赖装不上 | 脚本已用阿里云 pip 镜像；仍失败就 `curl -I https://mirrors.aliyun.com` 看网络 |
| Docker 拉不动镜像 | 脚本内置 5 个加速地址；都不行就在阿里云控制台取专属镜像加速器填进 `/etc/docker/daemon.json` |
| 机器人不回话 | 先 `curl /status`；再看 `logs/qq-bridge.log` 有没有「插件处理异常」；确认发消息的号在 `USERS` 里 |
| 想退回去跑老版（自研适配器） | `/opt/qqbridge/.venv/bin/python main.py`，并把 systemd 的 `ExecStart` 改回 `main.py` |

---

## 六、为什么是这套

- **NoneBot2** 负责连接/重连/事件分发，NapCat 只当协议端 → 掉线自动重连，不用人盯
- **systemd** 托管，服务器重启自动拉起；`watchdog` 再兜一层（服务死、NapCat 死、QQ 掉线都能自愈）
- 全部走 `127.0.0.1`，只对外开 6099 扫码端口；模型密钥只存在服务器本地 `config.yaml`
