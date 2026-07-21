$ErrorActionPreference = "Stop"
trap { Write-Output "ERROR: $($_.Exception.Message)`n$($_.InvocationInfo.PositionMessage)`n$($_.ScriptStackTrace)"; exit 1 }

# CONFIG ================
# Required
$AE_INSTALLER_S3_URI = "s3://<bucket>/After Effects_en_US_WIN_64.zip"  # required

# Optional components. Leave blank to skip.
$RED_GIANT_S3_URI = ""  # e.g. s3://<bucket>/RedGiant-2026.3.0-Win.exe
$MAXON_APP_S3_URI = ""  # required with Red Giant. e.g. s3://<bucket>/Maxon_App_2026.0.1_Win.exe
$WEBVIEW2_S3_URI  = ""  # required with Red Giant. e.g. s3://<bucket>/MicrosoftEdgeWebView2RuntimeInstallerX64.exe
$RED_GIANT_LICENSE_SERVER = ""  # port@host; blank = UBL. e.g. 7055@my-license-server

$BORIS_SAPPHIRE_S3_URI = ""  # e.g. s3://<bucket>/sapphire-ae-install-2026.exe
$BORIS_LICENSE_SERVER  = ""  # port@host; blank = no license (watermarked renders). e.g. 5053@my-license-server

$LENSCARE_S3_URI         = ""  # e.g. s3://<bucket>/lenscare_ae_v1.5.5(win).zip
$LENSCARE_LICENSE_S3_URI = ""  # license key; blank = no license (watermarked renders). e.g. s3://<bucket>/Lenscare_ae.key

$RSMB_S3_URI           = ""  # e.g. s3://<bucket>/RSMB6AEInstaller.zip
$RSMB_LICENSE_SERVER   = ""  # port@host; blank = no license (watermarked renders). e.g. 5053@my-license-server
$RSMB_LICENSING_S3_URI = ""  # required with RSMB_LICENSE_SERVER. e.g. s3://<bucket>/FloatingLicensing.zip
# END CONFIG ================

function Initialize-Junctions {
    param([bool]$CreateTargets)
    foreach ($j in $junctions) {
        if (Test-Path $j.Link) {
            $item = Get-Item $j.Link -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { continue }
            Remove-Item $j.Link -Recurse -Force
        }
        $parent = Split-Path $j.Link -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        if ($CreateTargets) { New-Item -ItemType Directory -Path $j.Target -Force | Out-Null }
        New-Item -ItemType Junction -Path $j.Link -Target $j.Target
        Write-Host "Junction: $($j.Link) -> $($j.Target)"
    }
}

function Export-InstallerState {
    New-Item -ItemType Directory -Path $SVC_BACKUP -Force | Out-Null
    $services = Get-WmiObject Win32_Service | Where-Object {
        $_.PathName -like "*Red Giant*" -or $_.Name -like "*RedGiant*"
    }
    foreach ($svc in $services) {
        @{ Name = $svc.Name; DisplayName = $svc.DisplayName; PathName = $svc.PathName
           StartMode = $svc.StartMode; Description = $svc.Description
        } | ConvertTo-Json | Out-File "$SVC_BACKUP\$($svc.Name).json"
    }
}

function Import-InstallerState {
    if (Test-Path $SVC_BACKUP) {
        foreach ($file in Get-ChildItem "$SVC_BACKUP\*.json") {
            try {
                $svcInfo = Get-Content $file.FullName | ConvertFrom-Json
                if ($svcInfo.Name -notlike "*Red Giant*") { continue }
                $existing = Get-Service -Name $svcInfo.Name -ErrorAction SilentlyContinue
                if (-not $existing) {
                    $startType = switch ($svcInfo.StartMode) { "Auto" { "auto" } "Manual" { "demand" } "Disabled" { "disabled" } default { "auto" } }
                    sc.exe create $svcInfo.Name binPath= "$($svcInfo.PathName)" start= $startType DisplayName= "$($svcInfo.DisplayName)"
                    if ($svcInfo.Description) { sc.exe description $svcInfo.Name "$($svcInfo.Description)" }
                    Write-Host "Registered service: $($svcInfo.Name)"
                }
                if ($svcInfo.StartMode -eq "Auto") {
                    Start-Service -Name $svcInfo.Name -ErrorAction SilentlyContinue
                }
            } catch {
                Write-Host "WARNING: Failed to restore service $($file.Name): $_"
            }
        }
    }
}

function Invoke-WithErrorCapture($path, $argList){
    $outFile = New-TemporaryFile
    $errFile = New-TemporaryFile
    $p = Start-Process -FilePath $path -ArgumentList $argList -Wait -PassThru -NoNewWindow -RedirectStandardOutput $outFile.FullName -RedirectStandardError $errFile.FullName
    if ($p.ExitCode -ne 0) {
        throw "Command failed with exit code $($p.ExitCode): $path $argList`n$(Get-Content $outFile -Raw)$(Get-Content $errFile -Raw)"
    }
}
function Save-URI($uri){
    $file = Split-Path -Leaf $uri
    $path = "$DOWNLOADS_PATH\$file"
    $outFile = New-TemporaryFile
    $errFile = New-TemporaryFile
    $p = Start-Process -FilePath "aws" -ArgumentList "s3 cp --no-progress `"$uri`" `"$path`"" -PassThru -NoNewWindow -RedirectStandardOutput $outFile.FullName -RedirectStandardError $errFile.FullName
    $p.Handle | Out-Null
    return [pscustomobject]@{ FilePath = $path; File = $file; ErrFile = $errFile.FullName; OutFile = $outFile.FullName; Uri = $uri; Process = $p }
}
function Wait-Download($download){
    $download.Process.WaitForExit()
    if ($download.Process.ExitCode -ne 0 -or -not (Test-Path $download.FilePath)) { throw "Download failed ($($download.Process.ExitCode)): $($download.Uri)`n$(Get-Content $download.OutFile -Raw)$(Get-Content $download.ErrFile -Raw)" }
}
function Set-MachineEnvVar($name, $value){ [Environment]::SetEnvironmentVariable($name,$value,"Machine") }
function Write-Duration($start, $name){ Write-Host "$($name): $(((Get-Date) - $start).ToString('hh\:mm\:ss'))" }
function Set-AERenderEnvVar {
    $aeDir = Get-ChildItem "C:\Program Files\Adobe" -Directory -Filter "Adobe After Effects*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $aeDir) { throw "After Effects install directory not found under C:\Program Files\Adobe" }
    $aeRender = Join-Path $aeDir.FullName "Support Files\aerender.exe"
    if (-not (Test-Path $aeRender)) { throw "aerender.exe not found at $aeRender" }
    Set-MachineEnvVar "AERENDER_EXECUTABLE" $aeRender
    Write-Host "Detected After Effects: $($aeDir.Name)"
}

$MOUNT_PATH = [Environment]::GetEnvironmentVariable("DEADLINE_PERSISTENT_MOUNT", "Machine")
if (-not $MOUNT_PATH) {
    Write-Host "No persistent volume - normal install"
    $PERSISTENCE_ENABLED = $false
} else {
    Write-Host "Persistent volume detected at: $MOUNT_PATH"
    $PERSISTENCE_ENABLED = $true
    $SW_PATH = "$MOUNT_PATH\Software"
    $DATA_PATH = "$MOUNT_PATH\SoftwareData"
    $SVC_BACKUP = "$MOUNT_PATH\SoftwareServices"
    $INSTALL_MARKER = "$SW_PATH\.install-complete"
}

$junctions = @()
if ($PERSISTENCE_ENABLED) {
    $junctions = @(
        @{ Link = "C:\Program Files\Adobe"; Target = "$SW_PATH\Adobe" }
        @{ Link = "C:\ProgramData\Adobe"; Target = "$DATA_PATH\Adobe" }
    )
    if ($RED_GIANT_S3_URI) {
        $junctions += @(
            @{ Link = "C:\Program Files\Maxon"; Target = "$SW_PATH\Maxon" }
            @{ Link = "C:\Program Files\Red Giant"; Target = "$SW_PATH\Red Giant" }
            @{ Link = "C:\Program Files (x86)\Microsoft\EdgeWebView"; Target = "$SW_PATH\EdgeWebView" }
            @{ Link = "C:\ProgramData\Maxon"; Target = "$DATA_PATH\Maxon" }
            @{ Link = "C:\ProgramData\Red Giant"; Target = "$DATA_PATH\Red Giant" }
        )
    }
    if ($BORIS_SAPPHIRE_S3_URI) {
        $junctions += @(
            @{ Link = "C:\Program Files\BorisFX"; Target = "$SW_PATH\BorisFX" }
            @{ Link = "C:\ProgramData\BorisFX"; Target = "$DATA_PATH\BorisFX" }
            @{ Link = "C:\ProgramData\GenArts"; Target = "$DATA_PATH\GenArts" }
        )
    }
    if ($RSMB_S3_URI) {
        $junctions += @(
            @{ Link = "C:\Program Files\REVisionEffects"; Target = "$SW_PATH\REVisionEffects" }
        )
    }
}

$scriptStartTime = Get-Date

Write-Host "Setting environment variables for rendering..."
Set-MachineEnvVar "MAXON_RENDERONLY" "true"
if ($RED_GIANT_S3_URI -and $RED_GIANT_LICENSE_SERVER) {
    Set-MachineEnvVar "redshift_LICENSE" $RED_GIANT_LICENSE_SERVER
}

if ($PERSISTENCE_ENABLED -and (Test-Path $INSTALL_MARKER)) {
    Write-Host "=== Restoring from persistent volume ==="
    $restoreStart = Get-Date
    Initialize-Junctions -CreateTargets $false
    Import-InstallerState
    Set-AERenderEnvVar  # AE is restored via junction; re-set the machine env var (C: registry is fresh each boot)
    Write-Duration $restoreStart "Restore"
    Write-Duration $scriptStartTime "Total"
    exit 0
}

if ($PERSISTENCE_ENABLED) {
    Write-Host "=== First boot - installing to persistent volume ==="
    Initialize-Junctions -CreateTargets $true
}

$DOWNLOADS_PATH = "C:\Temp"
$AE_PLUGIN_LOCATION = "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore"

if (-not $AE_INSTALLER_S3_URI) { throw "Missing After Effects installer archive" }
if ($RED_GIANT_S3_URI) {
    if (-not $MAXON_APP_S3_URI) { throw "Missing Red Giant dependency: Maxon app" }
    if (-not $WEBVIEW2_S3_URI) { throw "Missing Red Giant dependency: WebView2" }
}
if ($RSMB_S3_URI -and $RSMB_LICENSE_SERVER -and -not $RSMB_LICENSING_S3_URI) { throw "CONFIG RSMB_LICENSING_S3_URI is required when RSMB_LICENSE_SERVER is set" }

Write-Host "Downloading installers from S3 (parallel)..."
$aeDownload = Save-URI $AE_INSTALLER_S3_URI
if ($RED_GIANT_S3_URI) {
    $rgDownload = Save-URI $RED_GIANT_S3_URI
    $maxonDownload = Save-URI $MAXON_APP_S3_URI
    $webview2Download = Save-URI $WEBVIEW2_S3_URI
}
if ($BORIS_SAPPHIRE_S3_URI) { $borisDownload = Save-URI $BORIS_SAPPHIRE_S3_URI }
if ($LENSCARE_S3_URI) {
    $lenscareDownload = Save-URI $LENSCARE_S3_URI
    if ($LENSCARE_LICENSE_S3_URI) { $lenscareLicenseDownload = Save-URI $LENSCARE_LICENSE_S3_URI }
}
if ($RSMB_S3_URI) {
    $rsmbDownload = Save-URI $RSMB_S3_URI
    if ($RSMB_LICENSE_SERVER) { $rsmbLicensingDownload = Save-URI $RSMB_LICENSING_S3_URI }
}

$aeStartTime = Get-Date
Write-Host "Installing After Effects..."
Wait-Download $aeDownload
$aeTempExtract = "$DOWNLOADS_PATH\ae_temp"
Expand-Archive -Path $aeDownload.FilePath -DestinationPath $aeTempExtract -Force
$aeSetup = Get-ChildItem -Path $aeTempExtract -Filter "setup.exe" -Recurse | Select-Object -First 1
if (-not $aeSetup) { throw "After Effects installer (setup.exe) not found in archive" }
Invoke-WithErrorCapture $aeSetup.FullName "--silent"
Set-AERenderEnvVar
Write-Duration $aeStartTime "After Effects"

if ($rgDownload) {
    $webview2StartTime = Get-Date
    Write-Host "Installing WebView2 Runtime..."
    Wait-Download $webview2Download
    Invoke-WithErrorCapture $webview2Download.FilePath @("/silent", "/install")
    Write-Duration $webview2StartTime "WebView2"

    $maxonStartTime = Get-Date
    Write-Host "Installing Maxon App..."
    Wait-Download $maxonDownload
    Invoke-WithErrorCapture $maxonDownload.FilePath @("--mode", "unattended", "--unattendedmodeui", "none")
    Write-Duration $maxonStartTime "Maxon"

    $rgStartTime = Get-Date
    Write-Host "Installing Red Giant..."
    Wait-Download $rgDownload
    Invoke-WithErrorCapture $rgDownload.FilePath @("--mode", "unattended", "--unattendedmodeui", "none")
    Write-Duration $rgStartTime "Red Giant"
}

if ($borisDownload) {
    $bsStartTime = Get-Date
    Write-Host "Installing Boris Sapphire..."
    Wait-Download $borisDownload
    Invoke-WithErrorCapture $borisDownload.FilePath "/VERYSILENT"
    if ($BORIS_LICENSE_SERVER) {
        Set-MachineEnvVar "genarts_LICENSE" $BORIS_LICENSE_SERVER
    } else {
        Write-Host "WARNING: BORIS_LICENSE_SERVER blank - installed Boris Sapphire without license (renders will be watermarked)"
    }
    Write-Duration $bsStartTime "Boris Sapphire"
}

if ($lenscareDownload) {
    $lcStartTime = Get-Date
    Write-Host "Installing Lenscare..."
    $lenscareTempExtract = "$DOWNLOADS_PATH\lenscare_temp"
    Wait-Download $lenscareDownload
    Expand-Archive -Path $lenscareDownload.FilePath -DestinationPath $lenscareTempExtract -Force
    Copy-Item -Path "$lenscareTempExtract\*" -Destination "$AE_PLUGIN_LOCATION" -Recurse -Force
    if ($lenscareLicenseDownload) {
        Wait-Download $lenscareLicenseDownload
        Copy-Item -Path $lenscareLicenseDownload.FilePath -Destination "$AE_PLUGIN_LOCATION\$($lenscareLicenseDownload.File)" -Force
    } else {
        Write-Host "WARNING: LENSCARE_LICENSE_S3_URI blank - installed Lenscare without license (renders will be watermarked)"
    }
    Write-Duration $lcStartTime "Lenscare"
}

if ($rsmbDownload) {
    $rsmbStartTime = Get-Date
    Write-Host "Installing RSMB..."
    $rsmbTempExtract = "$DOWNLOADS_PATH\rsmb_temp"
    Wait-Download $rsmbDownload
    Expand-Archive -Path $rsmbDownload.FilePath -DestinationPath $rsmbTempExtract -Force
    $rsmbExe = Get-ChildItem -Path $rsmbTempExtract -Filter "*.exe" -Recurse | Select-Object -First 1
    if (-not $rsmbExe) { throw "RSMB installer executable not found in zip" }
    Invoke-WithErrorCapture $rsmbExe.FullName @("--mode", "unattended", "--unattendedmodeui", "none")
    if ($RSMB_LICENSE_SERVER) {
        $rsmbLicenseTempExtract = "$DOWNLOADS_PATH\rsmb_licensing_temp"
        Wait-Download $rsmbLicensingDownload
        Expand-Archive -Path $rsmbLicensingDownload.FilePath -DestinationPath $rsmbLicenseTempExtract -Force
        $rsmbLicenseExe = Get-ChildItem -Path $rsmbLicenseTempExtract -Filter "*.exe" -Recurse | Select-Object -First 1
        if (-not $rsmbLicenseExe) { throw "RSMB floating license installer not found in zip" }
        Invoke-WithErrorCapture $rsmbLicenseExe.FullName @("--mode", "unattended", "--unattendedmodeui", "none", "--acceptEULA", "1", "--clientOrServer", "client")
        Set-MachineEnvVar "RVL_SERVER" $RSMB_LICENSE_SERVER
    } else {
        Write-Host "WARNING: RSMB_LICENSE_SERVER blank - installed RSMB without license (renders will be watermarked)"
    }
    Write-Duration $rsmbStartTime "RSMB"
}

if ($PERSISTENCE_ENABLED) {
    Export-InstallerState
    Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Out-File $INSTALL_MARKER
    Write-Host "Install marker written"
}

Write-Duration $scriptStartTime "Total"
Write-Host "All installations completed!"