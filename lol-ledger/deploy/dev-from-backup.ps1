<#
  用「生产数据副本」在本地起开发环境，避免拿空库测出假结果。

  用法：
    powershell -ExecutionPolicy Bypass -File deploy/dev-from-backup.ps1
        只准备数据 + 打印启动命令

    powershell -ExecutionPolicy Bypass -File deploy/dev-from-backup.ps1 -Run
        准备数据后直接前台启动后端（Ctrl+C 停止），另开窗口跑 npm run dev

    powershell ... -File deploy/dev-from-backup.ps1 -Backup C:\path\backup-xxx.db

  数据来源：%USERPROFILE%\lol-backups（deploy/pull-backup.ps1 每天拉）。
  副本落在 backend\data\prod-copy.db，不会碰生产库。
#>
param(
    [string]$Backup = "",
    [switch]$Run
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "backend\data\prod-copy.db"
$py = Join-Path $root ".venv\Scripts\python.exe"

if ($Backup) {
    if (-not (Test-Path -LiteralPath $Backup)) { throw "找不到备份：$Backup" }
} else {
    $dir = Join-Path $env:USERPROFILE "lol-backups"
    if (-not (Test-Path -LiteralPath $dir)) {
        throw "本机还没有备份目录，先跑：powershell -File deploy/pull-backup.ps1"
    }
    $latest = Get-ChildItem -LiteralPath $dir -Filter "backup-*.db" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { throw "$dir 里没有 backup-*.db，先跑 deploy/pull-backup.ps1" }
    $Backup = $latest.FullName
}

# 文件头校验
$fs = [IO.File]::OpenRead($Backup)
try {
    $buf = New-Object byte[] 16
    $read = $fs.Read($buf, 0, 16)
} finally { $fs.Close() }
if ($read -ne 16 -or [Text.Encoding]::ASCII.GetString($buf, 0, 16) -ne "SQLite format 3`0") {
    throw "不是有效的 SQLite 文件：$Backup"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
Copy-Item -LiteralPath $Backup -Destination $dest -Force
$size = [math]::Round((Get-Item -LiteralPath $dest).Length / 1KB)
$age = [math]::Round(((Get-Date) - (Get-Item -LiteralPath $Backup).LastWriteTime).TotalHours, 1)
Write-Host "已准备副本：$dest（$size KB，备份时间距今 $age 小时）" -ForegroundColor Cyan

if (Test-Path -LiteralPath $py) {
    $tmpPy = Join-Path $env:TEMP ("lol-stat-" + [Guid]::NewGuid().ToString("N") + ".py")
    @'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    print("schema  ", conn.execute("PRAGMA user_version").fetchone()[0])
    print("商家    ", conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0])
    print("玩家    ", conn.execute("SELECT COUNT(*) FROM players").fetchone()[0])
    print("流水    ", conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0])
    print("班次    ", conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0])
finally:
    conn.close()
'@ | Set-Content -LiteralPath $tmpPy -Encoding UTF8
    try {
        & $py $tmpPy $dest
    } finally {
        Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "（没找到 .venv，跳过数据统计）"
}

if (-not $Run) {
    Write-Host ""
    Write-Host "接下来两个窗口：" -ForegroundColor Cyan
    Write-Host "  1) 后端：`$env:DB_PATH='$dest'; `$env:DEBUG='true'; cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8010"
    Write-Host "  2) 前端：cd frontend; npm run dev"
    Write-Host ""
    Write-Host "或者直接加 -Run 让脚本帮你起后端。"
    exit 0
}

$env:DB_PATH = $dest
$env:DEBUG = "true"
Write-Host ""
Write-Host "启动后端（Ctrl+C 停止）；前端另开窗口跑 npm run dev" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
try {
    & (Join-Path $root ".venv\Scripts\python.exe") -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
} finally {
    Pop-Location
}
