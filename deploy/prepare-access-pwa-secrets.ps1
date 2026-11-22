[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EnvFile,
    [string]$BootstrapCredentialFile,
    [switch]$Rotate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { return $null }
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=(.*)$") {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
                return $value.Substring(1, $value.Length - 2)
            }
            if ($value.Length -ge 2 -and $value.StartsWith("'") -and $value.EndsWith("'")) {
                return $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

function Set-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )
    $lines = if (Test-Path -LiteralPath $EnvFile) { @(Get-Content -LiteralPath $EnvFile) } else { @() }
    $updated = $false
    $result = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=") {
            $updated = $true
            "$Name=$Value"
        }
        else { $line }
    }
    if (-not $updated) { $result += "$Name=$Value" }
    Set-Content -LiteralPath $EnvFile -Value $result -Encoding utf8
}

function Test-IsConfigured {
    param([string]$Value)
    return -not [string]::IsNullOrWhiteSpace($Value) -and $Value -notmatch '^(replace-with|change-me)'
}

function New-RandomBytes {
    param([Parameter(Mandatory = $true)][int]$Count)
    $bytes = [byte[]]::new($Count)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return $bytes
}

function ConvertTo-Base64Url {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [switch]$KeepPadding
    )
    $encoded = [Convert]::ToBase64String($Bytes).Replace('+', '-').Replace('/', '_')
    return $KeepPadding ? $encoded : $encoded.TrimEnd('=')
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Arquivo .env.production nao encontrado."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $BootstrapCredentialFile) {
    $BootstrapCredentialFile = Join-Path $repositoryRoot ".private/bootstrap-credential.txt"
}

$existingDatabaseUrl = Get-DotEnvValue -Name "DATABASE_URL"
$migrationDatabaseUrl = Get-DotEnvValue -Name "MIGRATION_DATABASE_URL"
if (-not (Test-IsConfigured $migrationDatabaseUrl)) {
    if (-not (Test-IsConfigured $existingDatabaseUrl)) {
        throw "DATABASE_URL ou MIGRATION_DATABASE_URL precisa estar configurada antes desta preparacao."
    }
    Set-DotEnvValue -Name "MIGRATION_DATABASE_URL" -Value $existingDatabaseUrl
}

$runtimeUser = Get-DotEnvValue -Name "RUNTIME_DB_USER"
if (-not (Test-IsConfigured $runtimeUser)) {
    $runtimeUser = "vinance_runtime"
    Set-DotEnvValue -Name "RUNTIME_DB_USER" -Value $runtimeUser
}
if ($runtimeUser -notmatch '^[A-Za-z_][A-Za-z0-9_]{0,62}$') {
    throw "RUNTIME_DB_USER invalido."
}

$runtimePassword = Get-DotEnvValue -Name "RUNTIME_DB_PASSWORD"
if ($Rotate -or -not (Test-IsConfigured $runtimePassword)) {
    $runtimePassword = ConvertTo-Base64Url -Bytes (New-RandomBytes -Count 36)
    Set-DotEnvValue -Name "RUNTIME_DB_PASSWORD" -Value $runtimePassword
}
$databaseName = Get-DotEnvValue -Name "POSTGRES_DB"
if (-not (Test-IsConfigured $databaseName)) { throw "POSTGRES_DB ausente." }
$encodedRuntimePassword = [Uri]::EscapeDataString($runtimePassword)
Set-DotEnvValue -Name "RUNTIME_DATABASE_URL" -Value "postgresql+asyncpg://${runtimeUser}:${encodedRuntimePassword}@postgres:5432/${databaseName}"

$bootstrapHash = Get-DotEnvValue -Name "BOOTSTRAP_TOKEN_HASH"
if ($Rotate -or -not (Test-IsConfigured $bootstrapHash)) {
    $bootstrap = ConvertTo-Base64Url -Bytes (New-RandomBytes -Count 32)
    $digest = [System.Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($bootstrap))
    $bootstrapHash = [Convert]::ToHexString($digest).ToLowerInvariant()
    Set-DotEnvValue -Name "BOOTSTRAP_TOKEN_HASH" -Value $bootstrapHash

    $credentialDirectory = Split-Path -Parent $BootstrapCredentialFile
    New-Item -ItemType Directory -Force -Path $credentialDirectory | Out-Null
    Set-Content -LiteralPath $BootstrapCredentialFile -Value $bootstrap -NoNewline -Encoding utf8
    if ($IsWindows) {
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls $BootstrapCredentialFile /inheritance:r /grant:r "${identity}:(F)" *> $null
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel restringir o arquivo da credencial bootstrap." }
    }
    else {
        Get-Command chmod -ErrorAction Stop | Out-Null
        & chmod 600 -- $BootstrapCredentialFile
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel restringir o arquivo da credencial bootstrap." }
    }
}

$encryptionKey = Get-DotEnvValue -Name "PUSH_SUBSCRIPTION_ENCRYPTION_KEY"
if ($Rotate -or -not (Test-IsConfigured $encryptionKey)) {
    Set-DotEnvValue -Name "PUSH_SUBSCRIPTION_ENCRYPTION_KEY" -Value (ConvertTo-Base64Url -Bytes (New-RandomBytes -Count 32) -KeepPadding)
}

$vapidPublic = Get-DotEnvValue -Name "VAPID_PUBLIC_KEY"
$vapidPrivate = Get-DotEnvValue -Name "VAPID_PRIVATE_KEY"
if ($Rotate -or -not (Test-IsConfigured $vapidPublic) -or -not (Test-IsConfigured $vapidPrivate)) {
    # CreateFromFriendlyName works on both Windows PowerShell/.NET Framework
    # and PowerShell 7; the NamedCurves member is not exposed consistently.
    $curve = [System.Security.Cryptography.ECCurve]::CreateFromFriendlyName("nistP256")
    $ecdsa = [System.Security.Cryptography.ECDsa]::Create($curve)
    try {
        $parameters = $ecdsa.ExportParameters($false)
        $publicBytes = [byte[]]::new(1 + $parameters.Q.X.Length + $parameters.Q.Y.Length)
        $publicBytes[0] = 4
        [Array]::Copy($parameters.Q.X, 0, $publicBytes, 1, $parameters.Q.X.Length)
        [Array]::Copy($parameters.Q.Y, 0, $publicBytes, 1 + $parameters.Q.X.Length, $parameters.Q.Y.Length)
        Set-DotEnvValue -Name "VAPID_PUBLIC_KEY" -Value (ConvertTo-Base64Url -Bytes $publicBytes)
        # pywebpush accepts a base64url DER-encoded EC private key.
        Set-DotEnvValue -Name "VAPID_PRIVATE_KEY" -Value (ConvertTo-Base64Url -Bytes $ecdsa.ExportECPrivateKey())
    }
    finally { $ecdsa.Dispose() }
}

if (-not (Test-IsConfigured (Get-DotEnvValue -Name "VAPID_SUBJECT"))) {
    Set-DotEnvValue -Name "VAPID_SUBJECT" -Value "https://vinance.vinmedrado.com"
}
Set-DotEnvValue -Name "ACCESS_MODE" -Value "INVITE_ONLY"
Set-DotEnvValue -Name "REGISTRATION_ENABLED" -Value "false"
Set-DotEnvValue -Name "WEB_PUSH_ENABLED" -Value "true"

Write-Host "[VinanceOS] Segredos de Access/PWA preparados sem exibir valores." -ForegroundColor Green
if (Test-Path -LiteralPath $BootstrapCredentialFile) {
    Write-Host "[VinanceOS] Credencial bootstrap de uso unico armazenada em arquivo local protegido: $BootstrapCredentialFile" -ForegroundColor Yellow
}
