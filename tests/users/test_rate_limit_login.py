"""Rate limiting: ko'p urinishdan keyin 429 qaytadi (Redis storage backend bilan)."""

import pytest

from app.core.rate_limit import limiter
from tests.factories import create_student


@pytest.fixture
def enable_rate_limit():
    """Bu test uchun limiter yoqiladi va hisoblagich tozalanadi."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


async def test_too_many_login_attempts_return_429(client, session, enable_rate_limit):
    student = await create_student(session, email="limit@test.uz")
    payload = {"email": student.email, "password": "notogriparol"}

    statuses = []
    for _ in range(7):
        response = await client.post("/api/auth/login", json=payload)
        statuses.append(response.status_code)

    # Limit 5/daqiqa — oxirgi urinishlar bloklanadi.
    assert 429 in statuses
    assert statuses[0] == 401


async def test_rate_limit_message_does_not_leak_limit_details(
    client, session, enable_rate_limit
):
    """Xavfsizlik: foydalanuvchiga aniq limit sonlari ko'rsatilmaydi (TZ 14.5)."""
    payload = {"email": "yoq@test.uz", "password": "notogriparol"}

    last_response = None
    for _ in range(7):
        last_response = await client.post("/api/auth/login", json=payload)

    assert last_response.status_code == 429
    detail = last_response.json()["detail"]
    assert "5" not in detail
