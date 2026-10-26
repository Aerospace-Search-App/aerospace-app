Kurallar: docs/BACKEND_GELISTIRME_REHBERI.md

## Ne yaptım?
<2-4 madde>

## Takma noktası / etkilenen yer
<ör. SearchService → src/infrastructure/search/hybrid_search.py, deps.py'de SEARCH_PROVIDER=hybrid>

## Kontrol listesi
- [ ] `pytest -q` yerelde tamamen yeşil (sonucu yapıştır: `X passed`)
- [ ] Sözleşme (API_CONTRACT.md) değişmedi / değiştiyse önce sözleşme güncellendi ve duyuru metni aşağıda
- [ ] `src/domain/interfaces.py` imzaları değişmedi / değiştiyse gerekçe aşağıda
- [ ] Yeni bağımlılık yok / varsa `==` sürümle eklendi ve gerekçe aşağıda
- [ ] Yeni ayar varsa `config.py` + `.env.example` güncellendi; `.env` commit edilmedi
- [ ] Router'da iş mantığı yok; hatalar AppError ile; mesajlar Türkçe
- [ ] Yeni/değişen davranış için test eklendi (mutlu yol + hata yolu)
- [ ] Mock modda (`SEARCH_PROVIDER=mock`, `LLM_PROVIDER=mock`) uygulama hâlâ açılıyor ve tüm testler geçiyor
- [ ] Yapay zekâ ile üretilen kodu okudum ve anlıyorum

## Sözleşme değişikliği duyurusu (varsa)
