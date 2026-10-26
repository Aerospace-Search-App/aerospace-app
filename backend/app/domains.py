"""Standartları ve projeleri eşleştirmek için kullanılan konu alanları."""

DOMAINS: dict[str, dict[str, str]] = {
    "software": {"label": "Avionik Yazılım", "icon": "code-slash", "hint": "DO-178C, yazılım güvencesi"},
    "hardware": {"label": "Elektronik Donanım", "icon": "hardware-chip", "hint": "DO-254, karmaşık donanım"},
    "systems": {"label": "Sistem Geliştirme", "icon": "git-network", "hint": "ARP4754, gereksinim yönetimi"},
    "safety": {"label": "Sistem Emniyeti", "icon": "shield-checkmark", "hint": "Tehlike analizi, FHA, 1309"},
    "emc": {"label": "EMI / EMC", "icon": "pulse", "hint": "Elektromanyetik uyumluluk testleri"},
    "environmental": {"label": "Çevresel Testler", "icon": "thermometer", "hint": "Sıcaklık, titreşim, nem"},
    "maintenance": {"label": "Bakım & Onaylı Kuruluş", "icon": "construct", "hint": "Part-145, SHT-145"},
    "sms": {"label": "Emniyet Yönetimi (SMS)", "icon": "analytics", "hint": "Risk yönetimi, emniyet kültürü"},
    "airworthiness": {"label": "Uçuşa Elverişlilik", "icon": "airplane", "hint": "Sertifikasyon kriterleri"},
}


def clean_domains(values: list[str] | None) -> list[str]:
    return sorted({v for v in (values or []) if v in DOMAINS})
