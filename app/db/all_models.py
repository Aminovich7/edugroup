"""Barcha modellarni bir joyda ro'yxatdan o'tkazadi.

`Base.metadata` to'liq bo'lishi kerak bo'lgan joylarda import qilinadi:
Alembic migratsiyalari va testlardagi `create_all`.

Import tartibi — bog'liqlik tartibi: har bir modul faqat o'zidan oldingilarga
tayanadi (masalan `groups` `courses`ga, `payments` `enrollments`ga).
"""

from app.db.base import Base
from app.users import models as user_models
from app.courses import models as course_models
from app.groups import models as group_models
from app.lessons import models as lesson_models
from app.enrollments import models as enrollment_models
from app.payments import models as payment_models
from app.notifications import models as notification_models
from app.audit import models as audit_models

__all__ = [
    "Base",
    "user_models",
    "course_models",
    "group_models",
    "lesson_models",
    "enrollment_models",
    "payment_models",
    "notification_models",
    "audit_models",
]
