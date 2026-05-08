<#
.SYNOPSIS
    Submit the ssh_to_smf_windows Deadline Cloud job: create an SSM hybrid activation and submit the bundle.

.DESCRIPTION
    Creates a one-time SSM hybrid activation with `aws ssm create-activation`, then submits
    the Windows job bundle via `deadline bundle submit` with the activation code and ID
    passed as job parameters.

    Prerequisites:
    - AWS CLI v2 configured with ssm:CreateActivation permission
    - An IAM role for SSM hybrid nodes (e.g. SSMServiceRole with AmazonSSMManagedInstanceCore)
    - Deadline Cloud CLI (`deadline`) installed and configured
    - A Windows worker in the target queue with setup/host_config.ps1 already applied

.PARAMETER FarmId
    Deadline Cloud farm ID, e.g. farm-abc123...

.PARAMETER QueueId
    Deadline Cloud queue ID, e.g. queue-xyz789...

.PARAMETER SessionMinutes
    How many minutes to keep the managed node registered and the job alive. Default 60.

.PARAMETER IamRole
    SSM hybrid-activation IAM role name. Default 'SSMServiceRole'.

.PARAMETER Region
    AWS region. Default 'us-west-2'.

.PARAMETER Show
    Print the full activation code instead of masking it.

.EXAMPLE
    .\submit.ps1 -FarmId farm-abc -QueueId queue-xyz

.EXAMPLE
    .\submit.ps1 -FarmId farm-abc -QueueId queue-xyz -SessionMinutes 120 -IamRole MySSMRole -Region us-east-1 -Show
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FarmId,
    [Parameter(Mandatory=$true)][string]$QueueId,
    [int]   $SessionMinutes = 60,
    [string]$IamRole        = 'SSMServiceRole',
    [string]$Region         = 'us-west-2',
    [switch]$Show
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host '=============================================================='
Write-Host 'SSM Managed Node (Windows) - Job Submission'
Write-Host '=============================================================='
Write-Host "Session:  $SessionMinutes minutes"
Write-Host "IAM Role: $IamRole"
Write-Host "Region:   $Region"
Write-Host "Farm:     $FarmId"
Write-Host "Queue:    $QueueId"
Write-Host ''

# --- Create SSM hybrid activation ---
Write-Host 'Creating SSM hybrid activation...'
$activationJson = aws ssm create-activation `
    --iam-role $IamRole `
    --registration-limit 1 `
    --default-instance-name 'deadline-worker-ssm-windows' `
    --region $Region `
    --output json
if ($LASTEXITCODE -ne 0) {
    throw "aws ssm create-activation failed with exit code $LASTEXITCODE"
}

$activation = $activationJson | ConvertFrom-Json
$code = $activation.ActivationCode
$id   = $activation.ActivationId
if (-not $code -or -not $id) {
    throw "Malformed activation response: $activationJson"
}

Write-Host 'Activation created:'
if ($Show) {
    Write-Host "  Code: $code"
} else {
    $prefix = $code.Substring(0, [Math]::Min(4, $code.Length))
    Write-Host "  Code: $prefix****"
}
Write-Host "  ID:   $id"
Write-Host ''

# --- Submit the Deadline Cloud job ---
Write-Host 'Submitting Deadline Cloud job...'
$bundleDir = Join-Path $scriptDir 'job'
deadline bundle submit $bundleDir `
    --farm-id  $FarmId `
    --queue-id $QueueId `
    --parameter "ActivationCode=$code" `
    --parameter "ActivationId=$id" `
    --parameter "AWS_REGION=$Region" `
    --parameter "SessionMinutes=$SessionMinutes"
if ($LASTEXITCODE -ne 0) {
    throw "deadline bundle submit failed with exit code $LASTEXITCODE"
}

Write-Host ''
Write-Host 'Job submitted. Check the Deadline Cloud console for the mi-* ID in the job log.'
Write-Host '=============================================================='
