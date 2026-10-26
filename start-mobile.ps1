$ErrorActionPreference = 'Continue'  # native komutların stderr çıktısı PS 5.1'de hata sayılmasın
Set-Location (Join-Path $PSScriptRoot 'mobile')
function Get-LanIp {
    # Varsayılan ağ geçidi olan (Wi-Fi/Ethernet) arayüzün IPv4 adresi — VirtualBox/WSL sanal ağlarını atlar
    try {
        $cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
        if ($cfg) { return ($cfg.IPv4Address | Select-Object -First 1).IPAddress }
    } catch { }
    return 'localhost'
}

Write-Host ''
Write-Host '=== AeroStandart AI - mobil uygulama (Expo Go) ===' -ForegroundColor Red
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host 'Node.js bulunamadı. https://nodejs.org adresinden LTS sürümünü kurun.' -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path 'node_modules')) {
    Write-Host 'Bağımlılıklar kuruluyor (ilk seferde birkaç dakika)...'
    npm install
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

$ip = Get-LanIp
$env:REACT_NATIVE_PACKAGER_HOSTNAME = $ip
$env:EXPO_PUBLIC_API_URL = "http://${ip}:8000"
Write-Host "Bilgisayar IP: $ip  ->  API: $env:EXPO_PUBLIC_API_URL" -ForegroundColor Green
Write-Host 'Telefonda Expo Go ile QR kodu okutun (telefon ve bilgisayar aynı Wi-Fi ağında olmalı).'
Write-Host ''
npx expo start --clear
