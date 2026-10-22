# Deliberately use a plain script: advanced/common parameters consume CLI flags.
$ZivArgs = @($args)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

$Python = $null
$PythonCandidates = @()
if ($env:VIRTUAL_ENV) {
    $PythonCandidates += Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
}
$PythonCandidates += @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe")
)
foreach ($candidate in $PythonCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $Python = $candidate
        break
    }
}
if ($null -eq $Python) {
    Write-Error "No project Python environment found (.venv or venv). Run .\setup.ps1 first." -ErrorAction Continue
    exit 1
}

# Set only the child's directory, leaving the caller's PowerShell location alone.
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $Python
$startInfo.WorkingDirectory = $Root
$startInfo.UseShellExecute = $false
$nativeArgs = @("-m", "ziv") + $ZivArgs
if ($null -ne $startInfo.PSObject.Properties["ArgumentList"]) {
    foreach ($argument in $nativeArgs) {
        $startInfo.ArgumentList.Add([string] $argument)
    }
} else {
    # Windows PowerShell 5.1 lacks ArgumentList. Quote for Python's Windows argv
    # parser, retaining empty values, embedded quotes, and trailing backslashes.
    $quotedArgs = foreach ($argument in $nativeArgs) {
        '"' + (([string] $argument) -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
    }
    $startInfo.Arguments = $quotedArgs -join " "
}

try {
    $process = [System.Diagnostics.Process]::Start($startInfo)
    try {
        $process.WaitForExit()
        $exitCode = $process.ExitCode
    } finally {
        $process.Dispose()
    }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
exit $exitCode
