param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot
)

$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class LuckRegionReader {
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
    if (-not [LuckRegionReader]::ReadProcessMemory(
        $Handle, [IntPtr]([int64]$Address), $buffer, $Size, [ref]$read)) {
        throw ('ReadProcessMemory failed at 0x{0:X8}' -f $Address)
    }
    return ,$buffer
}

function Write-Region {
    param([IntPtr]$Handle, [uint32]$Address, [int]$Size)
    $bytes = Read-Bytes $Handle $Address $Size
    'REGION 0x{0:X8} {1}' -f $Address, (($bytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
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
    $handle = [LuckRegionReader]::OpenProcess(0x410, $false, $process.Id)
    if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed.' }
    try {
        Write-Region $handle 0x0043F620 0x100
        Write-Region $handle 0x00441330 0x2C0
    }
    finally {
        [LuckRegionReader]::CloseHandle($handle) | Out-Null
    }
}
finally {
    foreach ($process in $started) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    'RUNTIME_HOOK_PROCESS_STOPPED=1'
}
