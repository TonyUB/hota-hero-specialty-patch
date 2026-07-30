param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [ValidateSet('h3hota.exe', 'h3hota HD.exe')]
    [string]$ExecutableName
)

$ErrorActionPreference = 'Stop'
$resolvedPackage = (Resolve-Path -LiteralPath $PackageRoot).Path
$resolvedGame = (Resolve-Path -LiteralPath $GameRoot).Path
$relatives = @(
    'h3hota.exe',
    'h3hota HD.exe'
)
$optionalRelatives = @(
    '_HD3_Data\Compability\#hota15\UN32.DEF',
    '_HD3_Data\Compability\#hota15\UN44.DEF',
    'Data\HPS024DR.PCX'
)
foreach ($relative in $optionalRelatives) {
    if (Test-Path -LiteralPath (Join-Path $resolvedPackage $relative) -PathType Leaf) {
        $relatives += $relative
    }
}
$backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) `
    ('hota_scholar_smoke_' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$states = @{}
$launched = $null
$started = @()

try {
    $running = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like 'h3hota*' -and
            $_.Path -and
            $_.Path.StartsWith($resolvedGame, [System.StringComparison]::OrdinalIgnoreCase)
        }
    if ($running) { throw 'An h3hota process is already running in the selected game root.' }

    foreach ($relative in $relatives) {
        $source = Join-Path $resolvedPackage $relative
        $target = Join-Path $resolvedGame $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Missing package file: $source"
        }
        $exists = Test-Path -LiteralPath $target -PathType Leaf
        $states[$relative] = $exists
        if ($exists) {
            $backup = Join-Path $backupRoot $relative
            $backupParent = Split-Path -Parent $backup
            New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
            Copy-Item -LiteralPath $target -Destination $backup -Force
        }
        $targetParent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
        'INSTALLED {0} {1}' -f $relative, (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    }

    $before = Get-Date
    $launched = Start-Process `
        -FilePath (Join-Path $resolvedGame $ExecutableName) `
        -WorkingDirectory $resolvedGame `
        -WindowStyle Hidden `
        -PassThru
    try { $launched.WaitForInputIdle(15000) | Out-Null } catch { }
    Start-Sleep -Seconds 12
    $started = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like 'h3hota*' -and
            $_.StartTime -ge $before.AddSeconds(-2)
        }
    if (-not $started) {
        throw "$ExecutableName did not survive the startup-to-menu window."
    }
    $windowed = @($started | Where-Object { $_.MainWindowHandle -ne 0 })
    if (-not $windowed) {
        throw "$ExecutableName survived but did not create a main game window."
    }
    foreach ($process in $windowed) {
        'MAIN_WINDOW_READY executable={0} process={1} pid={2} handle=0x{3:X} title={4}' -f `
            $ExecutableName, $process.ProcessName, $process.Id, $process.MainWindowHandle.ToInt64(), $process.MainWindowTitle
    }
}
finally {
    if ($launched) {
        Stop-Process -Id $launched.Id -Force -ErrorAction SilentlyContinue
    }
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($relative in $relatives) {
        $target = Join-Path $resolvedGame $relative
        $backup = Join-Path $backupRoot $relative
        if ($states.ContainsKey($relative) -and $states[$relative]) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
            'RESTORED {0} {1}' -f $relative, (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
        }
        elseif (Test-Path -LiteralPath $target -PathType Leaf) {
            $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
            if (-not $resolvedTarget.StartsWith($resolvedGame, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove a file outside the game root: $resolvedTarget"
            }
            Remove-Item -LiteralPath $resolvedTarget -Force
            'REMOVED_NEW_FILE {0}' -f $relative
        }
    }
    Remove-Item -LiteralPath $backupRoot -Recurse -Force
    'ALL_GAME_FILES_RESTORED=1'
}
