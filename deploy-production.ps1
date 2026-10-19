[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("validate", "frontend", "backend", "all")]
    [string]$Target = "validate",

    [switch]$ApplyMigrations
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectName = "vinance-phase-e-prod"
$RepositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $RepositoryRoot "docker-compose.production.yml"
$EnvFile = Join-Path $RepositoryRoot ".env.production"
$ComposeBase = @(
    "--project-name", $ProjectName,
    "--env-file", $EnvFile,
    "-f", $ComposeFile
)
$PublicOrigin = "https://vinance.vinmedrado.com"
$PublicHost = "vinance.vinmedrado.com"

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[VinanceOS] $Message" -ForegroundColor Cyan
}

function Invoke-Compose {
    param([Parameter(Mandatory = $true)][string[]]$ComposeArguments)

    & docker compose @ComposeBase @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose falhou durante: $($ComposeArguments[0])."
    }
}

function Invoke-ComposeCapture {
    param([Parameter(Mandatory = $true)][string[]]$ComposeArguments)

    # Windows PowerShell promotes native stderr records to terminating errors
    # when ErrorActionPreference is Stop. Docker Compose writes normal progress
    # messages (for example, "Container ... Creating") to stderr, so capture
    # those messages without mistaking them for a failed command. The native
    # process exit code remains the authoritative success signal.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $result = @(& docker compose @ComposeBase @ComposeArguments 2>&1)
        $composeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($composeExitCode -ne 0) {
        throw "Docker Compose falhou durante uma verificacao segura. Nenhum segredo foi exibido."
    }
    return $result
}

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=(.*)$") {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2 -and $value.StartsWith("'") -and $value.EndsWith("'")) {
                return $value.Substring(1, $value.Length - 2).Replace("\'", "'")
            }
            if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
                return $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    throw "Variavel obrigatoria ausente em .env.production: $Name"
}

function Assert-Prerequisites {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw ".env.production nao existe. O deploy foi abortado antes de qualquer alteracao."
    }
    if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
        throw "docker-compose.production.yml nao foi encontrado."
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker nao esta disponivel no PATH."
    }

    & docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Engine nao esta acessivel."
    }

    $registrationEnabled = (Get-DotEnvValue -Name "REGISTRATION_ENABLED").Trim().ToLowerInvariant()
    if ($registrationEnabled -ne "false") {
        throw "REGISTRATION_ENABLED deve permanecer false em producao."
    }

    $corsOrigins = @((Get-DotEnvValue -Name "CORS_ORIGINS").Split(",") | ForEach-Object { $_.Trim() })
    if ($PublicOrigin -notin $corsOrigins) {
        throw "CORS_ORIGINS nao inclui o dominio oficial de producao."
    }

    $trustedHosts = @((Get-DotEnvValue -Name "TRUSTED_HOSTS").Split(",") | ForEach-Object { $_.Trim() })
    if ($PublicHost -notin $trustedHosts) {
        throw "TRUSTED_HOSTS nao inclui o dominio oficial de producao."
    }

    Write-Step "Validando o Compose sem renderizar valores sensiveis..."
    & docker compose @ComposeBase config --quiet *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config --quiet falhou. O deploy nao foi iniciado."
    }
}

function Get-ServiceContainerId {
    param([Parameter(Mandatory = $true)][string]$Service)

    $lines = @(Invoke-ComposeCapture -ComposeArguments @("ps", "-q", $Service))
    $ids = @($lines | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -match "^[0-9a-f]{12,64}$" })
    if ($ids.Count -ne 1) {
        throw "O servico $Service precisa possuir exatamente um container no projeto $ProjectName."
    }
    return $ids[0]
}

function Get-ContainerState {
    param([Parameter(Mandatory = $true)][string]$ContainerId)

    $state = @(& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $ContainerId 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel inspecionar um container do stack."
    }
    return ($state -join "").Trim()
}

function Wait-ServiceHealthy {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $containerId = Get-ServiceContainerId -Service $Service
        $state = Get-ContainerState -ContainerId $containerId
        if ($state -eq "healthy" -or $state -eq "running") {
            Write-Step "$Service esta $state."
            return
        }
        if ($state -eq "unhealthy" -or $state -eq "exited" -or $state -eq "dead") {
            throw "$Service entrou no estado $state. Consulte docker compose logs $Service."
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)

    throw "Timeout aguardando $Service ficar saudavel."
}

function Assert-InfrastructureHealthy {
    foreach ($service in @("postgres", "redis")) {
        $containerId = Get-ServiceContainerId -Service $service
        $state = Get-ContainerState -ContainerId $containerId
        if ($state -ne "healthy") {
            throw "$service precisa estar healthy antes do deploy; estado atual: $state."
        }
    }
}

function Get-AlembicRevision {
    param([ValidateSet("current", "heads")][string]$Command)

    $output = @(Invoke-ComposeCapture -ComposeArguments @("run", "--rm", "--no-deps", "migrate", "alembic", $Command))
    $text = $output -join "`n"
    $matches = [regex]::Matches($text, "(?m)^([0-9]{4}_[A-Za-z0-9_]+)(?:\s+\(head\))?\s*$")
    if ($matches.Count -ne 1) {
        throw "Nao foi possivel determinar a revision Alembic ($Command) de forma segura."
    }
    return $matches[0].Groups[1].Value
}

function Invoke-MigrationGate {
    $currentRevision = Get-AlembicRevision -Command "current"
    $headRevision = Get-AlembicRevision -Command "heads"

    if ($currentRevision -eq $headRevision) {
        Write-Step "Schema ja esta no Alembic head; nenhuma migration sera aplicada."
        return
    }

    if (-not $ApplyMigrations) {
        throw "Ha migration pendente ($currentRevision -> $headRevision). O deploy foi abortado antes de alterar o banco. Revise a migration, confirme um backup e reexecute com -ApplyMigrations."
    }

    Write-Warning "Uma migration alterara o schema PostgreSQL. Confirme antes que o backup foi criado e verificado."
    $confirmation = Read-Host "Digite MIGRAR para aplicar $currentRevision -> $headRevision"
    if ($confirmation -cne "MIGRAR") {
        throw "Migration cancelada pelo operador; nenhum servico foi recriado."
    }

    Invoke-Compose -ComposeArguments @("run", "--rm", "--no-deps", "migrate", "alembic", "upgrade", "head")
    $afterRevision = Get-AlembicRevision -Command "current"
    if ($afterRevision -ne $headRevision) {
        throw "Migration nao atingiu o head esperado. Os servicos de codigo nao serao recriados."
    }
    Write-Step "Migration aplicada e confirmada no head."
}

function Test-BackendImage {
    Write-Step "Executando smoke de import da nova imagem backend..."
    Invoke-Compose -ComposeArguments @(
        "run", "--rm", "--no-deps", "--entrypoint", "python", "backend",
        "-c", "from backend.app.main import app; assert app is not None"
    )
}

function Test-FrontendImage {
    Write-Step "Validando a configuracao Nginx da nova imagem frontend..."
    Invoke-Compose -ComposeArguments @("run", "--rm", "--no-deps", "--entrypoint", "nginx", "frontend", "-t")
}

function Invoke-EdgeSmoke {
    $mapping = @(Invoke-ComposeCapture -ComposeArguments @("port", "frontend", "8080")) -join ""
    $portMatch = [regex]::Match($mapping.Trim(), ":([0-9]+)$")
    if (-not $portMatch.Success) {
        throw "Nao foi possivel determinar a porta local do frontend."
    }

    $edgePort = $portMatch.Groups[1].Value
    $hostHeader = ((Get-DotEnvValue -Name "TRUSTED_HOSTS").Split(",")[0]).Trim()
    foreach ($path in @("/health", "/ready")) {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$edgePort$path" -Headers @{ Host = $hostHeader } -TimeoutSec 15
        if ($response.StatusCode -ne 200) {
            throw "Smoke $path retornou HTTP $($response.StatusCode)."
        }
    }
    Write-Step "Smokes same-origin /health e /ready passaram."
}

function Build-BackendImages {
    Write-Step "Construindo imagens backend, migrate, Worker e Beat sem tocar na infraestrutura..."
    Invoke-Compose -ComposeArguments @("build", "migrate", "backend", "celery_worker", "celery_beat")
    Test-BackendImage
}

function Update-BackendServices {
    Invoke-MigrationGate

    Write-Step "Recriando somente os servicos que executam o codigo Python..."
    Invoke-Compose -ComposeArguments @("up", "-d", "--no-deps", "--force-recreate", "backend", "celery_worker", "celery_beat")
    foreach ($service in @("backend", "celery_worker", "celery_beat")) {
        Wait-ServiceHealthy -Service $service
    }
}

function Build-FrontendImage {
    Write-Step "Construindo a imagem frontend sem tocar em PostgreSQL ou Redis..."
    Invoke-Compose -ComposeArguments @("build", "frontend")
    Test-FrontendImage
}

function Update-FrontendService {
    Write-Step "Recriando somente o frontend..."
    Invoke-Compose -ComposeArguments @("up", "-d", "--no-deps", "--force-recreate", "frontend")
    Wait-ServiceHealthy -Service "frontend"
}

function Restart-FrontendProxy {
    # Nginx resolves the backend service when it starts. After Docker replaces
    # the backend container, restart the existing edge container so it resolves
    # the new backend IP instead of serving a transient/sticky 502.
    $frontendBefore = Get-ServiceContainerId -Service "frontend"
    Write-Step "Reiniciando o frontend existente para renovar o DNS interno do backend..."
    Invoke-Compose -ComposeArguments @("restart", "frontend")
    Wait-ServiceHealthy -Service "frontend"
    $frontendAfter = Get-ServiceContainerId -Service "frontend"
    if ($frontendAfter -cne $frontendBefore) {
        throw "O frontend foi substituido inesperadamente durante o refresh de DNS."
    }
}

function Main {
    Assert-Prerequisites
    Assert-InfrastructureHealthy

    $postgresBefore = Get-ServiceContainerId -Service "postgres"
    $redisBefore = Get-ServiceContainerId -Service "redis"

    if ($ApplyMigrations -and $Target -notin @("backend", "all")) {
        throw "-ApplyMigrations so pode ser usado com backend ou all."
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        $sha = @(& git -C $RepositoryRoot rev-parse HEAD 2>$null) -join ""
        if ($LASTEXITCODE -eq 0 -and $sha.Trim() -match "^[0-9a-f]{40}$") {
            $env:APP_COMMIT_SHA = $sha.Trim()
        }
    }

    switch ($Target) {
        "validate" {
            Write-Step "Modo somente validacao: nenhum container sera recriado."
            foreach ($service in @("backend", "frontend", "celery_worker", "celery_beat")) {
                Wait-ServiceHealthy -Service $service -TimeoutSeconds 5
            }
        }
        "frontend" {
            Build-FrontendImage
            Update-FrontendService
        }
        "backend" {
            Build-BackendImages
            Update-BackendServices
            Restart-FrontendProxy
        }
        "all" {
            Write-Step "Construindo todas as imagens de codigo antes de alterar qualquer container..."
            Invoke-Compose -ComposeArguments @("build", "migrate", "backend", "celery_worker", "celery_beat", "frontend")
            Test-BackendImage
            Test-FrontendImage
            Update-BackendServices
            Update-FrontendService
        }
    }

    if ((Get-ServiceContainerId -Service "postgres") -ne $postgresBefore) {
        throw "Protecao acionada: o container PostgreSQL foi alterado inesperadamente."
    }
    if ((Get-ServiceContainerId -Service "redis") -ne $redisBefore) {
        throw "Protecao acionada: o container Redis foi alterado inesperadamente."
    }

    Assert-InfrastructureHealthy
    Invoke-EdgeSmoke
    Write-Host "[SUCESSO] Operacao '$Target' concluida. PostgreSQL e Redis foram preservados." -ForegroundColor Green
}

try {
    Main
}
catch {
    Write-Host "[ERRO] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
