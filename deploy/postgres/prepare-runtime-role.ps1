[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EnvFile,
    [string]$ProjectName = "vinance-phase-e-prod",
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)
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
    throw "Variavel obrigatoria ausente: $Name"
}

function Quote-SqlIdentifier {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -notmatch '^[A-Za-z_][A-Za-z0-9_]{0,62}$') {
        throw "Identificador PostgreSQL invalido."
    }
    return '"' + $Value.Replace('"', '""') + '"'
}

function Quote-SqlLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Arquivo de ambiente nao encontrado."
}

$runtimeUser = Get-DotEnvValue -Name "RUNTIME_DB_USER"
$runtimePassword = Get-DotEnvValue -Name "RUNTIME_DB_PASSWORD"
$migrationUser = Get-DotEnvValue -Name "POSTGRES_USER"
$databaseName = Get-DotEnvValue -Name "POSTGRES_DB"
$runtimeIdentifier = Quote-SqlIdentifier -Value $runtimeUser
$migrationIdentifier = Quote-SqlIdentifier -Value $migrationUser
$databaseIdentifier = Quote-SqlIdentifier -Value $databaseName
$runtimeLiteral = Quote-SqlLiteral -Value $runtimeUser

$composeOutput = @(& docker compose --project-name $ProjectName --env-file $EnvFile -f (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "docker-compose.production.yml") ps -q postgres 2>$null)
$composeExitCode = $LASTEXITCODE
$containerId = (($composeOutput | ForEach-Object { $_.ToString().Trim() }) -join "").Trim()
if ($composeExitCode -ne 0 -or $containerId -notmatch '^[0-9a-f]{12,64}$') {
    throw "Container PostgreSQL de producao nao foi identificado com seguranca."
}

if ($ValidateOnly) {
    $query = "SELECT CASE WHEN rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls THEN 'VALID' ELSE 'INVALID' END FROM pg_roles WHERE rolname = $runtimeLiteral;"
    $result = ($query | & docker exec -i $containerId psql -X -q -t -A -v ON_ERROR_STOP=1 -U $migrationUser -d $databaseName 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $result -ne "VALID") {
        throw "Papel de runtime ausente ou privilegiado em excesso."
    }
    Write-Host "[VinanceOS] Papel PostgreSQL de runtime validado: NOSUPERUSER/NOBYPASSRLS." -ForegroundColor Green
    exit 0
}

if ($runtimePassword.Length -lt 24) {
    throw "RUNTIME_DB_PASSWORD precisa ter pelo menos 24 caracteres."
}
$passwordLiteral = Quote-SqlLiteral -Value $runtimePassword

# SQL is sent through stdin so the password never appears in the process
# command line or normal command output.
$sql = @"
DO `$role`$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $runtimeLiteral) THEN
    CREATE ROLE $runtimeIdentifier LOGIN PASSWORD $passwordLiteral
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  ELSE
    ALTER ROLE $runtimeIdentifier WITH LOGIN PASSWORD $passwordLiteral
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END
`$role`$;
GRANT CONNECT ON DATABASE $databaseIdentifier TO $runtimeIdentifier;
GRANT USAGE ON SCHEMA public TO $runtimeIdentifier;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $runtimeIdentifier;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO $runtimeIdentifier;
ALTER DEFAULT PRIVILEGES FOR ROLE $migrationIdentifier IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $runtimeIdentifier;
ALTER DEFAULT PRIVILEGES FOR ROLE $migrationIdentifier IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO $runtimeIdentifier;
"@

$sql | & docker exec -i $containerId psql -X -q -v ON_ERROR_STOP=1 -U $migrationUser -d $databaseName *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao preparar o papel PostgreSQL de runtime."
}

& $PSCommandPath -EnvFile $EnvFile -ProjectName $ProjectName -ValidateOnly
