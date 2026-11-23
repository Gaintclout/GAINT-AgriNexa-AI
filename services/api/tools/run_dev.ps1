[CmdletBinding()]
param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8001,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$apiRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $apiRoot ".env"

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing services/api/.env. Create an authorized local development configuration first."
}

$createdJwtSecret = $false
$secretBytes = $null
$createdPhotoStorage = $false

try {
    if ([string]::IsNullOrWhiteSpace($env:AGRINEXA_PRIVATE_PHOTO_DIR)) {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw "LOCALAPPDATA is required when AGRINEXA_PRIVATE_PHOTO_DIR is not configured."
        }

        $env:AGRINEXA_PRIVATE_PHOTO_DIR = Join-Path `
            $env:LOCALAPPDATA `
            "GAINT AI Agri\private-photos"
        New-Item `
            -ItemType Directory `
            -Path $env:AGRINEXA_PRIVATE_PHOTO_DIR `
            -Force | Out-Null
        $createdPhotoStorage = $true
    }

    if ([string]::IsNullOrWhiteSpace($env:AGRINEXA_JWT_SECRET)) {
        $secretBytes = New-Object byte[] 48
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()

        try {
            $random.GetBytes($secretBytes)
        }
        finally {
            $random.Dispose()
        }

        $env:AGRINEXA_JWT_SECRET = [Convert]::ToBase64String($secretBytes)
        $createdJwtSecret = $true
        Write-Host "Using an ephemeral development JWT secret for this API process."
    }

    $arguments = @(
        "-m", "uvicorn", "app.main:app",
        "--env-file", ".env",
        "--host", $HostAddress,
        "--port", $Port.ToString()
    )

    if ($Reload) {
        $arguments += "--reload"
    }

    Push-Location $apiRoot
    try {
        & python @arguments
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($createdJwtSecret) {
        Remove-Item Env:AGRINEXA_JWT_SECRET -ErrorAction SilentlyContinue
    }

    if ($createdPhotoStorage) {
        Remove-Item Env:AGRINEXA_PRIVATE_PHOTO_DIR -ErrorAction SilentlyContinue
    }

    if ($null -ne $secretBytes) {
        [Array]::Clear($secretBytes, 0, $secretBytes.Length)
    }
}
