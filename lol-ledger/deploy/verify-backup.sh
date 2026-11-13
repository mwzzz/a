#!/usr/bin/env bash
# 在服务器上执行：sudo bash /opt/lol-ledger/deploy/verify-backup.sh
#
# 作用：拿最近一次自动备份，验证它「真的能恢复」——
#   1) 备份文件年龄与大小
#   2) integrity_check / foreign_key_check / schema 版本
#   3) 与生产库的关键指标对比（玩家数、押金总额、流水数、分红结算数）
#   4) 用备份在 8011 端口起一个临时实例，打 /api/health 和未登录接口
#
# 全程不碰生产库（只读对比），不占用 8010，跑完自动清理临时文件。
set -uo pipefail

APP=/opt/lol-ledger
BK="$APP/data/backups"
PORT=8011
WORK=$(mktemp -d /tmp/restore-test-XXXXXX)
FAIL=0

cleanup() {
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${PORT}" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

LATEST=$(ls -t "$BK"/backup-*.db 2>/dev/null | head -1 || true)
if [ -z "$LATEST" ]; then
  echo "!! 没有找到 backup-*.db，定时备份可能没在跑"
  echo "   systemctl status lol-ledger-backup.timer"
  exit 1
fi

SIZE=$(stat -c%s "$LATEST")
AGE_H=$(( ( $(date +%s) - $(stat -c%Y "$LATEST") ) / 3600 ))
echo "== 备份文件 =="
echo "路径：$LATEST"
echo "大小：$(( SIZE / 1024 )) KB    距今：${AGE_H} 小时"
[ "$SIZE" -gt 10240 ] || { echo "!! 文件过小，可能损坏"; FAIL=1; }
[ "$AGE_H" -le 48 ] || echo "   （提醒：超过 48 小时没新备份）"

cp "$LATEST" "$WORK/restore.db"
chown lol:lol "$WORK" "$WORK/restore.db"
chmod 600 "$WORK/restore.db"

echo
echo "== 完整性 =="
INTEGRITY=$(sqlite3 "$WORK/restore.db" "PRAGMA integrity_check;")
FK=$(sqlite3 "$WORK/restore.db" "PRAGMA foreign_key_check;" | wc -l)
VER=$(sqlite3 "$WORK/restore.db" "PRAGMA user_version;")
echo "integrity_check: $INTEGRITY"
echo "foreign_key_check 异常行数: $FK"
echo "schema 版本: $VER"
[ "$INTEGRITY" = "ok" ] || FAIL=1
[ "$FK" -eq 0 ] || FAIL=1

Q="select (select count(*) from players) || '|' || (select coalesce(sum(deposit_cents),0) from players) || '|' || (select count(*) from ledger) || '|' || (select count(*) from dividend_settlements) || '|' || (select count(*) from batches)"
PROD=$(sudo -u lol sqlite3 "$APP/data/ledger.db" "$Q")
REST=$(sudo -u lol sqlite3 "$WORK/restore.db" "$Q")
echo
echo "== 与生产库对比（玩家数|押金总额|流水数|分红结算数|班次数）=="
echo "生产：$PROD"
echo "备份：$REST"
if [ "$PROD" != "$REST" ]; then
  echo "   注意：数值不同属正常（备份是过去某个时刻），只要备份内部自洽即可"
fi

echo
echo "== 临时实例冒烟（127.0.0.1:${PORT}）=="
sudo -u lol env DB_PATH="$WORK/restore.db" "$APP/venv/bin/python" -m uvicorn app.main:app \
  --app-dir "$APP/backend" --host 127.0.0.1 --port "$PORT" --workers 1 --no-access-log >"$WORK/api.log" 2>&1 &
for _ in $(seq 1 20); do
  sleep 1
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then break; fi
done
HEALTH=$(curl -s --max-time 5 "http://127.0.0.1:${PORT}/api/health" || echo "no-response")
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/api/v1/players") || CODE="000"
echo "health: $HEALTH"
echo "未登录访问 /players: HTTP $CODE（应为 401）"
echo "$HEALTH" | grep -q '"ok":true' || FAIL=1
[ "$CODE" = "401" ] || FAIL=1

if [ "$FAIL" -eq 1 ]; then
  echo
  echo "!! 备份验证未通过"
  echo "--- 临时实例日志（最后 20 行）---"
  tail -20 "$WORK/api.log" 2>/dev/null || echo "(没有日志)"
  exit 1
fi

echo
echo "== 结论：备份可用（能起服务、数据自洽、鉴权正常）=="
