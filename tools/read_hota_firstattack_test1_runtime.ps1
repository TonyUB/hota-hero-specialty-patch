param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot
)

$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FirstAttackMemoryReader {
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
    if (-not [FirstAttackMemoryReader]::ReadProcessMemory(
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

$resolvedRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$existing = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like 'h3hota*' }
if ($existing) { throw 'An h3hota process is already running.' }

$started = @()
try {
    $before = Get-Date
    Start-Process `
        -FilePath (Join-Path $resolvedRoot 'h3hota HD.exe') `
        -WorkingDirectory $resolvedRoot `
        -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 12
    $started = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like 'h3hota*' -and
            $_.StartTime -ge $before.AddSeconds(-2)
        }
    $process = $started | Select-Object -First 1
    if (-not $process) { throw 'No game process survived to the inspection window.' }
    $handle = [FirstAttackMemoryReader]::OpenProcess(0x410, $false, $process.Id)
    if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed.' }
    try {
        Assert-RelativeJump $handle 0x004E39E8 0x006E7000
        Assert-RelativeJump $handle 0x00463B71 0x006E7500
        Assert-RelativeJump $handle 0x00478D70 0x006E7580
        Assert-RelativeJump $handle 0x00478B94 0x006E7600

        $hota = $process.Modules | Where-Object { $_.ModuleName -ieq 'hota.dll' } |
            Select-Object -First 1
        if (-not $hota) { throw 'HotA.dll was not loaded.' }
        [uint32]$base = $hota.BaseAddress.ToInt64()
        [uint32]$first = $base + 0x001392F0
        [uint32]$firstTarget = $base + 0x04692400
        Assert-RelativeJump $handle $first $firstTarget

        [uint32]$second = $base + 0x00129560
        $secondBytes = Read-Bytes $handle $second 6
        if ($secondBytes[0] -ne 0x68 -or $secondBytes[5] -ne 0xC3) {
            throw 'Callback 2 is not the expected relocated push/ret hook.'
        }
        [uint32]$secondTarget = [BitConverter]::ToUInt32($secondBytes, 1)
        [uint32]$expectedSecond = $base + 0x04692700
        if ($secondTarget -ne $expectedSecond) {
            throw ('Callback 2 targets 0x{0:X8}, expected 0x{1:X8}' -f `
                $secondTarget, $expectedSecond)
        }
        'HOOK 0x{0:X8}->0x{1:X8}' -f $second, $secondTarget
        'HD_RUNTIME_HOOKS_VERIFIED=1'
    }
    finally {
        [FirstAttackMemoryReader]::CloseHandle($handle) | Out-Null
    }
}
finally {
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    'RUNTIME_HOOK_PROCESS_STOPPED=1'
}
