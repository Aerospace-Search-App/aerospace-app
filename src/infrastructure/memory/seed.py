"""Seed (başlangıç) verisi: uygulama her açıldığında bellek-içi depolar bu kayıtlarla dolar.

İçerik:
- Demo kullanıcı (id=1, ADMIN): e-posta `demo@aerospace.local`, parola `demo12345`. `AUTH_ENABLED=false` iken
  her istek bu kullanıcıyla yapılır; `/auth/login` ile de giriş yapılabilir.
- 3 standart: MIL-STD-810H (INDEXED), MIL-STD-461G (INDEXED), DO-178C (NOT_INDEXED, PDF'i yok).
- Demo kullanıcıya ait 1 adet `READY` rapor ("Telsiz Titreşim Test Raporu") — sunumda analiz hemen denenebilsin.

Tarihler sabittir (deterministik demo). TODO(Doruk): PostgreSQL'de bunlar bir migration/seed script'i olur.
"""

from datetime import datetime, timezone

from loguru import logger

from src.core.security import hash_password
from src.domain.entities import Report, Standard, User
from src.domain.enums import IndexStatus, ReportStatus, ReportType, StandardStatus, StandardType, UserRole
from src.domain.interfaces import ReportRepository, StandardRepository, UserRepository
from src.infrastructure.search.mock_search import MockSearchService

DEMO_EMAIL = "demo@aerospace.local"
DEMO_PASSWORD = "demo12345"
_SEED_TIME = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)
_INDEXED_TIME = datetime(2026, 10, 26, 9, 30, tzinfo=timezone.utc)

DEMO_USER = User(id=1, email=DEMO_EMAIL, full_name="Demo Kullanıcı", role=UserRole.ADMIN, created_at=_SEED_TIME)


def _indexed(**fields: object) -> Standard:
    """Hazır indekslenmiş (PDF'i yüklü, aranabilir) bir standart."""
    return Standard(
        **fields,  # type: ignore[arg-type]
        status=StandardStatus.ACTIVE, index_status=IndexStatus.INDEXED, has_document=True,
        indexed_at=_INDEXED_TIME, index_progress=1.0, index_started_at=_SEED_TIME, index_finished_at=_INDEXED_TIME,
        created_at=_SEED_TIME, updated_at=_INDEXED_TIME,
    )


def seed_standards() -> list[Standard]:
    return [
        _indexed(
            code="MIL-STD-810H", title="Environmental Engineering Considerations and Laboratory Tests",
            standard_type=StandardType.MIL, version="H", issuing_body="U.S. Department of Defense",
            publication_year=2019,
            description="Askeri ekipmanların çevresel koşullara (titreşim, şok, sıcaklık, nem) dayanım test yöntemleri.",
            page_count=1089, chunk_count=5210, requirement_count=312,
        ),
        _indexed(
            code="MIL-STD-461G",
            title="Requirements for the Control of Electromagnetic Interference Characteristics of Subsystems "
                  "and Equipment",
            standard_type=StandardType.MIL, version="G", issuing_body="U.S. Department of Defense",
            publication_year=2015,
            description="Elektronik alt sistemlerin elektromanyetik yayınım (CE/RE) ve bağışıklık (CS/RS) gereksinimleri.",
            page_count=280, chunk_count=1340, requirement_count=96,
        ),
        Standard(
            code="DO-178C", title="Software Considerations in Airborne Systems and Equipment Certification",
            standard_type=StandardType.CIVIL, version="C", issuing_body="RTCA, Inc.", publication_year=2011,
            description="Hava aracı yazılımlarının sertifikasyonu için yazılım yaşam döngüsü hedefleri (DAL A–E).",
            status=StandardStatus.ACTIVE, index_status=IndexStatus.NOT_INDEXED, has_document=False,
            created_at=_SEED_TIME, updated_at=_SEED_TIME,
        ),
    ]


def seed_all(standards: StandardRepository, reports: ReportRepository, users: UserRepository,
             search: MockSearchService) -> None:
    """Depoları demo verisiyle doldurur ve indeksli standartların sahte parçalarını aramaya yükler."""
    demo = users.add(User(id=0, email=DEMO_USER.email, full_name=DEMO_USER.full_name, role=DEMO_USER.role,
                          created_at=DEMO_USER.created_at, password_hash=hash_password(DEMO_PASSWORD)))
    for standard in seed_standards():
        saved = standards.add(standard)
        if saved.is_indexed:
            search.load_seed_catalog(saved.id, saved.code)
    reports.add(Report(
        user_id=demo.id, title="Telsiz Titreşim Test Raporu", original_filename="telsiz_titresim_test_raporu.pdf",
        report_type=ReportType.TEST, status=ReportStatus.READY, file_size_kb=812.4, page_count=24,
        uploaded_at=_SEED_TIME, processed_at=datetime(2026, 10, 26, 9, 0, 5, tzinfo=timezone.utc),
    ))
    logger.info("Seed verisi yüklendi: 1 kullanıcı, 3 standart, 1 rapor")
