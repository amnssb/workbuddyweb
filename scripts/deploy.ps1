# ==============================================================================
# WorkBuddy All-in-One Windows PowerShell 一键部署脚本
# ==============================================================================
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       🚀 WorkBuddy All-in-One 容器化一键部署助手 (Windows)       " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. 检查 Docker 环境
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "❌ 未检测到 Docker！请先安装并启动 Docker Desktop。"
    exit 1
}

# 2. 检查 .env
if (-not (Test-Path ".env")) {
    Write-Host "📝 未检测到 .env 配置文件，正在从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 3. 创建目录
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }
if (-not (Test-Path "auths")) { New-Item -ItemType Directory -Path "auths" | Out-Null }

# 4. 运行 Compose
Write-Host "🔨 正在构建并拉起 WorkBuddy 融合容器..." -ForegroundColor Green
docker compose up -d --build

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🎉 WorkBuddy All-in-One 部署完成！" -ForegroundColor Green
Write-Host " 🌐 控制台访问地址: http://127.0.0.1:7864" -ForegroundColor White
Write-Host " 🔑 API 反代端点:   http://127.0.0.1:7864/v1" -ForegroundColor White
Write-Host " 📋 默认登录账号:   admin" -ForegroundColor White
Write-Host ""
Write-Host " 🔍 查看实时日志与首启随机密码：" -ForegroundColor Yellow
Write-Host "     docker compose logs -f workbuddy" -ForegroundColor Gray
Write-Host "=================================================================" -ForegroundColor Cyan
