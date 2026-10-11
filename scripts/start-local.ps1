param(
    [ValidateRange(1, 65535)][int]$WebPort = 3000,
    [ValidateRange(1, 65535)][int]$ApiPort = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $root '.local-data'
$python = Join-Path $root '.venv\Scripts\python.exe'
$next = Join-Path $root 'apps\web\node_modules\next\dist\bin\next'
$node = (Get-Command node -ErrorAction Stop).Source
if (-not (Test-Path $python)) { throw 'Python virtualenv belum tersedia. Ikuti langkah instalasi di README.md.' }
if (-not (Test-Path $next)) { throw 'Dependency web belum tersedia. Jalankan npm ci dari apps/web.' }
if ($WebPort -eq $ApiPort) { throw 'Port API dan web harus berbeda.' }
foreach ($port in @($WebPort, $ApiPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port sudah digunakan. Tidak ada proses yang dihentikan; pilih port lain atau hentikan server Anda sendiri."
    }
}
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$env:REFLOW_STORAGE_DIR = Join-Path $runtime 'reflow'
$env:REFLOW_CORS_ORIGINS = "http://127.0.0.1:$WebPort,http://localhost:$WebPort"
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$ApiPort"
$tessdata = Join-Path $runtime 'tessdata'
if ((Test-Path (Join-Path $tessdata 'ara.traineddata')) -and
    (Test-Path (Join-Path $tessdata 'ind.traineddata')) -and
    (Test-Path (Join-Path $tessdata 'eng.traineddata'))) {
    $env:TESSDATA_PREFIX = $tessdata
}
$checker = Join-Path $env:LOCALAPPDATA 'Temp\opencode\reflow-epubcheck-5.2.1\epubcheck-5.2.1\epubcheck.jar'
if (-not $env:EPUBCHECK_JAR -and (Test-Path $checker)) { $env:EPUBCHECK_JAR = $checker }

$api = Start-Process -FilePath $python -ArgumentList "-m uvicorn apps.api.main:app --host 127.0.0.1 --port $ApiPort" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'api.stdout.log') -RedirectStandardError (Join-Path $runtime 'api.stderr.log') -PassThru
try {
    $web = Start-Process -FilePath $node -ArgumentList ('"{0}" dev --hostname 127.0.0.1 --port {1}' -f $next, $WebPort) -WorkingDirectory (Join-Path $root 'apps\web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'web.stdout.log') -RedirectStandardError (Join-Path $runtime 'web.stderr.log') -PassThru
} catch {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id }
    throw
}
@{
    api_pid = $api.Id; web_pid = $web.Id; api_port = $ApiPort; web_port = $WebPort
    root = $root; python = $python; node = $node; next = $next
    api_started = $api.StartTime.ToUniversalTime().ToString('o')
    web_started = $web.StartTime.ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content (Join-Path $runtime 'processes.json') -Encoding UTF8
Write-Output "Web dimulai: http://localhost:$WebPort (PID $($web.Id))"
Write-Output "API dimulai: http://127.0.0.1:$ApiPort/docs (PID $($api.Id))"
Write-Output "Log dan dokumen lokal: $runtime"
Write-Output 'Gunakan scripts/stop-local.ps1 untuk menghentikan hanya kedua proses ini.'
