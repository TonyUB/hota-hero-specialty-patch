[CmdletBinding()]
param(
    [string]$BaselinePath,
    [string]$ManifestPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($BaselinePath)) {
    $BaselinePath = Join-Path $PSScriptRoot '..\baselines\Patch_v1.8'
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $PSScriptRoot '..\baselines\Patch_v1.8_SHA256.txt'
}

$resolvedManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifestLines = [System.IO.File]::ReadAllLines($resolvedManifest, [System.Text.Encoding]::UTF8)

$archiveHashLine = $manifestLines |
    Where-Object { $_ -match '^[0-9a-fA-F]{64}$' } |
    Select-Object -First 1

if (-not $archiveHashLine) {
    throw "Archive SHA-256 is missing from manifest: $resolvedManifest"
}

$expectedEntries = foreach ($line in $manifestLines) {
    if ($line -match '^([0-9a-fA-F]{64})\s{2}(.+)$') {
        [pscustomobject]@{
            Sha256 = $matches[1].ToLowerInvariant()
            Path = $matches[2].Replace('\', '/')
        }
    }
}

if ($expectedEntries.Count -eq 0) {
    throw "No package entries found in manifest: $resolvedManifest"
}

function Get-StreamSha256 {
    param([Parameter(Mandatory = $true)][System.IO.Stream]$Stream)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash($Stream)
        return [System.BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

$resolvedBaseline = (Resolve-Path -LiteralPath $BaselinePath).Path
$failures = New-Object System.Collections.Generic.List[string]
$results = New-Object System.Collections.Generic.List[object]

if (Test-Path -LiteralPath $resolvedBaseline -PathType Leaf) {
    $actualArchiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedBaseline).Hash.ToLowerInvariant()
    $expectedArchiveHash = $archiveHashLine.ToLowerInvariant()

    if ($actualArchiveHash -ne $expectedArchiveHash) {
        $failures.Add("Archive hash mismatch: expected $expectedArchiveHash, got $actualArchiveHash")
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($resolvedBaseline)
    try {
        foreach ($expected in $expectedEntries) {
            $entry = $archive.GetEntry($expected.Path)
            if ($null -eq $entry) {
                $failures.Add("Missing ZIP entry: $($expected.Path)")
                $results.Add([pscustomobject]@{ Status = 'MISSING'; Path = $expected.Path; Sha256 = '' })
                continue
            }

            $stream = $entry.Open()
            try {
                $actual = Get-StreamSha256 -Stream $stream
            }
            finally {
                $stream.Dispose()
            }

            $status = if ($actual -eq $expected.Sha256) { 'OK' } else { 'MISMATCH' }
            if ($status -ne 'OK') {
                $failures.Add("Hash mismatch: $($expected.Path)")
            }
            $results.Add([pscustomobject]@{ Status = $status; Path = $expected.Path; Sha256 = $actual })
        }

        $expectedNames = @($expectedEntries | ForEach-Object { $_.Path })
        $extraEntries = @($archive.Entries |
            Where-Object { -not $_.FullName.EndsWith('/') -and $_.FullName -notin $expectedNames } |
            ForEach-Object { $_.FullName })
        foreach ($extra in $extraEntries) {
            $failures.Add("Unexpected ZIP entry: $extra")
        }
    }
    finally {
        $archive.Dispose()
    }

    Write-Host "Archive SHA-256: $actualArchiveHash"
}
elseif (Test-Path -LiteralPath $resolvedBaseline -PathType Container) {
    foreach ($expected in $expectedEntries) {
        $relativeWindowsPath = $expected.Path.Replace('/', '\')
        $target = Join-Path $resolvedBaseline $relativeWindowsPath

        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            $failures.Add("Missing file: $($expected.Path)")
            $results.Add([pscustomobject]@{ Status = 'MISSING'; Path = $expected.Path; Sha256 = '' })
            continue
        }

        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        $status = if ($actual -eq $expected.Sha256) { 'OK' } else { 'MISMATCH' }
        if ($status -ne 'OK') {
            $failures.Add("Hash mismatch: $($expected.Path)")
        }
        $results.Add([pscustomobject]@{ Status = $status; Path = $expected.Path; Sha256 = $actual })
    }

    $expectedNames = @($expectedEntries | ForEach-Object { $_.Path })
    $extraFiles = @(Get-ChildItem -LiteralPath $resolvedBaseline -Recurse -File | ForEach-Object {
        $_.FullName.Substring($resolvedBaseline.Length).TrimStart('\').Replace('\', '/')
    } | Where-Object { $_ -notin $expectedNames })
    foreach ($extra in $extraFiles) {
        $failures.Add("Unexpected file: $extra")
    }

    Write-Host 'Directory representation detected; validating all 12 internal files.'
    Write-Host "Trusted source ZIP SHA-256 from manifest: $($archiveHashLine.ToLowerInvariant())"
}
else {
    throw "Unsupported baseline path: $resolvedBaseline"
}

$results | Sort-Object Path | Format-Table -AutoSize

if ($failures.Count -gt 0) {
    throw ("Baseline verification failed:`n- " + ($failures -join "`n- "))
}

Write-Host "Baseline verification passed: $($results.Count) files matched."
