# Copilot talimatları

Bu repo FastAPI tabanlı mobil API iskeletidir. Kod önermeden önce şu dosyalara uy:
`docs/BACKEND_GELISTIRME_REHBERI.md` (bağlayıcı kurallar, §1 altın kurallar), `docs/API_CONTRACT.md` (API sözleşmesi), `CLAUDE.md`.

- Sözleşmede olmayan endpoint/alan ekleme; var olanı silme veya adını değiştirme.
- `src/domain/interfaces.py` imzalarını değiştirme; bileşen seçimi sadece `src/core/deps.py`'de.
- Router'da iş mantığı ve try/except yok; servisler `AppError` alt sınıfları fırlatır.
- Testleri silme/gevşetme; `.env` dosyasına dokunma.
- Yeni bağımlılık yalnızca PR'da gerekçeyle, `==` sürümle; `requirements.txt` CODEOWNERS onayı gerektirir.
- `main`'e doğrudan push yok; her şey PR ile, 2 onayla (hassas dosyalarda biri CODEOWNERS'tan).
- Kod/alan adları İngilizce, kullanıcıya dönen mesajlar Türkçe.
- PR öncesi `.venv/Scripts/python -m pytest -q` yeşil olmalı.
