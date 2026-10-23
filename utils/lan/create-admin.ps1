$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$dockerExe = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
if (-not (Test-Path -LiteralPath $dockerExe)) {
    $dockerExe = (Get-Command docker -ErrorAction Stop).Source
}
$credentialsPath = Join-Path $PSScriptRoot '.credentials.json'
if (Test-Path -LiteralPath $credentialsPath) {
    $credentialsJson = Get-Content -LiteralPath $credentialsPath -Raw -Encoding UTF8
} else {
    $randomBytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
    $password = [Convert]::ToBase64String($randomBytes)
    $credentials = @{username='admin'; password=$password; url='http://192.168.110.92:8080'}
    $credentialsJson = $credentials | ConvertTo-Json
}
# Refuse an existing account instead of changing a user's password.
$pythonCode = 'import sys,json; from django.contrib.auth import get_user_model; d=json.load(sys.stdin); U=get_user_model(); assert not U.objects.filter(username=d["username"]).exists(), "admin already exists"; U.objects.create_superuser(username=d["username"],email="",password=d["password"]); print("Administrator created")'
# Save before creation so interruption cannot lose the generated password.
[System.IO.File]::WriteAllText($credentialsPath, $credentialsJson, [System.Text.UTF8Encoding]::new($false))
$ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
& icacls.exe $credentialsPath /inheritance:r /grant:r ('*' + $ownerSid.Value + ':(F)') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Unable to restrict access to the credentials file.' }
$encodedCode = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($pythonCode))
$bootstrap = "exec(__import__('base64').b64decode('$encodedCode'))"
$credentialsJson | & $dockerExe exec -i cvat_server python manage.py shell -c $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Admin creation failed; credentials file retained for recovery. Inspect container logs.' }
Write-Output "Login details saved to $credentialsPath"
