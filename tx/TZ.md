# Texnik Topshiriq (TZ)
## "EduGroup" — O'qituvchilar va guruhlar uchun onlayn ta'lim platformasi

**Versiya:** 2.0
**Sana:** 2026-07-29
**Referens:** exode.biz → "Repetitorlar va o'qituvchilar" bo'limi (yakka va kichik guruh mashg'ulotlari)

### O'zgarishlar tarixi (v1.0 → v2.0)
To'liq final tekshiruvdan so'ng quyidagi tuzatish/qo'shimchalar kiritildi:

1. **Celery + Redis qo'shildi** — fon vazifalar (waitlist/enrollment muddati tugashi, installment overdue flagging) va rate-limit backend uchun (8.2-bo'lim, yangi).
2. **Bug tuzatildi — superadmin manager yaratish/blokirovka endpointlari butunlay yo'q edi** (2.1-bo'limda "superadmin manager yaratadi" deyilgan, lekin 6-bo'limda mos endpoint yo'q edi) — yangi 6.11-bo'lim qo'shildi.
3. **Bug tuzatildi — `Enrollment` jadal-darajadagi `unique_constraint(student_id, group_id)`** talab qilingan holicha, cancel/expire bo'lgan studentni o'sha guruhga MANGU qayta yozilishdan to'sib qo'ygan bo'lardi — qisman (partial) unique index'ga o'zgartirildi (4.7, 9-bo'lim).
4. **Aniqlashtirildi — guruh "to'la" mezoni**: `awaiting_payment` + `active` statusidagi enrollmentlar birgalikda `capacity`ga qarshi hisoblanadi (9-bo'lim).
5. **Aniqlashtirildi — to'lov/`PaymentPlan` yaratish faqat `enrollment.status == awaiting_payment` bo'lganda mumkin** (waitlisted studentlar to'lay olmaydi) — 9-bo'lim.
6. **Aniqlashtirildi — `PaymentPlan.status=completed`** qachon va qanday o'rnatilishi (oxirgi installment tasdiqlanganda) — avval faqat test fayl nomida yashiringan qoida edi, endi 3/9-bo'limda aniq yozilgan.
7. **Aniqlashtirildi — `Payment` rad etilganda `Enrollment.status` o'zgarmaydi** (student qayta to'lashi mumkin) — 9-bo'lim.
8. **Frontendga 9 ta yetishmayotgan sahifa/forma mappingi qo'shildi**: profil tahrirlash, kurs/guruh/dars tahrirlash formalari, guruh holatini o'zgartirish (close/archive), teacher uchun waitlist ko'rinishi, manager/superadmin uchun umumiy enrollment ro'yxati, `reports/groups/{id}` va `reports/teachers/{id}` sahifalari, "barchasini o'qilgan qilish" tugmasi, superadmin manager-boshqaruv UI, enrollment bekor qilish formasi (14-bo'lim).
9. **Yangi 16-bo'lim** — `code_explanation.md` talabi haqida qisqa eslatma (to'liq talab `CLAUDE_CODE_PROMPT.md`da).

---

## 1. Loyiha haqida umumiy ma'lumot

### 1.1. Maqsad
Exode.biz'dagi "Repetitorlar va o'qituvchilar" (tutors/teachers) bo'limining kichraytirilgan, lekin professional versiyasini yaratish. Exode'da bu bo'lim quyidagilarga xizmat qiladi:

- O'qituvchi/repetitor o'z guruhini yaratadi, unga video darslar (Kinescope orqali) joylaydi
- O'quvchi guruhga yoziladi, to'lov qiladi va shundan keyingina video kontentga kirish huquqi oladi
- Menejer profil va guruh-o'qituvchi bog'lanishlarini boshqaradi (moderatsiya)
- Administratsiya (superadmin) barcha to'lovlar, hisobotlar va statistikani ko'radi

Bizning loyihamiz aynan shu ishchi jarayonni (workflow) takrorlaydi, lekin:
- To'lov tizimlari (Payme/Click/Uzum) bilan real integratsiya **YO'Q** — to'lov faqat "logical/manual" tarzda amalga oshiriladi (miqdor kiritiladi, tasdiqlanadi, balans/status yangilanadi).
- Video hosting sifatida **Kinescope** ishlatiladi — faqat video URL (va kinescope video ID) bazada saqlanadi, video fayl hech qachon serverga yuklanmaydi.

### 1.2. Loyihaning ko'lami (Scope)
To'liq **FastAPI** ichida ishlaydigan monolit loyiha — backend ham, frontend ham bitta ilova, bitta framework orqali:
- Async FastAPI backend
- PostgreSQL + SQLAlchemy (async) + Alembic migratsiyalari
- JWT autentifikatsiya (**python-jose** dan foydalanish majburiy — `python-jose[cryptography]`, `HS256`)
- 4 ta rol: `student`, `teacher`, `manager`, `superadmin`
- **Celery + Redis** — fon vazifalar (periodic tasks: enrollment so'rovi muddati tugashi/waitlist avtomatik ko'tarish, installment overdue flagging) va rate-limit storage backend uchun (batafsili — 8.2-bo'lim). Bu ikkalasi ham **zarur bo'lgan joyda** qo'shilgan — notifikatsiya yaratish esa ataylab sinxron qoldirilgan (sabab — 8.2-bo'lim).
- Docker Compose orqali ishga tushirish (`app`, `db`, `redis`, `celery_worker`, `celery_beat`)

Frontend — Jinja2 + HTML/CSS/JS asosida **to'liq server-rendered (SSR)** shaklda TZ doirasiga kiritildi (batafsili — 14-bo'lim). **Muhim arxitektura qoidasi:** frontend brauzer tomonidan alohida REST/JSON API'ga `fetch`/AJAX orqali murojaat qilmaydi. Barcha sahifalar FastAPI route handler'lari tomonidan to'g'ridan-to'g'ri (tegishli `service.py` funksiyalarini import qilib) serverda render qilinadi; formalar oddiy HTML `<form method="post">` orqali yuboriladi (Post/Redirect/Get patterni). JWT baribir ishlatiladi (python-jose orqali yaratiladi/tekshiriladi), lekin brauzerda **`httpOnly` cookie** ichida saqlanadi va FastAPI dependency uni cookie'dan o'qib tekshiradi — hech qanday client-side JavaScript token qiymatiga ega bo'lmaydi yoki uni header sifatida biriktirmaydi.

6-bo'limdagi JSON endpointlar (`/courses`, `/payments` va h.k.) TZ'da saqlanadi — kelajakda tashqi/mobil client kerak bo'lganda yoki `tests/`da ishlatish uchun — lekin veb-sahifalar ularni HTTP orqali chaqirmaydi; ular bilan bir xil `service.py` funksiyalarini bevosita import qilib ishlatadi (batafsili — 14-bo'lim).

---

## 2. Foydalanuvchi rollari va ruxsatlar

| Rol | Tavsif |
|---|---|
| **student** | Ro'yxatdan o'tadi, kurslar/guruhlarni ko'radi, guruhga yozilish so'rovi yuboradi, to'lov qiladi, to'lovdan keyin faqat o'z guruhi videolariga kirish huquqi oladi |
| **teacher** | Ro'yxatdan o'tadi (manager tasdiqlaydi), kurslar va guruhlar yaratadi (lekin guruhga rasman "biriktirilishi" uchun manager tasdig'i kerak), video darslar (Kinescope link) qo'shadi, o'z guruhidagi o'quvchilar ro'yxatini va progressni ko'radi |
| **manager** | Student va teacher profillarini tasdiqlaydi/rad etadi, guruh yaratadi va guruhga teacher biriktiradi, to'lovlarni tasdiqlaydi (student "to'ladim" deganda, manager buni tekshirib tasdiqlaydi — yoki avtomatik bo'lishi mumkin, quyida batafsil), guruh a'zolarini boshqaradi |
| **superadmin** | Tizimdagi barcha ma'lumotlarga to'liq kirish: barcha to'lovlar tarixi, barcha guruh hisobotlari, foydalanuvchi/teacher statistikasi, filtrlar (sana, guruh, teacher, status bo'yicha), managerlarni ham boshqarish huquqi |

### 2.1. Ruxsatlar matritsasi (qisqacha)

| Amal | student | teacher | manager | superadmin |
|---|---|---|---|---|
| Ro'yxatdan o'tish | ✅ | ✅ | — (superadmin yaratadi) | — |
| O'z profilini tahrirlash | ✅ | ✅ | ✅ | ✅ |
| Kurs/guruh yaratish | ❌ | ✅ (draft) | ✅ | ✅ |
| Guruhga teacher biriktirish | ❌ | ❌ | ✅ | ✅ |
| Teacher/student profilini tasdiqlash | ❌ | ❌ | ✅ | ✅ |
| Guruhga yozilish (enrollment so'rovi) | ✅ | ❌ | ❌ | ❌ |
| To'lov yaratish (o'zi uchun) | ✅ | ❌ | ❌ | ❌ |
| To'lovni tasdiqlash | ❌ | ❌ | ✅ | ✅ |
| Video qo'shish/tahrirlash | ❌ | ✅ (o'z guruhiga) | ✅ | ✅ |
| Videoni tomosha qilish | ✅ (to'lov qilgan bo'lsa) | ✅ (o'z guruhi) | ✅ | ✅ |
| Barcha to'lovlar/hisobotlarni ko'rish | ❌ | ❌ (faqat o'z guruhi) | ❌ (faqat o'zi boshqargan guruhlar) | ✅ (hammasi) |
| Bo'lib to'lash (installment) rejasini tanlash | ✅ (o'zi uchun) | ❌ | ❌ | ❌ |
| Guruh navbatini (waitlist) ko'rish | ✅ (faqat o'z pozitsiyasi) | ✅ (o'z guruhi, to'liq navbat) | ✅ | ✅ |
| Bildirishnomalarni ko'rish | ✅ (o'ziniki) | ✅ (o'ziniki) | ✅ (o'ziniki) | ✅ (o'ziniki) |
| Audit log'ni ko'rish | ❌ | ❌ | ❌ | ✅ |
| Manager akkaunt yaratish | ❌ | ❌ | ❌ | ✅ |
| Foydalanuvchini blokirovka/blokdan chiqarish (`status=blocked`) | ❌ | ❌ | ❌ | ✅ |
| O'z enrollment'ini bekor qilish (istalgan holatda: awaiting_payment/waitlisted/active) | ✅ | ❌ | ✅ (istalgan student uchun, majburiy sabab bilan) | ✅ |

---

## 3. Asosiy biznes-jarayon (Exode logikasiga mos)

1. **Ro'yxatdan o'tish**: Student yoki Teacher `/auth/register` orqali ro'yxatdan o'tadi → status = `pending`.
2. **Moderatsiya**: Manager `/manager/users/{id}/approve` yoki `/reject` orqali profilni tasdiqlaydi. Faqat `approved` statusidagi teacher guruh yaratishi/guruhga biriktirilishi mumkin; faqat `approved` student to'lov qilishi mumkin.
3. **Kurs va guruh yaratish**: Approved teacher `Course` (masalan, "Ingliz tili — Elementary") va uning ichida `Group` (masalan, "Dushanba-Chorshanba 18:00 guruhi") yaratadi. Guruh holati `draft` bo'ladi.
4. **Guruh-teacher biriktirish**: Manager guruhni ko'rib chiqib, `POST /manager/groups/{group_id}/assign-teacher` orqali uni rasman faollashtiradi (`draft` → `active`, `approved_by`/`approved_at` to'ldiriladi) va teacher'ni tasdiqlaydi (agar guruh boshqa teacher tomonidan taklif qilingan bo'lsa, manager `teacher_id`ni ham shu so'rovda o'zgartira oladi — bitta endpoint ham "tasdiqlash", ham "qayta biriktirish"ni bajaradi). Guruh `active` bo'lgandan keyingina u ommaviy katalogda (`GET /` , `GET /groups`) ko'rinadi va studentlar yozila oladi. Manager/superadmin keyinchalik guruhni `closed` (yangi yozilish qabul qilinmaydi, mavjud `active` enrollmentlar videoga kirishni davom ettiradi) yoki `archived` (butunlay yopiq, katalogdan yashiriladi) holatiga o'tkazishi mumkin — bu `PATCH /groups/{id}` orqali amalga oshadi.
5. **Video qo'shish**: Teacher o'z guruhiga `Lesson` qo'shadi — sarlavha, tavsif, **Kinescope video URL/ID**, davomiylik (5–10 daqiqa), tartib raqami. Video fayl serverga yuklanmaydi, faqat link saqlanadi.
6. **Guruhga yozilish**: Student `Group`larni ko'radi (filtr: fan, narx, teacher), yozilish so'rovi yuboradi → status `awaiting_payment`. Guruh "to'la" hisoblanishi uchun mezon: shu guruh bo'yicha `status IN (awaiting_payment, active)` bo'lgan enrollmentlar soni `capacity`ga teng yoki undan katta bo'lishi kerak (ya'ni to'lovni kutayotgan "band qilingan joy"lar ham hisobga olinadi, faqat `active` emas) — shunda so'rov rad etilmaydi, balki enrollment `waitlisted` statusi va navbatdagi `waitlist_position` bilan yaratiladi. Bitta student bitta guruh uchun bir vaqtning o'zida faqat bitta **faol bo'lmagan-yakunlanmagan** (`awaiting_payment`/`waitlisted`/`active`) enrollment yozuviga ega bo'lishi mumkin — ammo avval bekor qilingan (`cancelled`) yoki muddati o'tgan (`expired`) enrollmentdan keyin **xuddi shu guruhga qayta yozilish so'rovi yuborish mumkin** (4.7/9-bo'limlarga qarang — bu yangi qator sifatida yaratiladi, eski yozuv tarixiy sifatida saqlanib qoladi).
7. **To'lov (soddalashtirilgan, bo'lib to'lash imkoniyati bilan)**: Faqat `enrollment.status == awaiting_payment` bo'lgan enrollment uchun to'lov/`PaymentPlan` yaratish mumkin (`waitlisted` yoki `active` holatidagi enrollment uchun `POST /payments` yoki `POST /enrollments/{id}/payment-plan` chaqirilsa — `400`). Student to'liq summani, yoki oldindan tanlagan `PaymentPlan` bo'yicha navbatdagi `Installment`ni "to'ladim" deb belgilaydi (summani kiritadi). Bu — haqiqiy to'lov tizimisiz, faqat yozuv: `Payment(amount, method="manual", status="pending")`, kerak bo'lsa tegishli `Installment`ga bog'lanadi.
8. **To'lovni tasdiqlash**: Manager to'lovni tasdiqlaydi → `Payment.status = "confirmed"`. Agar bu birinchi (yoki yagona) tasdiqlangan to'lov bo'lsa — shu zahoti `Enrollment.status = "active"` bo'ladi va student guruhning barcha darslariga (video) kirish huquqini oladi (Exode'dagi kabi: "to'lov qilgach darhol kursga kirish"). Bo'lib to'lashda har bir `Installment` alohida tasdiqlanadi; **oxirgi (eng katta `sequence_number`li) `Installment` `paid` bo'lganda avtomatik ravishda `PaymentPlan.status = "completed"` o'rnatiladi**. Qolgan `Installment`lar `due_date`ga ko'ra kuzatilib boriladi; muddati o'tgan bo'lak `overdue` statusiga o'tadi — bu tekshiruv **Celery beat periodic task** orqali amalga oshadi (har request'da emas, 8.2-bo'limga qarang), kirish avtomatik yopilmaydi (MVP uchun soddalashtirish), va bu haqda student/managerga bildirishnoma yuboriladi. **Agar to'lov (`Payment.status = "rejected"`) rad etilsa, `Enrollment.status` o'zgarmaydi** (agar u `awaiting_payment` bo'lsa, shunday qoladi — student sababni ko'rib, qayta to'lov yuborishi mumkin; tegishli `Installment` ham `pending`da qoladi, qayta to'lash mumkin). Har bir tasdiqlash/rad etishda tegishli `Notification` yaratiladi.
9. **Video tomosha qilish**: Student faqat `active` enrollment'i bor guruhlarning darslarini ko'ra oladi — faqat kinescope URL'i qaytariladi (frontend shu link orqali Kinescope player'ni ko'rsatadi). Dars ochilganda/"tomosha qilindi" deb belgilanganda `LessonProgress(watched=True, watched_at=...)` yozuvi yaratiladi/yangilanadi — teacher shu orqali o'z guruhidagi progressni kuzatadi.
10. **Hisobotlar**: Superadmin va manager dashboard/hisobot sahifalari orqali daromad, faol o'quvchilar, guruh statistikasi va h.k.ni ko'radi.
11. **Navbat (waitlist)dan faollashtirish**: `enrollments.service.promote_next_waitlisted(group_id)` funksiyasi quyidagi **barcha** holatlarda chaqiriladi (bittasi emas, uchtasi ham): (a) student o'z `awaiting_payment`/`active` enrollment'ini bekor qilsa (`DELETE /enrollments/{id}`, 6.6-bo'lim), (b) manager/superadmin studentning enrollment'ini majburiy bekor qilsa, (c) Celery beat orqali `awaiting_payment` enrollment muddati tugab avtomatik `expired` bo'lsa (15-band, quyida). Har uch holatda ham: navbatdagi eng birinchi student (`waitlist_position=1`) avtomatik `awaiting_payment` holatiga o'tkaziladi (`waitlist_position=NULL` qilinadi), unga bildirishnoma yuboriladi (`waitlist_promoted`), qolganlarning `waitlist_position`i bittaga kamayadi.
12. **Bildirishnomalar**: Har qanday muhim holat o'zgarishi (approve/reject, to'lov tasdiqlash/rad etish, guruhga biriktirish, waitlist'dan ko'tarilish, yangi dars qo'shilishi, bo'lak muddati o'tishi, enrollment muddati tugashi) tegishli foydalanuvchiga in-app `Notification` sifatida yoziladi; foydalanuvchi buni frontendda ko'radi va o'qilgan deb belgilashi mumkin. `group_assigned` — guruhga biriktirilgan teacher'ga; `lesson_added` — o'sha guruhdagi barcha `active` enrollment'li studentlarga yuboriladi. Notification yaratish **sinxron** (asosiy so'rov/transaksiya ichida) bajariladi — sababi 8.2-bo'limda tushuntirilgan.
13. **Audit va soft delete**: `Course`/`Group`/`Lesson` ustida `create/update/delete/restore` amali bajarilganda `AuditLog` yozuvi yaratiladi (kim, qachon, nima o'zgardi). `DELETE` amali yozuvni jismonan o'chirmaydi — faqat `deleted_at` maydonini to'ldiradi (soft delete); superadmin xohlasa uni "restore" qilishi mumkin.
14. **Manager akkauntlarini boshqarish**: Manager akkauntlari o'z-o'zidan ro'yxatdan o'ta olmaydi — faqat superadmin `POST /superadmin/managers` orqali to'g'ridan-to'g'ri (moderatsiyasiz, darhol `is_active=True`) yaratadi. Superadmin istalgan foydalanuvchini (student/teacher/manager) `POST /superadmin/users/{id}/block` orqali blokirovka qilishi mumkin (`status=blocked`, `is_active=False` — login/`/auth/refresh` darhol `403` qaytaradi) va `POST /superadmin/users/{id}/unblock` orqali qaytarishi mumkin (6.11-bo'lim).
15. **Enrollment so'rovi muddatining tugashi (fon vazifa)**: Agar `awaiting_payment` yoki `waitlisted` holatidagi enrollment `ENROLLMENT_REQUEST_EXPIRY_HOURS` (`.env`, standart — 72 soat) ichida `active`ga o'tmasa, Celery beat periodic task (`enrollments.tasks.expire_stale_enrollments`, har soatda ishga tushadi) uni avtomatik `expired` statusiga o'tkazadi, `Notification(type=enrollment_expired)` yuboradi va agar bu `awaiting_payment` bo'lgan bo'lsa — bo'shagan joy uchun 11-banddagi kabi navbatdagi waitlist studentini ko'taradi (8.2-bo'limga qarang).

---

## 4. Ma'lumotlar bazasi modeli (SQLAlchemy Entities)

### 4.1. `User` (base, users jadvali)
```
id: UUID (PK)
full_name: str
email: str (unique)
phone: str (unique, nullable)
hashed_password: str
role: enum(student, teacher, manager, superadmin)
status: enum(pending, approved, rejected, blocked)   # teacher/student uchun moderatsiya
is_active: bool
created_at, updated_at: datetime
```

### 4.2. `TeacherProfile` (1:1 User, role=teacher)
```
id: UUID (PK)
user_id: UUID (FK -> users.id, unique)
bio: text
specialization: str          # masalan "Matematika", "IELTS"
experience_years: int
approved_by: UUID (FK -> users.id, nullable)  # manager
approved_at: datetime (nullable)
```

### 4.3. `StudentProfile` (1:1 User, role=student)
```
id: UUID (PK)
user_id: UUID (FK -> users.id, unique)
birth_date: date (nullable)
approved_by: UUID (FK -> users.id, nullable)
approved_at: datetime (nullable)
```

### 4.4. `Course`
```
id: UUID (PK)
teacher_id: UUID (FK -> users.id)
title: str
description: text
subject: str                 # fan nomi
price: numeric(10,2)         # bitta guruh/kurs narxi (so'm)
status: enum(draft, active, archived)
deleted_at: datetime (nullable)      # soft delete — to'ldirilsa, yozuv "o'chirilgan" hisoblanadi
created_at, updated_at
```

### 4.5. `Group`
```
id: UUID (PK)
course_id: UUID (FK -> courses.id)
teacher_id: UUID (FK -> users.id)     # manager tomonidan biriktiriladi/tasdiqlanadi
name: str                             # "Guruh A - Dush/Chor 18:00"
capacity: int                         # maksimal o'quvchilar soni
schedule: str                         # matn ko'rinishida, masalan "Dush, Chor 18:00-19:30"
status: enum(draft, active, closed, archived)
approved_by: UUID (FK -> users.id, nullable)  # manager
approved_at: datetime (nullable)
deleted_at: datetime (nullable)      # soft delete
created_at, updated_at
```

### 4.6. `Lesson`
```
id: UUID (PK)
group_id: UUID (FK -> groups.id)
title: str
description: text (nullable)
kinescope_video_id: str            # kinescope video identifikatori
kinescope_url: str                 # to'liq video link (faqat url, fayl emas)
duration_seconds: int              # 300-600 oralig'ida (5-10 daqiqa) validatsiya
order_index: int                   # darslar tartibi
deleted_at: datetime (nullable)    # soft delete
created_at, updated_at
```

### 4.7. `Enrollment` (Student <-> Group)
```
id: UUID (PK)
student_id: UUID (FK -> users.id)
group_id: UUID (FK -> groups.id)
status: enum(awaiting_payment, waitlisted, active, expired, cancelled)
requested_at: datetime
activated_at: datetime (nullable)
cancelled_at: datetime (nullable)
waitlist_position: int (nullable)     # faqat status=waitlisted bo'lganda to'ldiriladi
# MUHIM: bu yerda oddiy table-level unique_constraint(student_id, group_id) ISHLATILMAYDI —
# aks holda bekor qilingan/muddati o'tgan enrollment o'sha (student, group) juftligini abadiy band qilib qo'yadi
# va student o'sha guruhga qayta yozila olmay qoladi (v1.0'dagi bug, 9-bo'limda tuzatilgan).
# O'rniga PARTIAL UNIQUE INDEX ishlatiladi (PostgreSQL):
#   CREATE UNIQUE INDEX uq_enrollment_active_per_group
#     ON enrollments (student_id, group_id)
#     WHERE status IN ('awaiting_payment', 'waitlisted', 'active');
# Ya'ni: bitta student — bitta guruh uchun bir vaqtning o'zida faqat BITTA yakunlanmagan
# (non-terminal) enrollment yozuviga ega bo'la oladi; cancelled/expired yozuvlar tarixiy
# hisoblanadi va yangi so'rov yaratilishiga to'sqinlik qilmaydi.
```

### 4.8. `Payment`
```
id: UUID (PK)
enrollment_id: UUID (FK -> enrollments.id)
student_id: UUID (FK -> users.id)
installment_id: UUID (FK -> installments.id, nullable)   # bo'lib to'lashda tegishli bo'lakka bog'lanadi
amount: numeric(10,2)
method: enum(manual)                  # real to'lov tizimi yo'q, faqat "manual"
status: enum(pending, confirmed, rejected)
confirmed_by: UUID (FK -> users.id, nullable)  # manager/superadmin
confirmed_at: datetime (nullable)
note: text (nullable)                 # manager izohi (masalan rad etish sababi)
created_at, updated_at
```

### 4.9. `PaymentPlan` (ixtiyoriy — student bo'lib to'lashni tanlaganda, 1:1 `Enrollment`)
```
id: UUID (PK)
enrollment_id: UUID (FK -> enrollments.id, unique)
total_amount: numeric(10,2)          # = Course.price
installments_count: int              # 2–4 oralig'ida (validator)
status: enum(active, completed, cancelled)
created_at, updated_at
```

### 4.10. `Installment` (`PaymentPlan` ichidagi har bir bo'lak)
```
id: UUID (PK)
payment_plan_id: UUID (FK -> payment_plans.id)
sequence_number: int                 # 1, 2, 3 ...
amount_due: numeric(10,2)
due_date: date (nullable)
status: enum(pending, paid, overdue)
unique_constraint(payment_plan_id, sequence_number)
```

### 4.11. `RefreshToken` (rotatsiya va blacklist/revocation uchun)
```
id: UUID (PK)
user_id: UUID (FK -> users.id)
token_hash: str (unique)              # tokenning o'zi emas, SHA-256 hash'i saqlanadi
issued_at: datetime
expires_at: datetime
revoked: bool (default False)
replaced_by_token_hash: str (nullable)   # rotatsiya zanjiri — eski token yangisiga almashtirilganda to'ldiriladi
user_agent: str (nullable)
ip_address: str (nullable)
```

### 4.12. `LessonProgress` (majburiy — 2.1-bo'limdagi "teacher progressni ko'radi" talabini qondirish uchun)
```
id: UUID (PK)
student_id: UUID (FK -> users.id)
lesson_id: UUID (FK -> lessons.id)
watched: bool (default False)
watched_at: datetime (nullable)
unique_constraint(student_id, lesson_id)
```

### 4.13. `Notification`
```
id: UUID (PK)
user_id: UUID (FK -> users.id)
type: enum(profile_approved, profile_rejected, payment_confirmed, payment_rejected,
           enrollment_activated, waitlist_promoted, group_assigned, lesson_added, installment_overdue,
           enrollment_expired, account_blocked, account_unblocked)
title: str
message: text
is_read: bool (default False)
related_entity_type: str (nullable)   # masalan "payment", "group"
related_entity_id: UUID (nullable)
created_at: datetime
```

### 4.14. `AuditLog` (`Course`/`Group`/`Lesson` uchun o'zgarishlar tarixi)
```
id: UUID (PK)
entity_type: enum(course, group, lesson)
entity_id: UUID
action: enum(create, update, delete, restore)
actor_id: UUID (FK -> users.id)
changes: JSONB (nullable)            # {"field": {"old": ..., "new": ...}} formatida diff
created_at: datetime
```

### 4.15. ER munosabatlar xulosasi
```
User (teacher) 1---N Course
Course 1---N Group
Group N---1 User (teacher, biriktirilgan)
Group 1---N Lesson
User (student) N---N Group  (orqali Enrollment)
Enrollment 1---N Payment   (odatda 1:1, lekin qayta to'lov holatlari uchun 1:N)
Enrollment 1---1 PaymentPlan (ixtiyoriy, bo'lib to'lashda)
PaymentPlan 1---N Installment
Installment 1---1 Payment (to'langanda)
User 1---N RefreshToken
User 1---N Notification
User (student) N---N Lesson  (orqali LessonProgress)
User (actor) 1---N AuditLog
```

---

## 5. Loyihaning papka strukturasi

```
edugroup/
├── alembic/
│   ├── versions/
│   └── env.py
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── pyproject.toml
├── app/
│   ├── main.py                     # FastAPI app, router include (API + web), StaticFiles/Jinja2Templates mount
│   ├── core/
│   │   ├── config.py               # pydantic Settings (.env) — shu jumladan REDIS_URL, CELERY_*, ENROLLMENT_REQUEST_EXPIRY_HOURS
│   │   ├── security.py             # jwt yaratish/tekshirish (python-jose), parol hash (passlib), refresh token hash+rotatsiya logikasi
│   │   ├── dependencies.py         # get_current_user (header uchun), role-based deps
│   │   ├── rate_limit.py           # slowapi Limiter konfiguratsiyasi, storage_uri=Redis (/auth/login, /auth/register uchun) — 8.2-bo'lim
│   │   ├── celery_app.py           # Celery() instance, broker/backend=Redis, beat_schedule (periodic tasks ro'yxati) — 8.2-bo'lim
│   │   └── exceptions.py           # custom HTTPException handlers
│   ├── db/
│   │   ├── base.py                 # Base declarative, import barcha modellar
│   │   ├── session.py              # async engine (asyncpg), async_sessionmaker, get_db — FastAPI route'lar uchun
│   │   ├── sync_session.py         # SYNC engine (psycopg/psycopg2), sync sessionmaker — FAQAT Celery task'lar uchun (8.2-bo'lim: Celery worker sync process, asyncpg session'ni ishlata olmaydi)
│   │   └── mixins.py                # UUID PK, timestamp mixin, SoftDeleteMixin (deleted_at)
│   ├── users/                      # <-- barcha user-related fayllar shu yerda
│   │   ├── models.py                # User, TeacherProfile, StudentProfile, RefreshToken
│   │   ├── schemas.py                # Pydantic: UserCreate, UserOut, ProfileOut...
│   │   ├── repository.py             # DB query'lar (CRUD)
│   │   ├── service.py                 # biznes-logika (approve/reject, register, login, refresh-rotation, logout)
│   │   └── router.py                 # /auth, /users, /me endpointlari
│   ├── courses/
│   │   ├── models.py                # Course (soft delete)
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── router.py
│   ├── groups/
│   │   ├── models.py                # Group (soft delete)
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── router.py
│   ├── lessons/
│   │   ├── models.py                # Lesson (Kinescope URL, soft delete), LessonProgress
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py
│   │   └── router.py
│   ├── enrollments/
│   │   ├── models.py                # Enrollment (waitlist bilan, partial unique index)
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py               # yozilish, waitlist navbati (promote_next_waitlisted), avtomatik ko'tarish, cancel_enrollment
│   │   ├── tasks.py                 # Celery task: expire_stale_enrollments (beat, sync DB session orqali) — 8.2-bo'lim
│   │   └── router.py
│   ├── payments/
│   │   ├── models.py                # Payment, PaymentPlan, Installment
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py               # confirm/reject logikasi, enrollment activate, installment tracking, PaymentPlan auto-complete
│   │   ├── tasks.py                 # Celery task: flag_overdue_installments (beat, sync DB session orqali) — 8.2-bo'lim
│   │   └── router.py
│   ├── notifications/
│   │   ├── models.py                # Notification
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   ├── service.py                # create_notification(...) — boshqa modullar shu funksiyani chaqiradi
│   │   └── router.py                 # /notifications, /notifications/{id}/read
│   ├── audit/
│   │   ├── models.py                # AuditLog
│   │   ├── service.py                 # log_change(...) — soft delete/update qiluvchi service'lar shu funksiyani chaqiradi
│   │   └── router.py                  # /audit-logs (faqat superadmin)
│   ├── manager/
│   │   └── router.py                # manager uchun aggregator endpointlar
│   ├── superadmin/
│   │   └── router.py                # /superadmin/managers, /superadmin/users/{id}/block|unblock — users.service funksiyalarini chaqiradi (6.11-bo'lim)
│   ├── reports/
│   │   ├── schemas.py
│   │   ├── service.py                # superadmin uchun statistik querylar
│   │   └── router.py
│   └── web/                          # <-- Jinja2 SSR sahifalar (frontend), JSON API'dan alohida
│       ├── dependencies.py            # get_current_user_from_cookie — JWT'ni httpOnly cookie'dan o'qib tekshiradi
│       ├── router.py                  # barcha web sahifa-routerlarini yig'ib main.py'ga include qiladi
│       └── pages/
│           ├── public.py               # GET / , GET /courses/{id}, GET /groups/{id}
│           ├── auth.py                 # GET/POST /login, GET/POST /register, POST /logout
│           ├── student.py               # GET /dashboard (student), POST forma-handlerlar (enroll, pay, mark-watched)
│           ├── teacher.py               # GET /dashboard (teacher), POST forma-handlerlar (course/group/lesson yaratish)
│           ├── manager.py               # GET /dashboard (manager), POST forma-handlerlar (approve/reject/assign/confirm)
│           └── superadmin.py            # GET /dashboard (superadmin), hisobot va audit-log sahifalari
├── templates/                          # Jinja2 shablonlar (14-bo'limga qarang)
├── static/                              # CSS/JS/rasm fayllari (14-bo'limga qarang)
├── tests/                            # <-- BARCHA testlar shu yerda (app/ ichida emas)
│   ├── conftest.py                    # async test client, test DB (transaction rollback per test), fixtures
│   ├── factories.py                   # test uchun User/Course/Group/Lesson factory funksiyalari
│   ├── users/
│   │   ├── test_register.py
│   │   ├── test_login.py
│   │   ├── test_profile.py
│   │   ├── test_refresh_token_rotation.py     # rotatsiya va reuse-detection
│   │   └── test_rate_limit_login.py            # 429 stsenariysi
│   ├── manager/
│   │   ├── test_approve_reject.py
│   │   └── test_assign_teacher.py
│   ├── superadmin/
│   │   ├── test_create_manager.py
│   │   └── test_block_unblock_user.py
│   ├── courses/
│   │   └── test_courses_crud.py
│   ├── groups/
│   │   ├── test_groups_crud.py
│   │   └── test_group_capacity.py
│   ├── lessons/
│   │   ├── test_lessons_crud.py
│   │   ├── test_lesson_duration_validation.py
│   │   ├── test_lesson_access_control.py    # faqat active enrollment kirishi mumkinligi
│   │   └── test_lesson_progress.py            # watched belgilash, teacher progress ko'rishi
│   ├── enrollments/
│   │   ├── test_enrollments.py
│   │   ├── test_waitlist_promotion.py         # to'la guruh, waitlist, avtomatik ko'tarish
│   │   ├── test_reenroll_after_cancel.py      # bekor qilingandan keyin xuddi shu guruhga qayta yozilish mumkinligi (partial unique index)
│   │   └── test_expire_stale_enrollments_task.py   # Celery task: muddati o'tgan awaiting_payment/waitlisted → expired + promote
│   ├── payments/
│   │   ├── test_payment_create.py
│   │   ├── test_payment_confirm_activates_enrollment.py
│   │   ├── test_installment_plan_completion.py
│   │   ├── test_payment_plan_requires_awaiting_payment.py   # waitlisted/active holatda 400 qaytishi
│   │   └── test_flag_overdue_installments_task.py           # Celery task: overdue flagging + notification
│   ├── notifications/
│   │   └── test_notifications_created_on_events.py
│   ├── audit/
│   │   └── test_audit_log_on_soft_delete.py
│   ├── reports/
│   │   └── test_reports_filters.py
│   └── web/
│       └── test_web_pages_render.py            # asosiy sahifalar 200 qaytarishi, auth-himoyalangan sahifalar redirect qilishi
└── README.md
```

> **Eslatma:** Har bir domain-modul (`users`, `courses`, `groups`, `lessons`, `enrollments`, `payments`, `notifications`, `audit`) bir xil ichki qatlamlarga ega: `models → schemas → repository → service → router`. Bu FastAPI'da keng tarqalgan "vertical slice" arxitekturasi bo'lib, loyihani "overcomplicated" qilmasdan, kengaytirishga qulay qiladi. `app/web/` alohida qatlam sifatida shu domain-modullarning `service.py` funksiyalarini qayta ishlatadi, hech qanday biznes-logikani takrorlamaydi.
>
> **Testlar** loyihaning ildizida (`tests/`), `app/` papkasidan tashqarida joylashadi va har bir domain-modulga mos ichki papkaga bo'linadi. Bu Python paketlash amaliyotida standart holat (production kodi test kodi bilan aralashmaydi) va CI/CD, coverage konfiguratsiyasi uchun ham qulayroq. Har bir service/router funksiyasi uchun kamida bitta pytest test yozilishi talab qilinadi (muvaffaqiyatli holat + kamida bitta xatolik/ruxsat holati).

---

## 6. API endpointlari (asosiy ro'yxat)

### 6.1. Autentifikatsiya (`/auth`)
| Method | Endpoint | Rol | Tavsif |
|---|---|---|---|
| POST | `/auth/register/student` | public | Student ro'yxatdan o'tishi (status=pending) |
| POST | `/auth/register/teacher` | public | Teacher ro'yxatdan o'tishi (status=pending) |
| POST | `/auth/login` | public | JWT access+refresh token qaytaradi (rate-limited: 5/daqiqa/IP) |
| POST | `/auth/refresh` | public | Refresh token orqali yangi access+refresh token (eski refresh **rotatsiya qilinib revoke** bo'ladi; qayta ishlatilsa — barcha tokenlar revoke qilinadi) |
| POST | `/auth/logout` | authenticated | Joriy refresh token'ni revoke qiladi |
| GET | `/users/me` | authenticated | Joriy foydalanuvchi profili |
| PATCH | `/users/me` | authenticated | Profilni tahrirlash |

### 6.2. Manager — moderatsiya (`/manager`)
| Method | Endpoint | Tavsif |
|---|---|---|
| GET | `/manager/users?status=pending&role=teacher` | Tasdiqlanishi kerak bo'lgan foydalanuvchilar |
| POST | `/manager/users/{user_id}/approve` | Profilni tasdiqlash |
| POST | `/manager/users/{user_id}/reject` | Profilni rad etish (sabab bilan) |
| POST | `/manager/groups/{group_id}/assign-teacher` | Guruhga teacher biriktirish/tasdiqlash |
| GET | `/manager/groups` | Barcha guruhlar (filtr: status, teacher) |
| GET | `/manager/payments?status=pending` | Tasdiqlanishi kerak bo'lgan to'lovlar |

### 6.3. Kurslar (`/courses`)
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/courses` | teacher |
| GET | `/courses` | public/authenticated (filtr: subject, teacher, status=active) |
| GET | `/courses/{id}` | public |
| PATCH | `/courses/{id}` | teacher (o'ziniki), manager, superadmin |
| DELETE | `/courses/{id}` | teacher (o'ziniki, draft bo'lsa), superadmin |

### 6.4. Guruhlar (`/groups`)
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/groups` | teacher (draft holatda yaratadi) |
| GET | `/groups` | public (faqat active), teacher/manager (o'zinikilar/hammasi) |
| GET | `/groups/{id}` | public |
| PATCH | `/groups/{id}` | teacher (o'ziniki, cheklangan maydonlar), manager |
| GET | `/groups/{id}/students` | teacher (o'ziniki), manager, superadmin |

### 6.5. Darslar (`/lessons`)
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/groups/{group_id}/lessons` | teacher (o'z guruhiga) |
| GET | `/groups/{group_id}/lessons` | active enrollment'ga ega student, teacher, manager, superadmin |
| GET | `/lessons/{id}` | faqat kirish huquqi borlar (kinescope URL qaytadi) |
| PATCH | `/lessons/{id}` | teacher (o'ziniki), superadmin |
| DELETE | `/lessons/{id}` | teacher (o'ziniki, soft delete), superadmin |
| POST | `/lessons/{id}/progress` | student (active enrollment) — darsni "tomosha qilindi" deb belgilaydi (`LessonProgress`) |
| GET | `/groups/{id}/progress` | teacher (o'ziniki), manager, superadmin — guruhdagi barcha o'quvchilarning progress jadvali |

### 6.6. Ro'yxatga yozilish (`/enrollments`)
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/enrollments` | student — `{group_id}` bilan yozilish so'rovi (guruh to'la bo'lsa `status=waitlisted` bilan yaratiladi) |
| GET | `/enrollments/me` | student — o'z yozilishlari (waitlist pozitsiyasi bilan) |
| GET | `/enrollments` | manager/superadmin — barcha yozilishlar (filtr) |
| GET | `/groups/{id}/waitlist` | teacher (o'ziniki), manager, superadmin — guruh navbati (tartib bo'yicha) |
| DELETE | `/enrollments/{id}` | student (o'ziniki — `awaiting_payment`/`waitlisted`/`active` istalgan holatda bekor qilish) yoki manager/superadmin (istalgan studentniki, majburiy `reason` bilan) — `status=cancelled` qiladi; agar bekor qilingan enrollment `waitlisted` bo'lsa, qolganlarning pozitsiyasi qayta hisoblanadi; agar `awaiting_payment`/`active` bo'lsa — bo'shagan joy uchun `enrollments.service.promote_next_waitlisted()` chaqiriladi (3.11-bandga qarang) |

### 6.7. To'lovlar (`/payments`) — soddalashtirilgan, real integratsiyasiz, bo'lib to'lash bilan
| Method | Endpoint | Rol |
|---|---|---|
| POST | `/enrollments/{id}/payment-plan` | student — `{installments_count}` (2–4) bilan `PaymentPlan` + `Installment`lar yaratadi |
| GET | `/enrollments/{id}/payment-plan` | student (o'ziniki), manager, superadmin — to'lov jadvali (qaysi bo'lak to'langan/kutilmoqda/muddati o'tgan) |
| POST | `/payments` | student — `{enrollment_id, amount}` yoki `{installment_id, amount}` → status=pending |
| GET | `/payments/me` | student — o'z to'lovlari tarixi |
| POST | `/payments/{id}/confirm` | manager/superadmin — enrollment'ni faollashtiradi, tegishli installment'ni `paid` qiladi, `Notification` yaratadi |
| POST | `/payments/{id}/reject` | manager/superadmin — sabab bilan rad etadi, `Notification` yaratadi |
| GET | `/payments` | superadmin — barcha to'lovlar (filtr: sana, guruh, teacher, status) |

### 6.8. Hisobotlar (`/reports`)
| Method | Endpoint | Rol | Tavsif |
|---|---|---|---|
| GET | `/reports/overview` | superadmin | Umumiy: foydalanuvchilar soni, daromad, faol guruhlar (global, faqat superadmin) |
| GET | `/reports/revenue?from=&to=&group_id=&teacher_id=` | superadmin | Global daromad hisobotlari, filtrlar bilan |
| GET | `/reports/groups/{id}` | teacher (o'ziniki), manager (o'zi tasdiqlagan/boshqargan guruh), superadmin | Guruh bo'yicha to'liq hisobot (o'quvchilar, to'lovlar, darslar) |
| GET | `/reports/teachers/{id}` | manager, superadmin | Teacher bo'yicha statistikasi (guruhlar, o'quvchilar, daromad) |

### 6.9. Bildirishnomalar (`/notifications`)
| Method | Endpoint | Rol |
|---|---|---|
| GET | `/notifications` | authenticated — joriy foydalanuvchining bildirishnomalari (filtr: `is_read`) |
| POST | `/notifications/{id}/read` | authenticated — o'ziniki bildirishnomani o'qilgan deb belgilaydi |
| POST | `/notifications/read-all` | authenticated — barchasini o'qilgan deb belgilaydi |

### 6.10. Audit log (`/audit-logs`) — faqat superadmin
| Method | Endpoint | Tavsif |
|---|---|---|
| GET | `/audit-logs?entity_type=&entity_id=&actor_id=&date_from=&date_to=` | `Course`/`Group`/`Lesson` ustidagi barcha create/update/delete/restore tarixi, filtrlar va sahifalash bilan |
| POST | `/courses/{id}/restore`, `/groups/{id}/restore`, `/lessons/{id}/restore` | superadmin — soft-delete qilingan yozuvni tiklaydi (`AuditLog`ga `restore` action yoziladi) |

### 6.11. Superadmin — foydalanuvchi/manager boshqaruvi (`/superadmin`) — **YANGI (v2.0), v1.0'da yo'q edi**
> Bu bo'lim v1.0'dagi bugni tuzatadi: 2.1-bo'limdagi ruxsatlar matritsasida "superadmin manager yaratadi" va "hisoblarni boshqaradi" deyilgan, lekin mos endpoint umuman mavjud emas edi.

| Method | Endpoint | Rol | Tavsif |
|---|---|---|---|
| POST | `/superadmin/managers` | superadmin | Yangi manager akkaunt to'g'ridan-to'g'ri yaratadi (moderatsiyasiz, `status=approved`, `is_active=True` darhol) |
| GET | `/superadmin/managers` | superadmin | Barcha manager akkauntlari ro'yxati |
| POST | `/superadmin/users/{user_id}/block` | superadmin | Istalgan foydalanuvchini (`student`/`teacher`/`manager`) blokirovka qiladi — `status=blocked`, `is_active=False`; keyingi login/`/auth/refresh` `403` qaytaradi; `Notification(type=account_blocked)` yuboradi |
| POST | `/superadmin/users/{user_id}/unblock` | superadmin | Blokdan chiqaradi — oldingi statusga (`approved`) qaytaradi, `is_active=True`; `Notification(type=account_unblocked)` yuboradi |

---

## 7. Autentifikatsiya va xavfsizlik

- **JWT** (python-jose, `HS256`), `access_token` (30 daqiqa) + `refresh_token` (7 kun). Ikkala token ham **`httpOnly`, `Secure`, `SameSite=Lax` cookie** sifatida qo'yiladi — frontend/JS token qiymatiga hech qachon kira olmaydi (14-bo'limga qarang).
- Parollar `bcrypt` (passlib) orqali hash qilinadi.
- **Refresh token rotatsiyasi va blacklist (revocation)** — `RefreshToken` jadvali orqali (4.11-bo'lim):
  - Har safar `/auth/refresh` chaqirilganda: eski token `revoked=True` qilinadi, yangi refresh token yaratiladi va `replaced_by_token_hash` orqali eskisiga bog'lanadi (rotatsiya zanjiri).
  - Bazada tokenning o'zi emas, faqat **SHA-256 hash'i** saqlanadi.
  - `/auth/logout` joriy refresh tokenni darhol revoke qiladi.
  - **Reuse detection**: agar allaqachon `revoked=True` bo'lgan refresh token bilan `/auth/refresh` chaqirilsa (token o'g'irlanganidan dalolat) — shu foydalanuvchining barcha faol refresh tokenlari revoke qilinadi va qayta login talab qilinadi.
- **Rate limiting** (`slowapi`): `/auth/login` va `/auth/register/*` IP bo'yicha cheklanadi (masalan 5 so'rov/daqiqa); limitdan oshsa `429 Too Many Requests` — brute-force himoyasi. **Storage backend — Redis** (`storage_uri="redis://redis:6379/0"`), in-memory emas: agar `app` konteyneri bir nechta Uvicorn worker (yoki kelajakda bir nechta replika) bilan ishga tushirilsa, har bir worker/instansning o'z alohida in-memory hisoblagichi bo'ladi va real limit ko'p barobar oshib ketadi — Redis umumiy, markazlashtirilgan hisoblagich bo'lib xizmat qiladi (8.2-bo'limga qarang).
- `app/core/dependencies.py` ichida rol asosidagi dependency'lar:
  ```python
  def require_roles(*roles: UserRole):
      def dependency(current_user: User = Depends(get_current_user)):
          if current_user.role not in roles:
              raise HTTPException(403, "Ruxsat yo'q")
          return current_user
      return dependency
  ```
- Har bir himoyalangan endpointda `Depends(require_roles(...))` ishlatiladi.
- Video endpoint (`/lessons/{id}`) ichida qo'shimcha tekshiruv: joriy student shu guruhga `active` enrollment'ga egami — bo'lmasa `403`.
- **Audit va soft delete**: `Course`/`Group`/`Lesson` ustidagi `create/update/delete/restore` amallari `AuditLog`ga yoziladi; `DELETE` fizik o'chirish emas, `deleted_at` maydonini to'ldiradi.

---

## 8. Texnik talablar / stack

| Komponent | Texnologiya |
|---|---|
| Backend framework | FastAPI (async, Python 3.12) |
| ORM | SQLAlchemy 2.0 (async, `asyncpg` driver) |
| Migratsiya | Alembic |
| Autentifikatsiya | python-jose (JWT) + passlib[bcrypt] |
| Validatsiya | Pydantic v2 |
| Ma'lumotlar bazasi | PostgreSQL 16 |
| Konteynerizatsiya | Docker, docker-compose (app + db + redis + celery_worker + celery_beat + adminer ixtiyoriy) |
| Test | pytest, pytest-asyncio, pytest-cov, httpx (ASGI transport) |
| Video hosting | Kinescope (faqat URL/video_id saqlanadi, hech qanday fayl yuklash yo'q) |
| Rate limiting | `slowapi`, **storage backend = Redis** (`redis` xizmati) — 7/8.2-bo'lim |
| Fon vazifalar (background jobs) | **Celery** (worker + beat), broker/result backend = **Redis** — 8.2-bo'lim |
| Frontend | Jinja2 (server-rendered), vanilla HTML/CSS/JS (framework yo'q) — 14-bo'limga qarang |

### 8.1. Docker Compose xizmatlari
```yaml
services:
  app:
    build: .
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [db, redis]
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: edugroup
      POSTGRES_USER: edugroup
      POSTGRES_PASSWORD: edugroup
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redisdata:/data]
  celery_worker:
    build: .
    env_file: .env
    command: celery -A app.core.celery_app worker --loglevel=info
    depends_on: [db, redis]
  celery_beat:
    build: .
    env_file: .env
    command: celery -A app.core.celery_app beat --loglevel=info
    depends_on: [db, redis]
volumes:
  pgdata:
  redisdata:
```

### 8.2. Celery / Redis arxitekturasi va texnik detallar
Bu bo'lim v2.0'da qo'shilgan — Celery/Redis **faqat asosli bo'lgan joyda** kiritilgan, hamma joyga majburan tiqishtirilmagan:

**Nima uchun kerak:**
- **Fon vazifalar (periodic tasks)** — quyidagi ikkita jarayon vaqt bo'yicha, so'rovdan mustaqil ishlashi kerak, shuning uchun bitta HTTP request ichida bajarib bo'lmaydi:
  1. `enrollments.tasks.expire_stale_enrollments` — Celery beat orqali **har soatda** ishga tushadi; `ENROLLMENT_REQUEST_EXPIRY_HOURS` (standart 72 soat) dan ko'p vaqt o'tgan `awaiting_payment`/`waitlisted` enrollmentlarni topib `expired` qiladi, `Notification(enrollment_expired)` yaratadi va agar kerak bo'lsa `promote_next_waitlisted()`ni chaqiradi (3.15-band).
  2. `payments.tasks.flag_overdue_installments` — Celery beat orqali **kuniga bir marta** (masalan har kuni 03:00da) ishga tushadi; `due_date < bugun` va `status=pending` bo'lgan `Installment`larni `overdue` qiladi va tegishli studentga+guruh menejeriga `Notification(installment_overdue)` yaratadi.
- **Rate-limit storage** — `slowapi`ning Redis backend'i (Celery bilan bog'liq emas, lekin xuddi shu Redis instansidan foydalanadi — infratuzilmani soddalashtirish uchun).

**Nima uchun KERAK EMAS (ataylab qo'shilmagan):**
- **Notification yaratish Celery orqali navbatga QO'YILMAYDI** — chunki bu MVP'da faqat oddiy DB yozuvi (real email/SMS integratsiyasi yo'q, 15-bo'lim), tashqi I/O yo'q. Uni navbatga qo'yish hech qanday amaliy foyda bermaydi, faqat keraksiz "eventual consistency" muammosini (masalan to'lov tasdiqlangan, lekin bildirishnoma hali yaratilmagan) va murakkablikni qo'shadi. Notification yaratish **sinxron ravishda, asosiy `service.py` funksiyasi ichida, bir xil DB transaksiyasida** amalga oshiriladi. Kelajakda haqiqiy email/SMS qo'shilsa (15-bo'lim, "kengaytma"), aynan o'sha bosqichda tashqi I/O qismini (email yuborish) Celery task'ga chiqarish mantiqiy bo'ladi — lekin bu TZ doirasidan tashqarida.
- **Audit log yozuvi** ham sinxron qoladi — u state-change bilan bir xil transaksiyada, atomik ravishda yozilishi SHART (aks holda audit trail nomukammal bo'lib qolishi mumkin).

**Texnik muhim eslatma (Celery + async SQLAlchemy):** `app`ning asosiy FastAPI qatlami **async** SQLAlchemy (`asyncpg` drayveri, `app/db/session.py`) ishlatadi, lekin Celery worker **sinxron** Python process bo'lib ishlaydi va asyncpg session'ini to'g'ridan-to'g'ri ishlata olmaydi. Shu sababli:
- `app/db/sync_session.py` — alohida **sinxron** SQLAlchemy engine (`psycopg` yoki `psycopg2` drayveri bilan, xuddi o'sha PostgreSQL bazaga ulanadi) va `sessionmaker` yaratiladi, **faqat Celery task'lar** shundan foydalanadi.
- SQLAlchemy modellar (`app/*/models.py`) drayverdan mustaqil — bir xil model klasslari ham async, ham sync session bilan ishlatilishi mumkin, shuning uchun modelni ikki marta yozish shart emas.
- Har bir Celery task o'zining domain-modul `service.py`sidagi **sinxron variantdagi** funksiyani chaqiradi (masalan `enrollments/service.py` ichida `expire_stale_enrollments_sync(db: Session)` — asosiy `async def` funksiyalardan alohida, lekin bir xil biznes-qoidani bajaradigan sinxron hamkasbi). Bu ikki marta kod yozishga o'xshab ko'rinsa-da, amaliyotda FastAPI+Celery loyihalarida standart yechim — chunki Celery'ning o'zi `asyncio` event loop'ida ishlamaydi.
- `celery_app.py`da `beat_schedule` — ikkala periodic task uchun `crontab`/`timedelta` jadvali `core/config.py`dagi sozlamalardan (`.env`) o'qiladi (masalan `ENROLLMENT_EXPIRY_CHECK_INTERVAL_SECONDS=3600`, `OVERDUE_INSTALLMENT_CHECK_CRON="0 3 * * *"`).

**RabbitMQ haqida eslatma:** Ushbu loyiha hajmi uchun **Redis** Celery broker sifatida yetarli va infratuzilmani soddalashtiradi (bitta xizmat — ham broker, ham result backend, ham rate-limit storage). RabbitMQ ancha og'irroq, kelajakda yuqori yuklama/kafolatlangan yetkazish (guaranteed delivery, murakkab routing) kerak bo'lganda almashtirish uchun tavsiya etiladi, lekin bu TZ doirasida **talab qilinmaydi**.

---

## 9. Validatsiya qoidalari (muhim)

- `Lesson.duration_seconds`: 300 ≤ x ≤ 600 (5–10 daqiqa) — Pydantic validator orqali.
- `Lesson.kinescope_url`: regex/URL validatsiya, `kinescope.io` domenini o'z ichiga olishi tavsiya etiladi.
- `Payment.amount`: agar `PaymentPlan` mavjud bo'lmasa — `Course.price`ga teng bo'lishi kerak (to'liq to'lov, ortiqcha/kam to'lovga ruxsat berilmaydi). Agar `PaymentPlan` mavjud bo'lsa — `amount` tegishli `Installment.amount_due`ga teng bo'lishi kerak.
- **`POST /payments` va `POST /enrollments/{id}/payment-plan` faqat `enrollment.status == awaiting_payment` bo'lganda ruxsat etiladi** — aks holda (`waitlisted`, `active`, `expired`, `cancelled`) `400` qaytadi. Bu — v2.0'da aniqlashtirilgan qoida (3.7-band).
- `PaymentPlan.installments_count`: 2–4 oralig'ida bo'lishi kerak (Pydantic validator).
- `Installment.amount_due` qiymatlarining yig'indisi har doim `PaymentPlan.total_amount` (= `Course.price`)ga teng bo'lishi shart — aks holda `422`.
- **`PaymentPlan.status = "completed"`** — oxirgi (eng katta `sequence_number`li) `Installment.status = "paid"` bo'lganda `payments.service.confirm_payment()` ichida avtomatik o'rnatiladi (3.8-band).
- **`Payment.status = "rejected"` bo'lganda `Enrollment.status` o'ZGARMAYDI** — student/tegishli `Installment` qayta to'lov yuborishi mumkin (3.8-band).
- **`Enrollment` — partial unique index** (`WHERE status IN ('awaiting_payment','waitlisted','active')`, jadval-darajasidagi oddiy `unique_constraint` EMAS): bitta student bir guruh uchun bir vaqtning o'zida faqat bitta yakunlanmagan yozuvga ega bo'ladi, lekin `cancelled`/`expired` bo'lgan eski yozuvdan keyin xuddi shu guruhga yangi `POST /enrollments` so'rovi yuborilishi mumkin (4.7-bo'lim — v1.0'dagi bug tuzatildi).
- **`Group` "to'la" mezoni**: `status IN ('awaiting_payment','active')` bo'lgan enrollmentlar soni `capacity`ga teng yoki undan katta bo'lsa — yangi so'rov `waitlisted` bilan yaratiladi (flat `400` o'rniga). Faqat `active` (to'langan) enrollmentlarni hisoblash **noto'g'ri** — bu ortiqcha to'lov kutayotgan (`awaiting_payment`) joylarni e'tiborsiz qoldirib, guruhni real ehtiyojdan ko'proq "band qilingan" holga keltirib yuborishi mumkin (overselling xatari).
- **`Group.capacity` PATCH orqali kamaytirilganda**: yangi `capacity` qiymati joriy `status IN ('awaiting_payment','active')` enrollmentlar sonidan kichik bo'lishi mumkin emas — aks holda `422` (mavjud studentlarni "joyi yo'q" holatiga tushirib qo'ymaslik uchun).
- **`Group.status` o'tishlari**: `draft → active` (faqat `assign-teacher` orqali, manager/superadmin), `active → closed` (yangi yozilish qabul qilinmaydi, mavjud `active` enrollmentlar videoga kirishni davom ettiradi), `active/closed → archived` (katalogdan butunlay yashiriladi). `closed`/`archived` guruh `GET /` va `GET /groups` (public) natijalarida ko'rinmaydi.
- **`ENROLLMENT_REQUEST_EXPIRY_HOURS`** (`.env`, standart 72): shu muddatdan ko'p vaqt `awaiting_payment`/`waitlisted` holatida qolgan enrollment Celery beat orqali `expired` qilinadi (3.15, 8.2-bo'lim).
- Soft delete: `deleted_at IS NOT NULL` bo'lgan `Course`/`Group`/`Lesson` standart ro'yxatlash so'rovlarida (`GET /courses`, `GET /groups` va h.k.) ko'rsatilmaydi; faqat superadmin `include_deleted=true` parametri bilan ko'rishi mumkin.
- `User.status = "blocked"` bo'lgan foydalanuvchi `/auth/login` va `/auth/refresh`da `403` oladi (6.11-bo'lim).

---

## 10. Superadmin hisobotlari uchun filtrlar (batafsil)

`/reports/revenue` va `/payments` endpointlari quyidagi query-parametrlarni qo'llab-quvvatlaydi:
- `date_from`, `date_to`
- `teacher_id`
- `group_id`
- `status` (`pending`, `confirmed`, `rejected`)
- `subject` (Course.subject orqali join)

Natija sahifalab (`limit`, `offset`) va jami summalar (`total_amount`, `total_count`) bilan qaytariladi.

`/audit-logs` esa `entity_type`, `entity_id`, `actor_id`, `date_from`, `date_to` bo'yicha filtrlashni qo'llab-quvvatlaydi (sahifalash bilan).

---

## 11. Keyingi bosqichlar (loyihani amalga oshirish tartibi)

1. Loyiha skeleti, `pyproject.toml`/`requirements.txt`, Docker konfiguratsiyasi (`app`, `db`, `redis`, `celery_worker`, `celery_beat` — 8.1-bo'lim)
2. `db/base.py`, `db/session.py` (async), `db/sync_session.py` (sync, Celery uchun), config (`core/config.py` — shu jumladan `REDIS_URL`, `CELERY_*`, `ENROLLMENT_REQUEST_EXPIRY_HOURS`), soft-delete va timestamp mixin'lar (`db/mixins.py`)
3. `users` modul: model, JWT auth (`python-jose`), `RefreshToken` rotatsiyasi/blacklist, rate limiting (`slowapi`, Redis backend), register/login/logout, rol dependencylari
4. Alembic init + birinchi migratsiya (`users`, `refresh_tokens` jadvallari)
5. `courses`, `groups`, `lessons` modullari (soft delete bilan) + migratsiyalar
6. `enrollments` (waitlist logikasi, partial unique index, `cancel_enrollment`), `payments` (`PaymentPlan`/`Installment` bilan) modullari + biznes-logika (to'lov tasdiqlanganda enrollment faollashishi, waitlist'dan avtomatik ko'chirish, `PaymentPlan` auto-complete)
7. `notifications` moduli (boshqa modullar tomonidan ichkaridan chaqiriladigan `create_notification()` bilan, sinxron — 8.2-bo'lim)
8. `manager`, `superadmin` (6.11-bo'lim: manager yaratish, block/unblock), `reports` va `audit` modullari (agregatsiya so'rovlari, o'zgarishlar tarixi, soft-delete restore)
9. `app/core/celery_app.py`, `enrollments/tasks.py`, `payments/tasks.py` — Celery worker/beat konfiguratsiyasi va ikkita periodic task (8.2-bo'lim)
10. `app/web/` — Jinja2 SSR sahifalar: `templates/`, `static/`, har bir rol uchun dashboard, katalog, login/register sahifalari, profil/edit/status-change formalari (14-bo'limga qarang — barcha 14.3-jadvaldagi mappinglar to'liq qamrab olinishi shart)
11. Testlar (pytest) — asosiy oqimlar: register → approve → create group → enroll (yoki waitlist) → to'liq/bo'lib to'lash → confirm → watch lesson → progress; refresh token rotation/reuse-detection, rate-limit, Celery task (expiry/overdue) testlari
12. README, `code_explanation.md` va `.env.example`, Docker Compose bilan to'liq ishga tushirish tekshiruvi (`app`, `db`, `redis`, `celery_worker`, `celery_beat` barchasi ishga tushishi shart)

---

## 12. Test strategiyasi

- Framework: **pytest** + **pytest-asyncio** (`asyncio_mode = auto`) + **httpx.AsyncClient** (`ASGITransport`) FastAPI ilovasini haqiqiy server ko'tarmasdan test qilish uchun.
- Test bazasi: alohida PostgreSQL sxema/baza (`edugroup_test`) yoki har bir test funksiyasi uchun transaction ochib, oxirida rollback qilinadi (`conftest.py`da `db_session` fixture).
- **Qoida:** har bir `service.py` funksiyasi va har bir `router.py` endpointi uchun kamida bitta pytest test bo'lishi shart:
  - "happy path" (muvaffaqiyatli stsenariy)
  - kamida bitta ruxsat/validatsiya xatoligi (403/404/400) stsenariysi
- Muhim end-to-end oqim albatta test qilinishi kerak (`tests/payments/test_payment_confirm_activates_enrollment.py`):
  `register student → manager approve → teacher creates course/group → manager approves group → student enrolls → student creates payment → manager confirms payment → enrollment becomes active → student can fetch lesson kinescope url` va aksincha (tasdiqlanmagan holatda `403`).
- Qo'shimcha majburiy oqimlar:
  - `tests/enrollments/test_waitlist_promotion.py` — guruh to'lganda yangi so'rov `waitlisted` bo'lishi, faol enrollment bekor qilinganda navbatdagi student avtomatik `awaiting_payment`ga ko'chishi.
  - `tests/enrollments/test_reenroll_after_cancel.py` — enrollment bekor qilingandan/muddati tugagandan keyin xuddi shu student xuddi shu guruhga qayta yozilish so'rovi yubora olishi (partial unique index to'g'ri ishlashi, v1.0 bugi qaytmasligi).
  - `tests/enrollments/test_expire_stale_enrollments_task.py` — Celery task `ENROLLMENT_REQUEST_EXPIRY_HOURS`dan oshgan `awaiting_payment`/`waitlisted` enrollmentni `expired` qilishi va waitlist'ni ko'tarishi (sync DB session bilan to'g'ridan-to'g'ri chaqirilib test qilinadi, brokerga bog'liq bo'lmasdan).
  - `tests/payments/test_installment_plan_completion.py` — barcha bo'laklar tasdiqlangach `PaymentPlan.status=completed` bo'lishi, birinchi bo'lak tasdiqlanishi bilanoq enrollment faollashishi.
  - `tests/payments/test_payment_plan_requires_awaiting_payment.py` — `waitlisted`/`active` holatidagi enrollment uchun `POST /payments` yoki `POST /enrollments/{id}/payment-plan` chaqirilsa `400` qaytishi.
  - `tests/payments/test_payment_rejection_keeps_status.py` — to'lov rad etilganda `Enrollment.status` o'zgarmasligi, qayta to'lov yuborish mumkinligi.
  - `tests/payments/test_flag_overdue_installments_task.py` — Celery task muddati o'tgan `Installment`larni `overdue` qilishi va `Notification(installment_overdue)` yaratishi.
  - `tests/users/test_refresh_token_rotation.py` — eski refresh token qayta ishlatilganda foydalanuvchining barcha tokenlari revoke bo'lishi (reuse detection).
  - `tests/users/test_rate_limit_login.py` — limitdan oshganda `429` qaytishi (Redis storage backend bilan).
  - `tests/superadmin/test_create_manager.py` — superadmin yangi manager yaratishi, boshqa rollar `403` olishi.
  - `tests/superadmin/test_block_unblock_user.py` — bloklangan foydalanuvchi login/refresh'da `403` olishi, unblock'dan keyin qayta kira olishi.
  - `tests/audit/test_audit_log_on_soft_delete.py` — `DELETE` chaqirilganda yozuv fizik o'chmasligi, `deleted_at` to'lishi va `AuditLog` yaratilishi.
  - `tests/lessons/test_lesson_progress.py` — student darsni "tomosha qildim" deb belgilashi va teacher progress jadvalida buni ko'rishi.
  - `tests/notifications/test_notifications_created_on_events.py` — approve/reject, payment confirm/reject, waitlist promotion, enrollment expiry, block/unblock holatlarida tegishli `Notification` yaratilishi.
- Coverage: `pytest-cov` orqali hisoblanadi, minimal maqsad — 80%+ (asosan `service.py` qatlamlari uchun).
- CI (ixtiyoriy kengaytma): GitHub Actions orqali har bir PR'da `pytest` avtomatik ishga tushiriladi.

---

## 13. README.md — loyiha "xaritasi" (AI-agentlar uchun token-tejamkor kontekst)

### 13.1. Maqsad
Loyiha bilan ishlaydigan AI kodlash vositalari (masalan, Claude Code) har safar barcha fayllarni skanerlash o'rniga, avval **`README.md`**ni o'qib, loyihaning to'liq xaritasini (arxitektura, modullar, endpointlar, qoidalar) bir joydan olishi kerak. Bu token sarfini sezilarli kamaytiradi va agent ishini tezlashtiradi.

### 13.2. README.md tarkibiy qismlari (majburiy)

1. **Loyiha haqida (2–3 jumla)** — nima qiladi, kimlar uchun (bu TZ'ning 1-bo'limiga havola/qisqacha xulosa).
2. **Tezkor ishga tushirish** — `docker compose up`, migratsiya buyrug'i (`alembic upgrade head`), test buyrug'i (`pytest`), `.env` namunasi.
3. **Arxitektura xaritasi** — har bir `app/<module>/` papkasi nima uchun javobgar ekanligi 1 qatorda (jadval ko'rinishida), masalan:
   ```
   app/users        -> autentifikatsiya, foydalanuvchi/teacher/student profillari
   app/courses      -> teacher yaratgan kurslar (Course)
   app/groups       -> kurs ichidagi guruhlar, manager tomonidan tasdiqlanadi
   app/lessons      -> guruh darslari, faqat Kinescope video URL saqlanadi
   app/enrollments  -> student-guruh bog'lanishi (yozilish so'rovlari, waitlist)
   app/payments     -> to'lov oqimi (manual, to'liq yoki bo'lib to'lash/installment)
   app/notifications-> in-app bildirishnomalar (sinxron yaratiladi — 8.2-bo'lim)
   app/audit        -> Course/Group/Lesson uchun o'zgarishlar tarixi, soft-delete restore
   app/manager      -> moderatsiya va biriktirish endpointlari
   app/superadmin   -> manager yaratish, foydalanuvchi block/unblock (6.11-bo'lim)
   app/reports      -> superadmin/manager/teacher uchun agregatsiya/statistika
   app/web          -> Jinja2 SSR sahifalar (frontend), JSON API'ni HTTP orqali emas, service.py orqali chaqiradi
   app/core/celery_app.py, */tasks.py -> Celery worker/beat: enrollment expiry, installment overdue flagging (8.2-bo'lim)
   ```
4. **Rollar va ruxsatlar jadvali** — TZ'dagi 2.1-bo'limning qisqartirilgan versiyasi.
5. **Ma'lumotlar modeli sxemasi** — jadvallar va ular orasidagi FK bog'lanishlar ro'yxati (to'liq ustunlar emas, faqat entity va munosabatlar — batafsili kerak bo'lsa `app/<module>/models.py`ga havola beriladi).
6. **Endpointlar xulosasi** — TZ 6-bo'limidagi jadvallarning qisqa versiyasi (method + path + rol + 1 qatorlik tavsif).
7. **Muhim biznes qoidalar ro'yxati** (bullet holida) — masalan:
   - "To'lov `confirmed` bo'lgandan keyingina enrollment `active` bo'ladi va video ochiladi."
   - "Lesson davomiyligi 300–600 soniya oralig'ida bo'lishi shart."
   - "Bitta student bitta guruhga faqat bitta faol enrollment'ga ega bo'lishi mumkin."
   - "Guruh to'lganda yangi so'rovlar rad etilmaydi — `waitlisted` navbatga qo'yiladi."
   - "Refresh token qayta ishlatilsa (rotatsiyadan keyin) — foydalanuvchining barcha tokenlari revoke qilinadi."
   - "Course/Group/Lesson o'chirilganda yozuv fizik o'chmaydi — `deleted_at` to'ldiriladi va `AuditLog` yoziladi."
8. **Qayerga qarash kerak (navigatsiya bo'yicha maslahat)** — agentga: "Agar X funksiyasini o'zgartirish kerak bo'lsa, Y faylga qarang" formatida qisqa yo'l-yo'riq. Masalan: "To'lov tasdiqlanganda enrollment qanday faollashishini o'zgartirish kerakmi? → `app/payments/service.py::confirm_payment` funksiyasiga qarang."
9. **O'zgarishlar tarixi eslatmasi**: har safar yangi modul/endpoint qo'shilganda README shu ro'yxatlarni yangilab turishi kerakligi haqida eslatma (README loyihaning "single source of truth" xulosasi bo'lib qolishi uchun).

### 13.3. Amaliy qoida
README doim **qisqa va struktura** bo'lishi kerak — kodni takrorlamaydi, faqat "qayerda nima borligi"ni ko'rsatadi. Har bir domain modulida ixtiyoriy ravishda kichik `app/<module>/README.md` ham bo'lishi mumkin (chuqurroq tafsilot uchun), lekin asosiy, majburiy hujjat — ildizdagi `README.md`.

> **Eslatma:** `README.md`ga qo'shimcha ravishda, loyiha ildizida **`code_explanation.md`** fayli ham bo'lishi shart — bu README'dan farqli o'laroq "qayerda nima bor"ni emas, balki "kod qanday va nima uchun aynan shunday ishlaydi"ni chuqur tushuntiradigan alohida hujjat (to'liq talab — `CLAUDE_CODE_PROMPT.md`, 16-bo'limga ham qarang). README uni takrorlamaydi, faqat mavjudligiga havola qiladi.

---

## 14. Frontend (Jinja2 + HTML/CSS/JS)

### 14.1. Maqsad va yondashuv
Frontend — alohida SPA (React/Vue) emas va client-side REST/AJAX'ga tayanmaydi. **Hammasi FastAPI'ning o'zida, to'liq server-rendered (SSR) tarzda ishlaydi**:
- Har bir sahifa — FastAPI GET route handler, u tegishli domain-modulning (`courses`, `groups`, `enrollments`, `payments`, `notifications`, ...) `service.py` funksiyalarini **bevosita import qilib chaqiradi** (HTTP orqali emas!) va natijani Jinja2 shabloniga context sifatida uzatib, tayyor HTML qaytaradi.
- Har bir forma (login, register, enroll, pay, approve, confirm, delete va h.k.) — oddiy HTML `<form method="post">`. Brauzer PATCH/DELETE'ni native qo'llab-quvvatlamaydi, shu bois barcha o'zgartiruvchi web-amallar **POST** orqali amalga oshadi (masalan `POST /web/courses/{id}/delete`), lekin ichida xuddi JSON API'dagi (`DELETE /courses/{id}`) bilan **bir xil** `service.py` funksiyasini chaqiradi — mantiq ikki marta yozilmaydi. Muvaffaqiyatli amaldan so'ng **Post/Redirect/Get** patterni bilan `GET`ga redirect qilinadi (forma qayta yuborilib ketmasligi uchun), xato bo'lsa forma flash-xabar bilan qayta render qilinadi.
- Autentifikatsiya **shu TZ'ning 7-bo'limidagi bir xil JWT (python-jose) oqimiga** asoslanadi, lekin token brauzerda `httpOnly`, `Secure`, `SameSite=Lax` cookie ichida saqlanadi. `app/web/dependencies.py`dagi `get_current_user_from_cookie` cookie'dan tokenni o'qib, `core/security.py` orqali decode qiladi — client-side JavaScript token qiymatiga umuman kira olmaydi va uni hech qayerga biriktirmaydi.
- 6-bo'limdagi JSON endpointlar TZ'da **saqlanadi** (kelajakda tashqi/mobil client yoki `tests/`da ishlatish uchun), lekin veb-sahifalar ularga hech qachon HTTP so'rov yubormaydi.

### 14.2. Papka strukturasi
```
app/
├── templates/
│   ├── base.html                 # umumiy layout: <head>, blok'lar (Jinja {% block %})
│   ├── partials/
│   │   ├── navbar.html            # rolga qarab turli havolalar + bildirishnoma soni (serverda hisoblanadi)
│   │   └── flash_messages.html    # forma xato/muvaffaqiyat xabarlari (PRG patterni uchun)
│   ├── home.html                  # public: faol kurslar/guruhlar katalogi, filtr (fan/narx/teacher), to'la guruhlarda "N kishi navbatda"
│   ├── login.html                 # login formasi
│   ├── register.html              # ro'yxatdan o'tish (student/teacher tanlovi bilan)
│   ├── profile.html               # profil ko'rish/tahrirlash (barcha rollar uchun umumiy) — YANGI, v2.0
│   ├── post_detail.html           # umumiy "detail" shabloni — kurs/guruh tafsilotlari, darslar ro'yxati, Kinescope player, enroll/waitlist tugmasi, tahrirlash rejimi (teacher/manager/superadmin uchun)
│   └── dashboard/
│       ├── student.html           # yozilishlarim (waitlist pozitsiyasi bilan), to'lov jadvalim (installment), faol darslarim+progress, bildirishnomalar
│       ├── teacher.html           # kurslarim/guruhlarim (CRUD), dars qo'shish, o'quvchilar+progress jadvali, bildirishnomalar
│       ├── manager.html           # moderatsiya navbati, to'lov tasdiqlash, teacher biriktirish, guruh waitlist ko'rinishi, bildirishnomalar
│       └── superadmin.html        # umumiy statistika, filtrlanadigan hisobot/to'lovlar jadvali, audit-log ko'rinishi, manager boshqaruvi
├── static/
│   ├── css/
│   │   ├── base.css               # reset, ranglar (CSS custom properties), tipografiya, grid/layout
│   │   └── components.css         # kartalar, tugmalar, formalar, jadval, status-badge, modal
│   ├── js/
│   │   ├── ui.js                  # modal ochish/yopish, tab almashish — sof DOM interaktivligi, ma'lumot olib kelmaydi
│   │   ├── validation.js          # client-side forma tekshiruvi (masalan lesson duration 300–600s, kinescope URL pattern) — faqat tezkor UX uchun, yakuniy tekshiruv baribir serverda
│   │   └── confirm.js             # destructive amallar (delete/reject) uchun `window.confirm()` bilan tasdiqlash
│   └── images/
└── web/
    ├── dependencies.py            # get_current_user_from_cookie
    ├── router.py
    └── pages/                     # 5-bo'limdagi papka strukturasiga qarang
```

> **Eslatma (nomlanish bo'yicha):** `post_detail.html` nomi loyiha domenidan (kurs/guruh/dars) kelib chiqmaydi — umumiy "bitta obyekt tafsiloti" shabloni sifatida talqin qilindi va kurs/guruh detail sahifasi uchun ishlatiladi. Kelajakda vizual/mantiqiy jihatdan ancha farqlansa, ikkiga (`course_detail.html`, `group_detail.html`) ajratish tavsiya etiladi.
>
> `register.html` va `partials/` — foydalanuvchi tomonidan berilgan boshlang'ich ro'yxatga (`base.html`, `home.html`, `login.html`, `post_detail.html`) qo'shilgan zaruriy kengaytmalar: 4 ta rol va shu qadar ko'p biznes-jarayon (waitlist, installment, notifications, audit) bilan 4 ta sahifada sig'dirib bo'lmaydi.

### 14.3. Har bir sahifaning to'liq TZ mantig'i bilan bog'lanishi
Quyidagi jadval — TZ'da tavsiflangan **har bir** biznes-qoida/endpointning frontendda qayerda ko'rsatilishini belgilaydi (6-bo'limdagi barcha endpoint guruhlari, jumladan yangi 6.11-bo'lim, to'liq qamrab olingan). **Talab:** 6-bo'limdagi JSON API'da mavjud bo'lgan HAR BIR o'qish/yozish amali quyidagi jadvalda kamida bitta veb-sahifa/forma bilan mos kelishi shart — agar biror endpoint uchun mos frontend qatori topilmasa, bu kamchilik hisoblanadi va tuzatilishi kerak (v2.0'da 9 ta shunday kamchilik topilib, quyida "**(YANGI, v2.0)**" belgisi bilan qo'shildi).

| Sahifa (route) | Shablon | Chaqiradigan service-funksiyalar (6-bo'limdagi endpoint mantiqiga mos) |
|---|---|---|
| `GET /` | `home.html` | `courses.service.list_active()`, `groups.service.list_active()` — filtr: fan/narx/teacher; to'la guruhda navbat uzunligi ko'rsatiladi |
| `GET /login`, `POST /login` | `login.html` | `users.service.login()` — muvaffaqiyatda cookie qo'yilib `/dashboard`ga redirect |
| `GET /register`, `POST /register` | `register.html` | `users.service.register_student()` / `register_teacher()` — muvaffaqiyatda "moderatsiya kutilmoqda" xabari bilan `login.html`ga redirect |
| `POST /logout` | — | `users.service.revoke_refresh_token()` — cookie tozalanadi, `/`ga redirect |
| `GET /profile`, `POST /web/profile/edit` | `profile.html` **(YANGI, v2.0)** | `users.service.get_me()` / `users.service.update_profile()` — `PATCH /users/me`ning web ekvivalenti; barcha rollar uchun umumiy, navbardan ochiladi |
| `GET /courses/{id}`, `GET /groups/{id}` | `post_detail.html` | `courses.service.get()`/`groups.service.get()`, `lessons.service.list_for_group()` (agar `active` enrollment bo'lsa — Kinescope player), aks holda "Yozilish" yoki "Navbatga qo'shilish" tugmasi; agar ko'ruvchi teacher(o'ziniki)/manager/superadmin bo'lsa — shu yerda `reports.service.group_report()`ga havola ham ko'rsatiladi |
| `POST /web/enrollments` | — | `enrollments.service.request_enrollment()` — to'la bo'lsa `waitlisted`, aks holda `awaiting_payment`; `post_detail.html`ga redirect |
| `POST /web/enrollments/{id}/cancel` **(YANGI, v2.0)** | — | `enrollments.service.cancel_enrollment()` — `DELETE /enrollments/{id}`ning web ekvivalenti; student o'z enrollment'ini (istalgan holatda) bekor qiladi, `student.html`dagi har bir qator yonida "Bekor qilish"/"Navbatdan chiqish" tugmasi orqali chaqiriladi |
| `GET /dashboard` | rolga qarab quyidagilarga redirect | `users.service.get_me()` orqali rol aniqlanadi |
| — student | `dashboard/student.html` | `enrollments.service.list_my()` (waitlist pozitsiyasi bilan, har qator yonida "Bekor qilish" tugmasi), `payments.service.list_my()`, `payments.service.get_plan()` (installment jadvali), `lessons.service.list_progress_for_student()`, `notifications.service.list_my()` |
| `POST /web/enrollments/{id}/payment-plan` | — | `payments.service.create_payment_plan()` — `{installments_count}` formadan (faqat `awaiting_payment` enrollment uchun ko'rsatiladi) |
| `POST /web/payments` | — | `payments.service.create_payment()` — to'liq yoki navbatdagi installment uchun |
| `POST /web/lessons/{id}/progress` | — | `lessons.service.mark_watched()` |
| — teacher | `dashboard/teacher.html` | `courses.service.list_mine()`, `groups.service.list_mine()`, `groups.service.get_students()`, `groups.service.get_waitlist()` **(YANGI, v2.0 — 2.1-bo'limda teacher'ga "o'z guruhi to'liq navbatini ko'rish" ruxsati berilgan edi, lekin frontendda yo'q edi)**, `lessons.service.get_group_progress()`, `reports.service.group_report()` (o'z guruhlari uchun) |
| `POST /web/courses`, `POST /web/groups`, `POST /web/lessons` | — | tegishli `service.create_*()` funksiyalari (draft holatda) |
| `GET /web/courses/{id}/edit`, `POST /web/courses/{id}/edit` **(YANGI, v2.0)** | `post_detail.html` (edit rejimi) yoki alohida `edit_form.html` | `courses.service.update()` — `PATCH /courses/{id}`ning web ekvivalenti |
| `GET /web/groups/{id}/edit`, `POST /web/groups/{id}/edit` **(YANGI, v2.0)** | shundaycha | `groups.service.update()` — `PATCH /groups/{id}`ning web ekvivalenti; shu formada guruh holatini (`active → closed → archived`) o'zgartirish tugmalari ham bo'ladi (manager/superadmin uchun; 3.4/9-bo'limlarga qarang) |
| `GET /web/lessons/{id}/edit`, `POST /web/lessons/{id}/edit` **(YANGI, v2.0)** | shundaycha | `lessons.service.update()` — `PATCH /lessons/{id}`ning web ekvivalenti |
| `POST /web/courses/{id}/delete` va h.k. | — | `service.soft_delete_*()` — `deleted_at` to'ldiradi, `audit.service.log_change()` chaqiradi |
| — manager | `dashboard/manager.html` | `users.service.list_pending()`, `payments.service.list_pending()`, `groups.service.list_all()`, `enrollments.service.get_waitlist()`, `enrollments.service.list_all()` **(YANGI, v2.0 — filtrlanadigan umumiy enrollment ro'yxati, `GET /enrollments` endpointining frontend mappingi avval yo'q edi)** |
| `POST /web/manager/users/{id}/approve|reject` | — | `users.service.approve()`/`reject()` — `notifications.service.create()` chaqiradi |
| `POST /web/manager/groups/{id}/assign-teacher` | — | `groups.service.assign_teacher()` |
| `POST /web/manager/payments/{id}/confirm|reject` | — | `payments.service.confirm()`/`reject()` — enrollment faollashtiradi/installment yangilaydi, `notifications.service.create()` chaqiradi |
| `POST /web/enrollments/{id}/cancel` (manager/superadmin variant) | — | `enrollments.service.cancel_enrollment()` — majburiy `reason` maydoni bilan, `manager.html`dagi enrollment ro'yxatidan chaqiriladi |
| — superadmin | `dashboard/superadmin.html` | `reports.service.overview()`, `reports.service.revenue()` (GET query-parametr filtrlari bilan, forma orqali), `reports.service.teacher_report()` **(YANGI, v2.0 — `GET /reports/teachers/{id}` avval hech qayerda ko'rsatilmagan edi; teacherlar jadvalidan har biriga havola)**, `payments.service.list_all()`, `audit.service.list_logs()` (filtr: entity_type/actor/sana) |
| `POST /web/courses/{id}/restore` va h.k. | — | `service.restore_*()` — audit-logda `restore` action |
| `GET /web/superadmin/managers`, `POST /web/superadmin/managers` **(YANGI, v2.0)** | `dashboard/superadmin.html` ichida "Managerlar" bo'limi | `users.service.create_manager()` / `users.service.list_managers()` — `POST/GET /superadmin/managers`ning web ekvivalenti (6.11-bo'lim) |
| `POST /web/superadmin/users/{id}/block|unblock` **(YANGI, v2.0)** | — | `users.service.block()`/`unblock()` — `superadmin.html`dagi har qanday foydalanuvchi qatori yonida tugma sifatida |
| Navbar (barcha sahifalarda) | `partials/navbar.html` | `notifications.service.count_unread()` — har sahifa yuklanganda serverda hisoblanadi; alohida "bildirishnomalar" sahifasida `notifications.service.list_my()` + har bir yozuvni alohida "o'qilgan" deb belgilash formasi **va** "Barchasini o'qilgan qilish" tugmasi (`POST /notifications/read-all`ning web ekvivalenti — **YANGI, v2.0**, avval faqat bittalab belgilash mappingi bor edi) |

### 14.4. Autentifikatsiya va yo'naltirish (frontend qatlamida)
- Login/register formadan so'ng JWT `access_token`/`refresh_token` **httpOnly cookie** sifatida qo'yiladi — hech qanday JS bilan o'qilmaydi/saqlanmaydi.
- Har bir himoyalangan sahifa route'ida `Depends(get_current_user_from_cookie)` ishlatiladi; token yo'q/eskirgan bo'lsa `/login`ga redirect (`303 See Other`).
- Muvaffaqiyatli logindan so'ng foydalanuvchi `role`iga qarab tegishli `dashboard/*.html`ga yo'naltiriladi.
- Refresh token rotatsiyasi/reuse-detection va rate limiting (7-bo'lim) **to'liq shaffof** ishlaydi — foydalanuvchiga alohida ekran ko'rsatilmaydi; token eskirganda keyingi sahifa so'rovida avtomatik yangilanadi (yoki reuse aniqlansa — qayta login talab qilinadi).

### 14.5. Xavfsizlik sababli frontendda **ko'rsatilmaydigan** narsalar
Bu — TZ'ning talabi bo'yicha ("hech qanday mantiq/API tashlab ketilmasin, xavfsizlik yoki senior amaliyotiga zid bo'lmasa") ataylab chetlab o'tilgan qismlar va sababi:
- **Raw JWT/refresh token qiymati yoki hash'i** — hech qanday sahifada ko'rsatilmaydi (faqat `httpOnly` cookie ichida, backendga ko'rinadi).
- **Rate-limit ichki holati** (masalan qancha urinish qolgani) — faqat `429` bo'lganda foydalanuvchiga umumiy "biroz kuting" xabari ko'rsatiladi, aniq limit sonlari oshkor qilinmaydi (hujumchiga ma'lumot bermaslik uchun).
- **Boshqa foydalanuvchining shaxsiy ma'lumotlari** (email/telefon) — faqat manager/superadmin dashboard'larida, ular ruxsatiga mos darajada ko'rinadi (2.1-bo'lim ruxsatlar matritsasiga qat'iy mos).
- **PATCH/DELETE HTTP metodlari brauzerda ishlatilmaydi** — bu HTML spetsifikatsiyasining tabiiy cheklovi, shu sababli web-qatlamda hamma o'zgartiruvchi amal POST orqali amalga oshadi (yuqorida tushuntirilgan); bu FastAPI+Jinja2 SSR loyihalarda keng tarqalgan, "senior" amaliyot hisoblanadi.

### 14.6. Integratsiya bo'yicha eslatma
`app/main.py`da Jinja2Templates va StaticFiles mount qilinadi (`templates = Jinja2Templates(directory="templates")`, `app.mount("/static", StaticFiles(directory="static"), name="static")`) va `app/web/router.py` asosiy `app`ga include qilinadi. Bu — mavjud domain-modullarning (`users`, `courses`, `groups`, ...) JSON API qatlamiga hech qanday ta'sir qilmaydi; `app/web/` faqat shu modullarning `service.py` funksiyalarini iste'mol qiluvchi yangi, alohida qatlam sifatida qo'shiladi.

### 14.7. Dizayn talablari
- Mobile-first, responsive (breakpoint: ~768px).
- Ranglar/o'lchamlar CSS custom properties (`:root { --color-primary: ...; }`) orqali markazlashtirilgan.
- Framework yo'q — vanilla JS faqat UI interaktivligi uchun (modal, tab, client-side validatsiya, confirm dialog); ma'lumot olish uchun hech qachon ishlatilmaydi.
- Status badge'lar (`pending`, `waitlisted`, `awaiting_payment`, `active`, `confirmed`, `rejected`, `overdue` va h.k.) uchun rangli indikatorlar (`components.css`).

---

## 15. Loyihadan tashqarida qoladigan narsalar (Out of scope)

- Haqiqiy to'lov tizimlari integratsiyasi (Payme/Click/Uzum API)
- Video yuklash/transkodlash (faqat Kinescope URL saqlanadi)
- Mobil ilova (native iOS/Android) — faqat veb-frontend (Jinja2 SSR) TZ doirasiga kiradi
- Email/SMS xabarnomalar (kengaytma sifatida qoldiriladi) — **Celery/Redis infratuzilmasi (8.2-bo'lim) shu kengaytma uchun poydevor tayyorlaydi, lekin real email/SMS jo'natish hozircha out-of-scope**: Celery hozircha faqat DB-ichki periodic tekshiruvlar (enrollment expiry, installment overdue) uchun ishlatiladi, tashqi xizmatlarga (SendGrid, Twilio va h.k.) hech qanday chaqiruv qilinmaydi.
- Real-time messenger (Exode'dagi kabi ichki chat) — MVP doirasidan tashqarida

---

## 16. Qo'shimcha talab: `code_explanation.md`

Loyiha ildizida `README.md`dan tashqari **`code_explanation.md`** fayli ham yaratilishi shart. Bu ikkalasi turli maqsadlarga xizmat qiladi:
- `README.md` — "qayerda nima bor" (navigatsiya, AI-agent uchun token-tejamkor xarita).
- `code_explanation.md` — "kod nima uchun va qanday ishlaydi" (chuqur, o'qitiladigan tushuntirish; loyiha muallifi keyinchalik og'zaki himoya/imtihonda har qanday fayl/funksiya bo'yicha savolga javob bera olishi uchun).

`code_explanation.md`ning to'liq tarkibiy talablari **`CLAUDE_CODE_PROMPT.md`**da keltirilgan — bu yerda faqat uning mavjudligi va maqsadi TZ darajasida qayd etilmoqda, chunki u ham loyihaning yakuniy deliverable'lari qatoriga kiradi (11-bo'lim, oxirgi qadam).
