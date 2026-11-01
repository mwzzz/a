#!/usr/bin/env bash
# 在服务器上执行：sudo bash /opt/lol-ledger/deploy/install.sh
# 前提：代码已经上传到 /opt/lol-ledger（见 push.sh），前端 dist 已上传。
set -euo pipefail

APP_DIR=/opt/lol-ledger

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行：sudo bash $0"
  exit 1
fi

# 系统自带的 python3 可能还是 3.6，跑不了 FastAPI，至少要 3.9
PY=""
for candidate in /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3.10 /usr/bin/python3.9; do
  if [ -x "$candidate" ]; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "找不到 python3.9 以上。先装一个再重跑：sudo dnf install -y python3.11"
  exit 1
fi
echo "==> 使用 $PY"

if [ ! -f "$APP_DIR/backend/requirements.txt" ]; then
  echo "没找到 $APP_DIR/backend，请先在本机执行 deploy/push.sh 上传代码。"
  exit 1
fi

id lol >/dev/null 2>&1 || useradd -r -s /sbin/nologin lol

mkdir -p "$APP_DIR/data/backups" "$APP_DIR/logs" "$APP_DIR/frontend"

echo "==> 安装 Python 依赖"
if [ ! -d "$APP_DIR/venv" ]; then
  "$PY" -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install -q -U pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"

echo "==> 生成环境变量"
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
  cat > "$APP_DIR/.env" <<EOF
JWT_SECRET=$SECRET
DB_PATH=$APP_DIR/data/ledger.db
TOKEN_TTL_HOURS=12
DEBUG=false
EOF
  echo "已生成 $APP_DIR/.env（JWT_SECRET 随机）"
else
  echo "$APP_DIR/.env 已存在，保留原密钥"
fi

echo "==> 权限"
chown -R lol:lol "$APP_DIR"
chmod 750 "$APP_DIR/data"
chown root:lol "$APP_DIR/.env"
chmod 640 "$APP_DIR/.env"
chmod +x "$APP_DIR/deploy/backup.sh" 2>/dev/null || true

echo "==> 初始化数据库"
# 迁移可能重建表，先停服务；后面 systemctl enable --now 会再起来
systemctl stop lol-ledger-api 2>/dev/null || true
cd "$APP_DIR/backend"
sudo -u lol env DB_PATH="$APP_DIR/data/ledger.db" "$APP_DIR/venv/bin/python" -m app.migrations

echo "==> 安装 systemd 服务"
cp "$APP_DIR/deploy/lol-ledger-api.service" /etc/systemd/system/
cp "$APP_DIR/deploy/lol-ledger-backup.service" /etc/systemd/system/
cp "$APP_DIR/deploy/lol-ledger-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now lol-ledger-api
systemctl enable --now lol-ledger-backup.timer

echo "==> 接管 80 端口"
NGINX_DIR=/etc/nginx/conf.d
STAMP=$(date +%Y%m%d-%H%M%S)

# 原本占用 80 的官网：只改名停用，不删文件，随时可以改回来
if [ -f "$NGINX_DIR/neizhanjizhang.conf" ]; then
  mv "$NGINX_DIR/neizhanjizhang.conf" "$NGINX_DIR/neizhanjizhang.conf.disabled-$STAMP"
  echo "已停用 80 端口官网：neizhanjizhang.conf → neizhanjizhang.conf.disabled-$STAMP"
fi

# 默认站也听 80 的话会抢走 IP 访问，同样让位
if [ -f "$NGINX_DIR/default.conf" ] && grep -qE '^[[:space:]]*listen[[:space:]]+(\[::\]:)?80' "$NGINX_DIR/default.conf"; then
  mv "$NGINX_DIR/default.conf" "$NGINX_DIR/default.conf.disabled-$STAMP"
  echo "已停用 nginx 默认站：default.conf → default.conf.disabled-$STAMP"
fi

if [ -f "$NGINX_DIR/lol-ledger.conf" ]; then
  cp "$NGINX_DIR/lol-ledger.conf" "$NGINX_DIR/lol-ledger.conf.bak-$STAMP"
  echo "已备份旧配置：lol-ledger.conf.bak-$STAMP"
fi
cp "$APP_DIR/deploy/nginx-lol-ledger.conf" "$NGINX_DIR/lol-ledger.conf"

# nginx.conf 里自带的默认站（root /usr/share/nginx/html）会和我们的 server_name _ 重名，
# 这里整块注释掉并留备份，避免 80 端口到底由谁响应的歧义。
"$PY" - <<'PY' || true
from pathlib import Path
import shutil
import time

path = Path("/etc/nginx/nginx.conf")
text = path.read_text(encoding="utf-8")
if "/usr/share/nginx/html" not in text:
    print("nginx.conf 没有内置默认站，跳过")
    raise SystemExit(0)

lines = text.splitlines(keepends=True)
start = None
for i, line in enumerate(lines):
    if "root" in line and "/usr/share/nginx/html" in line:
        for j in range(i, -1, -1):
            if lines[j].strip().startswith("server") and "{" in lines[j]:
                start = j
                break
        break
if start is None:
    print("没定位到默认站的 server 块，跳过")
    raise SystemExit(0)

depth = 0
end = None
started = False
for i in range(start, len(lines)):
    depth += lines[i].count("{") - lines[i].count("}")
    if "{" in lines[i]:
        started = True
    if started and depth <= 0:
        end = i
        break
if end is None:
    print("没定位到默认站结尾，跳过")
    raise SystemExit(0)

backup = path.with_name(f"nginx.conf.bak-{time.strftime('%Y%m%d-%H%M%S')}")
shutil.copy2(path, backup)
for i in range(start, end + 1):
    if lines[i].strip():
        lines[i] = "# " + lines[i]
path.write_text("".join(lines), encoding="utf-8")
print(f"已注释 nginx 内置默认站（第 {start + 1}-{end + 1} 行），备份 {backup.name}")
PY

nginx -t
systemctl reload nginx

sleep 1
echo "==> 自检"
curl -s http://127.0.0.1:8010/api/health || true
echo
if curl -fsS --max-time 5 http://127.0.0.1/ | grep -q 'LOL 记录管理'; then
  echo "80 端口已指向本系统"
else
  echo "警告：80 端口返回的不是本系统首页，检查 /etc/nginx/conf.d/ 里还有没有别的站占用 80"
fi
systemctl is-active lol-ledger-api

cat <<'EOF'

完成。还需要两步：
  1) 建商家和管理员（首次自带「默认商家」，可以直接改名或另开）：
       cd /opt/lol-ledger/backend
       lg() { sudo -u lol env DB_PATH=/opt/lol-ledger/data/ledger.db /opt/lol-ledger/venv/bin/python "$@"; }
       lg -m app.cli create-merchant --name "极光电竞"
       lg -m app.cli create-admin --username jg-boss --merchant "极光电竞"
  2) 浏览器打开 http://<服务器IP>/（就是原来的 80 端口，安全组本来就放行）

要恢复原来的官网：
  sudo mv /etc/nginx/conf.d/neizhanjizhang.conf.disabled-<时间戳> /etc/nginx/conf.d/neizhanjizhang.conf
  sudo mv /etc/nginx/conf.d/lol-ledger.conf /etc/nginx/conf.d/lol-ledger.conf.off
  sudo systemctl reload nginx
EOF
