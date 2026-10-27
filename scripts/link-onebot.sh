#!/usr/bin/env bash
# 扫码登录之后跑这一个脚本：把 NapCat 接到机器人服务上（Linux / Docker 版）
#
#   bash /opt/qqbridge/scripts/link-onebot.sh
#
# 做的事：
#   1) 找 NapCat 登录后生成的那个 onebot11_<QQ>.json
#   2) 往里写一条「反向 WebSocket → ws://127.0.0.1:8199/onebot/v11/ws」
#   3) docker restart napcat
#   4) 等 /status 出现 connected: true
#   5) 把机器人号写进 config.yaml（bot_qq），以后静默登录
#   6) 打印下一步（认领白名单）
#
# 幂等：重复跑只会补配置、重启一次容器。

set -uo pipefail

ROOT="${ROOT:-/opt/qqbridge}"
NAPCAT_CFG="${NAPCAT_CFG:-/opt/napcat/config}"
CONTAINER="${CONTAINER:-napcat}"
WS_PORT="${WS_PORT:-8199}"
API_PORT="${API_PORT:-8088}"

c_cyan='\033[36m'; c_green='\033[32m'; c_yellow='\033[33m'; c_red='\033[31m'; c_off='\033[0m'
step() { echo -e "\n${c_cyan}==== $* ====${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }
warn() { echo -e "${c_yellow}! $*${c_off}"; }
die()  { echo -e "${c_red}✗ $*${c_off}"; exit 1; }

[ -x "$ROOT/.venv/bin/python" ] || die "找不到 $ROOT/.venv/bin/python（机器人还没装好？）"

step "1/4 找 NapCat 的账号配置"
mapfile -t files < <(ls -1 "$NAPCAT_CFG"/onebot11_*.json 2>/dev/null)
if [ "${#files[@]}" -eq 0 ]; then
  warn "还没找到 onebot11_*.json"
  echo "  说明：NapCat 是登录成功之后才生成这个文件。"
  echo "  先打开 http://<公网IP>:6099 用手机 QQ 扫码登录，然后再跑本脚本。"
  exit 1
fi
if [ "${#files[@]}" -gt 1 ]; then
  warn "找到多个账号配置，用最新的那个（想指定就设 NAPCAT_CFG=<文件>）"
fi
TARGET="${NAPCAT_CFG}/$(basename "${files[-1]}")"
ok "账号配置：$TARGET"

step "2/4 写入反向 WebSocket 指向 127.0.0.1:$WS_PORT"
"$ROOT/.venv/bin/python" - "$TARGET" "$WS_PORT" <<'PY'
import json, sys, pathlib

path = pathlib.Path(sys.argv[1])
port = int(sys.argv[2])
data = json.loads(path.read_text(encoding="utf-8") or "{}")
net = data.setdefault("network", {})
clients = net.setdefault("websocketClients", [])
url = f"ws://127.0.0.1:{port}/onebot/v11/ws"
for c in clients:
    if c.get("name") == "qq-bridge":
        c.update({"enable": True, "url": url, "messagePostFormat": "array"})
        break
else:
    clients.append({
        "name": "qq-bridge", "enable": True, "url": url,
        "reportSelfMessage": False, "messagePostFormat": "array",
        "token": "", "debug": False,
    })
net.setdefault("httpServers", [])
net.setdefault("websocketServers", [])
data.setdefault("musicSignUrl", "")
data.setdefault("enableLocalFile2Url", False)
data.setdefault("parseMultMsg", False)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("已写入", url)
PY
ok "OneBot 反向 WS 已配置"

step "3/4 重启 NapCat 并等连接"
docker restart "$CONTAINER" >/dev/null 2>&1 || warn "docker restart 失败，手动重启 NapCat 容器"
connected=""
for i in $(seq 1 24); do
  sleep 5
  s=$(curl -s --max-time 4 "http://127.0.0.1:${API_PORT}/status" || true)
  echo "  [$i] ${s:-（服务没响应）}"
  echo "$s" | grep -q '"connected":[[:space:]]*true' && { connected=1; break; }
done
if [ -z "$connected" ]; then
  warn "还没连上。排查：docker logs --tail 60 $CONTAINER；curl http://127.0.0.1:$API_PORT/status"
  exit 1
fi
ok "已连上机器人服务"

step "4/4 记录机器人号"
cd "$ROOT" || die "进不去 $ROOT"
"$ROOT/.venv/bin/python" tools/claim.py --set-qq auto 2>/dev/null | sed 's/^/  /' || \
  warn "记录机器人号失败（不影响使用，下次扫码再登也一样）"

echo ""
echo -e "${c_green}接通完成${c_off}"
echo ""
echo "最后一步：让客户用自己要聊天的 QQ 给机器人发一句话（比如「在吗」），"
echo "机器人这会儿还不会回，然后执行："
echo ""
echo "  cd $ROOT && .venv/bin/python tools/claim.py --auto"
echo ""
echo "它会把刚发消息的那个号加进白名单并热重载，客户再发一句就能聊了。"
