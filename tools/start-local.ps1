$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) {
    Write-Host (
        "The Entra app must support 'Accounts in any organizational directory " +
        "and personal Microsoft accounts' (AzureADandPersonalMicrosoftAccount)."
    )
    $clientId = Read-Host "Microsoft Entra application client ID"
    $secureClientSecret = Read-Host "Microsoft Entra application client secret" -AsSecureString
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureClientSecret)
    try {
        $clientSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    $password = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(24))
    $internalToken = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $sessionKey = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
    $fernetKey = [Convert]::ToBase64String(
        [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    ).Replace('+', '-').Replace('/', '_')
    @(
        "POSTGRES_PASSWORD=$password"
        "SENTINEL_INTERNAL_API_TOKEN=$internalToken"
        "SENTINEL_MICROSOFT_CLIENT_ID=$clientId"
        "SENTINEL_MICROSOFT_CLIENT_SECRET='$clientSecret'"
        "SENTINEL_MICROSOFT_REDIRECT_URI=http://localhost:8080/auth/callback"
        "SENTINEL_FRONTEND_URL=http://localhost:8080"
        "SENTINEL_SESSION_SIGNING_KEY=$sessionKey"
        "SENTINEL_TOKEN_ENCRYPTION_KEY=$fernetKey"
    ) | Set-Content -LiteralPath $envFile -Encoding ascii
}

docker compose --env-file $envFile up --build
