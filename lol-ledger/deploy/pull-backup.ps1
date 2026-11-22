<#
  把服务器上最新的每日备份拉到本机（异地副本），并校验文件完整性。

  用法：
    powershell -ExecutionPolicy Bypass -File deploy/pull-backup.ps1
    powershell ... -Dest D:\lol-backups -Keep 60

  默认：本机 %USERPROFILE%\lol-backups，保留 30 个/按天清理。
  配合 Windows 计划任务每天跑一次，磁盘坏了才有第二份。
#>
param(
    [string]$Server = "root@116.62.242.2",
    [string]$Key = "$env:USERPROFILE\.ssh\_mw.pem",
    [string]$Dest = "$env:USERPROFILE\lol-backups",
    [int]$Keep = 30
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

if (-not (Test-Path -LiteralPath $Key)) { throw "找不到密钥：$Key" }
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

# 取最新一份备份路径，再单独取它的字节数（下载后按真实大小校验，避免半截文件被当成完好）
$remote = ssh -i $Key -o BatchMode=yes $Server "ls -t /opt/lol-ledger/data/backups/backup-*.db 2>/dev/null | head -1"
if ($LASTEXITCODE -ne 0) { throw "连接服务器失败" }
$remote = ($remote | Out-String).Trim()
if (-not $remote) { throw "服务器上没有 backup-*.db，先看 systemctl status lol-ledger-backup.timer" }
$remoteSize = [int64]((ssh -i $Key -o BatchMode=yes $Server "stat -c %s '$remote'" | Out-String).Trim())

$name = Split-Path $remote -Leaf
$local = Join-Path $Dest $name

# 完整性 = 大小与服务器一致 + SQLite 头部记录的页数×页码大小恰好等于文件大小（能抓出被截断的传输）
function Test-BackupComplete([string]$p, [int64]$expectBytes) {
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    if ((Get-Item -LiteralPath $p).Length -ne $expectBytes) { return $false }
    $fs = [IO.File]::OpenRead($p)
    try { $b = New-Object byte[] 32; $n = $fs.Read($b, 0, 32) } finally { $fs.Close() }
    if ($n -lt 32) { return $false }
    if ([Text.Encoding]::ASCII.GetString($b, 0, 15) -ne "SQLite format 3") { return $false }
    $ps = ([int]$b[16] * 256) + [int]$b[17]; if ($ps -eq 1) { $ps = 65536 }
    $pages = ([int64]$b[28] * 16777216) + ([int64]$b[29] * 65536) + ([int64]$b[30] * 256) + [int64]$b[31]
    if ($pages -le 0 -or ($pages * $ps) -ne $expectBytes) { return $false }
    return $true
}

if (Test-BackupComplete $local $remoteSize) {
    Write-Host "[$stamp] $name 已存在且完整（$remoteSize 字节），跳过下载"
} else {
    if (Test-Path -LiteralPath $local) {
        $localSize = (Get-Item -LiteralPath $local).Length
        Write-Host "[$stamp] $name 本机 $localSize / 服务器 $remoteSize 不一致，重新下载" -ForegroundColor Yellow
    }
    $part = "$local.part"
    if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
    scp -i $Key -o BatchMode=yes "${Server}:$remote" $part
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw "下载失败：$remote"
    }
    if (-not (Test-BackupComplete $part $remoteSize)) {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw "下载后校验不通过（大小或 SQLite 头部页数与服务器不符），已丢弃：$name"
    }
    Move-Item -LiteralPath $part -Destination $local -Force
    Write-Host "[$stamp] 已下载并校验 $name（$remoteSize 字节）"
}

$size = [math]::Round((Get-Item -LiteralPath $local).Length / 1KB)
$age = [math]::Round(((Get-Date) - (Get-Item -LiteralPath $local).LastWriteTime).TotalHours, 1)
Write-Host "  校验通过：$size KB，文件时间距今 $age 小时"

# 清理过期副本
$cut = (Get-Date).AddDays(-$Keep)
Get-ChildItem -LiteralPath $Dest -Filter "backup-*.db" |
    Where-Object { $_.LastWriteTime -lt $cut } |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
        Write-Host "  清理旧备份：$($_.Name)"
    }

$count = (Get-ChildItem -LiteralPath $Dest -Filter "backup-*.db").Count
Write-Host "  本机现有 $count 份备份，目录 $Dest"
