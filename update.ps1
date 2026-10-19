[CmdletBinding()]
param(
    [switch] $SkipGit,
    [switch] $SkipDependencies,
    [switch] $Doctor,
    [string] $Branch = "main",
    [string] $Python = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -LiteralPath $Root

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)] [string] $Command,
        [Parameter(Mandatory = $false)] [string[]] $Arguments = @()
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

function Find-CommandPath {
    param([Parameter(Mandatory = $true)] [string] $Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

if (-not $SkipGit) {
    $git = Find-CommandPath "git"
    if ($null -eq $git) {
        throw "Git was not found. Install Git for Windows or rerun with -SkipGit."
    }

    $currentBranch = (& $git rev-parse --abbrev-ref HEAD).Trim()
    if ($currentBranch -ne $Branch) {
        throw "The current branch is '$currentBranch', not '$Branch'. Switch branches or pass -Branch <name>."
    }

    $changes = @(& $git status --porcelain)
    if ($changes.Count -gt 0) {
        throw "The working tree has local changes. Commit or stash them before updating."
    }

    Write-Host "[ziv] Pulling the latest $Branch changes..."
    Invoke-Checked $git @("pull", "--ff-only", "origin", $Branch)
}

if (-not $SkipDependencies) {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        $pythonCommand = $null
        $pythonArguments = @()
        if ($Python) {
            $pythonCommand = $Python
        } else {
            $pyLauncher = Find-CommandPath "py"
            $pythonExecutable = Find-CommandPath "python"
            if ($null -ne $pyLauncher) {
                $pythonCommand = $pyLauncher
                $pythonArguments = @("-3.11")
            } elseif ($null -ne $pythonExecutable) {
                $pythonCommand = $pythonExecutable
            }
        }

        if ($null -eq $pythonCommand) {
            throw "Python 3.11+ was not found. Install it from python.org or the Microsoft Store."
        }

        Write-Host "[ziv] Creating the .venv environment..."
        Invoke-Checked $pythonCommand ($pythonArguments + @("-m", "venv", ".venv"))
    }

    $uv = Find-CommandPath "uv"
    if ($null -ne $uv) {
        Write-Host "[ziv] Updating the lockfile and syncing all project extras with uv..."
        Invoke-Checked $uv @("lock", "--upgrade")
        Invoke-Checked $uv @("sync", "--all-extras")
    } else {
        Write-Host "[ziv] uv was not found; updating the project with pip..."
        Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
        Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "-e", ".[all,dev]")
    }
}

Write-Host "[ziv] Update complete."
if ($Doctor) {
    & (Join-Path $Root "ziv.ps1") doctor
    exit $LASTEXITCODE
}

Write-Host "[ziv] Try: .\ziv.ps1 --help"
