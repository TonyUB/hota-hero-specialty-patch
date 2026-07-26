param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [Parameter(Mandatory = $true)]
    [string]$RuntimeReader
)

$ErrorActionPreference = 'Stop'
$resolvedPackage = (Resolve-Path -LiteralPath $PackageRoot).Path
$resolvedGame = (Resolve-Path -LiteralPath $GameRoot).Path
$resolvedReader = (Resolve-Path -LiteralPath $RuntimeReader).Path
$expectedFiles = @('h3hota.exe', 'h3hota HD.exe', 'HotA.dll')
$logFiles = @('hota_luck_firstdiag02.bin', 'hota_luck_firstdiag03.bin')
$backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) `
    ('hota_diag03_smoke_' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$preexistingLogs = @{}
$started = @()
$direct = $null

try {
    $running = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -like 'h3hota*' }
    if ($running) {
        throw 'An h3hota process is already running.'
    }

    foreach ($name in $expectedFiles) {
        $source = Join-Path $resolvedPackage $name
        $target = Join-Path $resolvedGame $name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Missing package file: $source"
        }
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            throw "Missing game file: $target"
        }
        Copy-Item -LiteralPath $target -Destination (Join-Path $backupRoot $name)
        'BEFORE {0} {1}' -f $name, (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
        Copy-Item -LiteralPath $source -Destination $target -Force
        'DIAG03 {0} {1}' -f $name, (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    }

    foreach ($name in $logFiles) {
        $target = Join-Path $resolvedGame $name
        $exists = Test-Path -LiteralPath $target -PathType Leaf
        $preexistingLogs[$name] = $exists
        if ($exists) {
            Copy-Item -LiteralPath $target -Destination (Join-Path $backupRoot $name)
        }
    }

    & 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $resolvedReader `
        -GameRoot $resolvedGame
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime hook reader failed with exit code $LASTEXITCODE"
    }

    $before = Get-Date
    $direct = Start-Process `
        -FilePath (Join-Path $resolvedGame 'h3hota.exe') `
        -WorkingDirectory $resolvedGame `
        -WindowStyle Hidden `
        -PassThru
    Start-Sleep -Seconds 10
    $started = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like 'h3hota*' -and
            $_.StartTime -ge $before.AddSeconds(-2)
        }
    if (-not $started) {
        throw 'Standard executable did not survive the smoke-test window.'
    }
    'STANDARD_SMOKE_SURVIVED=1'
}
finally {
    if ($direct) {
        Stop-Process -Id $direct.Id -Force -ErrorAction SilentlyContinue
    }
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($name in $expectedFiles) {
        $backup = Join-Path $backupRoot $name
        $target = Join-Path $resolvedGame $name
        if (Test-Path -LiteralPath $backup -PathType Leaf) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
            'RESTORED {0} {1}' -f $name, (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
        }
    }
    foreach ($name in $logFiles) {
        $backup = Join-Path $backupRoot $name
        $target = Join-Path $resolvedGame $name
        if ($preexistingLogs[$name]) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
        }
        elseif (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
    'ALL_GAME_FILES_RESTORED=1'
}
