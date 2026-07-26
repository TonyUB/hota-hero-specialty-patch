param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot
)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class HotaMemoryReader {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(
        IntPtr handle, IntPtr address, byte[] buffer, int size, out IntPtr read);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
'@

function Read-TargetMemory {
    param(
        [IntPtr]$Handle,
        [uint32]$Address,
        [int]$Size
    )
    $buffer = New-Object byte[] $Size
    $read = [IntPtr]::Zero
    $ok = [HotaMemoryReader]::ReadProcessMemory(
        $Handle, [IntPtr]([int64]$Address), $buffer, $Size, [ref]$read)
    if (-not $ok) {
        return $null
    }
    return ,$buffer
}

$resolvedRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$existing = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -like 'h3hota*' }
if ($existing) {
    throw 'An h3hota process is already running.'
}

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
    if (-not $process) {
        throw 'No game process survived to the inspection window.'
    }

    $process.Modules |
        Select-Object `
            ModuleName,
            @{Name = 'Base'; Expression = { '0x{0:X8}' -f $_.BaseAddress.ToInt64() }},
            ModuleMemorySize,
            FileName |
        Format-Table -AutoSize

    $handle = [HotaMemoryReader]::OpenProcess(0x410, $false, $process.Id)
    if ($handle -eq [IntPtr]::Zero) {
        throw 'OpenProcess failed.'
    }
    try {
        foreach ($entry in @(0x0043F620, 0x00441330)) {
            $entryBytes = Read-TargetMemory $handle $entry 8
            $relative = [BitConverter]::ToInt32($entryBytes, 1)
            [uint32]$stub = $entry + 5 + $relative
            $stubBytes = Read-TargetMemory $handle $stub 64
            [uint32]$hookInfo = [BitConverter]::ToUInt32($stubBytes, 2)
            $object = Read-TargetMemory $handle $hookInfo 64
            'ENTRY 0x{0:X8} STUB 0x{1:X8} INFO 0x{2:X8}' -f `
                $entry, $stub, $hookInfo
            'STUB ' + (($stubBytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
            'OBJECT ' + (($object | ForEach-Object { $_.ToString('X2') }) -join ' ')

            foreach ($callOffset in @(6, 20, 32)) {
                if ($stubBytes[$callOffset] -ne 0xE8) {
                    throw ('Expected CALL at generated-stub offset 0x{0:X2}.' -f $callOffset)
                }
                $callRelative = [BitConverter]::ToInt32($stubBytes, $callOffset + 1)
                [uint32]$callTarget = $stub + $callOffset + 5 + $callRelative
                $callCode = Read-TargetMemory $handle $callTarget 128
                if ($callCode) {
                    'CALL +0x{0:X2}->0x{1:X8}: {2}' -f `
                        $callOffset,
                        $callTarget,
                        (($callCode | ForEach-Object { $_.ToString('X2') }) -join ' ')
                    if (
                        $callOffset -eq 20 -and
                        $callCode[0] -eq 0xB8 -and
                        $callCode[5] -eq 0x2D -and
                        $callCode[10] -eq 0x35 -and
                        $callCode[15] -eq 0xFF -and
                        $callCode[16] -eq 0xE0
                    ) {
                        [uint32]$encoded = [BitConverter]::ToUInt32($callCode, 1)
                        [uint32]$subtract = [BitConverter]::ToUInt32($callCode, 6)
                        [uint32]$xor = [BitConverter]::ToUInt32($callCode, 11)
                        [uint32]$callback = (($encoded - $subtract) -bxor $xor)
                        $callbackCode = Read-TargetMemory $handle $callback 256
                        'CALLBACK 0x{0:X8}: {1}' -f `
                            $callback,
                            (($callbackCode | ForEach-Object { $_.ToString('X2') }) -join ' ')
                    }
                }
            }

            foreach ($offset in @(8, 12, 16, 20, 32, 36, 52)) {
                [uint32]$pointer = [BitConverter]::ToUInt32($object, $offset)
                $candidate = Read-TargetMemory $handle $pointer 64
                if ($candidate) {
                    'PTR +0x{0:X2}=0x{1:X8}: {2}' -f `
                        $offset,
                        $pointer,
                        (($candidate | ForEach-Object { $_.ToString('X2') }) -join ' ')
                }
            }
        }
    }
    finally {
        [HotaMemoryReader]::CloseHandle($handle) | Out-Null
    }
}
finally {
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    'RUNTIME_HOOK_PROCESS_STOPPED=1'
}
