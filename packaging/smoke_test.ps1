# Check a finished build the way a user would meet it: run the packaged exe on a
# video with known speech and a known caption, and require both to come back.
# Also checks the window opens and stays open.
#
#   powershell -File packaging\smoke_test.ps1 -AppFolder "dist\Video ke Teks"

param(
    [Parameter(Mandatory = $true)][string]$AppFolder,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$exe = Join-Path (Resolve-Path $AppFolder) "Video ke Teks.exe"
$work = Join-Path $env:TEMP ("video-ke-teks-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $work | Out-Null

# 1. Speech from Windows' own voice, so nothing has to be downloaded.
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$voice.SetOutputToWaveFile("$work\speech.wav", $format)
$voice.Speak("Hello. This is a short test of the video to text application. The weather today is sunny and warm.")
$voice.Dispose()

& $Python packaging\make_smoke_video.py "$work\speech.wav" "$work\smoke.mp4"
if ($LASTEXITCODE -ne 0) { throw "could not make the test video" }

# 2. Run the packaged app on it, with the folder's own copy of everything.
$p = Start-Process -FilePath $exe -ArgumentList '--run', "`"$work\smoke.mp4`"", '--language', 'en' -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "the app exited with code $($p.ExitCode)" }

$txt = Join-Path $work "smoke.txt"
if (-not (Test-Path $txt)) { throw "no smoke.txt was written" }
$result = Get-Content $txt -Raw -Encoding UTF8
Write-Host "---- result ----"; Write-Host $result

$heard = [regex]::Matches($result, '\[SUARA\][^\r\n]*').Value -join ' '
$shown = [regex]::Matches($result, '\[LAYAR\][^\r\n]*').Value -join ' '
foreach ($word in 'weather', 'sunny') {
    if ($heard -notmatch $word) { throw "speech check failed: '$word' not heard" }
}
if ($shown -notmatch 'TEKS') { throw "screen check failed: caption not read" }
if (-not (Test-Path (Join-Path $work "smoke.srt"))) { throw "no smoke.srt was written" }
Write-Host "speech and screen both read correctly"

# 3. The window opens and stays open.
$w = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 15
if ($w.HasExited) { throw "the window closed on its own with code $($w.ExitCode)" }
Stop-Process -Id $w.Id -Force
Write-Host "window opened and stayed open"

Remove-Item -Recurse -Force $work
