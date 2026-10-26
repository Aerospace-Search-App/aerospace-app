---
name: api-contract-sync
description: API sözleşmesi (docs/API_CONTRACT.md) ile kod/Swagger arasındaki farkları bulur ve sözleşme değişikliğini doğru sırayla uygular; ekibe duyuru metni hazırlar. Endpoint/şema eklenip değiştiğinde, PR öncesinde ve "Swagger dokümanla uyumlu mu" sorusunda kullan.
---

# Sözleşme senkronizasyonu

Sözleşme mobil ekip (Şeyma, Ammar), web (Onur) ve backend (Taha, Doruk, Sudenur) arasındaki anlaşmadır.
Sessiz değişiklik = başkasının ekranı bozulur.

## A. Fark raporu (değişiklik yapmadan)
1. Sözleşmedeki endpoint tablosunu (`API_CONTRACT.md` §1) oku → (metot, yol) listesi.
2. Koddaki listeyi çıkar:
   ```bash
   python - <<'EOF'
   from main import app
   spec = app.openapi()
   for path, ops in sorted(spec["paths"].items()):
       for m, op in ops.items():
           print(m.upper(), path, "|", op.get("summary"), "|", ",".join(op.get("tags", [])))
   EOF
   ```
3. Karşılaştır ve tablo halinde raporla: **eksik** (sözleşmede var, kodda yok), **fazla** (kodda var, sözleşmede yok),
   **farklı** (status kodu, alan adı/tipi, zorunluluk, enum değerleri).
4. Şema alanlarını kontrol: sözleşmedeki JSON örneklerindeki her alan, OpenAPI `components.schemas` içinde aynı ad ve tipte mi?

## B. Sözleşmeyi değiştirme sırası
1. Değişikliği ve gerekçesini PR açıklamasında yaz. **Kırıcı değişiklik** (alan silme/yeniden adlandırma,
   tip değişikliği, yol değişikliği, zorunlu alan ekleme) ise ekip onayı (2 onay, biri CODEOWNERS) şart.
2. `docs/API_CONTRACT.md`'yi güncelle (tablo + şema örneği + hata kodları).
3. Kodu güncelle (`add-endpoint` reçetesi).
4. `tests/api/test_contract_coverage.py`'deki beklenen listeyi güncelle.
5. `pytest -q`.
6. Duyuru metni üret:
   ```
   📣 API değişikliği (v1) — <tarih>
   Ne değişti: <endpoint> — <alan/davranış>
   Kimi etkiler: <mobil / web / Taha / ...>
   Yapmanız gereken: <tek cümle>
   Kırıcı mı: Evet/Hayır
   ```

## Kırıcı olmayan değişiklik tercih et
Yeni opsiyonel alan ekle, eskiyi sunumdan sonra kaldır. Yol değişecekse bir süre eski yolu da tut (deprecated=True).
