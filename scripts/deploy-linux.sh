#!/usr/bin/env bash
# qq-bridge · Linux 一键部署（Ubuntu/Debian，低内存友好，全自动）
#
# 全自动（一次跑完，只剩扫码）：
#   QQ=机器人QQ GROUP=群号 CITY=西安 BASE_URL=... API_KEY=... MODEL=... \
#     PNAME=小念 AGE=20 WHO="..." STYLE="..." RELATION="..." \
#     bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
#
# 只装环境与 NapCat：
#   STAGE=docker bash <(curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh)
#
# 可选变量：
#   USERS=123,456      私聊白名单（逗号分隔）
#   AT_ONLY=false      群里不用@也回（默认 true）
#   HISTORY=60         上下文条数（默认 100）

set -uo pipefail

ROOT=/opt/qqbridge
CODE_URL="${CODE_URL:-https://gitee.com/wangcc111/qq-bridge-dist/raw/main/qq-bridge-code.zip}"
PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
STAGE="${STAGE:-all}"
SWAP_GB="${SWAP_GB:-2}"

c_cyan='\033[36m'; c_green='\033[32m'; c_yellow='\033[33m'; c_red='\033[31m'; c_off='\033[0m'
step() { echo -e "\n${c_cyan}==== $* ====${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }
warn() { echo -e "${c_yellow}! $*${c_off}"; }
die()  { echo -e "${c_red}✗ $*${c_off}"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 运行"
. /etc/os-release 2>/dev/null || true
echo "系统：${PRETTY_NAME:-unknown}"

# ---------- 0. swap ----------
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
echo "内存：${mem_mb}MB"
if [ "$mem_mb" -lt 3000 ] && ! swapon --show | grep -q .; then
  step "0/7 加 ${SWAP_GB}G 虚拟内存（低内存机器必须）"
  fallocate -l "${SWAP_GB}G" /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB*1024)) status=none
  chmod 600 /swapfile; mkswap /swapfile >/dev/null; swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -qw vm.swappiness=10
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
  ok "swap 已启用"
else
  ok "内存/swap 够用"
fi

# ---------- 1. 依赖 ----------
step "1/7 安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip unzip curl ca-certificates fonts-noto-cjk >/dev/null
ok "依赖就绪（含中文字体）"

# ---------- 2. 代码 ----------
step "2/7 下载并解压代码（250KB）"
mkdir -p /opt
tmp=$(mktemp -d)
curl -fsSL --retry 3 --max-time 300 -o "$tmp/code.zip" "$CODE_URL" || die "代码下载失败（检查 gitee.com 可达性）"
unzip -q "$tmp/code.zip" -d "$tmp/x" || die "解压失败"
inner=$(find "$tmp/x" -maxdepth 1 -mindepth 1 -type d | head -1)
if [ -d "$ROOT" ]; then
  warn "已存在 $ROOT：只覆盖代码，保留 config / data / logs / ticket"
  for d in nb qqbot docs scripts tools tests static assets; do
    [ -d "$inner/$d" ] && { mkdir -p "$ROOT/$d"; cp -r "$inner/$d/." "$ROOT/$d/"; }
  done
  find "$inner" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.yaml' \
    -o -name '*.txt' -o -name '*.example' -o -name '*.bat' -o -name '*.ps1' -o -name '*.vbs' \) \
    -exec cp {} "$ROOT/" \;
else
  mv "$inner" "$ROOT"
fi
rm -rf "$tmp"
cd "$ROOT" || die "进不去 $ROOT"
mkdir -p data logs stickers tmp
ok "代码在 $ROOT（含 nb/ 框架层）"

# ---------- 3. Python ----------
step "3/7 建 Python 环境"
[ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv" || die "venv 创建失败"
"$ROOT/.venv/bin/pip" install -q --upgrade pip -i "$PIP_MIRROR"
"$ROOT/.venv/bin/pip" install -q -r requirements.txt -i "$PIP_MIRROR" || die "依赖安装失败"
ok "Python 依赖就绪"

[ "$STAGE" = "base" ] && { ok "基础环境完成（STAGE=base）"; exit 0; }

# ---------- 4. Docker ----------
step "4/7 准备 Docker"
if ! command -v docker >/dev/null 2>&1; then
  warn "没装 Docker，开始安装"
  curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun >/dev/null 2>&1
  command -v docker >/dev/null 2>&1 || apt-get install -y -qq docker.io >/dev/null
fi
command -v docker >/dev/null 2>&1 || die "Docker 安装失败"
systemctl enable --now docker >/dev/null 2>&1 || true
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,)"

mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://dockerhub.icu",
    "https://docker.rainbond.cc"
  ],
  "log-driver": "json-file",
  "log-opts": {"max-size": "20m", "max-file": "3"}
}
JSON
systemctl restart docker >/dev/null 2>&1 || true
sleep 3

# ---------- 5. NapCat ----------
step "5/7 拉取 NapCat 镜像并准备配置"
IMAGE=""
for candidate in \
  "mlikiowa/napcat-docker:latest" \
  "docker.m.daocloud.io/mlikiowa/napcat-docker:latest" \
  "docker.1ms.run/mlikiowa/napcat-docker:latest" \
  "dockerhub.icu/mlikiowa/napcat-docker:latest" \
  "docker.rainbond.cc/mlikiowa/napcat-docker:latest"
do
  echo "  尝试 $candidate"
  if timeout 420 docker pull "$candidate" >/dev/null 2>&1; then IMAGE="$candidate"; break; fi
done
[ -n "$IMAGE" ] || die "镜像全拉失败。阿里云控制台→容器镜像服务→镜像加速器 取专属地址填进 /etc/docker/daemon.json 后重跑"
docker tag "$IMAGE" napcat:local >/dev/null 2>&1 || true
ok "镜像就绪：$IMAGE"

mkdir -p /opt/napcat/config /opt/napcat/qq

# 预置 OneBot 反向 WS 配置：扫码登录后自动连上机器人服务，不用手动点面板
if [ -n "${QQ:-}" ]; then
  OB="/opt/napcat/config/onebot11_${QQ}.json"
  if [ ! -f "$OB" ]; then
    cat > "$OB" <<JSON
{
  "network": {
    "httpServers": [],
    "httpSseServers": [],
    "httpClients": [],
    "websocketServers": [],
    "websocketClients": [
      {
        "name": "qq-bridge",
        "enable": true,
        "url": "ws://127.0.0.1:8199/onebot/v11/ws",
        "reportSelfMessage": false,
        "messagePostFormat": "array",
        "token": "",
        "debug": false
      }
    ],
    "plugins": []
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": false,
  "parseMultMsg": false
}
JSON
    ok "已预置 OneBot 连接配置（登录后自动连）"
  else
    ok "OneBot 配置已存在，保留"
  fi
fi

docker rm -f napcat >/dev/null 2>&1 || true
docker run -d --name napcat --restart unless-stopped --network host \
  -e NAPCAT_UID=0 -e NAPCAT_GID=0 -e TZ=Asia/Shanghai \
  -v /opt/napcat/config:/app/napcat/config \
  -v /opt/napcat/qq:/app/.config/QQ \
  napcat:local >/dev/null || die "容器启动失败"
sleep 10
docker ps --filter name=napcat --format '  {{.Names}} {{.Status}}'
ok "NapCat 已启动（面板 http://<公网IP>:6099）"

# ---------- 6. 配置 ----------
step "6/7 生成机器人配置"
# 两种输入都支持：
#   A. 只有 4 项：BASE_URL / API_KEY / MODEL / PERSONA（人格整段文字，可多行）
#   B. 再加 QQ / USERS / GROUP / CITY（知道就填，不知道留空，装完能自动认领）
if [ -n "${TICKET_FILE:-}" ] && [ -f "$TICKET_FILE" ]; then
  cp "$TICKET_FILE" "$ROOT/ticket.yaml"
  ok "使用已有工单：$TICKET_FILE"
elif [ -n "${BASE_URL:-}${API_KEY:-}${MODEL:-}${PERSONA:-}${PERSONA_FILE:-}" ]; then
  ROOT="$ROOT" "$ROOT/.venv/bin/python" - <<'PY'
import os, pathlib, yaml

def split(v):
    return [x.strip() for x in (v or "").replace("，", ",").split(",") if x.strip()]

root = pathlib.Path(os.environ["ROOT"])
persona_text = os.environ.get("PERSONA", "")
pf = os.environ.get("PERSONA_FILE", "")
if not persona_text and pf and pathlib.Path(pf).exists():
    persona_text = pathlib.Path(pf).read_text(encoding="utf-8")

ticket = {
    "api": {
        "base_url": os.environ.get("BASE_URL", "").strip(),
        "api_key": os.environ.get("API_KEY", "").strip(),
        "model": os.environ.get("MODEL", "").strip(),
    },
    "persona": {
        "name": os.environ.get("PNAME", "") or "小柚",
        "age": int(os.environ.get("AGE") or 20),
    },
}
if os.environ.get("QQ"):
    ticket["robot"] = {"qq": os.environ["QQ"].strip()}
users, groups = split(os.environ.get("USERS")), split(os.environ.get("GROUP"))
if users or groups:
    ticket["allow"] = {"users": users, "groups": groups}
if os.environ.get("CITY"):
    ticket["city"] = os.environ["CITY"].strip()
if persona_text.strip():
    ticket["persona"]["prompt"] = persona_text.strip()
root.mkdir(parents=True, exist_ok=True)
(root / "ticket.yaml").write_text(
    yaml.safe_dump(ticket, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("已生成 ticket.yaml")
PY
  ok "已生成 ticket.yaml（含人格 ${PERSONA:+文本}${PERSONA_FILE:+文件}）"
elif [ -f "$ROOT/ticket.yaml" ]; then
  ok "使用已有 ticket.yaml"
else
  warn "没有配置，跳过（环境与 NapCat 已装好）"
  echo "  下一步：填好 ticket.yaml 或带 BASE_URL/API_KEY/MODEL/PERSONA 重跑本脚本"
  exit 0
fi

"$ROOT/.venv/bin/python" autoconfig.py --ticket ticket.yaml || die "配置生成失败"


# ---------- 7. 启动（systemd 托管，避免多实例抢端口） ----------
step "7/7 用 systemd 启动机器人服务"
cat > /etc/systemd/system/qqbridge.service <<UNIT
[Unit]
Description=qq-bridge QQ bot
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=TMPDIR=$ROOT/tmp
ExecStart=$ROOT/.venv/bin/python main_nb.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
StandardOutput=append:$ROOT/logs/qq-bridge.log
StandardError=append:$ROOT/logs/qq-bridge.log

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/qqbridge-watchdog.service <<UNIT
[Unit]
Description=qq-bridge watchdog
After=qqbridge.service docker.service
Wants=qqbridge.service

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python scripts/watch_linux.py
Restart=always
RestartSec=15
StandardOutput=append:$ROOT/logs/watchdog.log
StandardError=append:$ROOT/logs/watchdog.log

[Install]
WantedBy=multi-user.target
UNIT
mkdir -p "$ROOT/tmp"
pkill -9 -f "main_nb.py" 2>/dev/null || true
pkill -9 -f "main\.py" 2>/dev/null || true
sleep 2
systemctl daemon-reload
systemctl enable --now qqbridge qqbridge-watchdog
systemctl restart qqbridge
sleep 12
"$ROOT/.venv/bin/python" - <<'PY'
import json, urllib.request
try:
    d = json.loads(urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=8).read().decode())
    print("  服务在跑：connected =", d.get("connected"), "| self_id =", d.get("self_id"))
except Exception as e:
    print("  状态接口还没起来：", e)
PY

echo ""
echo -e "${c_cyan}==============================================${c_off}"
echo -e "${c_green}部署完成${c_off}"
echo ""
echo "剩下两步都要人工（顺序别换）："
echo "  1) 安全组放行 6099（来源先填 0.0.0.0/0，扫完码改回自己的 IP）"
echo "  2) 浏览器打开 http://<公网IP>:6099 ，用手机 QQ 扫码登录机器人号"
echo ""
if [ -n "${QQ:-}" ]; then
  echo "  OneBot 连接已按 QQ=$QQ 预置，扫码后会自动连上："
  echo "     curl -s http://127.0.0.1:8088/status   →   \"connected\": true"
else
  echo "  扫完码再跑这一条，把 NapCat 接到机器人服务上（自动配 WS + 等连接 + 记机器人号）："
  echo "     bash $ROOT/scripts/link-onebot.sh"
fi
echo ""
echo "最后认领白名单：让客户用自己要聊天的 QQ 给机器人发一句「在吗」（这时还不回），然后执行："
echo "     cd $ROOT && .venv/bin/python tools/claim.py --auto"
echo "  它会把发消息的号加进白名单并热重载，客户再发一句就能聊。"
echo ""
echo "日志：tail -f $ROOT/logs/qq-bridge.log"
echo -e "${c_cyan}==============================================${c_off}"
