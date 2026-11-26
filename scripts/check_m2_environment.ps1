param([string]$BdsPath = '')
# 只读取客户端和显式 BDS 目录；不修改防火墙、回环豁免或系统注册表。
$ErrorActionPreference = 'Stop'
$windowsPowerShell = Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
& $windowsPowerShell -NoProfile -Command "Get-AppxPackage '*Minecraft*' | Select-Object Name,Version | Format-Table -AutoSize"
if ($BdsPath) {
    $server = Join-Path $BdsPath 'bedrock_server.exe'
    if (-not (Test-Path -LiteralPath $server -PathType Leaf)) { throw '未找到 bedrock_server.exe' }
    (Get-Item -LiteralPath $server).VersionInfo | Select-Object FileVersion,ProductVersion | Format-List
    Write-Host '文件版本仅供核对；最终版本与模块列表以 BDS 启动日志为准。'
} else {
    Write-Host '未指定 BDS 目录，实机兼容性仍待验证。'
}
