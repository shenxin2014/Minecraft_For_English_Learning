param([string]$BaseUrl = '', [switch]$AudioFails)
# 默认演示使用临时数据库，不覆盖家长或开发者已有进度。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$demoArguments = @('scripts/mock_demo.py')
if ($BaseUrl) { $demoArguments += @('--base-url', $BaseUrl) }
if ($AudioFails) { $demoArguments += '--audio-fails' }
Push-Location -LiteralPath $projectRoot
try {
    & '.\.venv\Scripts\python.exe' -X utf8 @demoArguments
    if ($LASTEXITCODE -ne 0) { throw '模拟课程演示失败' }
} finally {
    Pop-Location
}
