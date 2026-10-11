$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$record = Join-Path $root '.local-data\processes.json'
if (-not (Test-Path $record)) { Write-Output 'Tidak ada catatan server lokal yang dimulai oleh script ini.'; return }
$state = Get-Content $record -Raw | ConvertFrom-Json
if ($state.root -ne $root) { throw 'Catatan proses bukan milik proyek ini; tidak ada proses yang dihentikan.' }
foreach ($entry in @(
    @{ Id = $state.web_pid; Started = $state.web_started; Match = $state.next },
    @{ Id = $state.api_pid; Started = $state.api_started; Match = 'apps.api.main:app' }
)) {
    $process = Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $actual = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.Id)"
    # PowerShell 7 may deserialize ISO dates to DateTime already. Parsing that
    # object again as a locale-formatted string can swap day/month and lose UTC.
    $startedUtc = ([DateTimeOffset]$entry.Started).UtcDateTime
    $sameStart = [Math]::Abs(($process.StartTime.ToUniversalTime() - $startedUtc).TotalSeconds) -lt 1
    if (-not $sameStart -or -not $actual.CommandLine.Contains($entry.Match)) {
        Write-Warning "PID $($entry.Id) tidak lagi cocok dengan server proyek; dilewati."
        continue
    }
    # Kill only this known process tree, including Next.js's server child.
    & taskkill /PID $entry.Id /T /F
}
Write-Output 'Server lokal milik script ini sudah dihentikan. Dokumen dan log tidak dihapus.'
