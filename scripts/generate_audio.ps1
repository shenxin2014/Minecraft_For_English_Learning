# 用已安装的 Windows 英语声线生成固定 WAV，不访问云端、不采集麦克风。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$audioRoot = Join-Path $projectRoot 'frontend\assets\audio'
$manifest = Get-Content -LiteralPath (Join-Path $audioRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$speaker = New-Object -ComObject SAPI.SpVoice
$voice = $speaker.GetVoices() | Where-Object { $_.GetDescription() -eq $manifest.voice } | Select-Object -First 1
if (-not $voice) { throw '未安装 manifest.json 指定的英语声线，请安装后重新生成。' }
$speaker.Voice = $voice
$speaker.Rate = $manifest.rate
$speaker.Volume = 90
try {
    foreach ($clip in $manifest.clips.PSObject.Properties) {
        $stream = New-Object -ComObject SAPI.SpFileStream
        try {
            $stream.Format.Type = 22 # SAFT22kHz16BitMono，适合短教学语音。
            $stream.Open((Join-Path $audioRoot ($clip.Name + '.wav')), 3, $false)
            $speaker.AudioOutputStream = $stream
            [void]$speaker.Speak([string]$clip.Value)
        } finally {
            $stream.Close()
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($stream)
        }
    }
} finally {
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($speaker)
}
Write-Output "Generated $($manifest.clips.PSObject.Properties.Name.Count) local English clips."
