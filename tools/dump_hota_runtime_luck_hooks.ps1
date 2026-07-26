param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot
)

$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LuckHookReader {
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
    if (-not [LuckHookReader]::ReadProcessMemory(
        $Handle, [IntPtr]([int64]$Address), $buffer, $Size, [ref]$read)) {
        return $null
    }
    return ,$buffer
}

function Hex-Line {
    param([byte[]]$Bytes)
    return (($Bytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
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
    $handle = [LuckHookReader]::OpenProcess(0x410, $false, $process.Id)
    if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed.' }
    try {
        foreach ($entry in @(0x0043F63B, 0x0044151D)) {
            $entryBytes = Read-Bytes $handle $entry 8
            if (-not $entryBytes -or $entryBytes[0] -ne 0xE9) {
                throw ('Expected runtime E9 at 0x{0:X8}' -f $entry)
            }
            $relative = [BitConverter]::ToInt32($entryBytes, 1)
            [uint32]$stub = $entry + 5 + $relative
            $stubBytes = Read-Bytes $handle $stub 128
            'ENTRY 0x{0:X8} STUB 0x{1:X8}' -f $entry, $stub
            'STUB ' + (Hex-Line $stubBytes)

            for ($offset = 0; $offset -le 123; $offset++) {
                if ($stubBytes[$offset] -ne 0xE8) { continue }
                $callRelative = [BitConverter]::ToInt32($stubBytes, $offset + 1)
                [uint32]$callTarget = $stub + $offset + 5 + $callRelative
                $callCode = Read-Bytes $handle $callTarget 160
                if (-not $callCode) { continue }
                'CALL +0x{0:X2}->0x{1:X8}: {2}' -f `
                    $offset, $callTarget, (Hex-Line $callCode)
                if (
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
                    $callbackCode = Read-Bytes $handle $callback 320
                    if ($callbackCode) {
                        'CALLBACK 0x{0:X8}: {1}' -f $callback, (Hex-Line $callbackCode)
                    }
                }
            }
        }
    }
    finally {
        [LuckHookReader]::CloseHandle($handle) | Out-Null
    }
}
finally {
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    'RUNTIME_HOOK_PROCESS_STOPPED=1'
}
