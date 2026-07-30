"""Veb-formalar va filtrlar uchun ixtiyoriy maydon turlari.

HTML forma to'ldirilmagan maydonni ham yuboradi — faqat bo'sh qator (`""`) sifatida,
xuddi shunday GET-filtr formasi ham `?date_from=&group_id=` ko'rinishida keladi.
Oddiy `date | None` yoki `UUID | None` bunday qiymatni qabul qila olmaydi va 422
qaytaradi, shuning uchun bu yerdagi turlar bo'sh qatorni avval `None`ga o'giradi.

Muhim: `Form()`/`Query()` aynan `Annotated` ichida turishi kerak — aks holda
FastAPI validatorni e'tiborsiz qoldiradi va bo'sh qator baribir 422 beradi.

Ishlatilishi:
    async def handler(phone: FormText = None, date_from: QueryDate = None): ...
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, TypeVar

from fastapi import Form, Query
from pydantic import BeforeValidator

T = TypeVar("T")


def empty_string_to_none(value: T) -> T | None:
    """Bo'sh yoki faqat probeldan iborat qatorni None ga aylantiradi."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


_to_none = BeforeValidator(empty_string_to_none)

# POST forma maydonlari
FormText = Annotated[str | None, Form(), _to_none]
FormDate = Annotated[date | None, Form(), _to_none]
FormUuid = Annotated[uuid.UUID | None, Form(), _to_none]
FormDecimal = Annotated[Decimal | None, Form(), _to_none]
FormInteger = Annotated[int | None, Form(), _to_none]

# GET filtr parametrlari
QueryText = Annotated[str | None, Query(), _to_none]
QueryDate = Annotated[date | None, Query(), _to_none]
QueryUuid = Annotated[uuid.UUID | None, Query(), _to_none]
QueryDecimal = Annotated[Decimal | None, Query(), _to_none]


def query_enum(enum_class: type[T]):
    """Enum filtri uchun ixtiyoriy tur — "— barchasi —" tanlovi ham qabul qilinadi.

    Ishlatilishi: `status: query_enum(EnrollmentStatus) = None`
    """
    return Annotated[enum_class | None, Query(), _to_none]
