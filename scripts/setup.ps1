# 首次安装开发环境；下载依赖需要网络，课程运行与测试不需要云端服务。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw '创建 Python 3.12 虚拟环境失败' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw '安装锁定依赖失败' }
    & '.\.venv\Scripts\python.exe' -m pip install -e . --no-deps
    if ($LASTEXITCODE -ne 0) { throw '安装本地项目失败' }
} finally {
    Pop-Location
}
