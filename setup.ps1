param(
    [switch] $SkipFfmpeg,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $SetupArgs = @()
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root

function Invoke-Checked {
    param([string] $Command, [string[]] $Arguments = @())
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

if (-not $SkipFfmpeg -and (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
        -not (Get-Command ffprobe -ErrorAction SilentlyContinue))) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Invoke-Checked "winget" @("install", "--id", "Gyan.FFmpeg.Shared", "-e", "--accept-source-agreements", "--accept-package-agreements")
    } else {
        throw "FFmpeg/FFprobe are missing. Install FFmpeg or install winget, then rerun setup.ps1."
    }
}

$uvCommand = $null
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -ne $uv) {
    $uvCommand = $uv.Source
} else {
    if (-not (Get-Command irm -ErrorAction SilentlyContinue)) {
        throw "PowerShell's Invoke-RestMethod (irm) is required to install uv."
    }
    irm https://astral.sh/uv/install.ps1 | iex
    $candidate = Join-Path $HOME ".local\bin\uv.exe"
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $uvCommand = $candidate
    } else {
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if ($null -ne $uv) {
            $uvCommand = $uv.Source
        }
    }
}
if ($null -eq $uvCommand) {
    throw "uv could not be found after installation. Open a new PowerShell window and rerun setup.ps1."
}

# uv selects the compatible Python available on this machine. The project
# supports Python 3.10 and newer; do not force a particular minor release.
Invoke-Checked $uvCommand @("sync", "--locked", "--extra", "all")
Invoke-Checked (Join-Path $Root ".venv\Scripts\python.exe") (@("-m", "ziv", "setup") + $SetupArgs)
