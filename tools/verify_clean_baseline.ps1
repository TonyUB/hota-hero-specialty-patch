[CmdletBinding()]
param(
    [string]$BaselinePath,
    [string]$ManifestPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($BaselinePath)) {
    $BaselinePath = Join-Path $PSScriptRoot '..\baselines\hota180_clean'
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $PSScriptRoot '..\baselines\hota180_clean_SHA256.txt'
}

$resolvedBaseline = (Resolve-Path -LiteralPath $BaselinePath).Path
$resolvedManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$lines = [System.IO.File]::ReadAllLines($resolvedManifest, [System.Text.Encoding]::UTF8)
$results = New-Object System.Collections.Generic.List[object]
$failures = New-Object System.Collections.Generic.List[string]

foreach ($line in $lines) {
    if ($line -notmatch '^([0-9a-fA-F]{64})\s{2}(.+)$') {
        continue
    }

    $expected = $matches[1].ToLowerInvariant()
    $relative = $matches[2]
    $target = Join-Path $resolvedBaseline $relative

    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $results.Add([pscustomobject]@{ Status = 'MISSING'; Path = $relative; Sha256 = '' })
        $failures.Add("Missing file: $relative")
        continue
    }

    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    $status = if ($actual -eq $expected) { 'OK' } else { 'MISMATCH' }
    $results.Add([pscustomobject]@{ Status = $status; Path = $relative; Sha256 = $actual })
    if ($status -ne 'OK') {
        $failures.Add("Hash mismatch: $relative")
    }
}

if ($results.Count -eq 0) {
    throw "No hash entries found in manifest: $resolvedManifest"
}

$results | Sort-Object Path | Format-Table -AutoSize

if ($failures.Count -gt 0) {
    throw ("Clean baseline verification failed:`n- " + ($failures -join "`n- "))
}

Write-Host "Clean runtime baseline verification passed: $($results.Count) files matched."
