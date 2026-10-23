param(
    [ValidateSet('Start', 'Stop', 'Status', 'Logs', 'CreateAdmin')]
    [string]$Action = 'Start'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { $null }
if (-not $dockerExe) {
    $dockerCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'),
        'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    )
    $dockerExe = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerExe) { throw 'Docker CLI not found. Install Docker Desktop with WSL2 and Linux containers.' }
$env:PATH = (Split-Path $dockerExe) + ';' + $env:PATH
Push-Location $repoRoot
try {
    $containerOS = & $dockerExe info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker engine is unavailable. Start Docker Desktop first.' }
    if ($containerOS -ne 'linux') { throw 'Switch Docker Desktop to Linux containers.' }
    $composeArgs = @('compose', '--project-directory', $repoRoot, '--env-file', '.env',
        '-f', 'utils/lan/docker-compose.v2.80.0.yml',
        '-f', 'utils/lan/docker-compose.serverless.v2.80.0.yml', '-f', 'docker-compose.lan.yml')
    & $dockerExe @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Invalid Docker Compose configuration.' }
    switch ($Action) {
        'Start' { & $dockerExe @composeArgs up -d }
        'Stop' { & $dockerExe @composeArgs stop }
        'Status' { & $dockerExe @composeArgs ps }
        'Logs' { & $dockerExe @composeArgs logs --tail 100 cvat_server nuclio traefik }
        'CreateAdmin' { & $dockerExe @composeArgs exec cvat_server python manage.py createsuperuser }
    }
    if ($LASTEXITCODE -ne 0) { throw "CVAT action failed: $Action" }
} finally { Pop-Location }
