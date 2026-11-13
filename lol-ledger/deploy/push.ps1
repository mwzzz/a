<#
  一键发布到线上服务器（Windows PowerShell 版，不需要 Git Bash）。

  用法：
    powershell -ExecutionPolicy Bypass -File deploy/push.ps1
    powershell -ExecutionPolicy Bypass -File deploy/push.ps1 -Server root@1.2.3.4 -Key C:\path\key.pem
    powershell -ExecutionPolicy Bypass -File deploy/push.ps1 -SkipBuild   # 前端已构建过

  默认目标：root@116.62.242.2，密钥 %USERPROFILE%\.ssh\_mw.pem（权限必须是仅本人可读）。
  服务器上必须已跑过一次 deploy/install.sh。
#>
param(
    [string]$Server = "root@116.62.242.2",
    [string]$Key = "$env:USERPROFILE\.ssh\_mw.pem",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Key)) {
    throw "找不到密钥：$Key（先复制到该路径并收紧 ACL）"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$tmp = Join-Path $env:TEMP "lol-push-$stamp"
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$hostOnly = $Server.Split("@")[-1]

try {
    if (-not $SkipBuild) {
        Write-Host "==> 构建前端" -ForegroundColor Cyan
        Push-Location (Join-Path $root "frontend")
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw "前端构建失败（exit $LASTEXITCODE）" }
        } finally {
            Pop-Location
        }
    }

    Write-Host "==> 打包后端与前端产物" -ForegroundColor Cyan
    $backendTar = Join-Path $tmp "backend.tar.gz"
    $distTar = Join-Path $tmp "dist.tar.gz"
    tar -czf $backendTar -C $root --exclude=__pycache__ --exclude=*.pyc --exclude=backend/data --exclude=backend/.env backend deploy
    if ($LASTEXITCODE -ne 0) { throw "打包 backend 失败" }
    tar -czf $distTar -C (Join-Path $root "frontend") dist
    if ($LASTEXITCODE -ne 0) { throw "打包 dist 失败" }

    Write-Host "==> 上传到 $Server" -ForegroundColor Cyan
    scp -i $Key -o BatchMode=yes -o StrictHostKeyChecking=accept-new $backendTar $distTar "${Server}:/tmp/"
    if ($LASTEXITCODE -ne 0) { throw "上传失败" }

    $remote = @'
set -euo pipefail
trap 'echo "!! 部署中断，尝试启动服务"; sudo systemctl start lol-ledger-api || true' ERR

echo "==> 留存当前版本（代码 + 前端产物，保留最近 5 份）"
BK=/opt/lol-ledger/data/backups
if [ -d /opt/lol-ledger/backend ]; then
  sudo mkdir -p "$BK"
  STAMP=$(TZ=Asia/Shanghai date +%Y%m%d-%H%M%S)
  sudo tar -czf "$BK/code-$STAMP.tar.gz" -C /opt/lol-ledger backend deploy frontend/dist
  sudo ls -1t "$BK"/code-*.tar.gz 2>/dev/null | tail -n +6 | xargs -r sudo rm -f
  echo "   已留存 code-$STAMP.tar.gz（回滚：sudo bash /opt/lol-ledger/deploy/rollback.sh --list）"
fi

echo "==> 解包后端与 deploy"
sudo mkdir -p /opt/lol-ledger
sudo tar -xzf /tmp/backend.tar.gz -C /opt/lol-ledger

echo "==> 解包前端 dist"
sudo mkdir -p /opt/lol-ledger/frontend
sudo rm -rf /opt/lol-ledger/frontend/dist
sudo tar -xzf /tmp/dist.tar.gz -C /opt/lol-ledger/frontend

echo "==> 修正属主与权限"
sudo chown -R lol:lol /opt/lol-ledger/backend /opt/lol-ledger/deploy /opt/lol-ledger/frontend
sudo find /opt/lol-ledger/backend /opt/lol-ledger/deploy -type d -exec chmod 755 {} +
sudo find /opt/lol-ledger/backend -type f -exec chmod 644 {} +
# deploy 下的 .sh 必须可执行，否则 systemd 的 backup.service 会 203/EXEC
sudo find /opt/lol-ledger/deploy -type f ! -name '*.sh' -exec chmod 644 {} +
sudo find /opt/lol-ledger/deploy -type f -name '*.sh' -exec chmod 755 {} +
sudo find /opt/lol-ledger/frontend -type d -exec chmod 755 {} +
sudo find /opt/lol-ledger/frontend -type f -exec chmod 644 {} +

echo "==> 停服务并安装依赖"
sudo systemctl stop lol-ledger-api
cd /opt/lol-ledger/backend
sudo -u lol /opt/lol-ledger/venv/bin/pip install -q -r requirements.txt

echo "==> 迁移数据库"
sudo -u lol env DB_PATH=/opt/lol-ledger/data/ledger.db /opt/lol-ledger/venv/bin/python -m app.migrations

echo "==> 同步 nginx 配置"
sudo cp -f /opt/lol-ledger/deploy/nginx-lol-ledger.conf /etc/nginx/conf.d/lol-ledger.conf
sudo nginx -t
sudo systemctl reload nginx

echo "==> 重启服务"
sudo systemctl restart lol-ledger-api
sleep 2
sudo systemctl is-active lol-ledger-api
curl -s http://127.0.0.1:8010/api/health
echo
curl -s -o /dev/null -w 'home %{http_code}\n' http://127.0.0.1/
rm -f /tmp/backend.tar.gz /tmp/dist.tar.gz
'@

    $remotePath = Join-Path $tmp "remote.sh"
    [IO.File]::WriteAllText($remotePath, ($remote -replace "`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
    scp -i $Key -o BatchMode=yes $remotePath "${Server}:/tmp/lol-push.sh"
    if ($LASTEXITCODE -ne 0) { throw "上传部署脚本失败" }

    Write-Host "==> 远程部署（会短暂停服）" -ForegroundColor Cyan
    ssh -i $Key -o BatchMode=yes $Server "sed -i 's/\r$//' /tmp/lol-push.sh && bash /tmp/lol-push.sh"
    if ($LASTEXITCODE -ne 0) { throw "远程部署失败（exit $LASTEXITCODE）" }

    Write-Host "==> 完成：http://$hostOnly/" -ForegroundColor Green
} finally {
    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}
