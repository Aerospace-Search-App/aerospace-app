# Yönetici olarak çalıştırın: telefonun bilgisayardaki API (8000) ve Metro (8081) portlarına erişmesine izin verir.
New-NetFirewallRule -DisplayName 'AeroStandart API 8000' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain | Out-Null
New-NetFirewallRule -DisplayName 'AeroStandart Metro 8081' -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow -Profile Private,Domain | Out-Null
Write-Host 'Güvenlik duvarı kuralları eklendi (8000, 8081).' -ForegroundColor Green
