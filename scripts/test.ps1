param([switch]$BackendOnly)
# 运行验收测试、格式和复杂度检查；任一项失败都返回错误。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.\.venv\Scripts\python.exe' -X utf8 -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw '验收测试失败' }
    & '.\.venv\Scripts\python.exe' -X utf8 -m ruff check backend scripts
    if ($LASTEXITCODE -ne 0) { throw '代码检查失败' }
    & '.\.venv\Scripts\python.exe' -X utf8 -m ruff format --check backend scripts
    if ($LASTEXITCODE -ne 0) { throw '格式检查失败' }
    & '.\.venv\Scripts\python.exe' -X utf8 scripts/check_readability.py
    if ($LASTEXITCODE -ne 0) { throw '类与方法的职责注释检查失败' }
    if (-not $BackendOnly) {
        npm test
        if ($LASTEXITCODE -ne 0) { throw '前端边界测试失败' }
        npm run check
        if ($LASTEXITCODE -ne 0) { throw '前端可读性或格式检查失败' }
    }
} finally {
    Pop-Location
}
