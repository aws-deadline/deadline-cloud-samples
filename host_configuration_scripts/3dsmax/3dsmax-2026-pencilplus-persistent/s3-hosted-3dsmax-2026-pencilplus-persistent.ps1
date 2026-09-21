<#
3ds Max 2026 + Pencil+ 4 host configuration with S3-FIRST caching for AWS Deadline Cloud
Windows Service-Managed Fleets.

Architecture: S3 is the primary cache tier; the fleet's persistent volume is an optional
accelerator. The cache root is the persistent volume when one is attached
(DEADLINE_PERSISTENT_MOUNT), otherwise a local folder on C:. The payload is always reached
through NTFS junctions, so it works the same either way.

  S3-COLD   no S3 zip anywhere -> run the real installers (3ds Max + Pencil+) through
            junctions, capture registry/services/licensing/.NET, zip the cache-root payload,
            publish to S3. Normally happens once per version farm-wide.
  S3-WARM   S3 zip exists -> download + extract into the cache root (any AZ, any fleet, PV or
            not), then graft. Minutes instead of a full install.
  PV-WARM   cache root is a persistent volume that already holds a valid payload -> skip the
            download, graft in seconds.

There is deliberately no cross-worker lock. Workers that boot cold in the same window each install
once, which is what happens with no cache at all, and whoever finishes last skips the upload if a
zip is already published. A lock would save those duplicate installs on the first boot of a
generation, but it buys that with a wait path that can fail a boot outright, which is worse than
installing twice.

Zip contents: Software\ SoftwareData\ SoftwareRegistry\ (which carries .install-state.json).

This script is larger than the inline host-configuration scriptBody limit (15,000 chars), so
deploy it via s3-bootstrap-loader.ps1 (host this script in S3; paste the loader inline).

3ds Max zip creation guide:
https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md#creating-a-3ds-max-installer-archive-in-zip-format

Requirements:
- AWS CLI v2, which is already present on Deadline Cloud service-managed fleet workers.
- S3 bucket hosting the 3ds Max 2026 installer zip and the Pencil+ installer exe.
- Fleet role with s3:GetObject on the installers and s3:GetObject/s3:PutObject/s3:DeleteObject
  on the cache prefix (<bucket>/DeadlineCloud/pv-cache/*).

TRUST MODEL: the cache prefix is a code-distribution channel. Import-InstallerState runs as
SYSTEM and imports registry, registers services, and copies files taken from the cached zip.
Anyone who can write to the cache prefix can run code as SYSTEM on every worker that boots
afterward. Workers publish pv-payload.zip themselves, so the fleet role must be able to write the
prefix and that residual risk is inherent to this design rather than something the permissions can
remove. Keep the prefix reachable by nothing else, do not share it across farms, and enable
versioning. The loader's script object is different: nothing at runtime writes it, so keep it
read-only to the fleet role. See the README for details.

NOTE: 3ds Max 2026 is NOT affected by the 3ds Max 2027 Autodesk ADP "Failed to start" issue,
so no ADP workaround is needed here.
#>

$ErrorActionPreference = "Stop"
trap { Write-Output "ERROR: $($_.Exception.Message)`n$($_.InvocationInfo.PositionMessage)`n$($_.ScriptStackTrace)"; exit 1 }

# ================= CONFIG =================
$MAX_VERSION = "2026"
# TODO: Replace with your S3 URIs.
$3DS_MAX_INSTALLER_ZIP_S3_URI = "s3://your-bucket-name/path/to/3ds-max-2026.zip"
# Pencil+ 4 installer (NTR edition from PSOFT). Leave blank to skip Pencil+.
$PENCILPLUS_INSTALLER_S3_URI  = "s3://your-bucket-name/path/to/setup_Pencil+_4.2.7_for_3dsMax_ntr.exe"
$S3_CACHE = "s3://your-bucket-name/DeadlineCloud/pv-cache/3dsmax-$MAX_VERSION"
# Used when the fleet has no persistent volume. A directory path is expected. Pointing this at a bare
# drive letter is allowed but the drive has to exist on the worker: the script refuses to continue
# against a cache root that is not mounted, rather than creating the payload somewhere unintended.
$LOCAL_CACHE_ROOT = "C:\DeadlineCache"

# Cache generation. Bump this to force a fresh install farm-wide: it becomes part of the cache key,
# so every worker converges on a new object instead of racing to delete the old one. There is no flag
# to remember to unset, and a worker that boots mid-rollout either restores the new payload or builds
# it, never both. The previous generation's objects are left behind for you to delete when ready.
$CACHE_GENERATION = "1"
# ================= END CONFIG =================

# The key carries the generation, so bumping it retargets the whole fleet atomically with no deletes.
# A cold install has to finish inside the fleet's HostConfiguration scriptTimeoutSeconds, which the
# service caps at 3600 (60 minutes). The default of 300 is far too short: raise it before first use.
$ZIP_URI   = "$S3_CACHE/gen-$CACHE_GENERATION/pv-payload.zip"
$MAX_ROOT  = "C:\Program Files\Autodesk\3ds Max $MAX_VERSION"
$PENCIL_SILENT_ARGS = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")

# ================= HELPERS =================
function Write-Duration($start, $name) { Write-Host "$($name): $(((Get-Date) - $start).ToString('hh\:mm\:ss'))" }

function Invoke-Native([string]$line, [string]$errCtx) {
    cmd /c "$line >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "$errCtx failed: $LASTEXITCODE" }
}

function Invoke-Tar([string]$argLine, [string]$errCtx) {
    $errFile = "$SCRATCH\tar-err.txt"
    cmd /c "tar.exe $argLine 2>`"$errFile`""
    if ($LASTEXITCODE -ne 0) {
        $err = (Get-Content $errFile -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' '
        throw "$errCtx failed ($LASTEXITCODE): $err"
    }
}

function Invoke-Robocopy([string]$src, [string]$dst, [switch]$Required) {
    # A missing source returns 16, which the tolerance check below turns into a throw.
    #
    # On the capture side the source is an optional Autodesk or licensing directory that may simply
    # not exist on a given install, so absence is normal and skipping is correct. On the restore side
    # the source is inside the payload, and absence means the cached zip is incomplete: silently
    # continuing there would bring a worker up without its licensing state and fail every render with
    # a licence error instead of a clear message here. Callers that restore pass -Required.
    if (-not (Test-Path -LiteralPath $src)) {
        if ($Required) { throw "payload incomplete: expected directory missing from the cache: $src" }
        Write-Host "skipping copy, source not present: $src"
        return
    }
    if (-not (Test-Path $src)) { return }
    # Run through cmd with stderr redirected, like the other native helpers. robocopy exits 1-7 for
    # success and benign mismatches, so the exit code is tolerated below. Without the redirect a
    # native command writing to stderr while its output is redirected raises a NativeCommandError,
    # and under $ErrorActionPreference = Stop that terminates before the tolerance check runs.
    # Per-file access-denied and sharing-violation lines are expected here, so a single locked file
    # would otherwise fail host configuration on a graft the exit-code logic was written to survive.
    cmd /c "robocopy `"$src`" `"$dst`" /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL >nul 2>&1"
    $code = $LASTEXITCODE
    cmd /c exit 0
    if ($code -ge 8) { throw "robocopy '$src' -> '$dst' failed: $code" }
}

function Export-RegKey([string]$key, [string]$outFile) {
    # These exports used to be fire-and-forget, with output sent to nul and the exit code never read.
    # A key that is genuinely absent and an export that genuinely failed looked identical, and either
    # way the capture was published as the farm-global payload with a .reg file silently missing. Every
    # worker that later grafted it came up without those file associations.
    #
    # So separate the two cases: absent key is normal and skipped, present key that fails to export is
    # fatal, because the alternative is shipping a known-incomplete capture to the whole farm.
    if (-not (Test-Path "Registry::$key")) {
        Write-Host "registry key absent, nothing to capture: $key"
        return
    }
    Invoke-Native "reg.exe export `"$key`" `"$outFile`" /y" "reg export $key"
    if (-not (Test-Path -LiteralPath $outFile)) { throw "reg export of $key reported success but wrote no file" }
}

function New-CleanDir([string]$path) {
    # New-Item -Force is a no-op on an existing junction, and an unprivileged process can create one
    # under the cache root: a new directory there inherits AppendData for BUILTIN\Users, which is
    # CreateDirectories on a directory, and making a junction needs no privilege. Left in place, a
    # junction here would redirect what SYSTEM writes into a directory the job user owns and can
    # therefore modify at will - the multi-GB zip that tar then extracts as SYSTEM, for instance.
    # Delete the link only, never recurse into its target.
    #
    # A plain file planted under this name is cleared too, and this is the quiet case. On Windows
    # PowerShell 5.1 New-Item -ItemType Directory -Force against an existing file does NOT throw: it
    # silently leaves the file and creates no directory, so $ErrorActionPreference = Stop never fires.
    # Test-Path then answers $true for the path because a file does exist there, so the usual
    # "was it created" guard passes as well. The failure only surfaces much later, as a redirect or a
    # write failing with "Could not find a part of the path". Only ever a file or a link is removed; a
    # real directory keeps its contents, because a warm boot arrives here with the payload in place.
    $existing = Get-Item $path -Force -ErrorAction SilentlyContinue
    if ($existing -and ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        $existing.Delete()
    } elseif ($existing -and -not ($existing.Attributes -band [IO.FileAttributes]::Directory)) {
        Write-Host "removing unexpected file at $path"
        $existing.Delete()
    }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

function Protect-RegistryDir([string]$regRoot, [string]$graftDir) {
    # The registry tree is the one part of the cache that needs a narrower ACL than it inherits.
    # Import-InstallerState globs *.reg out of the graft directory and runs reg import as SYSTEM on
    # every boot, so any file an unprivileged render task can create there becomes SYSTEM-level
    # registry content. A new directory under the cache root does inherit CreateFiles and AppendData
    # for BUILTIN\Users, which is exactly enough to drop a new .reg file. Nothing unprivileged reads
    # this tree - no junction points into it - so the explicit ACL names SYSTEM and Administrators
    # only. The rest of the payload keeps its inherited ACL, which already denies modifying or
    # deleting the installed files.
    #
    # New-CleanDir first, and not a bare New-Item, because Get-Acl and Set-Acl follow a reparse point:
    # a junction pre-created under this name would take the ACL onto its target while the link itself
    # stayed writable.
    New-CleanDir $regRoot
    # SetAccessRuleProtection drops inheritance, then only the ACEs added below apply.
    $a = Get-Acl $regRoot
    $a.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($a.Access)) { $a.RemoveAccessRuleAll($rule) | Out-Null }
    foreach ($id in "NT AUTHORITY\SYSTEM", "BUILTIN\Administrators") {
        $a.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            $id, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")))
    }
    # Reset the owner too. An owner keeps WRITE_DAC implicitly whatever the DACL says, so a directory
    # pre-created by an unprivileged process could otherwise be re-granted write access afterwards.
    $a.SetOwner((New-Object System.Security.Principal.NTAccount("NT AUTHORITY\SYSTEM")))
    Set-Acl -Path $regRoot -AclObject $a
    # Created here rather than by whoever writes first, so "the registry tree is restricted" and "the
    # directory the .reg files land in exists inside it" are one operation with one contract. Still
    # New-CleanDir: the parent only became unwritable a few lines ago, so on a first boot this name
    # could have been claimed as a junction before that.
    New-CleanDir $graftDir
    Write-Host "Restricted $regRoot (SYSTEM/Administrators only)"
}


function Split-S3Uri([string]$uri) {
    if ($uri -notmatch '^s3://([^/]+)/(.+)$') { throw "bad s3 uri: $uri" }
    return @{ Bucket = $Matches[1]; Key = $Matches[2] }
}

function Test-S3Object([string]$uri) {
    # A non-zero exit means "not found" OR throttling, a transient network error, or a missing
    # permission, and callers treat a false answer as authorization to cold-install. Retry anything
    # that is not a clean 404 before reporting absence, so a 503 SlowDown during a fleet-wide boot does
    # not send every worker down the cold path over the same published zip.
    $p = Split-S3Uri $uri
    $errFile = "$SCRATCH\head-err.txt"
    foreach ($attempt in 1..3) {
        cmd /c "aws s3api head-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" >nul 2>`"$errFile`""
        if ($LASTEXITCODE -eq 0) { cmd /c exit 0; return $true }
        $err = ((Get-Content $errFile -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
        cmd /c exit 0
        # 403 counts as absent too, not just 404. S3 only returns 404 from HeadObject for a missing key
        # when the caller holds s3:ListBucket on the bucket, so with a prefix-scoped object grant the
        # ordinary "no zip yet" case arrives as 403. Retrying that would add 15s and a warning to the
        # boot-path gate and read like a permissions fault when nothing is wrong.
        if ($err -match '404|Not Found|403|Forbidden|AccessDenied') { return $false }
        if ($attempt -lt 3) {
            Write-Host "head-object on $uri failed (attempt $attempt), retrying: $err"
            Start-Sleep -Seconds (5 * $attempt)
        } else {
            Write-Host "WARNING: head-object on $uri kept failing, treating as absent: $err"
        }
    }
    return $false
}

# --- Cache root: PV when available, local disk otherwise ---
# Log the raw value quoted before deciding anything, so a surprising one is visible in the worker log
# rather than inferred from a later failure.
$MOUNT = [Environment]::GetEnvironmentVariable("DEADLINE_PERSISTENT_MOUNT", "Machine")
Write-Host "DEADLINE_PERSISTENT_MOUNT raw value: '$MOUNT'"
$MOUNT = if ($null -eq $MOUNT) { "" } else { $MOUNT.Trim() }
# IsNullOrWhiteSpace, not IsNullOrEmpty. A fleet with no persistent volume can still carry this
# variable present and blank. A blank-but-present value passes IsNullOrEmpty, which made $HAS_PV true
# and then failed New-Item with "The path is not of a legal form" two seconds into every boot. Host
# configuration exits non-zero, the agent shuts the host down, and the fleet replaces the worker and
# repeats, so the whole fleet loops instead of failing once and visibly.
$HAS_PV = -not [string]::IsNullOrWhiteSpace($MOUNT)
# Everything below writes a multi-GB payload here, so refuse anything that is not a drive-rooted
# path, and refuse a drive that is not actually present. Falling back to the local cache root costs
# only the persistent-volume acceleration; taking a bad value on trust costs the entire boot.
if ($HAS_PV -and $MOUNT -notmatch '^[A-Za-z]:(\\.*)?$') {
    Write-Host "WARNING: DEADLINE_PERSISTENT_MOUNT ('$MOUNT') is not a drive-rooted path. Using the local cache root."
    $HAS_PV = $false
}
if ($HAS_PV -and -not (Test-Path -LiteralPath ($MOUNT.Substring(0, 2) + "\"))) {
    Write-Host "WARNING: DEADLINE_PERSISTENT_MOUNT names drive $($MOUNT.Substring(0,2)) but it is not mounted. Using the local cache root."
    $HAS_PV = $false
}
$CACHE_ROOT = if ($HAS_PV) { $MOUNT } else { $LOCAL_CACHE_ROOT }
$CACHE_ROOT = $CACHE_ROOT.TrimEnd('\')
# DEADLINE_PERSISTENT_MOUNT is commonly a bare drive letter such as "D:", and a bare drive letter is
# drive-RELATIVE in PowerShell: "D:" resolves to the current directory on D:, not to D:\. Anything
# that passes the root itself to a cmdlet has to use the explicit form, so derive it once here.
$CACHE_DIR = if ($CACHE_ROOT -match '^[A-Za-z]:$') { "${CACHE_ROOT}\" } else { $CACHE_ROOT }
if ($CACHE_ROOT -match '^[A-Za-z]:$') {
    # $CACHE_DIR is a drive root, which is the normal shape of a persistent volume mount ("D:").
    # Verify rather than create: the root exists by definition once the volume is mounted, and
    # New-Item -ItemType Directory -Force on a root path throws "The path is not of a legal form".
    # The trailing separator that $CACHE_DIR adds for every other cmdlet is exactly what New-Item
    # rejects, so this branch has to come first.
    if (-not (Test-Path -LiteralPath $CACHE_DIR)) { throw "cache root $CACHE_DIR is not mounted" }
    Write-Host "Cache root $CACHE_DIR is a volume root; using it as-is"
} elseif ($HAS_PV) {
    # A mount that is a directory rather than a drive root. Never reparse-guard it: the service
    # provides this path and a directory mount point IS a reparse point, so deleting it would detach
    # the volume and then silently create an empty directory on the system disk in its place, losing
    # the cache and every later boot's cache with it. Take the path exactly as given.
    New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null
} else {
    # The local fallback is a plain directory this script owns, and an unprivileged user can create a
    # folder anywhere under C: including this name. Reject a junction rather than writing the whole
    # payload into a directory the job user controls.
    New-CleanDir $CACHE_DIR
}
Write-Host "Cache root: $CACHE_DIR (persistent volume: $HAS_PV)"
Write-Host "Cache generation: $CACHE_GENERATION"

# Built by string interpolation on purpose. "$CACHE_ROOT\Software" is already absolute even when
# $CACHE_ROOT is a bare drive letter, and unlike Join-Path it never consults the PowerShell provider,
# so it cannot throw DriveNotFound if the volume is not mounted yet.
$SW      = "$CACHE_ROOT\Software"
$DATA    = "$CACHE_ROOT\SoftwareData"
$REGROOT = "$CACHE_ROOT\SoftwareRegistry"
$GRAFT   = "$REGROOT\graft"
# Inside the restricted registry tree rather than at the cache root. It is the only gate on the warm
# path, so a forgeable state file would let an unprivileged task steer which boot path runs next.
$STATE   = "$REGROOT\.install-state.json"
$SETUPDIR = "$CACHE_ROOT\installers"
# Transient multi-GB zip, in its own directory so it can be reclaimed without touching the payload
# trees beside it.
$STAGING = "$CACHE_ROOT\staging"
$ZIPLOCAL = "$STAGING\pv-payload.zip"
# Captured stderr from the native commands below. Under the cache root rather than $env:TEMP so it is
# discarded with the cache and cannot collide with another script's temp files.
$SCRATCH = "$CACHE_ROOT\scratch"
New-CleanDir $SCRATCH
# Fail loudly rather than degrade. A cmd redirect into a missing directory returns non-zero with no
# output, so Test-S3Object would read every probe as an unrecognized error, retry it three times, and
# then report the zip absent - sending a whole warm fleet down the cold path.
if (-not (Test-Path $SCRATCH)) { throw "scratch directory $SCRATCH was not created" }

$junctions = @(
    @{ Link = "C:\Program Files\Autodesk";                           Target = "$SW\Autodesk" }
    @{ Link = "C:\ProgramData\Autodesk";                             Target = "$DATA\Autodesk" }
    @{ Link = "C:\Program Files\Common Files\Autodesk Shared";       Target = "$SW\AutodeskShared" }
    @{ Link = "C:\Program Files (x86)\Common Files\Autodesk Shared"; Target = "$SW\AutodeskSharedX86" }
)

function Initialize-Junctions([bool]$CreateTargets) {
    # Reject a pre-created junction on the payload roots before anything is created inside them. Every
    # directory level under C: lets an unprivileged user create a folder, so the guard belongs on these
    # parents and not only on the cache root: a junction at Software\ would redirect the entire install
    # into a directory the job user owns and can modify afterwards. Only on the create-targets path,
    # because a warm boot arrives here with a populated payload that must be left alone.
    if ($CreateTargets) { foreach ($d in @($SW, $DATA)) { New-CleanDir $d } }
    foreach ($j in $junctions) {
        # Get-Item -Force, not Test-Path. Test-Path resolves the reparse target, so it returns
        # $false for a junction whose target has been deleted. The link itself still exists, and
        # New-Item -ItemType Junction then fails with "already exists" under
        # $ErrorActionPreference = Stop. On a persistent volume those dangling links survive every
        # reboot, so the worker would fail host configuration permanently.
        $item = Get-Item $j.Link -Force -ErrorAction SilentlyContinue
        if ($item) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                # Keep the junction only if it already points at the expected target. The target
                # is derived from $CACHE_ROOT, which can change between boots (e.g. a persistent
                # volume attached later), so a stale junction must be recreated.
                $existing = @($item.Target) | Select-Object -First 1
                if ($existing -and $existing.TrimEnd('\') -ieq $j.Target.TrimEnd('\')) { continue }
                Write-Host "Junction $($j.Link) -> $existing, expected $($j.Target); recreating"
                $item.Delete()   # delete the link only, never recurse into the target
            } else {
                # A real directory here, so recursing is intended. Still rmdir rather than
                # Remove-Item -Recurse: the directory can itself contain junctions an installer
                # created, and Remove-Item follows those on Windows PowerShell 5.1.
                cmd /c "rmdir /s /q `"$($j.Link)`" >nul 2>&1"
                cmd /c exit 0
                if (Test-Path $j.Link) { throw "could not remove $($j.Link) before creating the junction" }
            }
        }
        $parent = Split-Path $j.Link -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        if ($CreateTargets) { New-CleanDir $j.Target }
        New-Item -ItemType Junction -Path $j.Link -Target $j.Target | Out-Null
        Write-Host "Junction: $($j.Link) -> $($j.Target)"
    }
    Protect-RegistryDir $REGROOT $GRAFT
}

function Set-EnvContract {
    [Environment]::SetEnvironmentVariable("3DSMAX_EXECUTABLE",      "$MAX_ROOT\3dsmaxbatch.exe", "Machine")
    [Environment]::SetEnvironmentVariable("MAXCMD_EXECUTABLE",      "$MAX_ROOT\3dsmaxcmd.exe",   "Machine")
    [Environment]::SetEnvironmentVariable("ADSK_3DSMAX_BATCH_EXE",  "$MAX_ROOT\3dsmaxbatch.exe", "Machine")
    [Environment]::SetEnvironmentVariable("ADSK_3DSMAX_EXECUTABLE", "$MAX_ROOT\3dsmax.exe",      "Machine")
    [Environment]::SetEnvironmentVariable("ADSK_3DSMAX_LOCATION",   $MAX_ROOT,                   "Machine")
    [Environment]::SetEnvironmentVariable("ADSK_3DSMAX_VERSION",    $MAX_VERSION,                "Machine")
    # PYTHONPATH is the one machine-wide name here that is not 3ds Max specific, so it is additive and
    # idempotent like Path below rather than an overwrite. A bare assignment would discard a value set
    # by another host configuration script, a queue environment, or the worker image on every boot.
    # Scripts\ is deliberately not included: it holds console-script .exe shims, which belong on Path
    # and contribute nothing to module resolution. Note this tree is 3ds Max's embedded CPython, so
    # anything on PYTHONPATH here is visible to every Python process on the worker.
    $pp = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Machine")
    if ($pp -notlike "*3ds Max $MAX_VERSION*") {
        $newPp = if ($pp) { "$MAX_ROOT\Python;$pp" } else { "$MAX_ROOT\Python" }
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $newPp, "Machine")
    }
    $path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($path -notlike "*3ds Max $MAX_VERSION*") {
        [Environment]::SetEnvironmentVariable("Path", "$MAX_ROOT;$MAX_ROOT\Python;$MAX_ROOT\Python\Scripts;$path", "Machine")
    }
}

$ServiceNames = @("AdskLicensingService", "FlexNet Licensing Service 64", "Autodesk Access Service Host")

function Stop-CapturedServices {
    # Returns the names that were running, so a caller can restart them.
    $stopped = @()
    foreach ($s in $ServiceNames) {
        $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq 'Running') {
            $stopped += $s
            Stop-Service -Name $s -Force -ErrorAction SilentlyContinue
        }
    }
    return $stopped
}

function Remove-JunctionLinks {
    # Delete the links only, never their targets. Called before clearing the payload so a link
    # never outlives the directory it points at.
    foreach ($j in $junctions) {
        $item = Get-Item $j.Link -Force -ErrorAction SilentlyContinue
        if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $item.Delete()
            Write-Host "Removed junction link: $($j.Link)"
        }
    }
}

function Clear-PayloadDirs {
    # Wipe the payload trees so a tar extract or a fresh install never merges into a previous
    # version. Without this, files dropped between versions survive as orphans and stale
    # graft .reg files get imported against an install they do not match.
    #
    # The licensing services must stop first. Their binaries live under the junctioned payload, so
    # a running service holds them open, and a partial delete followed by an extract leaves a mixed
    # tree that is harder to diagnose than a clean cold install. A clear that cannot complete
    # therefore throws rather than continuing.
    # The stopped list is deliberately discarded rather than restarted here, unlike Publish-S3Zip.
    # The payload these services run from is about to be deleted, so restarting them makes no sense.
    # Import-InstallerState brings them back after the extract, and it starts any captured service
    # that exists and is not disabled so a Manual one does not stay down.
    Stop-CapturedServices | Out-Null
    # Drop the junction links before their targets. Deleting a target first leaves
    # C:\Program Files\Autodesk pointing at nothing, and a throw before the payload is recreated
    # would leave a persistent volume in that state across every later boot.
    Remove-JunctionLinks
    try {
      foreach ($d in "Software", "SoftwareData", "SoftwareRegistry") {
        $target = "$CACHE_ROOT\$d"
        if (-not (Test-Path $target)) { continue }
        # rmdir /s /q rather than Remove-Item -Recurse. Remove-Item on Windows PowerShell 5.1
        # follows directory reparse points and deletes what they contain, and an Autodesk install
        # creates junctions of its own inside the payload, so a recursive delete could reach back
        # out into C:\Program Files\Common Files. rmdir removes the link without traversing it.
        $errFile = "$SCRATCH\clear-payload-err.txt"
        cmd /c "rmdir /s /q `"$target`" 2>`"$errFile`""
        cmd /c exit 0
        if (Test-Path $target) {
            $err = ((Get-Content $errFile -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
            throw "could not clear ${target} (files are likely locked by a running process): $err"
        }
      }
    } catch {
        # The junction links are already gone at this point. Put them back before failing, so the
        # worker never exits with C:\Program Files\Autodesk simply absent.
        try { Initialize-Junctions -CreateTargets $true } catch { Write-Host "WARNING: could not restore junctions: $_" }
        throw
    }
}

function Export-InstallerState([switch]$SkipHostLicensing) {
    # Capture into a sibling directory and swap it in only once every export has succeeded.
    #
    # Two reasons it cannot be done in place. Every export below is conditional or best-effort, so
    # re-exporting over a graft restored from a previous payload would leave stale .reg files that
    # Import-InstallerState globs and imports as SYSTEM. And on the PV-WARM seed path the existing
    # graft is the only copy of this volume's registry state, so deleting it up front means any throw
    # after that point leaves a truncated capture behind. The seed handler treats a failure as
    # non-fatal and deliberately keeps the state file, so the worker would exit 0 and every later boot
    # would graft a partial registry that Test-PayloadComplete and Test-Render both pass.
    #
    # rmdir rather than Remove-Item -Recurse, matching Clear-PayloadDirs, because Remove-Item follows
    # directory reparse points on Windows PowerShell 5.1.
    $graftNew = "$REGROOT\graft.new"
    if (Test-Path $graftNew) { cmd /c "rmdir /s /q `"$graftNew`" >nul 2>&1"; cmd /c exit 0 }
    # Checked, not best-effort. A surviving graft.new from an interrupted boot would be merged into by
    # New-Item -Force, and since every export below is conditional the stale .reg files would reach
    # $GRAFT and be imported as SYSTEM, which is the hazard this staging directory exists to avoid.
    if (Test-Path $graftNew) { throw "could not clear the previous partial capture at $graftNew" }
    New-Item -ItemType Directory -Force -Path "$graftNew\services" | Out-Null
    foreach ($s in $ServiceNames) {
        # WQL escapes a single quote with a backslash, NOT by doubling it the way SQL does. Doubling
        # produces "Invalid query" rather than a match. $ServiceNames is a fixed list in this script
        # rather than anything external, so this is form rather than a live exposure, but an
        # unescaped apostrophe would abort the capture instead of returning no match.
        $svcFilter = "Name='" + ($s -replace "'", "\'") + "'"
        $svc = Get-CimInstance Win32_Service -Filter $svcFilter
        if ($svc) {
            # Import-InstallerState recreates these with sc.exe, which can only reproduce a
            # built-in account. A custom or domain account also needs a password, which cannot be
            # captured, so recreating one would silently run it as LocalSystem on every warm-booted
            # worker while the cold-install worker kept the original account. Fail at capture time
            # rather than ship that asymmetry.
            $builtIn = @("LocalSystem", "NT AUTHORITY\LocalService", "NT AUTHORITY\NetworkService")
            if ($svc.StartName -and $builtIn -notcontains $svc.StartName) {
                throw "service $s runs as $($svc.StartName), which cannot be reproduced from the cache. Remove it from `$ServiceNames or extend the graft to handle credentials."
            }
            # WriteAllText, not Out-File. Out-File wraps at the host buffer width, which is 80 when
            # there is no host UI as under the host-config runner, and PathName is a full command line
            # that routinely exceeds that. A wrapped line is invalid JSON, and Import-InstallerState
            # would then throw on ConvertFrom-Json and fail the graft.
            $svcJson = @{ Name=$svc.Name; DisplayName=$svc.DisplayName; PathName=$svc.PathName
               StartMode=$svc.StartMode; StartName=$svc.StartName; Description=$svc.Description
            } | ConvertTo-Json
            [System.IO.File]::WriteAllText(
                "$graftNew\services\$($s -replace '[^A-Za-z0-9]','_').json",
                $svcJson, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host "Captured service: $s (account: $($svc.StartName))"
        }
    }
    # Only the 64-bit Macrovision (FlexNet) tree is captured. The x86 one under
    # C:\Program Files (x86)\Common Files is deliberately left alone: a worker restored from a payload
    # built this way rendered a 3ds Max scene with Arnold successfully, so nothing in the x86 tree was
    # needed for that workflow.
    # Observed on one fleet with one scene, which is worth knowing if you extend this to other
    # products: a plugin that does check local FlexNet storage may need more than this captures.
    Invoke-Robocopy "C:\Program Files\Common Files\Macrovision Shared" "$SW\MacrovisionShared"
    # C:\ProgramData\FLEXnet is a real local directory, not junctioned into the payload, so capturing
    # it after the licensing services have run pulls this host's activation state into a farm-global
    # artifact. The cold path wants it (it is the state Setup.exe produced). A re-export from an
    # already-grafted worker does not.
    if ($SkipHostLicensing) {
        Write-Host "Skipping FLEXnet capture (re-export from a grafted payload)"
    } else {
        Invoke-Robocopy "C:\ProgramData\FLEXnet" "$DATA\FLEXnet"
    }
    if (Test-Path "C:\Program Files\dotnet") {
        Invoke-Robocopy "C:\Program Files\dotnet" "$SW\dotnet"
        Export-RegKey "HKLM\SOFTWARE\dotnet"                "$graftNew\hklm-dotnet.reg"
        Export-RegKey "HKLM\SOFTWARE\Wow6432Node\dotnet"    "$graftNew\hklm-wow-dotnet.reg"
        Write-Host "Captured .NET Core runtime payload + registry"
    }
    Invoke-Native "reg.exe export `"HKLM\SOFTWARE\Autodesk`" `"$graftNew\hklm-autodesk.reg`" /y" "reg export Autodesk"
    Invoke-Native "reg.exe export `"HKLM\SOFTWARE\Wow6432Node\Autodesk`" `"$graftNew\hklm-wow-autodesk.reg`" /y" "reg export WOW Autodesk"
    foreach ($cls in "3dsmax","3dschr","3dsifl","3dsms","3dsmxp","3dsmcr",".max") {
        Export-RegKey "HKLM\SOFTWARE\Classes\$cls" "$graftNew\cls-$($cls -replace '\.','_').reg"
    }
    # Swap in the completed capture. Everything above has succeeded by this point, so the previous
    # graft is only discarded once there is a full replacement for it.
    if (Test-Path $GRAFT) { cmd /c "rmdir /s /q `"$GRAFT`" >nul 2>&1"; cmd /c exit 0 }
    if (Test-Path $GRAFT) { throw "could not replace the previous registry graft at $GRAFT" }
    Move-Item $graftNew $GRAFT -Force
    Write-Host "Registry graft exported"
}

function Import-InstallerState {
    # -Required: these come out of the payload, and Test-PayloadComplete refuses to publish a tree
    # missing either of them, so a missing one here means a broken cache rather than an absent
    # optional component. Capture stays best-effort, which is right because absence is normal on any
    # given install. The publish gate is what keeps the two sides from disagreeing.
    Invoke-Robocopy "$SW\MacrovisionShared" "C:\Program Files\Common Files\Macrovision Shared" -Required
    Invoke-Robocopy "$DATA\FLEXnet" "C:\ProgramData\FLEXnet" -Required
    if (Test-Path "$SW\dotnet") {
        Invoke-Robocopy "$SW\dotnet" "C:\Program Files\dotnet"
        Write-Host "Restored .NET Core runtime"
    }
    foreach ($regFile in Get-ChildItem "$GRAFT\*.reg" -ErrorAction SilentlyContinue) {
        Invoke-Native "reg.exe import `"$($regFile.FullName)`"" "reg import $($regFile.Name)"
        Write-Host "Imported $($regFile.Name)"
    }
    foreach ($file in Get-ChildItem "$GRAFT\services\*.json" -ErrorAction SilentlyContinue) {
        # Guarded, and it throws rather than skipping. An unguarded ConvertFrom-Json under
        # $ErrorActionPreference = Stop fails the graft with a parse error that names no file, and
        # skipping instead would bring the worker up without a licensing service, which surfaces later
        # as every render failing to check out a licence. Name the file and stop.
        try { $svc = Get-Content $file.FullName -Raw | ConvertFrom-Json }
        catch { throw "service capture $($file.Name) is not valid JSON, so the graft is incomplete: $_" }
        if (-not (Get-Service -Name $svc.Name -ErrorAction SilentlyContinue)) {
            $startType = switch ($svc.StartMode) { "Auto" {"auto"} "Manual" {"demand"} "Disabled" {"disabled"} default {"auto"} }
            # PathName is a full command line, usually already quoted. Preserve its quoting; only
            # add quotes when it has a space and none. Run through cmd so the quotes survive to
            # sc.exe (passing it as a native-command argument strips embedded quotes).
            $bin = [string]$svc.PathName
            if ($bin -notmatch '^\s*"' -and $bin -match '\s') { $bin = "`"$bin`"" }
            # Honor the captured account. Without obj= every service is recreated as LocalSystem,
            # which silently promotes one that originally ran as LocalService or NetworkService.
            # Export-InstallerState already rejected accounts sc.exe cannot reproduce.
            $objArg = if ($svc.StartName) { "obj= `"$([string]$svc.StartName)`"" } else { "" }
            # PathName, DisplayName and Description are interpolated into a cmd command line, so a
            # shell metacharacter in any of them would run as SYSTEM. Unlike StartName above, they are
            # not allowlisted, because they are free-form values sc.exe needs verbatim. They come from
            # the cached zip, and per the TRUST MODEL at the top of this file anyone who can write the
            # cache prefix already executes as SYSTEM here by design, so this widens no boundary. It
            # does mean the cache prefix must never be writable by anything you would not trust with
            # SYSTEM on every worker.
            #
            # Capture stderr, matching the two sc.exe calls below. Without it a non-zero exit is
            # reported as a bare number with no reason, and this is the one sc.exe call whose failure
            # means a licensing service is missing for the rest of the boot.
            $scErr = "$SCRATCH\sc-create-err.txt"
            cmd /c "sc.exe create `"$($svc.Name)`" binPath= $bin start= $startType $objArg DisplayName= `"$($svc.DisplayName)`" >nul 2>`"$scErr`""
            $scCode = $LASTEXITCODE
            cmd /c exit 0
            if ($scCode -ne 0) {
                $scMsg = ((Get-Content $scErr -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
                Write-Host "WARNING: sc.exe create $($svc.Name) returned ${scCode}: $scMsg"
            } else {
                Write-Host "Registered service: $($svc.Name) as $($svc.StartName)"
            }
            if ($svc.Description) {
                cmd /c "sc.exe description `"$($svc.Name)`" `"$([string]$svc.Description)`" >nul 2>&1"
                cmd /c exit 0
            }
        }
        if ($svc.Name -eq "Autodesk Access Service Host") {
            # Through cmd for the same reason as Invoke-Robocopy: a bare native call piped to
            # Out-Null turns any stderr line into a terminating NativeCommandError under
            # $ErrorActionPreference = Stop, and this failure is not worth failing a boot over.
            cmd /c "sc.exe config `"$($svc.Name)`" start= disabled >nul 2>&1"
            cmd /c exit 0
            continue
        }
        # Start anything captured that exists and is not disabled, rather than keying off the captured
        # StartMode. FlexNet Licensing Service 64 is normally Manual, so a StartMode check would leave
        # it stopped for the rest of the boot after Clear-PayloadDirs stopped it, and Test-Render
        # would not notice because 3dsmaxbatch.exe -help exercises no licensing.
        $live = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue
        if ($live -and $live.StartType -ne 'Disabled' -and $live.Status -ne 'Running') {
            try { Start-Service -Name $svc.Name } catch { Write-Host "WARNING: could not start $($svc.Name): $_" }
        }
    }
}

function Test-PayloadPresent {
    # Payload-side paths, not $MAX_ROOT, so this answers the question without depending on the junctions
    # being up. Used by Test-StateValid so a cache whose files are gone is rejected before Invoke-Graft
    # recreates junctions and starts importing registry state.
    if (-not (Test-Path "$SW\Autodesk\3ds Max $MAX_VERSION\3dsmaxbatch.exe")) { return $false }
    if ($PENCILPLUS_INSTALLER_S3_URI) {
        $plug = "$SW\Autodesk\3ds Max $MAX_VERSION\plugins"
        if (-not (Get-ChildItem $plug -Filter "*Pencil*" -ErrorAction SilentlyContinue)) { return $false }
    }
    return $true
}

function Test-StateValid {
    # Does the payload on disk match what this script is configured to install? Used for both the
    # local cache and a freshly restored zip, so there is one answer to "is this the right payload"
    # rather than a second question layered on top that could reject a payload that is in fact
    # correct.
    if (-not (Test-Path $STATE)) { return $false }
    try { $s = Get-Content $STATE -Raw | ConvertFrom-Json } catch { return $false }
    # Compare the full installer URIs, not just the leaf filenames. Installer archives are named
    # after the product rather than the build, so a leaf comparison treats a different build at a
    # new prefix as an identical cache and grafts a 3ds Max the fleet was never configured to use.
    # The generation is compared too, so a stale local payload from a previous generation is rejected
    # even though its S3 object lives under a different key.
    if (-not ($s.maxVersion -eq $MAX_VERSION `
        -and [string]$s.cacheGeneration -eq $CACHE_GENERATION `
        -and [string]$s.maxInstallerUri -eq $3DS_MAX_INSTALLER_ZIP_S3_URI `
        -and [string]$s.pencilInstallerUri -eq $PENCILPLUS_INSTALLER_S3_URI)) { return $false }
    # A state file can describe a payload whose files are missing: a partly-completed clear on an
    # earlier boot, a volume that filled mid-extract, manual intervention. Checking here means a
    # degraded cache is rejected at the gate rather than throwing part-way through Invoke-Graft, after
    # junctions have been recreated and registry state possibly imported.
    if (-not (Test-PayloadPresent)) {
        Write-Host "state file matches but the payload is incomplete - treating the cache as invalid"
        return $false
    }
    return $true
}

function Write-StateFile {
    @{ schemaVersion = 1; maxVersion = $MAX_VERSION
       cacheGeneration = $CACHE_GENERATION
       maxInstallerUri = $3DS_MAX_INSTALLER_ZIP_S3_URI
       pencilInstallerUri = $PENCILPLUS_INSTALLER_S3_URI
       installedAt = (Get-Date -Format o) } | ConvertTo-Json | ForEach-Object {
        # WriteAllText rather than Out-File: Out-File wraps at the host buffer width, 80 with no host
        # UI, and the installer URI lines exceed that for any realistic bucket and prefix. A wrapped
        # line is invalid JSON, so Test-StateValid would hit its catch and return $false on every
        # boot, silently sending every worker down the full download path.
        [System.IO.File]::WriteAllText($STATE, $_, (New-Object System.Text.UTF8Encoding($false)))
    }
}

function Install-3dsMax {
    # Clear any partial artifact from a previously terminated cold install so we never resume
    # from a truncated zip or half-populated extraction.
    # Not Remove-Item -Recurse. If $SETUPDIR has been pre-created as a junction, a recursive delete as
    # SYSTEM follows it and wipes an attacker-chosen directory. Delete a link as a link, and use
    # rmdir for a real directory so the traversal behavior matches Clear-PayloadDirs.
    $stale = Get-Item $SETUPDIR -Force -ErrorAction SilentlyContinue
    if ($stale -and ($stale.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        $stale.Delete()
    } elseif ($stale) {
        cmd /c "rmdir /s /q `"$SETUPDIR`" >nul 2>&1"
        cmd /c exit 0
    }
    New-Item -ItemType Directory -Force -Path $SETUPDIR | Out-Null
    $dl = Get-Date
    Invoke-Native "aws s3 cp --no-progress `"$3DS_MAX_INSTALLER_ZIP_S3_URI`" `"$SETUPDIR\3dsmax.zip.part`"" "installer download"
    Move-Item "$SETUPDIR\3dsmax.zip.part" "$SETUPDIR\3dsmax.zip" -Force
    Write-Duration $dl "Download"
    $ex = Get-Date
    Expand-Archive "$SETUPDIR\3dsmax.zip" "$SETUPDIR\extracted" -Force
    Write-Duration $ex "Extract"
    $setup = Get-ChildItem -Path "$SETUPDIR\extracted" -Filter "Setup.exe" -Recurse | Select-Object -First 1
    if (-not $setup) { throw "Setup.exe not found in installer archive" }
    $inst = Get-Date
    $p = Start-Process -FilePath $setup.FullName -ArgumentList "-q" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Setup.exe failed: $($p.ExitCode)" }
    Write-Duration $inst "Install (3ds Max)"
    if (-not (Test-Path "$MAX_ROOT\3dsmaxbatch.exe")) { throw "3dsmaxbatch.exe missing after install" }
}

function Install-Pencil {
    if (-not $PENCILPLUS_INSTALLER_S3_URI) { return }
    $leaf = Split-Path $PENCILPLUS_INSTALLER_S3_URI -Leaf
    $path = "$SETUPDIR\$leaf"
    Invoke-Native "aws s3 cp --no-progress `"$PENCILPLUS_INSTALLER_S3_URI`" `"$path`"" "Pencil+ download"
    # Inno Setup silent switches. The exit code is recorded but deliberately not used as pass/fail:
    # code 5 also means "already installed", so the authority is whether the plugin actually landed.
    # Carrying the code into the message is the difference between "plugin not found" and knowing the
    # installer itself refused to run.
    $pp = Start-Process -FilePath $path -ArgumentList $PENCIL_SILENT_ARGS -Wait -PassThru
    $found = Get-ChildItem "$MAX_ROOT\plugins" -Filter "*Pencil*" -ErrorAction SilentlyContinue
    if (-not $found) {
        throw "Pencil+ plugin not found in $MAX_ROOT\plugins after install (installer exit code $($pp.ExitCode))"
    }
    Write-Host "Pencil+ installed (installer exit code $($pp.ExitCode))"
}

function Install-Adaptor {
    # The adaptor is pip-installed into $MAX_ROOT\Python (inside the Autodesk junction) on the
    # cold path, so it is part of the cached payload. Skip the install on warm boots so the fast
    # path has no PyPI dependency and the adaptor version stays pinned to what was cached.
    if (Test-Path "$MAX_ROOT\Python\Scripts\3dsmax-openjd.exe") {
        Write-Host "adaptor already present from cache - skipping pip install"
        return
    }
    $py = "$MAX_ROOT\Python\python.exe"
    cmd /c "`"$py`" -m ensurepip >nul 2>&1"
    cmd /c "`"$py`" -m pip install --quiet deadline-cloud-for-3ds-max >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "adaptor pip install failed: $LASTEXITCODE" }
    if (-not (Test-Path "$MAX_ROOT\Python\Scripts\3dsmax-openjd.exe")) { throw "3dsmax-openjd.exe missing after pip install" }
    Write-Host "adaptor installed (3dsmax-openjd present)"
}

function Test-PayloadComplete {
    # The state file is written before Publish-S3Zip and travels inside the tar, so a zip built from
    # an incomplete tree carries a state file that matches perfectly. Test-StateValid cannot
    # see that, and Test-Render only exercises 3dsmaxbatch.exe, so a payload missing the Pencil+
    # plugin would graft, pass, and then fail every Pencil+ render on every worker in the fleet.
    if (-not (Test-Path "$MAX_ROOT\3dsmaxbatch.exe")) {
        throw "payload incomplete: 3dsmaxbatch.exe missing under $MAX_ROOT"
    }
    # Arnold (MAXtoA) ships with 3ds Max and is its default production renderer. It installs as an
    # ApplicationPlugins bundle under C:\ProgramData\Autodesk, not into the 3ds Max program directory,
    # so it is easy to lose from the payload without noticing: Test-Render passes regardless, because
    # 3dsmaxbatch.exe -help loads no renderer. A payload without it produces workers that log
    # "Missing dll: maxtoa.dlr", fall back to "Missing Renderer", and fail every render. Check for the
    # renderer itself rather than for the directory, which an exclusion leaves behind empty.
    # Checked on the payload path, not through C:\ProgramData\Autodesk. The junction resolves to the
    # same place, but the payload path is what actually gets archived, and it does not depend on the
    # junction being up at the moment of the check. -Filter rather than -Include, which is the form
    # that behaves predictably with -Recurse on a directory.
    $maxtoa = @(Get-ChildItem "$DATA\Autodesk\ApplicationPlugins" -Recurse -Force `
                -Filter "maxtoa.dlr" -ErrorAction SilentlyContinue)
    if ($maxtoa.Count -eq 0) {
        throw "payload incomplete: maxtoa.dlr (Arnold, the default 3ds Max renderer) is not present under $DATA\Autodesk\ApplicationPlugins. Publishing this payload would give every restored worker a 3ds Max that cannot render."
    }
    if ($PENCILPLUS_INSTALLER_S3_URI) {
        $found = Get-ChildItem "$MAX_ROOT\plugins" -Filter "*Pencil*" -ErrorAction SilentlyContinue
        if (-not $found) {
            throw "payload incomplete: Pencil+ is configured but no *Pencil* plugin exists under $MAX_ROOT\plugins"
        }
    }
    # The two licensing directories are copied best-effort on capture, because a given install may
    # genuinely not have them, but Import-InstallerState demands both with -Required on restore.
    # Gate the publish on them so the two sides cannot disagree. A tree missing either one is never
    # published, so no later worker can fail its restore on it.
    #
    # Without this gate, a cold worker that captured neither publishes a zip every later worker
    # fails to restore, and the republish-on-$restoreFailed path rebuilds the same gap with the same
    # conditional capture, so the fleet cold-installs and re-uploads a multi-GB zip on every boot.
    #
    # Throwing here is not fatal on the cold path. Publish-S3Zip runs inside a try/catch that logs a
    # non-fatal warning, so this worker still installs and renders. If a future 3ds Max stops using
    # one of these paths, the log names the directory and you drop it from the -Required calls in
    # Import-InstallerState, instead of finding out through a restore failure on every worker.
    foreach ($dir in "$SW\MacrovisionShared", "$DATA\FLEXnet") {
        if (-not (Test-Path -LiteralPath $dir)) {
            throw "payload incomplete: $dir is missing, and Import-InstallerState requires it on every restore. Publishing this payload would fail the restore on every later worker."
        }
    }
}

function Test-Render {
    # Do NOT merge stderr (2>&1): under $ErrorActionPreference=Stop, native stderr becomes a
    # terminating error, and 3dsmaxbatch -help can write to stderr on a healthy worker.
    $null = & "$MAX_ROOT\3dsmaxbatch.exe" -help 2>$null
    if ($LASTEXITCODE -ne 0) { throw "3dsmaxbatch -help failed: $LASTEXITCODE" }
    $dotnet = "C:\Program Files\dotnet\dotnet.exe"
    if (Test-Path $dotnet) {
        $runtimes = (& $dotnet --list-runtimes 2>$null | Out-String)
        if ($runtimes -notmatch 'Microsoft\.WindowsDesktop\.App') { throw ".NET Desktop Runtime not registered" }
    }
    Write-Host "3dsmaxbatch responds OK"
}

function Publish-S3Zip {
    # Refuse to make a degraded tree the farm-global cache. tar succeeds on a nearly empty directory,
    # so without this a partial payload could be published and then grafted onto every worker.
    Test-PayloadComplete
    New-CleanDir $STAGING
    $zipLocal = $ZIPLOCAL
    if (Test-Path $zipLocal) { Remove-Item $zipLocal -Force }
    # The payload does contain reparse points, and Windows tar.exe descends into a directory junction
    # rather than recording it, so the target content is duplicated into the archive. A 3ds Max 2026
    # install has been observed creating two, both "Current" version aliases pointing back through the
    # C:\Program Files junctions and therefore back into this same tree:
    #   Software\Autodesk\AdskIdentityManager\Current   -> ...\AdskIdentityManager\<version>
    #   Software\AutodeskSharedX86\AdskLicensing\Current -> ...\AdskLicensing\<version>
    # Neither resolves at or above its own tree, so the walk terminates rather than cycling. The cost
    # is a larger archive, and on restore each becomes a real directory holding a copy rather than a
    # link. Log them rather than failing: a version-alias directory is not obviously wrong to
    # duplicate, and an installer adding a junction that DOES resolve upward would cycle, which this
    # warning is how you would find out.
    foreach ($tree in @($SW, $DATA, $REGROOT)) {
        if (-not (Test-Path $tree)) { continue }
        $links = @(Get-ChildItem $tree -Recurse -Force -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count -gt 0) {
            Write-Host "WARNING: $($links.Count) reparse point(s) under $tree will be followed by tar:"
            $links | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.FullName) -> $(@($_.Target) | Select-Object -First 1)" }
        }
    }
    # Log what is about to be archived from ApplicationPlugins. An earlier version excluded this
    # directory and silently dropped Autodesk's MAXtoA (Arnold) renderer from every restored worker,
    # which nothing caught until a real render failed. Printing the entries makes the contents of the
    # payload a matter of record in the worker log rather than an assumption.
    $apDir = "$DATA\Autodesk\ApplicationPlugins"
    $ap = @(Get-ChildItem $apDir -ErrorAction SilentlyContinue)
    if ($ap.Count -gt 0) {
        Write-Host "ApplicationPlugins bundles being archived ($($ap.Count)):"
        $ap | ForEach-Object { Write-Host "  $($_.Name)" }
    } else {
        Write-Host "WARNING: $apDir is empty. A stock 3ds Max install ships bundles here, MAXtoA (Arnold) among them, so an empty directory means the payload is missing renderers and this zip will produce workers that cannot render."
    }

    $running = Stop-CapturedServices
    try {
        $t = Get-Date
        $rootFwd = $CACHE_ROOT.TrimEnd('\') + '/'
        # .install-state.json is not listed separately: it lives inside SoftwareRegistry now, so it
        # travels with that tree.
        #
        # ApplicationPlugins is NOT excluded, and it must not be. An earlier version of this script
        # excluded SoftwareData/Autodesk/ApplicationPlugins on the reasoning that it is the one payload
        # tree a render task can write, so a dropped .bundle would reach every worker through the
        # published zip. That reasoning ignored what actually lives there: Autodesk ships MAXtoA, the
        # Arnold renderer, as an ApplicationPlugins bundle, and Arnold is the default production
        # renderer for 3ds Max. Excluding the directory produced a zip whose restored workers logged
        # "Missing dll: maxtoa.dlr", fell back to "Missing Renderer", and failed every render with
        # "Render Error (Beginning Renderer)". Cold-install workers were fine, so the fault only
        # appeared on restore, and Test-Render did not catch it because 3dsmaxbatch.exe -help loads no
        # renderer.
        #
        # The write exposure is real but it is the same residual risk the README already documents for
        # the payload generally: a task that can drop a file in the payload can reach the published zip
        # through whichever worker seeds it. Keep the cache prefix trusted; do not solve it by removing
        # the renderer.
        Invoke-Tar "-a -cf `"$zipLocal`" -C `"$rootFwd`" Software SoftwareData SoftwareRegistry" "tar create"
        Write-Duration $t "Zip create ($([math]::Round((Get-Item $zipLocal).Length/1GB,1)) GB)"
    } finally {
        foreach ($s in $running) { try { Start-Service -Name $s } catch { Write-Host "WARNING: restart $s failed: $_" } }
    }
    # Upload to a temporary key, then server-side move into place so readers never observe a
    # partial object under the final key.
    $t = Get-Date
    $uploadUri = "$ZIP_URI.uploading-$env:COMPUTERNAME"
    try {
        Invoke-Native "aws s3 cp --no-progress `"$zipLocal`" `"$uploadUri`"" "zip upload"
        Invoke-Native "aws s3 mv `"$uploadUri`" `"$ZIP_URI`"" "zip publish"
        Write-Duration $t "Zip upload"
    } finally {
        # A failed mv leaves a complete multi-GB object under the temp key. An
        # AbortIncompleteMultipartUpload lifecycle rule never reaps that, and the key is
        # per-hostname so it accumulates one copy per worker instead of overwriting. Deleting it
        # here is a no-op once the mv has succeeded.
        cmd /c "aws s3 rm `"$uploadUri`" >nul 2>&1"
        cmd /c exit 0
        # Reclaim the local copy on the failure path too, so a retry is not short of disk.
        Remove-Item $zipLocal -Force -ErrorAction SilentlyContinue
    }
}

function Restore-S3Zip {
    $zipLocal = $ZIPLOCAL
    $t = Get-Date
    New-CleanDir $STAGING
    Invoke-Native "aws s3 cp --no-progress `"$ZIP_URI`" `"$zipLocal`"" "zip download"
    Write-Duration $t "Zip download"
    # tar merges into the cache root, so the previous payload has to go first. Reachable with the
    # licensing services running: a PV-WARM graft that fails after Import-InstallerState started
    # them falls through to here, so Clear-PayloadDirs stops them before deleting.
    Clear-PayloadDirs
    # Restrict the registry tree BEFORE extracting into it. tar does not carry NTFS ACLs, so a
    # directory it creates inherits from the cache root. Doing this afterwards would leave $GRAFT
    # writable for the length of a multi-GB extract, and Import-InstallerState then reg imports
    # whatever is in there as SYSTEM. tar runs as SYSTEM, so the restricted ACL is no obstacle to the
    # extract itself.
    Protect-RegistryDir $REGROOT $GRAFT
    $t = Get-Date
    $rootFwd = $CACHE_ROOT.TrimEnd('\') + '/'
    Invoke-Tar "-xf `"$zipLocal`" -C `"$rootFwd`"" "tar extract"
    Write-Duration $t "Zip extract"
    Remove-Item $zipLocal -Force
}

function Invoke-Graft {
    Initialize-Junctions -CreateTargets $false
    # Check the restored tree before spending time on registry imports and services.
    Test-PayloadComplete
    Import-InstallerState
    Set-EnvContract
    Install-Adaptor
    Test-Render
}

# ================= MAIN =================
$t0 = Get-Date

# PV-WARM: persistent volume already holds a valid payload from a previous boot.
# Not gated on $HAS_PV. Host configuration re-runs on every reboot, and a worker with no persistent
# volume still has a complete C:\DeadlineCache from its previous boot. Gating this on the persistent
# volume would make it re-download and re-extract the whole zip over a payload already on local disk.
if (Test-StateValid) {
    Write-Host "=== PV-WARM boot: grafting cached install ==="
    $grafted = $false
    try { Invoke-Graft; $grafted = $true }
    catch { Write-Host "WARNING: graft failed ($_). Invalidating cache."; Remove-Item $STATE -Force -ErrorAction SilentlyContinue }
    if ($grafted) {
        Write-Duration $t0 "Total (PV-warm graft)"
        # Opportunistically seed the farm-global zip. Guarded separately so a seeding failure
        # never re-invalidates a cache that grafted successfully.
        try {
            if (-not (Test-S3Object $ZIP_URI)) {
                Write-Host "=== Seeding S3 zip from this volume (one-time) ==="
                # Re-capture registry and service state before tarring. Import-InstallerState has
                # already run on this boot and the licensing services have been started, so the payload
                # on disk has moved on from the capture the original cold install wrote. Re-exporting
                # keeps the seeded zip internally consistent.
                # -SkipHostLicensing keeps this host's FLEXnet trusted-storage out of the capture.
                # Import-InstallerState already copied the payload's licensing state out to
                # C:\ProgramData\FLEXnet and started the services, which then wrote host-specific
                # activation data there. Re-exporting it would push one worker's licensing state to the
                # whole farm, and because robocopy /E merges rather than mirrors it would accumulate
                # across reboots.
                Export-InstallerState -SkipHostLicensing
                Publish-S3Zip
                Write-Host "S3 zip seeded from this persistent volume (licensing state left as captured)"
            }
        } catch {
            # Not fatal for this worker, which already grafted, but it is expensive for the fleet:
            # with no zip published, every other worker falls back to a full cold install. Log it
            # so the cause is visible rather than inferred from unexpectedly slow boots.
            Write-Host "WARNING: S3 seed FAILED - other workers will cold-install until a zip is published: $_"
        }
        exit 0
    }
}

# Set before the S3-WARM attempt so the publish decision at the end of the cold path can tell "no zip
# was ever there" apart from "a zip is there and it did not work".
$restoreFailed = $false

# S3-WARM: restore the farm-global payload from S3 (any AZ, PV or not).
if (Test-S3Object $ZIP_URI) {
    Write-Host "=== S3-WARM boot: restoring cache root from S3 zip ==="
    try {
        Restore-S3Zip
        if (-not (Test-StateValid)) { throw "restored zip does not match the configured installers" }
        Invoke-Graft
        Write-Duration $t0 "Total (S3-warm restore + graft)"
        exit 0
    } catch {
        Write-Host "WARNING: S3 restore failed ($_). Falling through to cold install."
        $restoreFailed = $true
        Remove-Item $STATE -Force -ErrorAction SilentlyContinue
        # Restore-S3Zip already removed the junction links through Clear-PayloadDirs, and the cold
        # path below recreates them. This call keeps the two independent: if anything between here
        # and there exits early, a persistent volume is not left with the Autodesk paths simply
        # absent. Idempotent with the cold path's later call.
        try { Initialize-Junctions -CreateTargets $true } catch { Write-Host "WARNING: could not restore junctions: $_" }
    }
}

Write-Host "=== S3-COLD boot: installing and publishing the farm-global zip ==="
# Start from an empty payload. A failed S3-WARM restore arrives here with whatever the interrupted
# extract wrote, and Setup.exe -q against a partial install of the same version can report success
# without repairing it, because the MSI cache it consults lives in C:\Windows\Installer. A partial
# install would then be captured and published as the farm-global payload.
Clear-PayloadDirs
Initialize-Junctions -CreateTargets $true
Install-3dsMax
Install-Pencil
Export-InstallerState
Set-EnvContract
Install-Adaptor
Write-StateFile
Test-Render
# Publish unless another worker got there first. Several workers booting cold at once each install
# their own copy, which is what happens with no cache at all, but there is no point in the later ones
# spending minutes uploading a multi-GB zip over an equivalent object that other workers may already
# be restoring. This worker is fully installed either way, so skipping the upload costs it nothing.
#
# $restoreFailed is the exception, and it inverts the decision. Arriving here from a failed S3-WARM
# means a zip IS published and this worker could not use it. Skipping the upload on that path would
# leave the bad object in place permanently: every future worker would fail the same restore and cold
# install, and no worker would ever replace it, because they would all reach this line with a zip
# present and skip too. The payload just installed and passed Test-Render, so overwrite instead.
if ((Test-S3Object $ZIP_URI) -and -not $restoreFailed) {
    Write-Host "another worker published a zip during this install - skipping the upload"
} else {
    if ($restoreFailed) { Write-Host "the published zip failed to restore on this worker - republishing over it" }
    Write-Host "=== Publishing S3 zip ==="
    try { Publish-S3Zip } catch { Write-Host "WARNING: S3 publish failed (non-fatal): $_" }
}
# Reclaim the several-GB installer download/extraction; it is not part of the payload.
# rmdir, not Remove-Item -Recurse, matching Install-3dsMax and Clear-PayloadDirs. This tree is the
# unpacked contents of a customer-supplied installer zip, and Remove-Item descends into any
# directory reparse point it finds there.
cmd /c "rmdir /s /q `"$SETUPDIR`" >nul 2>&1"
cmd /c exit 0
Write-Duration $t0 "Total (cold install + capture)"
exit 0
