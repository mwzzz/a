#!/usr/bin/env bash
# 在本机（Git Bash / macOS / Linux）执行：构建前端并上传到服务器。
#   默认发布到新服务器：root@116.62.242.2，密钥 ~/.ssh/_mw.pem
#   换机器：SERVER=root@1.2.3.4 SSH_KEY=/path/to/key bash deploy/push.sh
# 要求：本机能用密钥 ssh 到服务器（密码登录已禁用），服务器上已跑过一次 install.sh。
set -euo pipefail

SERVER="${SERVER:-root@116.62.242.2}"
URL_HOST="${URL_HOST:-${SERVER#*@}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 默认密钥：新服务器的 _mw.pem。原文件在 Downloads 下权限过宽，OpenSSH 会拒绝加载，
# 所以复制到 ~/.ssh 并 chmod 600（Windows 用 icacls）。
SSH_KEY="${SSH_KEY:-}"
if [ -z "$SSH_KEY" ]; then
  for candidate in "$HOME/.ssh/_mw.pem" "/c/Users/Administrator/.ssh/_mw.pem"; do
    if [ -f "$candidate" ]; then
      SSH_KEY="$candidate"
      break
    fi
  done
fi
if [ -n "$SSH_KEY" ] && [ ! -f "$SSH_KEY" ]; then
  echo "找不到密钥：$SSH_KEY" >&2
  exit 1
fi

SSH_ARGS=()
if [ -n "$SSH_KEY" ]; then
  SSH_ARGS=(-i "$SSH_KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new)
fi
ssh_run() { ssh "${SSH_ARGS[@]}" "$@"; }

echo "==> 构建前端"
(cd "$ROOT/frontend" && npm run build)

echo "==> 上传后端与部署文件"
tar -czf - -C "$ROOT" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='backend/data' \
  --exclude='backend/.env' \
  backend deploy \
  | ssh_run "$SERVER" "sudo mkdir -p /opt/lol-ledger; if [ -d /opt/lol-ledger/backend ]; then sudo mkdir -p /opt/lol-ledger/data/backups; sudo tar -czf /opt/lol-ledger/data/backups/code-\$(TZ=Asia/Shanghai date +%Y%m%d-%H%M%S).tar.gz -C /opt/lol-ledger backend deploy frontend/dist; sudo ls -1t /opt/lol-ledger/data/backups/code-*.tar.gz | tail -n +6 | xargs -r sudo rm -f; fi; sudo tar -xzf - -C /opt/lol-ledger && if id lol >/dev/null 2>&1; then sudo chown -R lol:lol /opt/lol-ledger/backend /opt/lol-ledger/deploy; sudo find /opt/lol-ledger/deploy -type f -name '*.sh' -exec chmod 755 {} +; fi"

echo "==> 上传前端静态文件"
tar -czf - -C "$ROOT/frontend" dist \
  | ssh_run "$SERVER" "sudo mkdir -p /opt/lol-ledger/frontend && sudo rm -rf /opt/lol-ledger/frontend/dist && sudo tar -xzf - -C /opt/lol-ledger/frontend && if id lol >/dev/null 2>&1; then sudo chown -R lol:lol /opt/lol-ledger/frontend; fi"

echo "==> 安装依赖并迁移数据库"
if ssh_run "$SERVER" "test -x /opt/lol-ledger/venv/bin/python"; then
  # 迁移会重建表，先停服务，避免迁移过程中还有写请求进来
  ssh_run "$SERVER" "sudo systemctl stop lol-ledger-api || true"
  ssh_run "$SERVER" "cd /opt/lol-ledger/backend && sudo -u lol /opt/lol-ledger/venv/bin/pip install -q -r requirements.txt && sudo -u lol env DB_PATH=/opt/lol-ledger/data/ledger.db /opt/lol-ledger/venv/bin/python -m app.migrations"
  ssh_run "$SERVER" "sudo cp -f /opt/lol-ledger/deploy/nginx-lol-ledger.conf /etc/nginx/conf.d/lol-ledger.conf && sudo nginx -t && sudo systemctl reload nginx"
else
  echo "服务器上还没有 venv，走首次安装（会停用原 80 官网并接管 80 端口）"
  ssh_run "$SERVER" "sudo bash /opt/lol-ledger/deploy/install.sh"
fi

echo "==> 重启服务"
ssh_run "$SERVER" "sudo systemctl restart lol-ledger-api && sleep 1 && curl -s http://127.0.0.1:8010/api/health && echo"

echo "==> 检查 80 端口"
ssh_run "$SERVER" "curl -s -o /dev/null -w '首页 HTTP %{http_code}\n' http://127.0.0.1/"

echo
echo "完成。打开 http://${URL_HOST}/"
