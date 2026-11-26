param([int]$Port = 8000)
# 开发服务仅绑定回环地址，避免默认暴露到局域网。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.\.venv\Scripts\python.exe' -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port $Port --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw '后端启动失败' }
} finally {
    Pop-Location
}
