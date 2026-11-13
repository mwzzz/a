#!/usr/bin/env bash
# 在服务器上执行：sudo bash /opt/lol-ledger/deploy/rollback.sh
#
#   sudo bash deploy/rollback.sh --list            看有哪些版本可回滚
#   sudo bash deploy/rollback.sh code-20261105-101530
#
# 每次 push 前，部署脚本都会把「当前代码 + deploy + 前端 dist」打包成
# /opt/lol-ledger/data/backups/code-<时间>.tar.gz，保留最近 5 份。
#
# 只回滚代码；如果这次发布改过数据库结构，必须同时用迁移前备份还原数据库，
# 否则旧代码读不了新库（脚本末尾会提示要用哪个文件）。
set -euo pipefail

APP=/opt/lol-ledger
BK="$APP/data/backups"
DB="$APP/data/ledger.db"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行：sudo bash $0 $*"
  exit 1
fi

if [ "${1:-}" = "--list" ] || [ -z "${1:-}" ]; then
  echo "== 可回滚的代码版本（新 → 旧）=="
  if ls -1t "$BK"/code-*.tar.gz >/dev/null 2>&1; then
    for f in $(ls -1t "$BK"/code-*.tar.gz); do
      printf "  %-34s %s\n" "$(basename "$f")" "$(du -h "$f" | cut -f1)"
    done
  else
    echo "  （暂无，下一次发布时会自动生成）"
  fi
  echo
  echo "== 最近的数据库备份 =="
  ls -1t "$BK"/*.db 2>/dev/null | head -6 | while read -r f; do
    printf "  %-34s %s\n" "$(basename "$f")" "$(du -h "$f" | cut -f1)"
  done
  echo
  echo "用法：sudo bash $0 code-20261105-101530"
  exit 0
fi

TARGET="$1"
FILE="$BK/$TARGET"
[ -f "$FILE" ] || FILE="$TARGET"
if [ ! -f "$FILE" ]; then
  echo "找不到版本包：$TARGET"
  echo "用 --list 看看有哪些"
  exit 1
fi

CUR_VER=$(sqlite3 "$DB" "PRAGMA user_version;" 2>/dev/null || echo "?")
echo "当前数据库 schema：$CUR_VER"

echo "== 停止服务 =="
systemctl stop lol-ledger-api || true

echo "== 还原代码：$(basename "$FILE") =="
tar -xzf "$FILE" -C "$APP"

echo "== 修正权限 =="
chown -R lol:lol "$APP/backend" "$APP/deploy"
[ -d "$APP/frontend/dist" ] && chown -R lol:lol "$APP/frontend"
find "$APP/backend" -type f -exec chmod 644 {} +
find "$APP/deploy" -type d -exec chmod 755 {} +
find "$APP/deploy" -type f ! -name '*.sh' -exec chmod 644 {} +
find "$APP/deploy" -type f -name '*.sh' -exec chmod 755 {} +

echo "== 启动服务 =="
systemctl start lol-ledger-api
sleep 2
systemctl is-active lol-ledger-api
curl -s http://127.0.0.1:8010/api/health || true
echo

cat <<EOF

== 回滚完成 ==
如果这次发布改过数据库结构（schema 从 $CUR_VER 变过），旧代码可能读不了新库，
需要同时还原迁移前的数据库备份：

  sudo systemctl stop lol-ledger-api
  sudo -u lol cp $BK/<pre-vN-时间戳>.db $DB
  sudo rm -f $DB-wal $DB-shm
  sudo systemctl start lol-ledger-api

界面还是新版？前端 dist 已随代码一起还原，浏览器强制刷新一次（Ctrl+F5）即可。
EOF
