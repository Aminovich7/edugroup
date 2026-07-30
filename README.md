# EduGroup

O'qituvchilar va o'quv guruhlari uchun onlayn ta'lim platformasi. O'qituvchi kurs va
guruh yaratadi, unga Kinescope video darslarini biriktiradi; o'quvchi guruhga yoziladi,
to'lov qiladi va faqat shundan keyin videolarga kirish huquqini oladi. Manager
profillarni va to'lovlarni moderatsiya qiladi, superadmin esa butun tizim hisobotlarini
ko'radi va manager akkauntlarini boshqaradi.

Bitta FastAPI ilovasi ichida ham JSON API, ham server-rendered (Jinja2) veb-interfeys
ishlaydi. Batafsil texnik tushuntirish — [`code_explanation.md`](code_explanation.md).

---

## Tezkor ishga tushirish

```bash
cp .env.example .env
docker compose up --build
```

Ishga tushgach:

| Manzil | Nima |
|---|---|
| http://localhost:8000 | Veb-interfeys (kurslar katalogi) |
| http://localhost:8000/docs | JSON API hujjatlari (Swagger) |
| http://localhost:8000/health | Servis holati |

Birinchi superadmin ilova ishga tushganda `.env` dagi qiymatlar asosida avtomatik
yaratiladi (standart: `admin@edugroup.uz` / `admin12345`).

```bash
# Migratsiyalar (docker compose up avtomatik bajaradi)
docker compose exec app alembic upgrade head

# Testlar
docker compose exec app pytest

# Testlar + coverage hisoboti
docker compose exec app pytest --cov --cov-report=term-missing
```

Xizmatlar: `app` (FastAPI), `db` (PostgreSQL 16), `redis`, `celery_worker`, `celery_beat`.

---

## Arxitektura xaritasi

```
app/core          -> sozlamalar, JWT/parol, cookie, rol-dependency'lar, rate limit, Celery, xatolar
app/db            -> async sessiya (FastAPI), sync sessiya (Celery), Base, mixin'lar
app/users         -> autentifikatsiya, foydalanuvchi/teacher/student profillari, refresh token
app/courses       -> teacher yaratgan kurslar (soft delete)
app/groups        -> kurs ichidagi guruhlar, manager tasdiqlaydi (soft delete)
app/lessons       -> guruh darslari (faqat Kinescope URL) va LessonProgress
app/enrollments   -> yozilish so'rovlari, waitlist navbati, bekor qilish
app/payments      -> to'lov oqimi (to'liq yoki bo'lib to'lash / installment)
app/notifications -> in-app bildirishnomalar (sinxron yaratiladi)
app/audit         -> Course/Group/Lesson o'zgarishlar tarixi
app/manager       -> manager uchun aggregator endpointlar
app/superadmin    -> manager yaratish, foydalanuvchini block/unblock
app/reports       -> statistika va daromad hisobotlari
app/web           -> Jinja2 SSR sahifalar; service.py ni bevosita chaqiradi, HTTP orqali emas
templates/        -> Jinja2 shablonlar
static/           -> CSS va vanilla JS (faqat UI interaktivligi)
tests/            -> pytest testlari, domain modullarga mos papkalarga bo'lingan
```

Har bir domain modul bir xil ichki qatlamlarga ega:
`models.py → schemas.py → repository.py → service.py → router.py`.

**Muhim:** JSON API `/api` prefiksi ostida (`/api/courses`, `/api/payments`), veb-sahifalar
esa ildizdan (`/`, `/login`, `/groups/{id}`). Prefiks kerak edi, chunki TZ 6-bo'limdagi
API yo'llari va 14.3-bo'limdagi sahifa yo'llari bir xil (`GET /courses/{id}`) — bitta
ilovada ular to'qnashadi. Ikkala qatlam bir xil `service.py` funksiyalarini chaqiradi.

---

## Rollar va ruxsatlar

| Amal | student | teacher | manager | superadmin |
|---|---|---|---|---|
| Ro'yxatdan o'tish | ✅ | ✅ | — (superadmin yaratadi) | — |
| O'z profilini tahrirlash | ✅ | ✅ | ✅ | ✅ |
| Kurs/guruh yaratish | ❌ | ✅ (draft) | ✅ | ✅ |
| Guruhga teacher biriktirish | ❌ | ❌ | ✅ | ✅ |
| Profilni tasdiqlash/rad etish | ❌ | ❌ | ✅ | ✅ |
| Guruhga yozilish | ✅ | ❌ | ❌ | ❌ |
| To'lov yaratish | ✅ | ❌ | ❌ | ❌ |
| To'lovni tasdiqlash | ❌ | ❌ | ✅ | ✅ |
| Video qo'shish/tahrirlash | ❌ | ✅ (o'z guruhi) | ✅ | ✅ |
| Videoni ko'rish | ✅ (to'lagan bo'lsa) | ✅ (o'z guruhi) | ✅ | ✅ |
| Guruh navbatini ko'rish | ✅ (o'z pozitsiyasi) | ✅ (o'z guruhi) | ✅ | ✅ |
| Hisobotlar | ❌ | ✅ (o'z guruhi) | ✅ | ✅ (global) |
| Audit log | ❌ | ❌ | ❌ | ✅ |
| Manager yaratish, block/unblock | ❌ | ❌ | ❌ | ✅ |

---

## Ma'lumotlar modeli

```
User ──1:1── TeacherProfile / StudentProfile
User ──1:N── RefreshToken, Notification, AuditLog

User (teacher) ──1:N── Course ──1:N── Group ──1:N── Lesson
Group ──N:1── User (biriktirilgan teacher)

User (student) ──N:N── Group   (Enrollment orqali)
Enrollment ──1:N── Payment
Enrollment ──1:1── PaymentPlan ──1:N── Installment
Installment ──1:1── Payment (to'langanda)

User (student) ──N:N── Lesson  (LessonProgress orqali)
```

To'liq ustunlar ro'yxati — tegishli `app/<modul>/models.py` faylida.

---

## Endpointlar xulosasi

JSON API `/api` prefiksi bilan.

### Autentifikatsiya
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/api/auth/register/student` | public (rate-limited) |
| POST | `/api/auth/register/teacher` | public (rate-limited) |
| POST | `/api/auth/login` | public (rate-limited) |
| POST | `/api/auth/refresh` | public (token rotatsiyasi) |
| POST | `/api/auth/logout` | authenticated |
| GET / PATCH | `/api/users/me` | authenticated |

### Kurs, guruh, dars
| Method | Endpoint | Rol |
|---|---|---|
| POST / GET | `/api/courses` | teacher / public |
| GET / PATCH / DELETE | `/api/courses/{id}` | public / egasi, manager, superadmin |
| POST | `/api/courses/{id}/restore` | superadmin |
| POST / GET | `/api/groups` | teacher / public (faqat active) |
| GET | `/api/groups/mine` | teacher |
| GET / PATCH / DELETE | `/api/groups/{id}` | public / egasi, manager |
| POST | `/api/groups/{id}/restore` | superadmin |
| GET | `/api/groups/{id}/students`, `/waitlist`, `/progress` | teacher (o'ziniki), manager, superadmin |
| POST / GET | `/api/groups/{id}/lessons` | teacher / kirish huquqi borlar |
| GET / PATCH / DELETE | `/api/lessons/{id}` | kirish huquqi borlar / egasi, superadmin |
| POST | `/api/lessons/{id}/progress` | student (active enrollment) |
| POST | `/api/lessons/{id}/restore` | superadmin |

### Yozilish va to'lov
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/api/enrollments` | student (to'la guruhda — waitlist) |
| GET | `/api/enrollments/me` | student |
| GET | `/api/enrollments` | manager, superadmin |
| DELETE | `/api/enrollments/{id}` | egasi yoki manager/superadmin (sabab bilan) |
| POST / GET | `/api/enrollments/{id}/payment-plan` | student / egasi, manager, superadmin |
| POST | `/api/payments` | student |
| GET | `/api/payments/me` | student |
| GET | `/api/payments` | superadmin (filtrlar + jami) |
| POST | `/api/payments/{id}/confirm`, `/reject` | manager, superadmin |

### Moderatsiya, hisobot, audit
| Method | Endpoint | Rol |
|---|---|---|
| GET | `/api/manager/users`, `/groups`, `/payments` | manager, superadmin |
| POST | `/api/manager/users/{id}/approve`, `/reject` | manager, superadmin |
| POST | `/api/manager/groups/{id}/assign-teacher` | manager, superadmin |
| POST / GET | `/api/superadmin/managers` | superadmin |
| POST | `/api/superadmin/users/{id}/block`, `/unblock` | superadmin |
| GET | `/api/reports/overview`, `/revenue` | superadmin |
| GET | `/api/reports/groups/{id}` | teacher (o'ziniki), manager, superadmin |
| GET | `/api/reports/teachers/{id}` | manager, superadmin |
| GET | `/api/notifications` | authenticated |
| POST | `/api/notifications/{id}/read`, `/read-all` | authenticated |
| GET | `/api/audit-logs` | superadmin |

### Veb-sahifalar (Jinja2)
| Sahifa | Shablon |
|---|---|
| `/` | `home.html` — katalog, fan/narx filtri |
| `/login`, `/register` | `login.html`, `register.html` |
| `/courses/{id}`, `/groups/{id}` | `post_detail.html` — darslar, video pleyer, yozilish tugmasi |
| `/dashboard/{rol}` | `dashboard/student|teacher|manager|superadmin.html` |
| `/profile` | `profile.html` |
| `/notifications` | `notifications.html` |
| `/web/superadmin/managers` | `managers.html` |
| `/reports/groups/{id}`, `/reports/teachers/{id}` | `report_group.html`, `report_teacher.html` |
| `/web/*/edit` | `edit_form.html` — kurs/guruh/dars tahrirlash |

Barcha o'zgartiruvchi veb-amallar `POST /web/...` orqali (HTML forma PATCH/DELETE'ni
qo'llab-quvvatlamaydi) va Post/Redirect/Get patternida ishlaydi.

---

## Muhim biznes qoidalar

- To'lov `confirmed` bo'lgandan keyingina enrollment `active` bo'ladi va videolar ochiladi.
- Guruh "to'la" hisoblanadi, agar `awaiting_payment` + `active` yozilishlar soni `capacity`ga
  yetsa. To'lov kutayotgan joy ham band — aks holda bitta joy ikki kishiga sotilib ketardi.
- Guruh to'lganda so'rov rad etilmaydi — student `waitlisted` navbatga qo'yiladi.
- Joy bo'shaganda (bekor qilish, majburiy bekor qilish yoki muddat tugashi) navbatdagi
  birinchi student avtomatik `awaiting_payment` holatiga ko'tariladi.
- Bitta student bitta guruhda faqat bitta yakunlanmagan yozilishga ega bo'ladi
  (**partial unique index**), lekin `cancelled`/`expired` bo'lgandan keyin qayta yozila oladi.
- To'liq to'lov va yangi to'lov rejasi faqat `awaiting_payment` holatida yaratiladi.
  Mavjud rejaning keyingi bo'laklari esa enrollment `active` bo'lgandan keyin ham to'lanadi.
- Oxirgi bo'lak to'langanda `PaymentPlan.status = completed` avtomatik o'rnatiladi.
- To'lov rad etilsa, enrollment holati **o'zgarmaydi** — student qayta to'lay oladi.
- Dars davomiyligi 300–600 soniya, video havolasi `kinescope.io` domenida bo'lishi shart.
- Refresh token har `/auth/refresh` da rotatsiya qilinadi; bekor qilingan token qayta
  ishlatilsa — foydalanuvchining barcha tokenlari revoke qilinadi.
- Bloklangan foydalanuvchi `/auth/login` va `/auth/refresh` da `403` oladi.
- Course/Group/Lesson o'chirilganda yozuv fizik o'chmaydi — `deleted_at` to'ldiriladi va
  `AuditLog` yoziladi; superadmin uni tiklashi mumkin.
- Celery faqat ikkita vaqtga bog'liq ish uchun: yozilish muddati tugashi (har soatda) va
  to'lov bo'lagi muddati o'tishi (kuniga bir marta). Bildirishnoma va audit — sinxron.

---

## Qayerga qarash kerak

| Nimani o'zgartirmoqchisiz | Qaysi faylga qarang |
|---|---|
| To'lov tasdiqlanganda enrollment qanday faollashadi | `app/payments/service.py::confirm_payment` |
| Guruh to'lganda navbat qanday ishlaydi | `app/enrollments/service.py::request_enrollment`, `promote_next_waitlisted` |
| Bo'lib to'lash summasi qanday bo'linadi | `app/payments/service.py::_split_amount` |
| Qayta yozilishga ruxsat beruvchi cheklov | `app/enrollments/models.py` (`uq_enrollment_active_per_group`) |
| Guruh holati o'tishlari (draft/active/closed/archived) | `app/groups/service.py::ALLOWED_STATUS_TRANSITIONS` |
| Video kimga ko'rinadi | `app/lessons/service.py::ensure_can_view_lessons` |
| JWT yaratish/tekshirish | `app/core/security.py` |
| Refresh token rotatsiyasi va reuse-detection | `app/users/service.py::refresh_token_pair` |
| Rate limit sozlamalari | `app/core/rate_limit.py`, `.env` dagi `AUTH_RATE_LIMIT` |
| Celery jadvali | `app/core/celery_app.py::beat_schedule` |
| Veb-sahifa cookie orqali kimni taniydi | `app/web/dependencies.py::get_current_user_from_cookie` |
| Formadagi bo'sh maydonlar qanday qayta ishlanadi | `app/web/form_fields.py` |
| Bildirishnoma matnlari | tegishli modulning `service.py` fayli |

---

## Eslatma

Yangi modul, endpoint yoki biznes qoidasi qo'shilganda shu README dagi ro'yxatlarni
(arxitektura xaritasi, endpointlar, biznes qoidalar, navigatsiya jadvali) ham yangilab
qo'ying — README loyihaning qisqa "xaritasi" bo'lib qolishi kerak.

### Qabul qilingan qarorlar (TZ da ochiq qolgan joylar)

1. **JSON API `/api` prefiksi** — TZ 6 va 14.3 bir xil yo'llarni talab qilgani uchun.
2. **`templates/` va `static/` loyiha ildizida** — TZ 14.6 dagi kod namunasiga mos
   (`Jinja2Templates(directory="templates")`), TZ 14.2 dagi `app/` prefiksi emas.
3. **Kurs `draft` holatda yaratiladi**, teacher uni `PATCH` orqali `active` qiladi —
   TZ kurs uchun alohida moderatsiya oqimini ko'rsatmagan, guruh esa manager tasdig'idan o'tadi.
4. **`Enrollment.cancel_reason`** ustuni qo'shildi — TZ manager uchun majburiy sabab
   talab qiladi, lekin uni saqlash joyini ko'rsatmagan.
5. **Bo'lak to'lovi `active` enrollmentda ham ruxsat etiladi** — aks holda birinchi bo'lak
   tasdiqlangach qolgan bo'laklarni to'lash imkonsiz bo'lardi va reja hech qachon
   `completed` bo'lmasdi. To'liq to'lov va yangi reja uchun `awaiting_payment` sharti saqlanadi.
