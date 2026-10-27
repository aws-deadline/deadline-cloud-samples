# V-Ray render test, run as the queue's job user by template.yaml. Log lines start with "P4".
# 1. 3dsmaxbatch make_scene.ms   -> builds and saves a V-Ray scene (no external OCIO reference)
# 2. 3dsmaxbatch render_scene.ms -> renders it through RenderCam
# Pass: both exits 0, image exists, vraylog has no "error:" line, and no log has
# "Could not obtain a license". Logs and the image are copied to -OutDir (job attachment output).
param([Parameter(Mandatory)][string]$OutDir, [Parameter(Mandatory)][string]$ScriptsDir, [string]$Tag = "p4")
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$out = Join-Path $OutDir $Tag
New-Item -ItemType Directory -Force -Path $out | Out-Null
$work = Join-Path $env:TEMP "p4-$Tag"
New-Item -ItemType Directory -Force -Path $work | Out-Null

$batch = if ($env:ADSK_3DSMAX_BATCH_EXE) { $env:ADSK_3DSMAX_BATCH_EXE } else { 'C:\Program Files\Autodesk\3ds Max 2026\3dsmaxbatch.exe' }
$vraylog = Join-Path $env:TEMP 'vraylog.txt'
$scene = Join-Path $work 'p4_vray_teapot.max'
$img = Join-Path $out "p4_vray_$Tag.png"

Write-Output "P4 whoami: $(whoami)"
Write-Output "P4 host: $env:COMPUTERNAME worker: $env:DEADLINE_WORKER_ID session: $env:DEADLINE_SESSION_ID"
foreach ($v in 'VRAY_FOR_3DSMAX2026_MAIN', 'VRAY_FOR_3DSMAX2026_PLUGINS', 'VRAY_MDL_PATH_3DSMAX2026',
               'VRAY_AUTH_CLIENT_FILE_PATH', 'VRAY_AUTH_CLIENT_SETTINGS', 'ADSK_3DSMAX_BATCH_EXE') {
    $val = [Environment]::GetEnvironmentVariable($v)
    if ($v -eq 'VRAY_AUTH_CLIENT_SETTINGS' -and $val) { $val = ($val -replace '//[^:]+:', '//<endpoint>:') }
    Write-Output "P4 env ${v}: $(if ($val) { $val } else { '<unset>' })"
}

function Invoke-MaxBatch([string]$name, [string[]]$batchArgs) {
    Remove-Item $vraylog -Force -ErrorAction SilentlyContinue
    $listener = Join-Path $out "$name-listener.log"
    $blog = Join-Path $out "$name-batch.log"
    $stdout = Join-Path $out "$name-stdout.txt"
    $t0 = Get-Date
    # Windows PowerShell 5.1 turns redirected native stderr into error records, which Stop would make fatal.
    $ErrorActionPreference = 'Continue'
    & $batch @batchArgs -listenerlog $listener -log $blog -v 5 *> $stdout
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Write-Host ("P4 {0}: 3dsmaxbatch exit {1} in {2:mm\:ss}" -f $name, $code, ((Get-Date) - $t0))
    if (Test-Path $vraylog) { Copy-Item $vraylog (Join-Path $out "$name-vraylog.txt") -Force }
    if (Test-Path $listener) {
        (Get-Content $listener -Raw) -replace "`0", '' -split "`n" | Select-Object -First 200 | ForEach-Object { Write-Host "  [listener] $($_.TrimEnd())" }
    }
    return $code
}

$env:P4_SCENE = $scene
$genCode = Invoke-MaxBatch 'make' @((Join-Path $ScriptsDir 'make_scene.ms'))
$env:P4_IMG = $img
$renderCode = if ($genCode -eq 0) { Invoke-MaxBatch 'render' @((Join-Path $ScriptsDir 'render_scene.ms'), '-sceneFile', $scene) } else { 'skipped' }
if (Test-Path $scene) { Copy-Item $scene $out -Force }

# Evidence scan across every log this run produced.
$licenseFail = @(); $vrayErrors = @(); $notable = @()
foreach ($f in Get-ChildItem $out -File | Where-Object { $_.Extension -in '.log', '.txt' }) {
    $lines = (Get-Content $f.FullName -Raw) -replace "`0", '' -split "`n"
    $licenseFail += $lines | Where-Object { $_ -match 'Could not obtain a license' } | ForEach-Object { "$($f.Name): $($_.Trim())" }
    $notable += $lines | Where-Object { $_ -match 'licen|watermark|demo|ERR:|error|OCIO|could not' } | Select-Object -First 40 | ForEach-Object { "$($f.Name): $($_.Trim())" }
    if ($f.Name -like '*vraylog.txt') {
        $vrayErrors += $lines | Where-Object { $_ -match '\berror:' } | ForEach-Object { "$($f.Name): $($_.Trim())" }
        $lines | Where-Object { $_ -match '\d+ error\(s\), \d+ warning\(s\)' } | ForEach-Object { Write-Output "P4 vraylog summary ($($f.Name)): $($_.Trim())" }
    }
}
Write-Output "P4 notable log lines:"; $notable | Select-Object -Unique | ForEach-Object { "  $_" }
$imgOk = (Test-Path $img) -and ((Get-Item $img).Length -gt 0)
Write-Output "P4 image: $img exists=$imgOk bytes=$(if ($imgOk) { (Get-Item $img).Length } else { 0 })"
Write-Output "P4 license-failure lines: $($licenseFail.Count)"; $licenseFail | ForEach-Object { "  $_" }
Write-Output "P4 vraylog error: lines: $($vrayErrors.Count)"; $vrayErrors | ForEach-Object { "  $_" }

$pass = ($genCode -eq 0) -and ($renderCode -eq 0) -and $imgOk -and ($licenseFail.Count -eq 0) -and ($vrayErrors.Count -eq 0)
Write-Output "P4 VERDICT: $(if ($pass) { 'PASS' } else { 'FAIL' }) (make=$genCode render=$renderCode image=$imgOk license=$($licenseFail.Count) vrayErrors=$($vrayErrors.Count))"
if (-not $pass) { exit 1 }
