<#
3ds Max 2026 + Pencil+ 4 host configuration with S3-FIRST caching for AWS Deadline Cloud
Windows Service-Managed Fleets.

Architecture: S3 is the primary cache tier; the fleet's persistent volume is an optional
accelerator. The cache root is the persistent volume when one is attached
(DEADLINE_PERSISTENT_MOUNT), otherwise a local folder on C:. The payload is always reached
through NTFS junctions, so it works the same either way.

  S3-COLD   no S3 zip anywhere -> claim token, run the real installers (3ds Max + Pencil+)
            through junctions, capture registry/services/licensing/.NET, zip the cache-root
            payload, publish to S3, release token. Happens ONCE per version farm-wide.
  S3-WARM   S3 zip exists -> download + extract into the cache root (any AZ, any fleet, PV or
            not), then graft. Minutes instead of a full install.
  PV-WARM   cache root is a persistent volume that already holds a valid payload -> skip the
            download, graft in seconds.
  WAIT      another worker holds the install token -> poll for its zip. A stale token is
            taken over.

Zip contents: Software\ SoftwareData\ SoftwareRegistry\ (which carries .install-state.json).

This script is larger than the inline host-configuration scriptBody limit (15,000 chars), so
deploy it via s3-bootstrap-loader.ps1 (host this script in S3; paste the loader inline).

3ds Max zip creation guide:
https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md#creating-a-3ds-max-installer-archive-in-zip-format

Requirements:
- AWS CLI v2.22 or newer (the install token relies on conditional writes: `put-object`
  older versions fall back to a racy claim - see the README).
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
$LOCAL_CACHE_ROOT = "C:\DeadlineCache"   # used when the fleet has no persistent volume

# Cache generation. Bump this to force a fresh install farm-wide: it becomes part of the cache key,
# so every worker converges on a new object instead of racing to delete the old one. There is no flag
# to remember to unset, and a worker that boots mid-rollout either restores the new payload or builds
# it, never both. The previous generation's objects are left behind for you to delete when ready.
$CACHE_GENERATION = "1"

# Minutes before a held install token is treated as stale (crashed installer) and taken over.
# Both this and $WAIT_ZIP_MAX_MIN have to fit inside the fleet's HostConfiguration
# scriptTimeoutSeconds, which the service caps at 3600 (60 minutes). Set either above that ceiling and
# the service kills the script first, so the takeover never fires and the wait timeout never reports
# anything.
#
# This bounds the gap between token re-stamps, not the whole install. Update-InstallToken runs after the
# installer download, after the archive extract, after Setup.exe, and again before the publish, so no
# single step may exceed this value. Adding a long step without a re-stamp reintroduces the concurrent
# install this is meant to prevent.
$TOKEN_STALE_MIN = 40
# Maximum minutes a waiting worker polls for another worker's published zip. Must exceed
# $TOKEN_STALE_MIN so a waiting worker can reach the takeover, and stay under the fleet's
# scriptTimeoutSeconds. Raise that setting to 3600 when using these defaults.
$WAIT_ZIP_MAX_MIN = 50
# ================= END CONFIG =================

# Cleared the first time the AWS CLI rejects --if-none-match, which gates the stale-token takeover.
$script:ConditionalWritesSupported = $true

# Both keys carry the generation, so bumping it retargets the whole fleet atomically with no deletes.
$ZIP_URI   = "$S3_CACHE/gen-$CACHE_GENERATION/pv-payload.zip"
$TOKEN_URI = "$S3_CACHE/gen-$CACHE_GENERATION/installing.token"
if ($WAIT_ZIP_MAX_MIN -le $TOKEN_STALE_MIN) {
    Write-Host "WARNING: `$WAIT_ZIP_MAX_MIN ($WAIT_ZIP_MAX_MIN) must exceed `$TOKEN_STALE_MIN ($TOKEN_STALE_MIN), otherwise a waiting worker can never take over a dead holder's token and a crashed install parks the fleet until the token ages out on its own."
}
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

function Invoke-Robocopy([string]$src, [string]$dst) {
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

function Protect-Dir([string]$path, [string]$usersRight) {
    # SetAccessRuleProtection drops inheritance, then only the ACEs named here apply. Pass $null for
    # $usersRight to give BUILTIN\Users no access at all.
    #
    # Refuse to reuse a reparse point first. New-Item -Force is a no-op on an existing junction and
    # Get-Acl/Set-Acl follow it, so an unprivileged process could pre-create this name pointing at a
    # directory it owns and the hardening would land on that target while the link stayed writable.
    # Creating a directory junction needs no privilege, and the cache root is not hardened, so a
    # subdirectory of it is pre-creatable. Delete the link only, never recurse into its target.
    $existing = Get-Item $path -Force -ErrorAction SilentlyContinue
    if ($existing -and ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $existing.Delete() }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $a = Get-Acl $path
    $a.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($a.Access)) { $a.RemoveAccessRuleAll($rule) | Out-Null }
    foreach ($id in "NT AUTHORITY\SYSTEM", "BUILTIN\Administrators") {
        $a.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            $id, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")))
    }
    if ($usersRight) {
        $a.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            "BUILTIN\Users", $usersRight, "ContainerInherit,ObjectInherit", "None", "Allow")))
    }
    # Reset the owner too. An owner keeps WRITE_DAC implicitly whatever the DACL says, so a directory
    # pre-created by an unprivileged process could otherwise be re-granted write access afterwards.
    $a.SetOwner((New-Object System.Security.Principal.NTAccount("NT AUTHORITY\SYSTEM")))
    Set-Acl -Path $path -AclObject $a
}


function Split-S3Uri([string]$uri) {
    if ($uri -notmatch '^s3://([^/]+)/(.+)$') { throw "bad s3 uri: $uri" }
    return @{ Bucket = $Matches[1]; Key = $Matches[2] }
}

function Test-S3Object([string]$uri) {
    # A non-zero exit means "not found" OR throttling, a transient network error, or a missing
    # permission, and callers treat a false answer as authorization to cold-install or to take over a
    # token. Retry anything that is not a clean 404 before reporting absence, so a 503 SlowDown during
    # a fleet-wide boot does not send every worker down the cold path over the same published zip.
    $p = Split-S3Uri $uri
    $errFile = "$SCRATCH\head-err.txt"
    foreach ($attempt in 1..3) {
        cmd /c "aws s3api head-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" >nul 2>`"$errFile`""
        if ($LASTEXITCODE -eq 0) { cmd /c exit 0; return $true }
        $err = ((Get-Content $errFile -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
        cmd /c exit 0
        # 403 counts as absent too, not just 404. S3 only returns 404 from HeadObject for a missing key
        # when the caller holds s3:ListBucket on the bucket, so with a prefix-scoped object grant the
        # ordinary "no zip yet" case arrives as 403. Retrying that would add 15s and a warning to every
        # poll of the WAIT loop and read like a permissions fault when nothing is wrong.
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

function Get-S3ObjectAgeMinutes([string]$uri) {
    $p = Split-S3Uri $uri
    $out = cmd /c "aws s3api head-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --query LastModified --output text 2>nul"
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    return [int]((Get-Date).ToUniversalTime() - [DateTime]::Parse($out).ToUniversalTime()).TotalMinutes
}

function Write-TokenBody([string]$path) {
    # JSON rather than positional fields, and WriteAllText rather than Out-File. Out-File wraps at the
    # host buffer width, which is 80 when there is no host UI as under the host-config runner, so a
    # longer body would split across lines and the holder parse would read a wrapped remainder. A
    # worker would then refuse to release its own token and strand the fleet until it aged out.
    $json = @{ claimedAt = (Get-Date).ToUniversalTime().ToString('o'); holder = $env:COMPUTERNAME } |
            ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-TokenHolder($body) {
    # Returns the holder name, or $null when the body cannot be read or parsed. Callers treat $null as
    # "ownership unknown" and leave the token alone.
    $text = ($body | Out-String).Trim()
    if (-not $text) { return $null }
    try { return [string](($text | ConvertFrom-Json).holder) } catch { return $null }
}

function Test-OldCliError([string]$err) {
    # S3 shipped If-None-Match on PutObject in Aug 2024 and If-Match in Nov 2024, so a CLI can accept
    # the first and reject the second. Probing only --if-none-match would leave both conditional
    # overwrite paths failing while reporting a lost race. Any "Unknown options" from either form means
    # conditional writes are unavailable on this CLI.
    if ($err -match 'Unknown options') {
        $script:ConditionalWritesSupported = $false
        Write-Host "WARNING: this AWS CLI lacks conditional writes on put-object. Upgrade to 2.22 or newer."
        return $true
    }
    return $false
}

function Get-InstallClaim {
    # Atomic claim via conditional put (only one worker wins). Requires AWS CLI >= 2.22.
    $p = Split-S3Uri $TOKEN_URI
    $tmp = "$SCRATCH\pv-token.txt"
    # The holder in the body is what establishes ownership for Remove-InstallToken.
    Write-TokenBody $tmp
    cmd /c "aws s3api put-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --body `"$tmp`" --if-none-match `"*`" >nul 2>`"$SCRATCH\pv-token-err.txt`""
    if ($LASTEXITCODE -eq 0) { Write-Host "install token claimed (conditional)"; return $true }
    $err = ((Get-Content "$SCRATCH\pv-token-err.txt" -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
    if ($err -match 'PreconditionFailed|412') {
        Write-Host "token already held"
    } elseif ($err -match 'Unknown options') {
        # AWS CLI too old for --if-none-match. Degrade to a best-effort (racy) claim and warn.
        # Recorded so the stale-takeover path below refuses to run rather than racing.
        $script:ConditionalWritesSupported = $false
        Write-Host "WARNING: AWS CLI lacks --if-none-match; using racy token claim. Upgrade to CLI >= 2.22."
        if (-not (Test-S3Object $TOKEN_URI)) {
            cmd /c "aws s3 cp `"$tmp`" `"$TOKEN_URI`" >nul 2>&1"
            if ($LASTEXITCODE -eq 0) { Write-Host "install token claimed (racy fallback)"; return $true }
        }
        Write-Host "token already held (racy check)"
    } else {
        # Any other error is treated as "held" (fail safe: never run a second concurrent install).
        Write-Host "token claim error (treating as held): $err"
    }
    # Stale-token takeover. An unconditional put here would let every worker that crosses the
    # staleness threshold in the same 60s poll window win at once, which is the exact outcome the
    # token exists to prevent. Overwrite conditionally on the ETag observed a moment ago so only
    # the first writer succeeds and the losers keep waiting.
    if (-not $script:ConditionalWritesSupported) {
        # No safe takeover exists on an old CLI. Refusing is better than racing.
        Write-Host "token appears held; skipping stale takeover (AWS CLI lacks conditional writes)"
        return $false
    }
    $etag = (cmd /c "aws s3api head-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --query ETag --output text 2>nul")
    $etagOk = ($LASTEXITCODE -eq 0)      # capture before the cmd /c exit 0 below resets it
    cmd /c exit 0
    $etag = ([string]$etag).Trim()
    # --output text prints the string "None" with exit 0 when the query resolves to nothing. Passing
    # that to --if-match fails with a 412 that looks exactly like losing the race, so a worker would
    # log "takeover lost" forever and a crashed cold install would park the whole fleet.
    if (-not $etagOk -or -not $etag -or $etag -eq 'None') { return $false }
    $age = Get-S3ObjectAgeMinutes $TOKEN_URI
    if ($null -ne $age -and $age -gt $TOKEN_STALE_MIN -and -not (Test-S3Object $ZIP_URI)) {
        Write-Host "token stale (${age}m > ${TOKEN_STALE_MIN}m, no zip) - attempting takeover"
        # Quote the value explicitly instead of relying on head-object returning the ETag with its
        # own surrounding quotes, which every other interpolation in this script already does.
        $etagVal = $etag.Trim('"')
        $takeoverErr = "$SCRATCH\pv-takeover-err.txt"
        cmd /c "aws s3api put-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --body `"$tmp`" --if-match `"$etagVal`" >nul 2>`"$takeoverErr`""
        if ($LASTEXITCODE -eq 0) {
            cmd /c exit 0
            # The staleness and zip checks above are separate round trips, so a zip can be published
            # between them and this put. Grafting a payload that already exists beats starting the
            # cold install this claim would otherwise authorize.
            if (Test-S3Object $ZIP_URI) {
                Write-Host "zip appeared during takeover - releasing the token for the S3-WARM path"
                Remove-InstallToken
                return $false
            }
            Write-Host "stale token taken over"
            return $true
        }
        $tkErr = ((Get-Content $takeoverErr -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
        cmd /c exit 0
        # Distinguish an old CLI from a genuinely lost race. Reporting the former as the latter would
        # make every worker log "lost" forever while a crashed install parks the fleet.
        if (-not (Test-OldCliError $tkErr)) {
            Write-Host "takeover lost to another worker - continuing to wait"
        }
    }
    return $false
}

function Update-InstallToken {
    # Re-stamp the token so $TOKEN_STALE_MIN measures liveness rather than time since the claim.
    #
    # The write is conditional on the ETag observed before the body read. An unconditional put would
    # resurrect a token already taken over: a takeover landing between the read and the write would be
    # overwritten, leaving two workers cold-installing with the token naming only one of them. That is
    # the same race the takeover itself uses --if-match to avoid.
    $p = Split-S3Uri $TOKEN_URI
    if (-not $script:ConditionalWritesSupported) {
        # No safe re-stamp without conditional writes. Skipping is better than an unconditional put.
        Write-Host "skipping token refresh (AWS CLI lacks conditional writes)"
        return
    }
    $etag = (cmd /c "aws s3api head-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --query ETag --output text 2>nul")
    $etagOk = ($LASTEXITCODE -eq 0)
    cmd /c exit 0
    $etag = ([string]$etag).Trim()
    if (-not $etagOk -or -not $etag -or $etag -eq 'None') {
        Write-Host "WARNING: could not read the install token ETag - not refreshing"
        return
    }
    $body = cmd /c "aws s3 cp --no-progress `"$TOKEN_URI`" - 2>nul"
    $readOk = ($LASTEXITCODE -eq 0)
    cmd /c exit 0
    if (-not $readOk) { return }
    if ((Get-TokenHolder $body) -ne $env:COMPUTERNAME) {
        Write-Host "WARNING: install token is no longer held by this worker - not refreshing"
        return
    }
    $tmp = "$SCRATCH\pv-token.txt"
    Write-TokenBody $tmp
    $refreshErr = "$SCRATCH\pv-refresh-err.txt"
    cmd /c "aws s3api put-object --bucket `"$($p.Bucket)`" --key `"$($p.Key)`" --body `"$tmp`" --if-match `"$($etag.Trim('"'))`" >nul 2>`"$refreshErr`""
    $failed = ($LASTEXITCODE -ne 0)
    $rfErr = ((Get-Content $refreshErr -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' ').Trim()
    cmd /c exit 0
    if ($failed -and -not (Test-OldCliError $rfErr)) {
        Write-Host "WARNING: install token refresh lost to a concurrent takeover - not extending it"
    }
}

function Remove-InstallToken {
    # Release only a token this worker owns. Get-InstallClaim returns $true both for a won
    # conditional put and for a stale takeover, and an unconditional delete here would let a
    # worker drop a token that a different worker has since claimed, reopening the window for a
    # second concurrent install.
    # --no-progress matters here. Without it the CLI writes a "download: s3://... to -" line to
    # stdout alongside the body, and the holder parse below could land on "-" instead of a hostname,
    # which would make a worker refuse to release its own token.
    $body = cmd /c "aws s3 cp --no-progress `"$TOKEN_URI`" - 2>nul"
    $readOk = ($LASTEXITCODE -eq 0)      # capture before the cmd /c exit 0 below resets it
    cmd /c exit 0
    if (-not $readOk) {
        # Throttling, a transient network error, or a missing s3:GetObject on the token key all land
        # here. Ownership cannot be established, so leave the token alone. Waiting out
        # $TOKEN_STALE_MIN once costs less than deleting a token another worker is holding.
        Write-Host "WARNING: could not read the install token to verify ownership - leaving it in place"
        return
    }
    # Exact comparison on a parsed field. A substring match would treat a token held by EC2AMAZ-ABC123
    # as belonging to EC2AMAZ-ABC12, which is the cross-worker deletion this check exists to stop.
    $holder = Get-TokenHolder $body
    if (-not $holder) {
        Write-Host "WARNING: install token body did not parse - leaving it in place"
        return
    }
    if ($holder -ne $env:COMPUTERNAME) {
        Write-Host "not releasing install token: held by $holder"
        return
    }
    cmd /c "aws s3 rm `"$TOKEN_URI`" >nul 2>&1"
    cmd /c exit 0
}

# --- Cache root: PV when available, local disk otherwise ---
$MOUNT = [Environment]::GetEnvironmentVariable("DEADLINE_PERSISTENT_MOUNT", "Machine")
$HAS_PV = -not [string]::IsNullOrEmpty($MOUNT)
$CACHE_ROOT = if ($HAS_PV) { $MOUNT } else { $LOCAL_CACHE_ROOT }
$CACHE_ROOT = $CACHE_ROOT.TrimEnd('\')
# DEADLINE_PERSISTENT_MOUNT is commonly a bare drive letter such as "D:", and a bare drive letter is
# drive-RELATIVE in PowerShell: "D:" resolves to the current directory on D:, not to D:\. Anything
# that passes the root itself to a cmdlet has to use the explicit form, so derive it once here.
$CACHE_DIR = if ($CACHE_ROOT -match '^[A-Za-z]:$') { "${CACHE_ROOT}\" } else { $CACHE_ROOT }
New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null
Write-Host "Cache root: $CACHE_DIR (persistent volume: $HAS_PV)"
Write-Host "Cache generation: $CACHE_GENERATION"

# Built by string interpolation on purpose. "$CACHE_ROOT\Software" is already absolute even when
# $CACHE_ROOT is a bare drive letter, and unlike Join-Path it never consults the PowerShell provider,
# so it cannot throw DriveNotFound if the volume is not mounted yet.
$SW      = "$CACHE_ROOT\Software"
$DATA    = "$CACHE_ROOT\SoftwareData"
$REGROOT = "$CACHE_ROOT\SoftwareRegistry"
$GRAFT   = "$REGROOT\graft"
# Inside the hardened registry tree rather than at the cache root. It is the only gate on the warm
# path, so a forgeable state file would let an unprivileged task steer which boot path runs next.
$STATE   = "$REGROOT\.install-state.json"
$SETUPDIR = "$CACHE_ROOT\installers"
# Transient multi-GB zip. Kept out of the cache root because the root cannot be hardened (it may be a
# volume root) and the zip is extracted as SYSTEM, so a writable location would let an unprivileged
# task swap it between download and extract and land content in the registry graft.
$STAGING = "$CACHE_ROOT\staging"
$ZIPLOCAL = "$STAGING\pv-payload.zip"
# Scratch files for the token body and captured stderr. Not $env:TEMP: as SYSTEM that is
# C:\Windows\Temp, which any authenticated user can write, and the token body written there is passed
# straight to put-object. An attacker winning that window could put a different hostname in the token
# and make the real holder refuse to release or refresh its own claim.
$SCRATCH = "$CACHE_ROOT\scratch"

# Harden the scratch directory before anything writes into it or touches S3. Both the token body and
# the captured stderr that drives the claim logic live here, so it has to come before any other
# directory. Placed after the assignments above for the obvious reason that it needs $SCRATCH set.
Protect-Dir $SCRATCH $null
# Fail loudly rather than degrade. A cmd redirect into a missing directory returns non-zero with no
# output, which Get-InstallClaim reads as an unrecognized error and treats as "token held", so a whole
# cold fleet would wait for a zip nobody is building.
if (-not (Test-Path $SCRATCH)) { throw "scratch directory $SCRATCH was not created" }

function Protect-PayloadDirs {
    # Creates the graft directory as well as hardening the trees, so "the payload trees are protected"
    # and "the directory the .reg files land in exists and is protected" are one operation with one
    # contract. Keeping them separate meant a caller could harden the trees without the graft, which is
    # what left it inheriting the cache-root ACL for a whole cold boot.
    # Harden the payload directories, deliberately NOT the cache root. The root can be a persistent
    # volume drive root, and stripping inherited ACEs from a whole volume would change access for
    # everything else stored on it. These paths are always absolute, which also avoids the
    # drive-relative pitfall above.
    #
    # Why this matters at all: C:\Program Files\Autodesk is a junction into this tree and NTFS
    # evaluates the target's ACL rather than the link's, so without this an unprivileged render task
    # could replace a binary here, or drop a .reg file that Import-InstallerState imports as SYSTEM on
    # the next boot. On a persistent volume that tampering survives reboots and reaches the
    # farm-global zip through the PV-WARM seed.
    # Render tasks read and execute the install. They never need to modify it.
    foreach ($d in @($SW, $REGROOT)) {
        Protect-Dir $d "ReadAndExecute"
        Write-Host "Hardened $d (SYSTEM/Administrators full, Users read-only)"
    }
    # SoftwareData is the exception. C:\ProgramData\Autodesk is junctioned into it, and 3ds Max plus
    # the Autodesk licensing stack write license state, telemetry, and per-run logs there. Denying
    # that would not fail Test-Render, because 3dsmaxbatch.exe -help writes nothing, so it would
    # surface later as licence checkout or scene-load errors on every task on every worker.
    Protect-Dir $DATA "Modify"
    Write-Host "Hardened $DATA (Users modify - Autodesk writes license and log state there)"
    # The graft lives inside the hardened registry tree, and the .reg files written into it are
    # imported as SYSTEM, so it must exist and be protected before anything can write there.
    New-Item -ItemType Directory -Force -Path $GRAFT | Out-Null
}

$junctions = @(
    @{ Link = "C:\Program Files\Autodesk";                           Target = "$SW\Autodesk" }
    @{ Link = "C:\ProgramData\Autodesk";                             Target = "$DATA\Autodesk" }
    @{ Link = "C:\Program Files\Common Files\Autodesk Shared";       Target = "$SW\AutodeskShared" }
    @{ Link = "C:\Program Files (x86)\Common Files\Autodesk Shared"; Target = "$SW\AutodeskSharedX86" }
)

function Initialize-Junctions([bool]$CreateTargets) {
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
        if ($CreateTargets) { New-Item -ItemType Directory -Path $j.Target -Force | Out-Null }
        New-Item -ItemType Junction -Path $j.Link -Target $j.Target | Out-Null
        Write-Host "Junction: $($j.Link) -> $($j.Target)"
    }
    Protect-PayloadDirs
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
        $svc = Get-CimInstance Win32_Service -Filter "Name='$s'"
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
            # WriteAllText, not Out-File, for the reason given in Write-TokenBody: Out-File wraps at
            # the host buffer width, 80 with no host UI, and PathName is a full quoted command line
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
        cmd /c "reg.exe export `"HKLM\SOFTWARE\dotnet`" `"$graftNew\hklm-dotnet.reg`" /y >nul 2>&1"
        cmd /c "reg.exe export `"HKLM\SOFTWARE\Wow6432Node\dotnet`" `"$graftNew\hklm-wow-dotnet.reg`" /y >nul 2>&1"
        cmd /c exit 0
        Write-Host "Captured .NET Core runtime payload + registry"
    }
    Invoke-Native "reg.exe export `"HKLM\SOFTWARE\Autodesk`" `"$graftNew\hklm-autodesk.reg`" /y" "reg export Autodesk"
    Invoke-Native "reg.exe export `"HKLM\SOFTWARE\Wow6432Node\Autodesk`" `"$graftNew\hklm-wow-autodesk.reg`" /y" "reg export WOW Autodesk"
    foreach ($cls in "3dsmax","3dschr","3dsifl","3dsms","3dsmxp","3dsmcr",".max") {
        cmd /c "reg.exe export `"HKLM\SOFTWARE\Classes\$cls`" `"$graftNew\cls-$($cls -replace '\.','_').reg`" /y >nul 2>&1"
    }
    cmd /c exit 0
    # Swap in the completed capture. Everything above has succeeded by this point, so the previous
    # graft is only discarded once there is a full replacement for it.
    if (Test-Path $GRAFT) { cmd /c "rmdir /s /q `"$GRAFT`" >nul 2>&1"; cmd /c exit 0 }
    if (Test-Path $GRAFT) { throw "could not replace the previous registry graft at $GRAFT" }
    Move-Item $graftNew $GRAFT -Force
    Write-Host "Registry graft exported"
}

function Import-InstallerState {
    Invoke-Robocopy "$SW\MacrovisionShared" "C:\Program Files\Common Files\Macrovision Shared"
    Invoke-Robocopy "$DATA\FLEXnet" "C:\ProgramData\FLEXnet"
    if (Test-Path "$SW\dotnet") {
        Invoke-Robocopy "$SW\dotnet" "C:\Program Files\dotnet"
        Write-Host "Restored .NET Core runtime"
    }
    foreach ($regFile in Get-ChildItem "$GRAFT\*.reg" -ErrorAction SilentlyContinue) {
        Invoke-Native "reg.exe import `"$($regFile.FullName)`"" "reg import $($regFile.Name)"
        Write-Host "Imported $($regFile.Name)"
    }
    foreach ($file in Get-ChildItem "$GRAFT\services\*.json" -ErrorAction SilentlyContinue) {
        $svc = Get-Content $file.FullName -Raw | ConvertFrom-Json
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
            cmd /c "sc.exe create `"$($svc.Name)`" binPath= $bin start= $startType $objArg DisplayName= `"$($svc.DisplayName)`" >nul"
            if ($LASTEXITCODE -ne 0) { Write-Host "WARNING: sc.exe create $($svc.Name) returned $LASTEXITCODE" } else { Write-Host "Registered service: $($svc.Name) as $($svc.StartName)" }
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
    # Setup.exe is downloaded here and then run as SYSTEM, so the staging area must not be writable by
    # anything unprivileged. It would inherit the cache-root ACL otherwise, which on the
    # no-persistent-volume path lets Authenticated Users modify it, and a render task could swap
    # Setup.exe or a DLL it loads from its own directory during the multi-GB download. No
    # BUILTIN\Users ACE at all, since nothing unprivileged needs to read the staging area.
    Protect-Dir $SETUPDIR $null
    $dl = Get-Date
    Invoke-Native "aws s3 cp --no-progress `"$3DS_MAX_INSTALLER_ZIP_S3_URI`" `"$SETUPDIR\3dsmax.zip.part`"" "installer download"
    Move-Item "$SETUPDIR\3dsmax.zip.part" "$SETUPDIR\3dsmax.zip" -Force
    Write-Duration $dl "Download"
    # Re-stamp the token after each long step rather than only at the end of the install. Other workers
    # judge liveness by the token's age, so without this the age reflects "time since I claimed it" and
    # a healthy holder is treated as dead part-way through, letting a second worker start a concurrent
    # cold install into the same cache root. Each call is a single conditional S3 write and does not
    # pause anything.
    Update-InstallToken
    $ex = Get-Date
    Expand-Archive "$SETUPDIR\3dsmax.zip" "$SETUPDIR\extracted" -Force
    Write-Duration $ex "Extract"
    Update-InstallToken
    $setup = Get-ChildItem -Path "$SETUPDIR\extracted" -Filter "Setup.exe" -Recurse | Select-Object -First 1
    if (-not $setup) { throw "Setup.exe not found in installer archive" }
    $inst = Get-Date
    $p = Start-Process -FilePath $setup.FullName -ArgumentList "-q" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Setup.exe failed: $($p.ExitCode)" }
    Write-Duration $inst "Install (3ds Max)"
    Update-InstallToken
    if (-not (Test-Path "$MAX_ROOT\3dsmaxbatch.exe")) { throw "3dsmaxbatch.exe missing after install" }
}

function Install-Pencil {
    if (-not $PENCILPLUS_INSTALLER_S3_URI) { return }
    $leaf = Split-Path $PENCILPLUS_INSTALLER_S3_URI -Leaf
    $path = "$SETUPDIR\$leaf"
    Invoke-Native "aws s3 cp --no-progress `"$PENCILPLUS_INSTALLER_S3_URI`" `"$path`"" "Pencil+ download"
    # Inno Setup silent switches. Exit code not checked: code 5 also means "already installed".
    Start-Process -FilePath $path -ArgumentList $PENCIL_SILENT_ARGS -Wait -PassThru | Out-Null
    $found = Get-ChildItem "$MAX_ROOT\plugins" -Filter "*Pencil*" -ErrorAction SilentlyContinue
    if (-not $found) { throw "Pencil+ plugin not found in $MAX_ROOT\plugins after install" }
    Write-Host "Pencil+ installed"
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
    if ($PENCILPLUS_INSTALLER_S3_URI) {
        $found = Get-ChildItem "$MAX_ROOT\plugins" -Filter "*Pencil*" -ErrorAction SilentlyContinue
        if (-not $found) {
            throw "payload incomplete: Pencil+ is configured but no *Pencil* plugin exists under $MAX_ROOT\plugins"
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
    Protect-Dir $STAGING $null
    $zipLocal = $ZIPLOCAL
    if (Test-Path $zipLocal) { Remove-Item $zipLocal -Force }
    # The payload should contain no reparse points. Windows tar.exe descends into a directory junction
    # rather than recording it, which would duplicate the target content into the archive, and a
    # junction resolving at or above its own tree would make the walk cycle. Clear-PayloadDirs uses
    # rmdir /s /q on the assumption that Autodesk may create some, so log any found here rather than
    # letting a silent duplication through. Nothing has been observed on a real install yet.
    foreach ($tree in @($SW, $DATA, $REGROOT)) {
        if (-not (Test-Path $tree)) { continue }
        $links = @(Get-ChildItem $tree -Recurse -Force -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($links.Count -gt 0) {
            Write-Host "WARNING: $($links.Count) reparse point(s) under $tree will be followed by tar:"
            $links | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.FullName) -> $(@($_.Target) | Select-Object -First 1)" }
        }
    }
    $running = Stop-CapturedServices
    try {
        $t = Get-Date
        $rootFwd = $CACHE_ROOT.TrimEnd('\') + '/'
        # .install-state.json is not listed separately: it lives inside SoftwareRegistry now, so it travels
    # with that tree.
    # SoftwareData is the one payload tree an unprivileged render task can write, because
    # C:\ProgramData\Autodesk is junctioned into it and the Autodesk licensing stack needs write
    # access. Excluding ApplicationPlugins keeps that local exposure from becoming farm-wide: 3ds Max
    # loads .bundle packages from there on startup, so a task dropping one on the worker that happens
    # to win the seed claim would otherwise reach every worker that restores the published zip.
    Invoke-Tar "-a -cf `"$zipLocal`" -C `"$rootFwd`" --exclude `"SoftwareData/Autodesk/ApplicationPlugins`" Software SoftwareData SoftwareRegistry" "tar create"
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
    # Harden the staging directory before the download. The zip is extracted as SYSTEM straight into
    # the payload trees, including the registry graft that Import-InstallerState then reg imports, so
    # an unprivileged process able to swap it here would reach SYSTEM on this boot.
    Protect-Dir $STAGING $null
    Invoke-Native "aws s3 cp --no-progress `"$ZIP_URI`" `"$zipLocal`"" "zip download"
    Write-Duration $t "Zip download"
    # tar merges into the cache root, so the previous payload has to go first. Reachable with the
    # licensing services running: a PV-WARM graft that fails after Import-InstallerState started
    # them falls through to here, so Clear-PayloadDirs stops them before deleting.
    Clear-PayloadDirs
    # Harden the trees BEFORE extracting into them. tar does not carry NTFS ACLs, so directories it
    # creates inherit from the cache root, which is not hardened. That would leave $GRAFT writable by
    # unprivileged code for the length of a multi-GB extract, and Import-InstallerState then reg
    # imports whatever is in there as SYSTEM. Protect-PayloadDirs later changes the ACL but does not
    # remove anything that arrived through the window. tar runs as SYSTEM so the strict ACL is no
    # obstacle to the extract itself.
    Protect-PayloadDirs
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
            if (-not (Test-S3Object $ZIP_URI) -and (Get-InstallClaim)) {
                Write-Host "=== Seeding S3 zip from this volume (one-time) ==="
                # The token is released either way. Holding it after a failed seed would park every
                # other worker in WAIT for $TOKEN_STALE_MIN waiting for a zip that is not coming.
                # Remove-InstallToken only releases a token this worker still owns.
                try {
                    # Re-check now the token is held. A cold-installing worker can publish between
                    # the first check and the claim, and Publish-S3Zip overwrites the final key.
                    if (Test-S3Object $ZIP_URI) {
                        Write-Host "another worker published first - skipping seed"
                    } else {
                        # Re-capture registry and service state before tarring. Import-InstallerState
                        # has already run on this boot and the licensing services have been started,
                        # so the payload on disk has moved on from the capture the original cold
                        # install wrote. Re-exporting keeps the seeded zip internally consistent.
                        # -SkipHostLicensing keeps this host's FLEXnet trusted-storage out of the
                        # capture. Import-InstallerState already copied the payload's licensing state
                        # out to C:\ProgramData\FLEXnet and started the services, which then wrote
                        # host-specific activation data there. Re-exporting it would push one worker's
                        # licensing state to the whole farm, and because robocopy /E merges rather
                        # than mirrors it would accumulate across reboots.
                        Export-InstallerState -SkipHostLicensing
                        Publish-S3Zip
                        Write-Host "S3 zip seeded from this persistent volume (licensing state left as captured)"
                    }
                } finally { Remove-InstallToken }
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
        Remove-Item $STATE -Force -ErrorAction SilentlyContinue
        # Restore-S3Zip already removed the junction links through Clear-PayloadDirs. The cold path
        # recreates them, but this fall-through does not always reach it: losing the token claim below
        # leads to the WAIT loop, which can exit by throwing, leaving a persistent volume with the
        # Autodesk paths simply absent. Idempotent with the cold path's later call.
        try { Initialize-Junctions -CreateTargets $true } catch { Write-Host "WARNING: could not restore junctions: $_" }
    }
}

# S3-COLD (token-guarded, once per version farm-wide) or WAIT.
$claimed = Get-InstallClaim
if (-not $claimed) {
    Write-Host "=== WAIT: another worker is installing; polling for S3 zip ==="
    $deadline = (Get-Date).AddMinutes($WAIT_ZIP_MAX_MIN)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 60
        # No generation guard needed here. The zip key carries $CACHE_GENERATION, so any zip that
        # appears under it was built for this generation and is safe to graft.
        if (Test-S3Object $ZIP_URI) {
            Write-Host "zip appeared - taking S3-WARM path"
            try {
                Restore-S3Zip
                if (-not (Test-StateValid)) { throw "published zip does not match the configured installers" }
                Invoke-Graft
                Write-Duration $t0 "Total (waited + S3-warm)"
                exit 0
            } catch {
                # This catch rethrows into the top-level trap, so the script ends here. Clear-PayloadDirs
                # has already removed the junction links, and nothing further would recreate them.
                # On a persistent volume that state is durable and reads as "the Autodesk directories
                # vanished" rather than as a failed restore.
                try { Initialize-Junctions -CreateTargets $true } catch { Write-Host "WARNING: could not restore junctions: $_" }
                throw "waited for concurrent install but restore/graft failed: $_"
            }
        }
        if (Get-InstallClaim) { $claimed = $true; break }
    }
    if (-not $claimed) { throw "timed out waiting for concurrent install to publish the S3 zip" }
}

Write-Host "=== S3-COLD boot: installing and publishing the farm-global zip ==="
$tokenReleased = $false
try {
    # Re-check for a zip now the token is held. The gate that sent this worker here and the claim are
    # separate round trips, so the publisher can complete its aws s3 mv and release the token in
    # between. Grafting an existing payload beats a multi-hour install that would then overwrite the
    # zip other workers may already have grafted. The takeover path in Get-InstallClaim makes the same
    # check for the same reason.
    if (Test-S3Object $ZIP_URI) {
        Write-Host "zip was published while claiming the token - releasing it and restoring instead"
        Remove-InstallToken
        $tokenReleased = $true
        try {
            Restore-S3Zip
            if (-not (Test-StateValid)) { throw "published zip does not match the configured installers" }
            Invoke-Graft
        } catch {
            # Same reason as the WAIT-loop handler: Restore-S3Zip removed the junction links and the
            # token is already gone, so no cold install follows to recreate them. Without this the
            # worker exits with the Autodesk paths absent, durably so on a persistent volume.
            try { Initialize-Junctions -CreateTargets $true } catch { Write-Host "WARNING: could not restore junctions: $_" }
            throw
        }
        Write-Duration $t0 "Total (claimed then S3-warm)"
        exit 0
    }
    # Start from an empty payload. Two paths arrive here with a partly-populated tree: a stale
    # token takeover, where the previous holder crashed mid-install, and a failed S3-WARM restore
    # that leaves whatever the interrupted extract wrote. Setup.exe -q against a partial install of
    # the same version can report success without repairing it, because the MSI cache it consults
    # lives in C:\Windows\Installer and belongs to the worker that crashed. That would be captured
    # and published as the farm-global payload.
    Clear-PayloadDirs
    Initialize-Junctions -CreateTargets $true
    Install-3dsMax
    Update-InstallToken      # Install-3dsMax re-stamps internally; this covers Pencil+ and the capture
    Install-Pencil
    Export-InstallerState
    Set-EnvContract
    Install-Adaptor
    Write-StateFile
    Test-Render
    Write-Host "=== Publishing S3 zip ==="
    Update-InstallToken      # tar plus a multi-GB upload is the second long step
    try { Publish-S3Zip } catch { Write-Host "WARNING: S3 publish failed (non-fatal): $_" }
    # Reclaim the several-GB installer download/extraction; it is not part of the payload.
    # rmdir, not Remove-Item -Recurse, matching Install-3dsMax and Clear-PayloadDirs. This tree is the
    # unpacked contents of a customer-supplied installer zip, and Remove-Item descends into any
    # directory reparse point it finds there.
    cmd /c "rmdir /s /q `"$SETUPDIR`" >nul 2>&1"
    cmd /c exit 0
} finally {
    # Skip if the zip re-check above already released it. Calling again would read back nothing and
    # log "could not read the install token to verify ownership" on what was a fully successful path.
    if (-not $tokenReleased) { Remove-InstallToken }
}
Write-Duration $t0 "Total (cold install + capture + publish)"
exit 0
