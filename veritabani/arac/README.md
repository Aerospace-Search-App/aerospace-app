# veritabani/arac

## Parçaları yükleme (yukle.py)
Sudenur'un parcalama.py çıktısını (JSON) veri tabanına yazar.

    set DATABASE_URL=postgresql+psycopg2://app:ŞİFRE@localhost:5433/standartlar
    python yukle.py parcalar.json --baslik "Standardın adı" --kurum ECSS --yil 2020

- Aynı (kod, revizyon) tekrar yüklenirse eski parçalar silinip yenisi yazılır.
- Hata olursa hiçbir şey yazılmaz (tek işlem).
- title, heading_path, page_end alanları şemada yok, yüklenmez. content zaten başlık satırıyla başlıyor.
- embedding sütunu boş kalır, embedding modeli seçilince ayrı bir adımda doldurulacak.

## Erişim fonksiyonları (erisim.py)
Kağan'ın API'si için: standart listeleme/getirme, kelime-anlam-hibrit arama,
sohbet ve mesaj kaydı, cevap kaynakları, kaydedilen standartlar.
Her fonksiyon bir SQLAlchemy bağlantısı alır (`with motor.begin() as c:`).
