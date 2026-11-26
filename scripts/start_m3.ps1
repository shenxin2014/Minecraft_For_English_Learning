param([int]$Port = 8000)
# M3 复用 BDS 专用凭据与数据库，通过新行为包和伴随页启用游戏闭环。
$ErrorActionPreference = 'Stop'
Write-Host "Minecraft voice companion: http://127.0.0.1:$Port/bedrock"
& (Join-Path $PSScriptRoot 'start_m2.ps1') -Port $Port
