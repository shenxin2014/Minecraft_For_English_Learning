param([int]$Port = 8000)
# 为 M2 独立数据库启用专用事件凭据；仍保留 Mock 动作和 M1 入口。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
$previousToken = $env:BDS_TOKEN
$previousDatabase = $env:DATABASE_PATH
try {
    $tokenPath = Join-Path $projectRoot 'data/bds-token.txt'
    if (-not (Test-Path -LiteralPath $tokenPath)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $tokenPath) | Out-Null
        $tokenBytes = New-Object byte[] 32
        $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $generator.GetBytes($tokenBytes) } finally { $generator.Dispose() }
        [System.IO.File]::WriteAllText($tokenPath, [Convert]::ToBase64String($tokenBytes))
    }
    $env:BDS_TOKEN = [System.IO.File]::ReadAllText($tokenPath).Trim()
    $env:DATABASE_PATH = Join-Path $projectRoot 'data/m2-progress.sqlite3'
    Write-Host "M2 API: http://127.0.0.1:$Port ; real BDS connection not yet verified."
    & '.\.venv\Scripts\python.exe' -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port $Port --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw 'M2 API 启动失败' }
} finally {
    $env:BDS_TOKEN = $previousToken
    $env:DATABASE_PATH = $previousDatabase
    Pop-Location
}
