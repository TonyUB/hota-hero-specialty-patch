param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [switch]$RequireFixedPlusThree
)

$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FirstAttackTest2MemoryReader {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(
        IntPtr handle, IntPtr address, byte[] buffer, int size, out IntPtr read);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
'@

function Read-Bytes {
    param([IntPtr]$Handle, [uint32]$Address, [int]$Size)
    $buffer = New-Object byte[] $Size
    $read = [IntPtr]::Zero
    if (-not [FirstAttackTest2MemoryReader]::ReadProcessMemory(
        $Handle, [IntPtr]([int64]$Address), $buffer, $Size, [ref]$read)) {
        throw ('ReadProcessMemory failed at 0x{0:X8}' -f $Address)
    }
    return ,$buffer
}

function Assert-RelativeJump {
    param([IntPtr]$Handle, [uint32]$Address, [uint32]$ExpectedTarget)
    $bytes = Read-Bytes $Handle $Address 8
    if ($bytes[0] -ne 0xE9) {
        throw ('Expected E9 at 0x{0:X8}' -f $Address)
    }
    $relative = [BitConverter]::ToInt32($bytes, 1)
    [uint32]$target = $Address + 5 + $relative
    if ($target -ne $ExpectedTarget) {
        throw ('Jump 0x{0:X8} targets 0x{1:X8}, expected 0x{2:X8}' -f `
            $Address, $target, $ExpectedTarget)
    }
    'HOOK 0x{0:X8}->0x{1:X8}' -f $Address, $target
}

function Test-BytePattern {
    param([byte[]]$Data, [byte[]]$Pattern)
    for ($start = 0; $start -le $Data.Length - $Pattern.Length; $start++) {
        $match = $true
        for ($index = 0; $index -lt $Pattern.Length; $index++) {
            if ($Data[$start + $index] -ne $Pattern[$index]) {
                $match = $false
                break
            }
        }
        if ($match) { return $true }
    }
    return $false
}

$resolvedRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$existing = Get-Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.ProcessName -like 'h3hota*' -and
        $_.Path -and
        $_.Path.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)
    }
if ($existing) { throw 'An h3hota process is already running.' }

$started = @()
try {
    $before = Get-Date
    Start-Process `
        -FilePath (Join-Path $resolvedRoot 'h3hota HD.exe') `
        -WorkingDirectory $resolvedRoot `
        -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 10
    $started = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like 'h3hota*' -and
            $_.Path -and
            $_.Path.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            $_.StartTime -ge $before.AddSeconds(-2)
        }
    $process = $started | Select-Object -First 1
    if (-not $process) { throw 'No game process survived to the inspection window.' }
    $handle = [FirstAttackTest2MemoryReader]::OpenProcess(0x410, $false, $process.Id)
    if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed.' }
    try {
        Assert-RelativeJump $handle 0x004E39E8 0x006E7000
        Assert-RelativeJump $handle 0x00463B71 0x006E7500
        Assert-RelativeJump $handle 0x00478D70 0x006E7580
        Assert-RelativeJump $handle 0x00478B94 0x006E7600
        if ($RequireFixedPlusThree) {
            $gateBytes = Read-Bytes $handle 0x006E7000 0x200
            $fixedPattern = [byte[]](
                0xB8, 0x03, 0x00, 0x00, 0x00, 0x5F, 0x5E,
                0x89, 0xEC, 0x5D, 0xC2, 0x0C, 0x00
            )
            if (-not (Test-BytePattern $gateBytes $fixedPattern)) {
                throw 'Fixed Luck +3 return path is missing from the runtime wrapper.'
            }
            'FIXED_LUCK_PLUS_THREE_RUNTIME_VERIFIED=1'
        }

        $hota = $process.Modules | Where-Object { $_.ModuleName -ieq 'hota.dll' } |
            Select-Object -First 1
        if (-not $hota) { throw 'HotA.dll was not loaded.' }
        [uint32]$base = $hota.BaseAddress.ToInt64()
        [uint32]$roll = $base + 0x00133880
        [uint32]$wrapper = $base + 0x04692400
        Assert-RelativeJump $handle $roll $wrapper
        $wrapperBytes = Read-Bytes $handle $wrapper 6
        $expected = [byte[]](0x56, 0x57, 0x8B, 0x7C, 0x24, 0x10)
        for ($index = 0; $index -lt $expected.Length; $index++) {
            if ($wrapperBytes[$index] -ne $expected[$index]) {
                throw ('Unexpected Luck wrapper prologue at byte {0}' -f $index)
            }
        }
        'HOTA_BASE=0x{0:X8}' -f $base
        'HD_RUNTIME_HOOKS_VERIFIED=1'
    }
    finally {
        [FirstAttackTest2MemoryReader]::CloseHandle($handle) | Out-Null
    }
}
finally {
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    'RUNTIME_HOOK_PROCESS_STOPPED=1'
}
