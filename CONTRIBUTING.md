# Katkı rehberi

Bağlayıcı kurallar ve PR süreci: [docs/BACKEND_GELISTIRME_REHBERI.md](docs/BACKEND_GELISTIRME_REHBERI.md)
(özellikle §0 yapay zekâ asistanı, §1 altın kurallar, §10 testler, §11 PR süreci).
API sözleşmesi: [docs/API_CONTRACT.md](docs/API_CONTRACT.md).

- **`main`'e doğrudan push yok.** Her şey kendi dalından PR ile, 2 onayla (hassas dosyalarda biri CODEOWNERS'tan) birleşir.
- **Onay kuralı:** PR açan kişi kendi PR'ını onaylayamaz; yeni commit gelirse onaylar sıfırlanır.
- **Bağımlılık:** Yeni bağımlılık yalnızca PR'da gerekçeyle, `==` sürümle; `requirements.txt` CODEOWNERS onayı gerektirir.
- **Dal adı:** `<isim>/<kısa-konu>` → ör. `doruk/postgres-repositories`, `sudenur/hybrid-search`, `taha/jwt-auth`.
- **Commit mesajı:** Conventional Commits, açıklama Türkçe → ör. `feat(api): ...`, `fix(search): ...`, `docs: ...`.
- **PR kontrol listesi:** PR açınca açıklamaya otomatik gelir (`.github/pull_request_template.md`); doldur ve işaretle.
- **Testler:** PR öncesi `.venv/Scripts/python -m pytest -q` yerelde yeşil olmalı; GitHub Actions'taki `pytest` kontrolü de geçmeli.
