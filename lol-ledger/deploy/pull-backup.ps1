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

$remote = ssh -i $Key -o BatchMode=yes $Server "ls -t /opt/lol-ledger/data/backups/backup-*.db 2>/dev/null | head -1"
if ($LASTEXITCODE -ne 0) { throw "连接服务器失败" }
$remote = ($remote | Out-String).Trim()
if (-not $remote) { throw "服务器上没有 backup-*.db，先看 systemctl status lol-ledger-backup.timer" }

$name = Split-Path $remote -Leaf
$local = Join-Path $Dest $name

if (Test-Path -LiteralPath $local) {
    Write-Host "[$stamp] 已存在 $name，跳过下载"
} else {
    scp -i $Key -o BatchMode=yes "${Server}:$remote" $local
    if ($LASTEXITCODE -ne 0) { throw "下载失败：$remote" }
    Write-Host "[$stamp] 已下载 $name"
}

# SQLite 文件头校验：文件以 "SQLite format 3\0" 开头
$fs = [IO.File]::OpenRead($local)
try {
    $buf = New-Object byte[] 16
    $read = $fs.Read($buf, 0, 16)
} finally {
    $fs.Close()
}
$magic = [Text.Encoding]::ASCII.GetString($buf, 0, 16)
if ($read -ne 16 -or $magic -ne "SQLite format 3`0") {
    throw "文件头不正确，可能传输损坏：$local"
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
