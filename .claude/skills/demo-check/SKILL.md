---
name: demo-check
description: Sunum/demo öncesi uçtan uca duman testi — sunucuyu ağa açık başlatır, ana akışı (sağlık → standart → PDF yükleme → indeks durumu → soru → rapor → analiz) curl ile dener ve mobilin bağlanacağı adresi verir. "Demo hazır mı", "sunum öncesi kontrol" isteklerinde kullan.
---

# Demo kontrolü (mock mod)

## 1. Ortam
- `.venv/Scripts/python -m pytest -q` yeşil mi?
- `.env` gerekmez (mock mod). Varsa içeriğini okuma.

## 2. Sunucu
Bash aracıyla arka planda (`run_in_background`):
```bash
.venv/Scripts/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
Sonra `curl -s localhost:8000/health`. LAN IP: `ipconfig | grep -i "IPv4"`.
Mobil base URL: emülatör `http://10.0.2.2:8000`, gerçek cihaz `http://<LAN-IP>:8000` (aynı Wi-Fi, Windows güvenlik duvarı 8000'e izin vermeli).

## 3. Akış (her adımda status kodunu ve önemli alanları yazdır: `curl -s -w "\n%{http_code}\n"`)
```bash
B=http://localhost:8000/api/v1
curl -s $B/meta/enums | head -c 300
curl -s "$B/standards?page=1&page_size=5"
curl -s -X POST $B/standards -H 'Content-Type: application/json' \
  -d '{"code":"MIL-STD-1553B","title":"Digital Time Division Command/Response Multiplex Data Bus","standard_type":"MIL"}'
printf '%%PDF-1.4\n%%demo\n' > /tmp/demo.pdf
curl -s -X POST "$B/standards/1/document" -F "file=@/tmp/demo.pdf;type=application/pdf"
curl -s $B/standards/1/index-status
curl -s -X POST $B/chat/ask -H 'Content-Type: application/json' \
  -d '{"question":"Vibrasyon testi için gereksinimler nelerdir?","standard_ids":[1]}'
curl -s -X POST $B/reports -F "file=@/tmp/demo.pdf;type=application/pdf" -F "report_type=TEST"
curl -s -X POST $B/reports/1/analyses -H 'Content-Type: application/json' \
  -d '{"query":"Rapor vibrasyon gereksinimlerini karşılıyor mu?","standard_ids":[1]}'
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email":"kagan@example.com","password":"Sifre1234"}'
```

## 4. Rapor
Tablo: adım | status | not. Başarısız adım varsa muhtemel nedeni ve en hızlı çözümü yaz.
Bittiğinde arka plandaki uvicorn'u durdur (kullanıcı açık kalsın demediyse).
