#!/usr/bin/env bash
# qq-bridge · Linux 服务器一键部署（Ubuntu 22.04 / Debian 12，低内存友好）
#
# 第一次（只装环境 + NapCat，不起机器人）：
#   curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh | STAGE=docker bash
#
# 填好工单后再跑一次（写配置 + 起服务）：
#   curl -fsSL https://gitee.com/wangcc111/qq-bridge-dist/raw/main/deploy-linux.sh | bash

set -uo pipefail

ROOT=/opt/qqbridge
PKG_URL="https://gitee.com/wangcc111/qq-bridge-dist/releases/download/v1.0/qq-bridge-full.zip"
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

# ---------- 0. swap（低内存机器必须） ----------
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
echo "内存：${mem_mb}MB"
if [ "$mem_mb" -lt 3000 ] && ! swapon --show | grep -q .; then
  step "0/7 加 ${SWAP_GB}G 虚拟内存（内存太小，必须）"
  fallocate -l "${SWAP_GB}G" /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB*1024)) status=none
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -qw vm.swappiness=10
  grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
  ok "swap 已启用：$(swapon --show=size --noheadings | tr -d ' ')"
else
  ok "内存/swap 够用，跳过"
fi

# ---------- 1. 系统依赖 ----------
step "1/7 安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip unzip curl ca-certificates fonts-noto-cjk >/dev/null
ok "依赖就绪（含中文字体）"

# ---------- 2. 代码 ----------
step "2/7 下载并解压代码（34MB）"
mkdir -p /opt
tmp=$(mktemp -d)
curl -fsSL --retry 3 --max-time 900 -o "$tmp/pkg.zip" "$PKG_URL" || die "下载失败（检查能否访问 gitee.com）"
unzip -q "$tmp/pkg.zip" -d "$tmp/x" || die "解压失败"
inner=$(find "$tmp/x" -maxdepth 1 -mindepth 1 -type d | head -1)
if [ -d "$ROOT" ]; then
  warn "已存在 $ROOT：只覆盖代码，保留 config / data / logs"
  for d in qqbot docs scripts tools tests; do
    [ -d "$inner/$d" ] && cp -r "$inner/$d" "$ROOT/"
  done
  find "$inner" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.yaml' \) -exec cp {} "$ROOT/" \;
else
  mv "$inner" "$ROOT"
fi
rm -rf "$tmp"
cd "$ROOT" || die "进不去 $ROOT"
mkdir -p data logs stickers tmp
ok "代码在 $ROOT"

# ---------- 3. Python ----------
step "3/7 建 Python 环境"
[ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv" || die "venv 创建失败"
"$ROOT/.venv/bin/pip" install -q --upgrade pip -i "$PIP_MIRROR"
"$ROOT/.venv/bin/pip" install -q -r requirements.txt -i "$PIP_MIRROR" || die "依赖安装失败"
ok "Python 依赖就绪（$(.venv/bin/python -V 2>&1)）"

# ---------- 4. Docker ----------
if [ "$STAGE" = "base" ]; then
  ok "基础环境完成（STAGE=base 到此为止）"; exit 0
fi

step "4/7 准备 Docker"
if ! command -v docker >/dev/null 2>&1; then
  warn "没装 Docker，开始安装（1-2 分钟）"
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
step "5/7 拉取 NapCat 镜像并启动"
IMAGE=""
for candidate in \
  "mlikiowa/napcat-docker:latest" \
  "docker.m.daocloud.io/mlikiowa/napcat-docker:latest" \
  "docker.1ms.run/mlikiowa/napcat-docker:latest" \
  "dockerhub.icu/mlikiowa/napcat-docker:latest" \
  "docker.rainbond.cc/mlikiowa/napcat-docker:latest"
do
  echo "  尝试 $candidate"
  if timeout 300 docker pull "$candidate" >/dev/null 2>&1; then IMAGE="$candidate"; break; fi
done
[ -n "$IMAGE" ] || die "镜像全拉失败。请在阿里云控制台→容器镜像服务→镜像加速器 取专属地址，填进 /etc/docker/daemon.json 后重跑"
docker tag "$IMAGE" napcat:local >/dev/null 2>&1 || true
ok "镜像就绪：$IMAGE"

mkdir -p /opt/napcat/config /opt/napcat/qq
docker rm -f napcat >/dev/null 2>&1 || true
docker run -d --name napcat --restart unless-stopped --network host \
  -e NAPCAT_UID=0 -e NAPCAT_GID=0 -e TZ=Asia/Shanghai \
  -v /opt/napcat/config:/app/napcat/config \
  -v /opt/napcat/qq:/app/.config/QQ \
  napcat:local >/dev/null || die "容器启动失败"
sleep 10
docker ps --filter name=napcat --format '  {{.Names}} {{.Status}} {{.Image}}'
ok "NapCat 已启动"

# ---------- 6. 配置（有工单才做） ----------
step "6/7 生成机器人配置"
if [ ! -f "$ROOT/ticket.yaml" ]; then
  warn "没有 ticket.yaml，跳过配置"
  echo ""
  echo -e "${c_yellow}接下来：${c_off}"
  echo "  1. 防火墙放行 6099（来源填你自己的IP）"
  echo "  2. 浏览器打开 http://<公网IP>:6099 → 手机 QQ 扫码登录"
  echo "  3. 进【网络配置】新建【WebSocket 客户端】：ws://127.0.0.1:8199/onebot/v11/ws"
  echo "  4. 把客户信息给我，生成 ticket.yaml 后再跑一次本脚本"
  exit 0
fi
"$ROOT/.venv/bin/python" autoconfig.py --ticket ticket.yaml || die "配置生成失败"
ok "配置已生成"

# ---------- 7. 启动 ----------
step "7/7 启动机器人服务"
pkill -f "qqbridge/main.py" 2>/dev/null || pkill -f "main.py" 2>/dev/null || true
sleep 2
nohup "$ROOT/.venv/bin/python" main.py >> "$ROOT/logs/qq-bridge.log" 2>&1 &
echo $! > "$ROOT/qqbridge.pid"
sleep 8
.venv/bin/python - <<'PY'
import json, urllib.request
try:
    d = json.loads(urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=8).read().decode())
    print("  服务：connected =", d.get("connected"), "| self_id =", d.get("self_id"))
except Exception as e:
    print("  状态接口还没起来：", e)
PY
ok "已启动"
echo ""
echo "查日志：tail -f $ROOT/logs/qq-bridge.log"
echo "重启：kill \$(cat $ROOT/qqbridge.pid); cd $ROOT && nohup .venv/bin/python main.py >> logs/qq-bridge.log 2>&1 &"
