param([int]$Port = 8000)
# M1 页面和 API 共用同一服务；所有教学音频都随项目提供。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.venv\Scripts\python.exe'))) {
    throw '请先运行 scripts\setup.ps1 安装 Python 环境。'
}
Write-Host "English Farm: http://127.0.0.1:$Port/"
Write-Host 'Keep this window open while playing. Press Ctrl+C to stop.'
& (Join-Path $PSScriptRoot 'start_backend.ps1') -Port $Port
