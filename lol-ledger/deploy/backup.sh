#!/usr/bin/env bash
# 每日备份 SQLite。WAL 模式下不能直接 cp，必须用 sqlite3 的 backup API。
set -euo pipefail

APP_DIR=/opt/lol-ledger
DB="$APP_DIR/data/ledger.db"
OUT="$APP_DIR/data/backups"
KEEP_DAYS=30

mkdir -p "$OUT"
STAMP=$(TZ=Asia/Shanghai date +%Y%m%d-%H%M%S)
TARGET="$OUT/backup-$STAMP.db"

# 通过管道传脚本，避免 systemd 环境下的 heredoc 转义问题
"$APP_DIR/venv/bin/python" - "$DB" "$TARGET" <<'PY'
import sqlite3
import sys

source_path, target_path = sys.argv[1], sys.argv[2]
source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
target = sqlite3.connect(target_path)
try:
    with target:
        source.backup(target)
    result = target.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    target.close()
    source.close()
if result != "ok":
    raise SystemExit(f"备份完整性检查失败: {result}")
PY

find "$OUT" -name 'backup-*.db' -type f -mtime +"$KEEP_DAYS" -delete
echo "备份完成：$TARGET"
