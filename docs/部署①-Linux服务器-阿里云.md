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

参数说明：

| 变量 | 必填 | 说明 |
|---|---|---|
| `QQ` | ✅ | 机器人号（小号） |
| `USERS` | ✅（或 `GROUP`） | 允许私聊的 QQ，逗号分隔 |
| `GROUP` | 可选 | 群号，逗号分隔；配合 `AT_ONLY=false` 可在群里主动插话（默认只被 @ 时回） |
| `BASE_URL` `API_KEY` `MODEL` | ✅ | OpenAI 兼容接口三项 |
| `CITY` | 可选 | 天气关怀用，留空不报天气 |
| `PNAME` `AGE` `WHO` `STYLE` `RELATION` | 可选 | 人格五件套 |
| `HISTORY` | 可选 | 上下文条数，默认 100（越大越贵） |
| `STAGE=base` | 可选 | 只装环境不装 Docker（想用自己的协议端时） |

脚本做的事：加 swap → 装系统依赖 → 下载代码 → `pip install` → 装 Docker + 拉 NapCat →
预置 OneBot 反向 WS 指向 `127.0.0.1:8199` → 生成 `config.yaml` / `data/personas.yaml` →
装 systemd 服务（`qqbridge` + `qqbridge-watchdog`）→ 等 `/status` 通 → 打印验收报告。

---

## 三、最后一步：扫码登录（必须人工）

1. 浏览器打开 `http://<公网IP>:6099`
2. 用手机 QQ 扫机器人号的码
3. 等 10 秒，验证：

```bash
curl -s http://127.0.0.1:8088/status
# {"ok": true, "adapter": "onebot11", "self_id": 10001, "connected": true, "plugins": 28}
```

`connected: true` 就通了。然后在 QQ 上给机器人发：

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
