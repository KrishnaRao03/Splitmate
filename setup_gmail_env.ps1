$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $projectRoot '.env'
$mailAddress = 'krishna.rao.0302@gmail.com'

$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::Create()
try {
    $rng.GetBytes($bytes)
}
finally {
    $rng.Dispose()
}
$secretKey = [Convert]::ToBase64String($bytes)

$securePassword = Read-Host "Paste Gmail app password for $mailAddress" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $mailPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

$mailPassword = ($mailPassword -replace '\s', '')

if ([string]::IsNullOrWhiteSpace($mailPassword)) {
    throw 'MAIL_PASSWORD cannot be empty.'
}

@"
SECRET_KEY=$secretKey
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=$mailAddress
MAIL_DEFAULT_SENDER=$mailAddress
MAIL_PASSWORD=$mailPassword
OTP_EXPIRY_MINUTES=10
OTP_RESEND_COOLDOWN_SECONDS=60
PASSWORD_RESET_EXPIRY_MINUTES=30
STRIPE_SECRET_KEY=
STRIPE_CURRENCY=inr
STRIPE_ACCOUNT_COUNTRY=IN
"@ | Set-Content -Path $envPath -Encoding UTF8

Write-Host ".env created at $envPath"
Write-Host "Restart Flask, then resend the OTP."
