$ErrorActionPreference = 'Continue'  # native komutların stderr çıktısı PS 5.1'de hata sayılmasın
Set-Location $PSScriptRoot
function Get-LanIp {
    # Varsayılan ağ geçidi olan (Wi-Fi/Ethernet) arayüzün IPv4 adresi — VirtualBox/WSL sanal ağlarını atlar
    try {
        $cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
        if ($cfg) { return ($cfg.IPv4Address | Select-Object -First 1).IPAddress }
    } catch { }
    return 'localhost'
}

Write-Host ''
Write-Host '=== AeroStandart AI - backend (PostgreSQL + FastAPI) ===' -ForegroundColor Red

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker bulunamadı. Docker Desktop kurun ve açın: https://www.docker.com/products/docker-desktop/' -ForegroundColor Yellow
    exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker Desktop çalışmıyor. Uygulamayı açıp birkaç saniye bekleyin, sonra tekrar deneyin.' -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path '.env')) {
    $lines = Get-Content '.env.example'
    $chars = [char[]](48..57 + 65..90 + 97..122)
    $secret = -join (1..48 | ForEach-Object { $chars | Get-Random })
    $lines = $lines -replace '^JWT_SECRET=.*', "JWT_SECRET=$secret"
    Write-Host ''
    Write-Host 'Gemini API anahtarı: https://aistudio.google.com/apikey (ücretsiz)' -ForegroundColor Cyan
    $key = Read-Host 'Anahtarı yapıştırın (şimdilik boş bırakabilirsiniz)'
    if ($key) { $lines = $lines -replace '^GEMINI_API_KEY=.*', "GEMINI_API_KEY=$($key.Trim())" }
    [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot '.env'), $lines)
    Write-Host '.env oluşturuldu.' -ForegroundColor Green
}

# Yavaş/kesintili bağlantıda paket indirme zaman aşımına uğrayabilir: 3 kez dene (inenler önbellekte kalır)
$built = $false
for ($try = 1; $try -le 3; $try++) {
    if ($try -gt 1) { Write-Host "Derleme tekrar deneniyor ($try/3)..." -ForegroundColor Yellow; Start-Sleep -Seconds 5 }
    docker compose up -d --build
    if ($LASTEXITCODE -eq 0) { $built = $true; break }
}
if (-not $built) {
    Write-Host 'docker compose 3 denemede de başarısız oldu.' -ForegroundColor Red
    Write-Host 'İnternet bağlantınızı kontrol edin; VPN (ör. Proton VPN) açıksa kapatıp tekrar deneyin.' -ForegroundColor Yellow
    exit 1
}

Write-Host 'API başlatılıyor...' -NoNewline
$ok = $false
for ($i = 0; $i -lt 90; $i++) {
    try { $h = Invoke-RestMethod -Uri 'http://localhost:8000/api/health' -TimeoutSec 2; $ok = $true; break } catch { Start-Sleep -Seconds 2; Write-Host '.' -NoNewline }
}
Write-Host ''
if (-not $ok) { Write-Host "API yanıt vermedi. Kayıtlar için: docker compose logs api" -ForegroundColor Red; exit 1 }

$ip = Get-LanIp
Write-Host ''
Write-Host "Hazır! Yüklü standart: $($h.documents)  |  Gemini: $(if ($h.llm_enabled) {'açık'} else {'kapalı (yalnızca tam metin)'})" -ForegroundColor Green
Write-Host "  Swagger API    : http://${ip}:8000/docs"
Write-Host "  Yönetim paneli : http://${ip}:8000/admin   (admin@aerostd.dev / Admin12345! - .env içinden değiştirilebilir)"
Write-Host ''
Write-Host 'İlk açılışta kamuya açık standartlar arka planda indirilip indekslenir (birkaç dakika sürebilir).'
Write-Host 'İlerlemeyi yönetim panelinden izleyebilirsiniz. Şimdi mobil uygulama için: .\start-mobile.ps1'
