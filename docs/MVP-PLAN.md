# MVP rejasi — «Тендер-Сверка»

> Versiya 0.1 · 2026-10-11 · Asos: TZ v0.1 §12
> Arxitektura: [ARCHITECTURE.md](ARCHITECTURE.md) · Konveyer va AI: [PIPELINE.md](PIPELINE.md)

---

## 0. Bir qarashda

```
            Okt 2026   Noy          Dek          Yan 2027     Fev          Mar
Sprint 0    ██                                                               Poydevor + tadqiqot
Sprint 1      ██                                                             Qabul, matnli hujjatlar, orkestrator
Sprint 2         ███                                                         End-to-end yupqa kesim (matnli PDF)
Sprint 3            ███                                                      Skanlar/OCR + chek-list sifati
Sprint 4               ███                                                   Solishtirish chuqurligi + «Сравнение»
Sprint 5                  ██████                                             Tavsiyalar, xulosa, eksport (Yangi yil bilan)
Sprint 6                        ███                                          Mustahkamlash → MVP RELIZ 22.01.2027
Pilot                              ████████████                              5–10 kompaniya, 6 hafta
Kengaytirish                                   ████████▶                     Buyurtmachi rejimi, integratsiyalar
```

**Strategiya: avval xavfli qism, keyin vertikal kesim.** Sprint 0 da eng noaniq ikki narsa o'lchanadi: o'zbekcha skanlarda OCR sifati va LLM ajratishining to'liqligi. Sprint 2 oxirida esa butun zanjir (yuklash → chek-list → solishtirish → %) matnli PDF'larda ishlashi kerak. Undan keyingi har bir sprint shu ishlaydigan zanjirni chuqurlashtiradi, uni noldan qurmaydi.

---

## 1. Taxminlar (o'zgarsa, reja qayta ko'rib chiqiladi)

| # | Taxmin | Manba |
|---|---|---|
| A1 | MVP ning birinchi foydalanuvchisi **yetkazib beruvchi** (o'z arizasini tekshiradi). Buyurtmachi rejimi (N ta ariza) kengaytirish bosqichida | TZ §12, MVP ro'yxati |
| A2 | Asosiy xarid turi: O'zbekiston davlat xaridlari (tender, tanlov, eng yaxshi takliflarni tanlash) | TZ §13, javob kutilmoqda |
| A3 | Dasturlash va pilot davomida bulutli LLM (Claude API) ishlatish mumkin. On-prem yo'li adapter orqali ochiq qoladi | TZ §13, javob kutilmoqda |
| A4 | Jamoa 3 dasturchi + yarim stavka tender eksperti + product owner. Sprint 2 hafta | Baho |
| A5 | Mahsulot API'ga ega mustaqil servis. TenderZone/TenderGPT ga integratsiya kengaytirish bosqichida | TZ §13, javob kutilmoqda |
| A6 | Ish 12.10.2026 dan boshlanadi | — |

> **Jamoa kichikroq bo'lsa** (1–2 kishi), muddatlar taxminan 2 baravar uzayadi, ketma-ketlik o'zgarmaydi. Claude Code bilan ishlash boilerplate qismini sezilarli tezlashtiradi, lekin sifat iteratsiyasi (eval → tuning) va ekspert vaqti tezlashmaydi.

---

## 2. MVP doirasi

| Kiradi (MVP) | MVP+ (vaqt bo'lsa / pilot) | Kirmaydi (kengaytirish) |
|---|---|---|
| Ikki paketni yuklash, arxivlar, barcha TZ formatlari (DWG/DXF dan tashqari) | Qayta tekshirish + «История» (72% → 94%) | Buyurtmachi rejimi: N ariza va matritsa |
| OCR: skanlar, fotolar, jadvallar, muhr/imzo/QR | Loyiha bo'yicha chat | DWG/DXF |
| Tillar: UZ (lotin + kirill), RU, EN. Boshqalari «LLM qo'llagancha» | Telefon OTP login | Tashqi reyestrlar (STIR, insofsiz ijrochilar, litsenziyalar) |
| Talablar chek-listi (T/U), tahrirlash, tasdiqlash, «Вопросы к заказчику» | Chizmalar: o'lcham va dopusklarni solishtirish | TenderZone importi, TenderGPT moduli |
| Ariza faktlari, hujjat tekshiruvlari | Tushuntirish va o'zgartirishlar → chek-list diff | Ommaviy API va API kalitlar |
| Solishtirish: 5 status, ikki manba, qo'lda o'zgartirish | | Platforma SSO, Kubernetes |
| Skoring, verdikt, prognoz | | |
| Tavsiyalar, 1 sahifalik xulosa, tushuntirish so'rovi | | |
| Eksport: PDF, XLSX, DOCX, JSON | | |
| Interfeys RU / UZ / EN, rollar, audit | | |
| Chizmalar: shtamp + texnik talablar matni | | |

---

## 3. Jamoa va rollar

| Rol | Kod | Mas'uliyat |
|---|---|---|
| Backend / infra lead | **BE** | API, ma'lumotlar modeli, orkestrator, qoidalar dvigateli, skoring, eksport, xavfsizlik, deploy |
| AI / ML muhandis | **AI** | OCR, LLM gateway, promptlar, ajratish, judge, eval, sifat tuning |
| Frontend | **FE** | 7 ta ekran, DocumentViewer, i18n |
| Tender eksperti (0.5) | **EXP** | Etalon to'plam va belgilash, domen bo'yicha promptlarni ko'rib chiqish, UAT |
| Product owner | **PO** | Biznes qarorlari (§8), ustuvorliklar, pilot mijozlari |

---

## 4. Sprintlar va vazifalar

Baho ishchi kunlarda (person-day). Har bir vazifaning ID'si commit va PR nomlarida ishlatiladi: `feat(I-05): ...`.

### Sprint 0 · 12.10 – 23.10 · Poydevor va tadqiqot

**Maqsad:** dev muhit ishlaydi, eng katta texnik noaniqliklar o'lchangan, qarorlar ADR sifatida yozilgan.

| ID | Vazifa | Tayyor bo'lish mezoni (DoD) | Kim | Kun |
|---|---|---|---|---|
| F-01 | Repo: git, monorepo tuzilmasi ([ARCHITECTURE §5](ARCHITECTURE.md)), uv + pnpm, ruff/mypy/eslint, pre-commit, Makefile | `make lint`, `make test` ishlaydi | BE | 1 |
| F-02 | `docker-compose.yml`: postgres (pgvector), redis, clamav, api, worker, web. Fayl ombori: Cloudflare R2 (dev bucket). `.env.example` | `docker compose up` → barcha healthcheck'lar yashil | BE | 1.5 |
| F-03 | Backend skeleti: pydantic-settings, DB session, Alembic, bazaviy modellar (org, user, membership, project, package, file), xatolar, structlog, Sentry, `/health` | Migratsiya ishlaydi, pytest + testcontainers | BE | 2 |
| F-04 | Auth + RBAC + audit: login/refresh/logout, JWT cookie, rollar, `org_id` konteksti + RLS | Integration test: boshqa org ma'lumoti ko'rinmaydi | BE | 3 |
| F-05 | Frontend skeleti: Vite + React + TS, routing (7 ekran stub), maketdagi tablar, i18n RU/UZ/EN, login, OpenAPI klient | Login → bo'sh «Проекты» | FE | 3 |
| F-06 | CI (GitHub Actions): lint, test, build | PR'da yashil | BE | 1 |
| FE-00 | UI kit (shadcn), status ranglari, KPI kartalar. TZ maketi asosida ekranlar prototipi | PO prototiplarni ma'qullaydi | FE | 4 |
| L-01 | LLM gateway v1: `AnthropicProvider`, `messages.parse` + Pydantic, prompt registri, `llm_calls` keshi, xarajat hisobi, retry, refusal + fallback, token-bucket | Bitta route end-to-end ishlaydi, takroriy chaqiruv keshdan keladi | AI | 3 |
| R-02 | **OCR benchmark:** 50–80 sahifa (UZ lotin/kirill, RU, EN; skan 150/200/300 dpi, telefon fotosi, jadvallar, muhrlar) × engine'lar (Docling, PaddleOCR, Tesseract, Surya, Azure DI, Claude vision). O'lchanadi: CER, jadval aniqligi, tezlik, narx, litsenziya | `docs/adr/ADR-002-ocr.md` | AI | 4 |
| R-03 | **LLM ajratish spike:** 3 tender, Opus 5.5 (effort high va medium), natijani qo'lda tekshirish: recall, precision, token va $ / sahifa | `docs/adr/ADR-003-extraction.md` + xarajat bahosi | AI | 3 |
| R-01 | **Etalon to'plam:** `gold_schema.json`, 10 tender + arizalarni yig'ish, ekspert 5 tasini belgilaydi (ilova tayyor bo'lguncha Excel shablonda) | 10 tender papkada, 5 tasi belgilangan | EXP, PO | davomiy |
| R-04 | **Biznes qarorlari** (§8, Q1–Q5) | Yozma javoblar | PO | — |

**Demo:** login → bo'sh loyihalar ro'yxati. OCR va ajratish benchmarklari natijalari, xarajat bahosi.

### Sprint 1 · 26.10 – 06.11 · Qabul, matnli hujjatlar, orkestrator

**Maqsad:** fayllar yuklanadi, sahifalarga ajratiladi, matn bbox bilan olinadi, progress real vaqtda ko'rinadi.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| I-01 | Loyiha va paket CRUD API + «Проекты» ekrani | Loyiha yaratish, ro'yxat, o'chirish | BE 1.5, FE 2 | 3.5 |
| I-02 | Yuklash: presigned multipart, limitlar, sha256 dedup, ClamAV, MIME sniffing + «Загрузка» ekrani (2 zona, drag-and-drop) | 100 fayl / 500 MB yuklanadi, limitdan oshsa aniq xabar | BE 2, FE 2 | 4 |
| I-03 | Arxivlar: ZIP/RAR/7Z, rekursiya ≤ 3, zip-slip va zip-bomb himoyasi | Testlarda yomon arxivlar rad etiladi | BE | 1.5 |
| I-04 | Konvertatsiya: LibreOffice → PDF, HEIC/TIFF/WEBP, sahifa render 200 dpi + thumbnail | Barcha TZ formatlari (DWG'dan tashqari) sahifalarga aylanadi | BE | 2 |
| I-05 | Matn qatlami: PyMuPDF bloklar + bbox, `find_tables()`, XLSX/CSV native, UDR ni saqlash | Matnli PDF va DOCX → `pages` + `blocks` | AI | 3 |
| I-06 | Orkestrator: `pipeline_steps`, navbatlar, idempotentlik, retry, fan-out/fan-in + SSE + UI progress paneli | Paket qayta ishlanishini bosqichlar bo'yicha ko'rish mumkin, qayta ishga tushirish dublikat yaratmaydi | BE 4, FE 1.5 | 5.5 |
| I-07 | `doc.classify` + rekvizitlar + UI'da turini tuzatish | Etalon hujjatlarda tur aniqligi ≥ 90% | AI 2, FE 1 | 3 |
| I-08 | `DocumentViewer` v1: PDF.js + bbox overlay + sahifaga o'tish | Blok tanlansa, sahifada belgilanadi | FE | 3 |
| EV-01 | Eval harness skeleti: gold loader, recall va citation validity, hisobot | `uv run eval/run_eval.py --set mini` ishlaydi | AI | 3 |

**Demo:** tender papkasini (ZIP) yuklash → hujjatlar turlari bilan → sahifani ochish va bloklarni ko'rish.

### Sprint 2 · 09.11 – 20.11 · End-to-end yupqa kesim (matnli PDF)

**Maqsad:** haqiqiy (matnli) tenderda butun zanjir ishlaydi: chek-list → faktlar → solishtirish → %.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| Q-01 | `tender.meta`: pozitsiyalar, topshirish muddati, baholash mezonlari + UI'da muddatni tahrirlash | Etalonda muddat va pozitsiyalar to'g'ri | AI 2, FE 0.5 | 2.5 |
| Q-02 | Strukturaviy chunking (bandlar, jadvallar qatorlar bo'yicha) | Birorta blok chunk'lardan tashqarida qolmaydi (test) | AI | 1.5 |
| Q-03 | `req.extract` v1: sxema, prompt, prompt caching | Etalonda birinchi recall o'lchovi | AI | 3 |
| Q-04 | Sitata tekshiruvi + manba lokalizatsiyasi (bbox) + `extraction_rejects` | Citation validity = 100% | BE | 2 |
| Q-05 | Normallashtirish: pint + `units.yaml`, `parameters.yaml` (~150 parametr seed), qiymat parse | Unit testlar: RU/UZ/EN birliklar va formatlar | BE | 3 |
| B-01 | `bid.extract` v1 (maqsadli) + manba ustuvorligi | Faktlar talablarga bog'langan, sitatalari tekshirilgan | AI | 3 |
| M-01 | Qoidalar dvigateli: barcha operatorlar + hypothesis testlari | [PIPELINE §5.4](PIPELINE.md) dagi barcha holatlar testda | BE | 3 |
| S-01 | Skoring + verdikt + [PIPELINE §6.5](PIPELINE.md) test vektori | Test vektori aniq mos keladi | BE | 1.5 |
| FE-01 | Chek-list v1 (ko'rish + tasdiqlash) va Solishtirish jadvali v1 (statuslar, KPI kartalar, viewer'ga havola) | Demo ssenariysi brauzerda ishlaydi | FE | 8 |
| EV-02 | Eval: majburiy talablar recall, status aniqligi, false-green. Birinchi to'liq o'lchov | `eval/reports/` da birinchi hisobot | AI | 1 |

**Demo (muhim bosqich):** matnli tender + ariza → tasdiqlangan chek-list → statuslar → % va verdikt. Eval'dagi birinchi raqamlar.

### Sprint 3 · 23.11 – 04.12 · Skanlar va chek-list sifati

**Maqsad:** skan va fotolar ishlaydi, chek-list to'liq va toza, foydalanuvchi uni to'liq tahrirlay oladi.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| I-09 | Preprocessing (OpenCV): orientatsiya, deskew, perspektiva, denoise, CLAHE | Telefon fotosida CER benchmarkdan yaxshilangan | AI | 3 |
| I-10 | OCR adapter + tanlangan engine (ADR-002), jadval tuzilmasi, ko'p sahifali jadvallar | Skanlar UDR ga aylanadi, jadval kataklari bilan | AI | 3 |
| I-11 | `page.read` (vision ikkinchi o'qish) + raqamlar cross-check + `needs_review` sahifalar | Raqam kelishmovchiligi ishonchni pasaytiradi, UI'da ogohlantirish chiqadi | AI | 2.5 |
| I-12 | Muhr, imzo, QR + sana parse (RU/UZ/EN) + `valid_until` | Etalon hujjatlarda to'g'ri | BE | 2 |
| I-13 | Til aniqlash + o'zbekcha normallashtirish va translit | «қувват» = «quvvat» testlari | BE | 1 |
| Q-06 | Havolalarni ochish (`req.resolve_refs`) | «Приложение 3 ga ko'ra» talablari to'liq | BE | 2 |
| Q-07 | Dublikat, qarama-qarshilik, cheklovchi talablar → `customer_issues` | 24 va 12 oy kabi holatlar topiladi | BE | 2.5 |
| Q-08 | Qoplama auditi: detektor + `req.coverage` + `coverage_gaps` + jadval nazorati | `coverage_rate` eval'da kuzatiladi | AI | 2 |
| Q-09 | Chek-list API: CRUD, merge, approve, versiyalash, T/U ID berish | [PIPELINE §3.6](PIPELINE.md) qoidalari testda | BE | 2.5 |
| Q-10 | «Чек-лист» ekrani to'liq: inline tahrir, filtrlar, qo'shish/birlashtirish/o'chirish, savollar bloki, qoplama bo'shliqlari, tasdiqlash oqimi | PO va ekspert ssenariylardan o'tadi | FE | 6 |
| FE-02 | «Загрузка»: o'qib bo'lmaydigan sahifalar ogohlantirishi, hujjat turlari ro'yxati | — | FE | 2 |

**Demo:** telefonda suratga olingan va skanerlangan tender → to'liq chek-list, savollar bloki, qo'lda tuzatish va tasdiqlash.

### Sprint 4 · 07.12 – 18.12 · Solishtirish chuqurligi va «Сравнение» ekrani

**Maqsad:** solishtirish TZ §6 ga to'liq mos, ekran maket bo'yicha.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| B-02 | Hujjat tekshiruvlari: muddat, imzo/muhr, rekvizitlar (STIR, nom), tarjima | [PIPELINE §4.1](PIPELINE.md) jadvali testda | BE | 2.5 |
| B-03 | Ishtirokchi identifikatsiyasi + ichki qarama-qarshiliklar (`bid_issues`) | Taklif va pasport o'rtasidagi farq topiladi | BE | 2 |
| B-04 | Pozitsiyalarni moslashtirish | Ko'p pozitsiyali lotlar etalonda to'g'ri | AI | 1.5 |
| B-05 | Gibrid qidiruv: BGE-M3 embedder, `chunks`, pgvector + FTS/trigram, RRF | Dalil qidiruvi recall@8 o'lchangan | BE | 3 |
| M-02 | `match.judge`: semantik, ekvivalentlik, yo'qlikni tekshirish | Sitatalar tekshirilgan, `needs_expert` → ⚪ | AI | 4 |
| M-03 | Qaror daraxti + darvozalar + ishonch hisoblash | False-green etalonda 0 | AI | 2.5 |
| M-04 | Matches API + qo'lda o'zgartirish (izoh majburiy) + audit + qayta hisoblash | O'zgartirish foizni darhol yangilaydi | BE | 2 |
| FE-03 | «Сравнение» ekrani to'liq: maket, split-view, ikki manba belgilangan, asos va tavsiya paneli, «Только проблемы», status o'zgartirish | Maketga mos, PO ma'qullaydi | FE | 8 |
| EV-03 | Eval (maqsad 20 tender) + xatolar tahlili #1 | Hisobot: top-10 xato turlari | AI | 1.5 |

**Demo:** TZ maketidagi ekran haqiqiy ma'lumotlar bilan, statusni qo'lda o'zgartirish, foiz qayta hisoblanadi.

### Sprint 5 · 21.12 – 08.01 · Tavsiyalar, xulosa, eksport (3 hafta, Yangi yil bilan)

**Maqsad:** foydalanuvchi tayyor hisobot va harakatlar rejasini oladi.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| S-02 | Tavsiyalar: skelet + `reco.write` + faktlarni buzishga qarshi darvoza + «nima yig'ish kerak» | [PIPELINE §7.1](PIPELINE.md) qoidalari testda | AI | 3 |
| S-03 | `report.narrative` + placeholder'lar + raqamlarni post-tekshirish (RU/UZ/EN) | Matnda noto'g'ri raqam yo'q (test) | AI | 2 |
| S-04 | Tushuntirish so'rovi (DOCX) | Ekspert ma'qullaydi | BE | 1.5 |
| S-05 | Eksport: PDF (WeasyPrint), XLSX, JSON | Uchala til, kirill va lotin to'g'ri chiqadi | BE | 4 |
| S-06 | Admin sozlamalari API: vaznlar, k, chegaralar, lug'atlar | Sozlama o'zgarsa, foiz qayta hisoblanadi | BE | 2 |
| I-14 | Chizmalar: shtamp maydonlari + texnik talablar matni | Etalon chizmalarda maydonlar to'g'ri | AI | 2.5 |
| FE-04 | «Сводка» ekrani: kartalar, kategoriyalar, xulosa, harakatlar rejasi (checkbox), «nima yig'ish», prognoz, eksport | PO ma'qullaydi | FE | 5 |
| FE-05 | Admin UI (vaznlar, lug'atlar, foydalanuvchilar) + i18n to'liq (3 til) | Barcha matnlar tarjima qilingan | FE | 4 |
| EV-04 | Xatolar tahlili #2 + prompt tuning | Metrikalar EV-03 ga nisbatan yaxshilangan | AI | 2 |

**Demo:** to'liq ssenariy: yuklash → chek-list → solishtirish → xulosa → PDF va DOCX yuklab olish.

### Sprint 6 · 11.01 – 22.01 · Mustahkamlash va MVP reliz

**Maqsad:** qabul mezonlari bajarilgan, pilot muhiti tayyor.

| ID | Vazifa | DoD | Kim | Kun |
|---|---|---|---|---|
| H-01 | Qabul mezonlariga erishish (§6): to'liq eval, prompt va chegaralarni tuning, false-green = 0 | Barcha mezonlar yashil yoki og'ishlar PO bilan kelishilgan | AI | 5 |
| H-02 | Unumdorlik: 100 sahifa ≤ 10 daqiqa (profillash, parallellik). Yuklama testi: 50 parallel tekshiruv (k6 yoki locust) | Hisobot + Grafana panel | BE | 3 |
| H-03 | Xavfsizlik: RLS auditi, S3 shifrlash, retention va o'chirish vazifasi, loglarda PII maskalash, injection testlari, OWASP cheklisti | Cheklist yopilgan | BE | 3 |
| H-04 | Takrorlanuvchanlik testi: bir xil fayllar → bir xil natija | CI'da test | AI | 0.5 |
| H-05 | Pilot muhiti: deploy, backup (pg_dump + S3 versiyalash), Grafana panellari, alertlar | Backup'dan tiklash sinab ko'rilgan | BE | 3 |
| H-06 | UAT ekspert bilan, foydalanuvchi qo'llanmasi (RU/UZ), disclaimer matni | UAT bayonnomasi | PO, EXP, FE | 3 |
| H-07 | MVP+ (vaqt bo'lsa): qayta tekshirish (kesh orqali) + «История» ekrani | 72% → 94% ssenariysi ishlaydi | BE 2, FE 3 | 5 |

**MVP RELIZ: 22.01.2027.**

---

## 5. Pilot va kengaytirish

### Pilot · 25.01 – 05.03.2027 (6 hafta)

| ID | Vazifa |
|---|---|
| P-01 | 5–10 yetkazib beruvchini onboarding qilish, haqiqiy tenderlarda ishlatish |
| P-02 | Haftalik xatolar triaji: har bir topilgan xato eval to'plamiga qo'shiladi (30 tendergacha) |
| P-03 | Qayta tekshirish + versiyalar tarixi (MVP ga kirmagan bo'lsa) |
| P-04 | Loyiha bo'yicha chat: faqat yuklangan hujjatlar asosida, sitatalar bilan («почему U-007 красный?») |
| P-05 | Telefon OTP orqali kirish (SMS provayder) |
| P-06 | Chizmalar: o'lcham va dopusklarni tuzilgan holda solishtirish |
| P-07 | Tushuntirish va o'zgartirishlarni yuklash → chek-list diff, o'zgargan bandlar belgilanadi (TZ §2, 5-ssenariy) |
| P-08 | Xarajat statistikasi asosida narx va tarif modeli (TZ §13) |

### Kengaytirish · mart 2027+

| ID | Vazifa |
|---|---|
| X-01 | Buyurtmachi rejimi: bitta hujjatlar to'plami + N ariza, «требование × участник» matritsasi |
| X-02 | DWG/DXF |
| X-03 | Tashqi reyestrlar orqali tekshirish (TenderZone kontragentlar moduli bilan birga) |
| X-04 | TenderZone'dan lotni havola orqali import qilish |
| X-05 | TenderGPT ga komissiya moduli sifatida joylash |
| X-06 | Ommaviy REST API + API kalitlar |
| X-07 | Kubernetes, navbatlar bo'yicha avtomasshtablash |
| X-08 | Platforma SSO |

---

## 6. MVP qabul mezonlari

| # | Mezon (TZ §12) | Taklif (D-06) | Qanday tekshiriladi |
|---|---|---|---|
| 1 | Majburiy talablarni ajratish to'liqligi 100% | ≥ 98% + qolganlari `coverage_gaps` da foydalanuvchiga ko'rsatiladi (ya'ni tizim ularni jimgina yo'qotmaydi) | Eval, etalon to'plam |
| 2 | Status aniqligi 100% (⚪ siz), ⚪ ulushi ≤ 15% | Aniqlik ≥ 95%, ⚪ ≤ 15% | Eval |
| 3 | Bajarilmagan majburiy talablar uchun 0 ta «Соответствует» | **O'zgarishsiz: = 0** | Eval (false-green) |
| 4 | 100% bandlarda manba sahifasiga ishlaydigan havola | O'zgarishsiz | Avtomatik tekshiruv |
| 5 | 100 sahifa ≤ 10 daqiqa | O'zgarishsiz (inson tasdiqlash vaqti hisobga kirmaydi) | Metrikalar, H-02 |
| 6 | Tavsiyalar ≥ 80% hollarda qo'llaniladigan | O'zgarishsiz | Ekspert baholashi, H-06 |

> 1 va 2 mezonlarni o'zgartirish **@Марат bilan kelishiladi**. Asos: OCR+LLM tizimida 100% ni statistik jihatdan kafolatlab bo'lmaydi va bu qabul paytida nizoga olib keladi. Haqiqatan qimmat bo'lgan xato 3-mezonda qat'iy qoladi.

---

## 7. Risklar

| # | Risk | Ehtimol | Ta'sir | Kamaytirish |
|---|---|---|---|---|
| K1 | O'zbekcha skan va fotolarda OCR sifati past (`oʻ/gʻ`, kirill+lotin aralash) | O'rta | Yuqori | R-02 benchmark Sprint 0 da. Ikkinchi o'qish (vision LLM). Past ishonch → qo'lda tekshirish |
| K2 | Lokalizatsiya talabi bulutli LLM'ni taqiqlaydi | O'rta | **Juda yuqori** | R-04 ni birinchi haftada hal qilish. Gateway'da on-prem adapter. Eng yomon holatda on-prem model bilan sifat o'lchanadi |
| K3 | Etalon to'plam kechikadi (ekspert vaqti, ma'lumotlarga ruxsat) | Yuqori | Yuqori | R-01 birinchi kundan boshlanadi. Ilovaning o'zi annotatsiya vositasi bo'ladi. Ekspertga haftalik kvota |
| K4 | 100% maqsadlar sabab qabulda nizo | Yuqori | O'rta | D-06 ni Sprint 0 da kelishish |
| K5 | LLM xarajati yuqori (taxminan $8–15 / 100+100 sahifa, Opus 5.5) | O'rta | O'rta | Kesh, prompt caching, maqsadli ajratish. Route'lar bo'yicha arzonroq modellarni etalonda o'lchash. Batch API faqat eval uchun |
| K6 | API rate limit va kechikish 10 daqiqalik SLA ni buzadi | Past | O'rta | Token-bucket, parallellik, limitlarni oshirish so'rovi, oraliq natijalarni ko'rsatish |
| K7 | Hujjatlar xilma-xilligi kutilganidan katta (formalar, qo'lyozma, g'alati jadvallar) | Yuqori | O'rta | Pilotdagi xatolar eval'ga qo'shiladi. `needs_review` mexanizmi |
| K8 | Hujjatlar orqali prompt injection | Past | Yuqori | [ARCHITECTURE §11](ARCHITECTURE.md), injection testlari, raqamlarni kod hal qiladi |
| K9 | Scope creep (buyurtmachi rejimi, integratsiyalar MVP ga suqiladi) | O'rta | O'rta | §2 dagi doira qat'iy. Yangi talab faqat PO qarori bilan va boshqasining o'rniga |

---

## 8. Ochiq savollar va qarorlar

**Birinchi hafta ichida javob kerak** (Sprint 1 rejasi va arxitekturaga ta'sir qiladi):

| # | Savol | Kim | Muddat | Default taxmin | Javob ta'siri |
|---|---|---|---|---|---|
| Q1 | Hujjatlarni tashqi AI API (Claude) ga yuborish mumkinmi? Shaxsiy ma'lumotlarni lokalizatsiya qilish talabi qanday (yurist)? | PO + yurist | 16.10 | Ha, pilot uchun mijoz roziligi bilan | «Yo'q» bo'lsa, on-prem LLM: GPU server, sifat qayta o'lchanadi, reja +3–4 hafta |
| Q2 | Bulut yoki on-prem? Qaysi data-markaz? | PO | 16.10 | O'zbekistondagi VM | Deploy va xarajat |
| Q3 | MVP ning birinchi mijozi kim: yetkazib beruvchimi yoki buyurtmachimi? | PO | 16.10 | Yetkazib beruvchi (A1) | Buyurtmachi bo'lsa, X-01 MVP ga o'tadi, boshqa narsa chiqariladi |
| Q4 | Etalon to'plam: qaysi tarmoqlar, kim belgilaydi, haftasiga nechta? | PO + EXP | 14.10 | 2 ekspert-kun/hafta | Sifat iteratsiyasi tezligi |
| Q5 | Qabul mezonlarini D-06 bo'yicha o'zgartirish | @Марат | 23.10 | D-06 | Qabul |
| Q6 | Verdikt qoidalari D-01…D-03, D-07 ([PIPELINE §10](PIPELINE.md)) | @Марат | 23.10 | Taklif qilinganidek | Skoring |

**Sprintlar davomida javob kerak:**

| # | Savol | Kim | Muddat |
|---|---|---|---|
| Q7 | Mahsulot qayerda yashaydi: mustaqil servis, TenderZone komponenti yoki TenderGPT moduli? | PO | Sprint 3 |
| Q8 | Qaysi xarid turlari birinchi: davlat xaridlari, korporativ, xalqaro (Jahon banki, OTB)? | PO | Sprint 1 |
| Q9 | Monetizatsiya: obuna, tekshiruv uchun to'lov yoki sahifa uchun to'lov? | PO | Pilot |
| Q10 | Disclaimer («hisobot tavsiyaviy xarakterga ega va komissiya qarorining o'rnini bosmaydi») | PO + yurist | Sprint 5 (tavsiya: **ha**) |
| Q11 | Mahsulot nomi | PO | Pilot |

---

## 9. Definition of Done (har bir vazifa uchun)

- [ ] Kod review'dan o'tgan, `main` ga PR orqali kiritilgan
- [ ] Lint va type-check toza (ruff, mypy strict, eslint)
- [ ] Testlar: biznes logikada unit testlar, API'da integration testlar. Qoidalar dvigateli va skoring uchun 100% branch coverage
- [ ] Migratsiya bor va orqaga qaytariladi (`downgrade`)
- [ ] OpenAPI yangilangan, frontend klient qayta generatsiya qilingan
- [ ] UI matnlari 3 tilda (`i18n/*.json`)
- [ ] Loglar va metrikalar qo'shilgan, xatolar Sentry'ga tushadi
- [ ] AI qismi o'zgargan bo'lsa: mini-eval o'tkazilgan, false-green = 0, recall pasaymagan
- [ ] Demo qilish mumkin (staging'da)

---

## 10. Birinchi hafta: nimadan boshlash kerak

| Kun | BE | AI | FE | PO / EXP |
|---|---|---|---|---|
| **Du 12.10** | F-01: git init, monorepo, tooling | R-02: benchmark uchun 50–80 sahifa tanlash (EXP bilan), engine'larni o'rnatish | FE-00: maketni tahlil qilish, UI kit | Q1–Q4 savollarini yuborish. R-01: 10 tender + arizalarni yig'ish |
| **Se 13.10** | F-02: docker-compose | R-02: Tesseract, PaddleOCR, Docling ishga tushirish | F-05: Vite + React skeleti | `gold_schema` ni ekspert bilan kelishish |
| **Ch 14.10** | F-03: backend skeleti, Alembic | L-01: LLM gateway minimal (bitta route) | F-05: routing, i18n | Ekspert 1-tenderni belgilaydi |
| **Pa 15.10** | F-03, F-06: CI | R-03: 1-tenderda talablarni ajratish | FE-00: ekran prototiplari | Q1–Q4 javoblarini olish |
| **Ju 16.10** | F-04: auth boshlash | R-02 natijalari, ADR-002 qoralamasi | FE-00 | 2-hafta rejasini tasdiqlash |

**Birinchi kun uchun eng muhim ish ham texnik emas:** Q1 (tashqi AI API'ga ruxsat) va R-01 (haqiqiy tenderlar + arizalar). Ularsiz sifatni o'lchashning iloji yo'q, ikkalasi ham boshqa odamlarga bog'liq va kutish vaqti uzoq. Shuning uchun ular 12.10 kuni ertalab jo'natiladi.
