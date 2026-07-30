"""Jinja2 shablonlari uchun yagona sozlama.

Alohida modulda turadi, chunki uni ham `main.py` (xato sahifalari uchun),
ham `app/web/pages/*.py` (odatiy sahifalar uchun) import qiladi.
"""

from decimal import Decimal

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def format_money(value) -> str:
    """1500000 -> "1 500 000". Tiyin nolga teng bo'lmasa, u ham ko'rsatiladi."""
    if value is None:
        return "0"

    amount = Decimal(value)
    whole_soms = int(amount)
    formatted = f"{whole_soms:,}".replace(",", " ")

    tiyins = int((amount - whole_soms) * 100)
    return f"{formatted},{tiyins:02d}" if tiyins else formatted


templates.env.filters["money"] = format_money
