#!/usr/bin/env bash
# 在本机（Git Bash）执行，构建前端并上传到服务器。
#   SERVER=admin@47.95.146.168 bash deploy/push.sh
# 要求：本机能 ssh 到服务器（密钥登录），服务器上已跑过一次 install.sh。
set -euo pipefail

SERVER="${SERVER:-admin@47.95.146.168}"
URL_HOST="${URL_HOST:-${SERVER#*@}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 构建前端"
(cd "$ROOT/frontend" && npm run build)

echo "==> 上传后端与部署文件"
tar -czf - -C "$ROOT" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='backend/data' \
  --exclude='backend/.env' \
  backend deploy \
  | ssh "$SERVER" "sudo mkdir -p /opt/lol-ledger && sudo tar -xzf - -C /opt/lol-ledger && if id lol >/dev/null 2>&1; then sudo chown -R lol:lol /opt/lol-ledger/backend /opt/lol-ledger/deploy; fi"

echo "==> 上传前端静态文件"
tar -czf - -C "$ROOT/frontend" dist \
  | ssh "$SERVER" "sudo mkdir -p /opt/lol-ledger/frontend && sudo rm -rf /opt/lol-ledger/frontend/dist && sudo tar -xzf - -C /opt/lol-ledger/frontend && if id lol >/dev/null 2>&1; then sudo chown -R lol:lol /opt/lol-ledger/frontend; fi"

echo "==> 安装依赖并迁移数据库"
if ssh "$SERVER" "test -x /opt/lol-ledger/venv/bin/python"; then
  # 迁移会重建表，先停服务，避免迁移过程中还有写请求进来
  ssh "$SERVER" "sudo systemctl stop lol-ledger-api || true"
  ssh "$SERVER" "cd /opt/lol-ledger/backend && sudo -u lol /opt/lol-ledger/venv/bin/pip install -q -r requirements.txt && sudo -u lol env DB_PATH=/opt/lol-ledger/data/ledger.db /opt/lol-ledger/venv/bin/python -m app.migrations"
  ssh "$SERVER" "sudo cp -f /opt/lol-ledger/deploy/nginx-lol-ledger.conf /etc/nginx/conf.d/lol-ledger.conf && sudo nginx -t && sudo systemctl reload nginx"
else
  echo "服务器上还没有 venv，走首次安装（会停用原 80 官网并接管 80 端口）"
  ssh "$SERVER" "sudo bash /opt/lol-ledger/deploy/install.sh"
fi

echo "==> 重启服务"
ssh "$SERVER" "sudo systemctl restart lol-ledger-api && sleep 1 && curl -s http://127.0.0.1:8010/api/health && echo"

echo "==> 检查 80 端口"
ssh "$SERVER" "curl -s -o /dev/null -w '首页 HTTP %{http_code}\n' http://127.0.0.1/"

echo
echo "完成。打开 http://${URL_HOST}/"
