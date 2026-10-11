# Arxitektura — «Тендер-Сверка» MVP

> Versiya 0.1 · 2026-10-11 · Asos: TZ v0.1 (08.10.2026, @Марат) — [spec/TZ-v0.1.docx](spec/TZ-v0.1.docx)
> Holat: **taklif**. Sprint 0 benchmarklari (R-02, R-03) natijasida yangilanadi.
> Bog'liq hujjatlar: [PIPELINE.md](PIPELINE.md) (konveyer va AI dizayni) · [MVP-PLAN.md](MVP-PLAN.md) (reja va vazifalar)

---

## MVP amalga oshirilishi (11.10.2026)

Quyidagi hujjat to'liq maqsadli dizaynni tasvirlaydi. Topshirish muddati sababli MVP kodi 8 ta asosiy funksiyaga qisqartirildi va quyidagi joylarda soddalashtirildi:

| Dizaynda | MVP kodida |
|---|---|
| Alohida OCR engine, UDR bloklar, bbox | Claude PDF'ni o'zi o'qiydi (matn + skan). Manba: fayl + sahifa + sitata, sitata PDF matnida kod bilan tekshiriladi. Manba havolasi PDF'ni kerakli sahifada ochadi |
| O'z LLM gateway'imiz (kesh, limit, xarajat) | **Cloudflare AI Gateway** (kesh, loglar, xarajat analitikasi), Anthropic SDK `base_url` orqali |
| MinIO | **Cloudflare R2**. Kalitlar bo'lmasa, lokal docker volume |
| Auth, rollar, RLS, audit jadvali | Yo'q (kengaytirish bosqichida). Qo'lda o'zgartirilgan status izoh va `method=manual` bilan saqlanadi |
| SSE, `pipeline_steps` holat mashinasi | Polling (2 s) + paket/tekshiruv statusi |
| Alembic, embeddinglar, qoplama auditi | `create_all`, embeddingsiz, qoplama auditi yo'q |

## 0. Bir qarashda

- **Gibrid tizim.** LLM hujjatni o'qiydi va talqin qiladi. Raqamlar, birliklar, sanalar va foizni Python kodi hisoblaydi.
- **Har bir xulosani tekshirish mumkin.** Sitata, sahifa va sahifadagi joy (bbox) bo'lmasa, tizim talab yoki status chiqarmaydi.
- **Bitta konveyer.** Buyurtmachi hujjatlari ham, ishtirokchi arizasi ham bir xil tanib olish konveyeridan o'tadi va solishtirish bosqichida uchrashadi.
- **Asinxron va idempotent.** Har bir bosqich natijasi bazaga yoziladi, UI oraliq natijalarni darhol ko'rsatadi, qayta ishga tushirish xavfsiz.
- **Provayderdan mustaqil.** LLM ham, OCR ham adapter orqali ulanadi. Lokalizatsiya talab qilinsa, on-prem modelga o'tish konfiguratsiya darajasida bo'ladi.

---

## 1. Arxitektura tamoyillari

| # | Tamoyil | Amalda nimani anglatadi |
|---|---|---|
| P1 | **Isbotlanuvchanlik** | Talab, fakt va status faqat tekshirilgan sitata bilan saqlanadi. Sitata manba matnida topilmasa, element tashlanadi yoki «Требует проверки» holatiga o'tadi |
| P2 | **Determinizm** | Raqam, birlik, sana va foizni kod hisoblaydi. LLM javoblari kirish xeshi bo'yicha keshlanadi, shuning uchun bir xil fayllarda qayta ishga tushirish bir xil natija beradi |
| P3 | **Xato narxi asimmetrik** | Eng qimmat xato: bajarilmagan majburiy talabga 🟢 «Соответствует» qo'yish. Shubha bo'lsa, ⚪ «Требует проверки» qo'yiladi |
| P4 | **Provayderdan mustaqillik** | `LLMProvider`, `OcrEngine`, `Embedder` interfeyslari. Model, effort va chegaralar konfiguratsiyada, kodda emas |
| P5 | **Inson nazorati** | Chek-list solishtirishdan oldin tasdiqlanadi. Har qanday status izoh bilan qo'lda o'zgartiriladi va audit jurnaliga yoziladi |
| P6 | **Ma'lumotlar xavfsizligi** | Tashkilotlar izolyatsiyasi (`org_id` + Postgres RLS), TLS va saqlashda shifrlash, saqlash muddati, o'chirish |

---

## 2. Tizim konteksti

```
   Yetkazib beruvchi        Buyurtmachi /          Administrator
   (mutaxassis, rahbar)     komissiya a'zosi
            │                     │                      │
            └─────────────────────┼──────────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │      «Тендер-Сверка»      │
                    │   (web + API + workers)   │
                    └─┬──────────┬──────────┬───┘
                      │          │          │
          ┌───────────▼──┐ ┌─────▼──────┐ ┌─▼────────────────────────┐
          │ LLM API      │ │ SMS-shlyuz │ │ TenderZone / TenderGPT   │
          │ (Claude)     │ │ (pilot,    │ │ (3-bosqich: lot importi, │
          │ yoki on-prem │ │  OTP)      │ │  modul sifatida ichki)   │
          └──────────────┘ └────────────┘ └──────────────────────────┘
```

MVP da tashqi bog'liqlik bitta: LLM API. OCR, embeddinglar va fayl ombori o'z serverimizda ishlaydi.

---

## 3. Komponentlar

```
                         ┌──────────────────────────────┐
     Brauzer ──────────▶ │  web  (React SPA)            │
                         └──────────────┬───────────────┘
                                        │ HTTPS: REST + SSE
                         ┌──────────────▼───────────────┐
                         │  api  (FastAPI)              │── auth · RBAC · audit
                         └──┬──────────┬──────────┬─────┘
                            │          │          │
                ┌───────────▼──┐ ┌─────▼─────┐ ┌──▼───────────────┐
                │ PostgreSQL   │ │  Redis    │ │ Cloudflare R2    │
                │ + pgvector   │ │ navbat,   │ │ asl fayllar,     │
                │ + pg_trgm    │ │ hodisalar,│ │ sahifa rasmlari, │
                │              │ │ limitlar  │ │ eksportlar       │
                └───────▲──────┘ └─────┬─────┘ └──▲───────────────┘
                        │              │          │
                ┌───────┴──────────────▼──────────┴─────────────────┐
                │  Celery workers (navbatlar bo'yicha ajratilgan)    │
                │  ingest │ ocr │ llm │ core (match/score) │ report  │
                └───────┬────────────────┬──────────────────────────┘
                        │                │
              ┌─────────▼──────┐  ┌──────▼─────────────────────────┐
              │ OCR / layout   │  │ LLM gateway ──▶ Claude API     │
              │ (self-hosted)  │  │ (adapter: on-prem model)       │
              └────────────────┘  └────────────────────────────────┘
```

| Komponent | Mas'uliyati | Masshtablash |
|---|---|---|
| `web` | 7 ta ekran, PDF/rasm ko'ruvchi (bbox bilan belgilash), i18n RU/UZ/EN | Statik fayllar, nginx yoki CDN |
| `api` | REST, autentifikatsiya, validatsiya, presigned yuklash URL'lari, SSE progress, konveyerni ishga tushirish | Stateless, gorizontal |
| `worker-ingest` | Arxivlarni ochish, format konvertatsiyasi, sahifa render, matn qatlami | CPU, gorizontal |
| `worker-ocr` | Preprocessing, OCR, layout, jadvallar, QR | CPU yoki GPU, eng og'ir navbat |
| `worker-llm` | Barcha LLM yo'nalishlari (route'lar) | I/O-bound, parallellik rate-limiter bilan cheklangan |
| `worker-core` | Qoidalar dvigateli, skoring, embeddinglar | CPU-light |
| `worker-report` | PDF, XLSX, DOCX eksport | CPU-light |
| `beat` | Rejali vazifalar: saqlash muddati o'tganlarini o'chirish, osilib qolgan vazifalarni tozalash | 1 instans |
| PostgreSQL | Yagona haqiqat manbai, vektor qidiruv, FTS | Vertikal + read-replika (keyin) |
| Redis | Celery broker, progress pub/sub, LLM rate-limit bucketlari, locklar | 1 instans (keyin Sentinel) |
| Cloudflare R2 | Fayllar (S3 API). Saqlashda shifrlash (AES-256) R2 da default yoqilgan | — |
| ClamAV | Yuklangan fayllarni antivirus tekshiruvi | Sidecar |

---

## 4. Texnologiya steki

| Qatlam | Tanlov | Nega | Alternativa |
|---|---|---|---|
| Backend tili | **Python 3.12** | TZ talabi. OCR, ML va hujjatlar ekotizimi | — |
| API | **FastAPI + Pydantic v2** | Async, avtomatik OpenAPI. Pydantic modellari API'da ham, LLM structured output sxemalarida ham bir xil ishlatiladi | Litestar |
| ORM / migratsiya | **SQLAlchemy 2.0 + Alembic** | Standart, yetuk | — |
| Navbat | **Celery 5 + Redis** | TZ talabi, oddiy start | RabbitMQ broker, Dramatiq, Temporal |
| DB | **PostgreSQL 16 + pgvector + pg_trgm** | TZ talabi. Vektor, FTS va trigram bitta bazada | — |
| Fayl ombori | **Cloudflare R2** (S3 API, `boto3`) | Jamoa qarori (11.10.2026). S3 API bo'lgani uchun kod provayderga bog'lanmaydi. Egress bepul. **Diqqat:** R2 O'zbekistonda saqlamaydi, lokalizatsiya talab qilinsa (Q1/Q2), faqat konfiguratsiya o'zgaradi | MinIO, mahalliy S3 |
| PDF | **PyMuPDF** | Bbox bilan matn, sahifa render, `find_tables()` | pdfplumber |
| Ofis formatlari | **LibreOffice headless** | DOC, DOCX, RTF, ODT, XLS fayllarini PDF ga o'tkazadi, shunda sahifa va bbox yagona bo'ladi | — |
| Rasmlar | **Pillow + pillow-heif, OpenCV** | HEIC, TIFF, preprocessing (deskew, perspektiva) | — |
| OCR / layout | **R-02 benchmark hal qiladi.** Nomzodlar: Docling (layout + TableFormer), PaddleOCR, Tesseract 5 (`uzb`, `uzb_cyrl`, `rus`, `eng`), Surya. Bulutli: Azure Document Intelligence | Bbox va ishonch darajasi kerak. LLM vision bbox bermaydi | — |
| QR / shtrixkod | **zxing-cpp** | Tez, ko'p formatli | pyzbar |
| LLM | **Claude Opus 5.5** (`claude-opus-5-5`), rasmiy `anthropic` Python SDK | Multimodal, 1M kontekst, structured outputs, ko'p tilli | Adapter orqali on-prem model |
| Embeddinglar | **BGE-M3** (self-hosted, 1024 o'lcham) | Ko'p tilli (UZ/RU/EN), lokal ishlaydi, shuning uchun lokalizatsiyaga mos | Voyage multilingual (bulut) |
| Birliklar | **pint** + o'z registrimiz (RU/UZ/EN aliaslar) | Deterministik konvertatsiya | — |
| Fuzzy moslik | **rapidfuzz** | Sitata tekshiruvi, nomlarni solishtirish | — |
| Til aniqlash | **lingua-py** | Qisqa matnda ham aniq, o'zbek tilini taniydi | fasttext-lid |
| Eksport | **WeasyPrint** (PDF, HTML/Jinja2 shablon), **openpyxl** (XLSX), **docxtpl** (DOCX) | Kirill va lotin shriftlari, shablonlar bilan boshqariladi | — |
| Frontend | **React 19 + TypeScript + Vite**, TanStack Router/Query/Table, Tailwind + shadcn/ui, **react-pdf (PDF.js)**, i18next | Login ortidagi B2B ilova, shuning uchun SSR kerak emas. SPA deploy qilish oddiy | Next.js |
| API klient | **openapi-typescript** (OpenAPI'dan generatsiya) | Front va back tiplari sinxron turadi | orval |
| Paket menejerlar | **uv** (Python), **pnpm** (JS) | Tez, lock fayllar | — |
| Sifat | ruff, mypy (strict), pytest, hypothesis · eslint, vitest, Playwright | — | — |
| Kuzatuv | structlog, Sentry, Prometheus + Grafana, Langfuse (ixtiyoriy, self-host) | — | — |
| Deploy | Docker Compose (dev, pilot) → Kubernetes (kengaytirish bosqichida) | — | — |

---

## 5. Repozitoriy tuzilmasi

```
tenderai/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI routerlar (projects, packages, requirements, runs, ...)
│   │   ├── core/                # config, security, db session, logging, errors
│   │   ├── models/              # SQLAlchemy modellari
│   │   ├── schemas/             # Pydantic: API DTO + LLM chiqish sxemalari
│   │   ├── services/            # biznes logika (routerlar shu qatlamni chaqiradi)
│   │   ├── pipeline/
│   │   │   ├── orchestrator.py  # bosqichlar holat mashinasi
│   │   │   ├── ingest/          # yuklash, arxivlar, konvertatsiya, render
│   │   │   ├── recognize/       # matn qatlami, OCR adapterlari, layout, jadvallar, QR, muhr
│   │   │   ├── classify/        # hujjat turi, rekvizitlar
│   │   │   ├── extract/         # tender metadata, talablar, ariza faktlari, post-processing
│   │   │   ├── match/           # pozitsiyalar, qidiruv, qoidalar dvigateli, LLM judge
│   │   │   ├── scoring/         # sof funksiyalar: foiz, verdikt, prognoz
│   │   │   └── report/          # tavsiyalar, xulosa, eksportlar
│   │   ├── llm/                 # gateway: provayderlar, prompt registri, kesh, limitlar, xarajat
│   │   ├── normalize/           # birliklar, parametrlar lug'ati, o'zbek translit, sanalar
│   │   └── workers/             # Celery app, navbatlar, tasklar
│   ├── prompts/v1/              # versiyalangan promptlar (*.md + metadata)
│   ├── dictionaries/            # parameters.yaml, units.yaml, doc_types.yaml, modal_words.yaml
│   ├── templates/               # PDF/DOCX/XLSX hisobot shablonlari
│   ├── alembic/
│   └── tests/                   # unit, integration, golden (fixture hujjatlar)
├── frontend/
│   └── src/
│       ├── routes/              # projects, upload, checklist, compare, summary, history, settings
│       ├── components/          # DocumentViewer (bbox highlight), StatusBadge, ScoreCards, ...
│       ├── api/                 # generatsiya qilingan klient
│       └── i18n/                # ru.json, uz.json, en.json
├── eval/
│   ├── datasets/                # (gitignore) haqiqiy tenderlar, faqat lokal yoki shifrlangan omborda
│   ├── gold_schema.json         # etalon belgilash formati
│   ├── run_eval.py              # metrikalar: recall, accuracy, false-green, citation validity
│   └── reports/
├── docker-compose.yml           # dev muhit (repo ildizida)
├── Makefile
├── infra/
│   ├── postgres/init/           # pgvector, pg_trgm
│   └── k8s/                     # (kengaytirish bosqichi)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PIPELINE.md
│   ├── MVP-PLAN.md
│   ├── adr/                     # qarorlar jurnali (ADR-001, ...)
│   └── spec/TZ-v0.1.docx
├── .github/workflows/           # CI: lint, test, build, eval (qo'lda yoki tungi)
└── README.md
```

---

## 6. Ma'lumotlar modeli

Har bir jadvalda `id` (UUID v7), `created_at`, `updated_at` bor. Biznes jadvallarida `org_id` ham bor va RLS siyosati shu ustun bo'yicha ishlaydi. Bbox normallashtirilgan koordinatalarda saqlanadi: `[x0, y0, x1, y1]`, sahifa o'lchamiga nisbatan 0..1. Shuning uchun u render ruxsatiga bog'liq emas.

### 6.1. Foydalanuvchilar va tashkilotlar

| Jadval | Asosiy maydonlar |
|---|---|
| `organizations` | `name`, `settings jsonb` (vaznlar, k koeffitsientlari, chegaralar, saqlash muddati) |
| `users` | `phone`, `email`, `full_name`, `locale`, `password_hash` |
| `memberships` | `user_id`, `org_id`, `role: admin \| specialist \| viewer` |
| `audit_log` | `user_id`, `action`, `entity`, `entity_id`, `before jsonb`, `after jsonb` |

### 6.2. Loyiha, paketlar, hujjatlar

| Jadval | Asosiy maydonlar |
|---|---|
| `projects` | `title`, `lot_number`, `customer_name`, `procurement_type`, `submission_deadline timestamptz`, `start_price`, `currency`, `report_language`, `status` |
| `packages` | `project_id`, `kind: customer \| bid`, `participant_name`, `version`, `parent_package_id` (qayta tekshiruv uchun), `status` |
| `files` | `package_id`, `s3_key`, `original_name`, `archive_path`, `mime`, `size`, `sha256`, `scan_status` |
| `documents` | `file_id`, `doc_type`, `doc_type_source: ai \| user`, `doc_type_confidence`, `languages[]`, `page_count`, `issuer`, `doc_number`, `doc_date`, `valid_until`, `has_signature`, `has_seal`, `qr_payloads jsonb`, `status` |
| `pages` | `document_id`, `page_no`, `image_key`, `width`, `height`, `text_source: text_layer \| ocr \| native`, `ocr_engine`, `mean_confidence`, `needs_review` |
| `blocks` | `page_id`, `type: heading \| paragraph \| list_item \| table \| table_cell \| stamp \| seal \| signature \| qr \| figure`, `text`, `text_norm`, `bbox`, `confidence`, `reading_order`, `parent_id`, `section_ref`, `lang`, `cell_ref` (XLSX uchun, masalan `Лист1!B7`) |
| `chunks` | `document_id`, `block_ids[]`, `text`, `embedding vector(1024)`, `tsv tsvector` |

### 6.3. Talablar (buyurtmachi tomoni)

| Jadval | Asosiy maydonlar |
|---|---|
| `lot_positions` | `project_id`, `number`, `name`, `classifier_code`, `quantity`, `unit` |
| `evaluation_criteria` | `project_id`, `name`, `max_points`, `method` |
| `requirements` | `project_id`, `code` (T-014 / U-007), `scope: product \| participant`, `category`, `lot_position_id`, `parameter`, `parameter_key`, `operator`, `value_num`, `value_min`, `value_max`, `tolerance`, `value_text`, `unit`, `unit_norm`, `req_type: mandatory \| rated \| desired`, `rated_points`, `weight`, `proof_method[]`, `consequence`, `equivalent_allowed`, `restrictive_flag`, `has_conflict`, `confidence`, `state: draft \| approved \| deleted`, `origin: ai \| user \| merged`, `checklist_version` |
| `requirement_sources` | `requirement_id`, `block_ids[]`, `page_id`, `quote`, `bbox`, `match_score`, `role: primary \| reference` |
| `customer_issues` | `kind: contradiction \| ambiguity \| restrictive`, `description`, `requirement_ids[]`, `sources jsonb`, `include_in_clarification` |
| `coverage_gaps` | `block_ids[]`, `sentence`, `detector_reason`, `resolution: added \| not_requirement \| pending` |

### 6.4. Ariza va solishtirish

| Jadval | Asosiy maydonlar |
|---|---|
| `participants` | `package_id`, `name`, `name_norm`, `stir`, `director`, `address` |
| `facts` | `package_id`, `requirement_id` (maqsadli ajratishda), `scope`, `lot_position_ref`, `parameter`, `parameter_key`, `value_num`, `value_text`, `unit`, `unit_norm`, `source_rank: 3 \| 2 \| 1`, `document_id`, `confidence` |
| `fact_sources` | `fact_id`, `block_ids[]`, `quote`, `bbox` |
| `document_checks` | `document_id`, `check: validity \| signature \| seal \| requisites \| translation`, `result: ok \| fail \| unknown`, `details jsonb` |
| `bid_issues` | `kind: internal_contradiction \| requisites_mismatch \| expired`, `description`, `fact_ids[]` |
| `check_runs` | `project_id`, `bid_package_id`, `checklist_version`, `pipeline_version`, `prompt_set_version`, `models jsonb`, `status`, `score jsonb` (snapshot), `started_at`, `finished_at` |
| `matches` | `run_id`, `requirement_id`, `status: match \| partial \| unconfirmed \| mismatch \| review`, `ai_status`, `method: rule \| llm \| manual`, `reasoning`, `confidence`, `fact_ids[]`, `bid_sources jsonb`, `overridden_by`, `override_comment`, `overridden_at` |
| `recommendations` | `run_id`, `match_id`, `problem`, `action`, `action_type: add_document \| fix_data \| replace_product \| request_clarification \| unfixable`, `severity: high \| medium \| low`, `impact_pct`, `is_done` |
| `reports` | `run_id`, `kind: pdf \| xlsx \| docx_clarification \| json`, `language`, `s3_key` |

### 6.5. Texnik jadvallar

| Jadval | Vazifasi |
|---|---|
| `pipeline_steps` | `subject_type`, `subject_id`, `stage`, `unit_key` (masalan, `page:12`), `status`, `attempts`, `input_hash`, `error`, vaqt. Orkestratsiyaning holat mashinasi shu jadvalda |
| `llm_calls` | `route`, `model`, `prompt_version`, `input_hash` (unique), `response jsonb`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`, `latency_ms`, `stop_reason`. Kesh, takrorlanuvchanlik va xarajat hisobi uchun |
| `extraction_rejects` | Sitatasi tekshiruvdan o'tmagan LLM chiqishlari. Eval va xatolar tahlili uchun |

Lug'atlar (`parameters.yaml`, `units.yaml`, `doc_types.yaml`, `modal_words.yaml`) repoda seed sifatida turadi va admin UI orqali `dictionary_entries` jadvalida kengaytiriladi.

---

## 7. REST API (MVP)

Prefiks `/api/v1`. Autentifikatsiya: httpOnly cookie ichida JWT (access va refresh). Barcha ro'yxatlar paginatsiyali.

| Guruh | Endpoint | Tavsif |
|---|---|---|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /me` | MVP: email yoki telefon + parol. Pilotda telefon OTP |
| Loyihalar | `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}` | Ro'yxat: lot, buyurtmachi, muddat, %, status |
| Paketlar | `POST /projects/{id}/packages` | `kind: customer \| bid` |
| Yuklash | `POST /packages/{id}/uploads` → presigned URL'lar, `POST /packages/{id}/uploads/complete` | Limitlar: 100 fayl, 500 MB, 1000 sahifa |
| Qayta ishlash | `POST /packages/{id}/process` | Konveyerni ishga tushiradi |
| Progress | `GET /projects/{id}/events` (SSE) | Bosqichlar, ogohlantirishlar, oraliq natijalar |
| Hujjatlar | `GET /packages/{id}/documents`, `PATCH /documents/{id}` (turini tuzatish), `GET /documents/{id}/pages/{n}` (rasm URL + bloklar) | Ko'ruvchi uchun |
| Chek-list | `GET /projects/{id}/requirements?scope&req_type&category&position`, `POST /projects/{id}/requirements`, `PATCH/DELETE /requirements/{id}`, `POST /requirements/merge`, `POST /projects/{id}/checklist/approve` | Tasdiqlash chek-listni qulflaydi va versiya beradi |
| Savollar | `GET /projects/{id}/issues`, `PATCH /issues/{id}` | «Вопросы к заказчику» |
| Qoplama | `GET /projects/{id}/coverage-gaps`, `PATCH /coverage-gaps/{id}` | Ehtimoliy o'tkazib yuborilgan talablar |
| Tekshiruv | `POST /projects/{id}/runs {bid_package_id}`, `GET /runs/{id}` | Solishtirish va skoring |
| Natijalar | `GET /runs/{id}/matches?status&scope&only_problems`, `PATCH /matches/{id} {status, comment}` | Qo'lda o'zgartirish auditga yoziladi va foiz qayta hisoblanadi |
| Xulosa | `GET /runs/{id}/summary`, `GET /runs/{id}/recommendations`, `PATCH /recommendations/{id} {is_done}` | — |
| Eksport | `POST /runs/{id}/exports {kind, language}`, `GET /exports/{id}` | PDF, XLSX, DOCX, JSON |
| Admin | `GET/PUT /org/settings`, `GET/POST/PATCH /dictionaries/{name}`, `GET /audit` | Vaznlar, koeffitsientlar, chegaralar, lug'atlar |

---

## 8. Konveyer orkestratsiyasi

Batafsil bosqichlar [PIPELINE.md](PIPELINE.md) da. Bu yerda faqat mexanika.

```
packages.process
   └─▶ ingest ─▶ normalize ─▶ recognize (sahifa bo'yicha fan-out) ─▶ classify
         customer paketi: ─▶ tender_meta ─▶ req_extract (chunk fan-out) ─▶ req_postprocess ─▶ [CHECKPOINT: tasdiqlash]
         bid paketi:      ─▶ bid_meta + document_checks ─────────────────────────────▶ [tasdiqlashni kutadi]
runs.create (tasdiqlangan chek-list + bid paketi)
   └─▶ bid_extract (hujjat fan-out) ─▶ match (talab fan-out) ─▶ score ─▶ recommend ─▶ narrative
```

- **Holat bazada, Celery faqat bajaradi.** Har bir ish birligi (`stage`, `unit_key`) `pipeline_steps` jadvalida qator sifatida turadi. Task boshlanganda `running` bo'ladi, tugaganda `done` yoki `failed`. Orkestrator birliklar tugaganini tekshirib, keyingi bosqichni ochadi (fan-in). Celery chord'lariga tayanmaymiz.
- **Idempotentlik.** Har bir task kirishining xeshini (`input_hash`) hisoblaydi. Shunday xeshli `done` natija bo'lsa, qayta ishlamaydi. Natijada fayl qayta yuklanganda faqat o'zgargan hujjatlar qayta ishlanadi, ya'ni qayta tekshiruv deyarli bepul bo'ladi.
- **Navbatlar:** `ingest`, `ocr`, `llm`, `core`, `report`. Har biri alohida worker pool. `llm` navbatida parallellik Redis token-bucket orqali API limitlariga moslanadi.
- **Qayta urinishlar.** Eksponensial backoff, 3 urinish. 429 va 5xx xatolar qayta uriniladi. 400 xatolar qayta urinilmaydi: darhol `failed` bo'ladi va UI'da ko'rsatiladi.
- **Progress.** Har bir holat o'zgarishi Redis pub/sub ga e'lon qilinadi, `api` uni SSE orqali brauzerga uzatadi. UI bosqichlarni, «o'qib bo'lmaydigan sahifalar» ogohlantirishlarini va tayyor bo'lgan talablarni real vaqtda ko'rsatadi.
- **Bekor qilish.** Loyiha yoki paket o'chirilsa, `revoke` + `pipeline_steps.status = cancelled`.

---

## 9. LLM gateway (`backend/app/llm/`)

Barcha LLM chaqiruvlari bitta qatlam orqali o'tadi. Biznes kodi to'g'ridan-to'g'ri SDK'ni chaqirmaydi.

```python
result = await llm.run(
    route="req.extract",  # konfiguratsiyada: model, effort, max_tokens, prompt versiyasi
    variables={...},  # prompt shablon o'zgaruvchilari
    images=[...],  # ixtiyoriy: sahifa rasmlari
    output_model=RequirementBatch,  # Pydantic sxema → structured output
)
```

| Vazifa | Yechim |
|---|---|
| Structured output | Rasmiy SDK'dagi `client.messages.parse()` va Pydantic modellari. Javob sxema bo'yicha validatsiya qilinadi |
| Sitatalar | Claude Citations API structured outputs bilan birga ishlamaydi. Shuning uchun sxemada o'z `quote` va `source_block_ids` maydonlarimiz bor va ular kod bilan tekshiriladi ([PIPELINE.md §3.4](PIPELINE.md)) |
| Kesh va takrorlanuvchanlik | `input_hash = sha256(model + prompt_version + rendered prompt + rasm xeshlari)`. Xesh `llm_calls` da bo'lsa, API chaqirilmaydi. Opus 5.5 da `temperature` parametri yo'q, shuning uchun determinizm aynan shu kesh orqali ta'minlanadi |
| Prompt caching | Tizim prompti, JSON sxema va tender konteksti (pozitsiyalar, lug'at) o'zgarmas prefiks sifatida birinchi joyga qo'yiladi va `cache_control` bilan belgilanadi. Bitta loyihaning chunklari shu prefiksni qayta ishlatadi |
| Effort | Opus 5.5 da thinking'ni o'chirib bo'lmaydi va default effort `medium`. Effort har bir route uchun konfiguratsiyada aniq beriladi |
| Refusal | `stop_reason == "refusal"` tekshiriladi. Server-side fallback yoqiladi: beta `server-side-fallback-2026-07-01` + `fallbacks: "default"` |
| Uzun javoblar | Streaming + `get_final_message()` |
| Rate limit | Redis token-bucket (RPM va TPM bo'yicha), SDK'ning o'z retry'lari, navbat parallelligi |
| Xarajat | Har chaqiruvda tokenlar va `cost_usd` yoziladi. Loyiha va tashkilot bo'yicha agregat, Grafana panel |
| Batch API | Faqat eval va regressiya ishlari uchun (50% arzon, asinxron). Interaktiv tekshiruvda ishlatilmaydi |
| Prompt registri | `prompts/v1/<route>.md` fayllari, versiya `check_runs.prompt_set_version` ga yoziladi |
| Provayder | `LLMProvider` interfeysi: `AnthropicProvider` (default). Lokalizatsiya talab qilinsa `OpenAICompatibleProvider` (vLLM ichidagi on-prem model) — R-04 qaroridan keyin |

### Route'lar (default qiymatlar, eval natijasiga qarab sozlanadi)

Barcha route'larda default model `claude-opus-5-5`. Har bir route uchun modelni alohida almashtirish mumkin. Arzonroq model (Sonnet 5.5, Haiku 4.5) etalon to'plamda sifatni saqlasa, unga o'tish **biznes qarori** bo'ladi va avval o'lchanadi.

| Route | Vazifa | Effort | Kirish | Chiqish |
|---|---|---|---|---|
| `doc.classify` | Hujjat turi va rekvizitlar | low | 1–3 birinchi sahifa matni + 1-sahifa rasmi | `doc_type`, `languages`, `issuer`, `doc_number`, `doc_date`, `valid_until` |
| `page.read` | Vision orqali ikkinchi o'qish | medium | Sahifa rasmi + OCR bloklari | Bloklar bo'yicha tuzatilgan matn, jadvallar, `has_seal`, `has_signature` |
| `tender.meta` | Tender metama'lumotlari | high | Info-karta, TZ boshi | Pozitsiyalar, topshirish muddati, baholash mezonlari, ruxsat etilgan tillar |
| `req.extract` | Talablarni ajratish | high | Chunk + kontekst | `[ExtractedRequirement]` |
| `req.resolve_refs` | Havolalarni ochish | medium | Talab + havola qilingan bo'lim | Boyitilgan talab |
| `req.dedupe` | Dublikat va qarama-qarshiliklar | medium | O'xshash talablar klasteri | merge, conflict yoki distinct |
| `req.coverage` | Qoplama auditi | high | Qoplanmagan me'yoriy jumlalar | Yangi talablar yoki «talab emas» |
| `bid.extract` | Ariza faktlari (maqsadli) | high | Hujjat matni + tegishli talablar ro'yxati | `[ExtractedFact]` |
| `match.judge` | Semantik solishtirish, ekvivalentlik, yo'qlikni tekshirish | high | Talab + dalil sitatalari | `JudgeVerdict` |
| `reco.write` | Tavsiya matni | medium | Strukturalangan muammo | `action`, `action_type` |
| `report.narrative` | Analitik xulosa | medium | Natija JSON | Placeholder'li matn |

---

## 10. Frontend

| Ekran (TZ §9) | MVP tarkibi |
|---|---|
| **Проекты** | Jadval: lot, buyurtmachi, topshirish muddati, %, verdikt, status. Qidiruv, «Yangi loyiha» |
| **Загрузка** | Ikki zona (buyurtmachi va ishtirokchi), drag-and-drop, bir nechta fayl. Bosqichlar bo'yicha progress. O'qib bo'lmaydigan sahifalar haqida ogohlantirish. Hujjat turlari ro'yxati (tuzatish mumkin) |
| **Чек-лист** | Tahrirlanadigan jadval. Filtrlar: tovar/ishtirokchi, tur, kategoriya, pozitsiya. Har bir qatorda manba tugmasi (ko'ruvchi ochiladi). Qo'shish, birlashtirish, o'chirish. «Вопросы к заказчику» va «Ehtimoliy o'tkazib yuborilgan» bloklari. **«Утвердить»** tugmasi |
| **Сравнение** | TZ dagi maket bo'yicha: tepada KPI kartalar, chapda statusli jadval, o'ngda ikki manba (sitata belgilangan) + asos + tavsiya. «Только проблемы» filtri, «Изменить статус», «Комментарий» |
| **Сводка** | %, «Товар» va «Участник» bo'yicha foiz, kategoriyalar, hisoblagichlar, verdikt, prognoz «tuzatilsa N%», analitik xulosa, harakatlar rejasi (belgilanadigan), «nima yig'ish kerak» ro'yxati, eksport |
| **История** | MVP+: versiyalar bo'yicha foiz dinamikasi (72% → 94%) va nima o'zgargani |
| **Настройки** (admin) | Vaznlar, k, chegaralar, lug'atlar, foydalanuvchilar |

**Asosiy komponent: `DocumentViewer`.** PDF uchun PDF.js, skan va rasmlar uchun sahifa PNG'si. Ustiga bbox overlay chiziladi: normallashtirilgan koordinatalar ko'rsatish o'lchamiga ko'paytiriladi. XLSX katakni belgilash bilan HTML jadval sifatida ko'rsatiladi. Sahifaga va bbox'ga avtomatik scroll qilinadi. Tarjima tugmasi asl sitatani tanlangan hisobot tiliga o'giradi (LLM, kesh bilan).

**i18n.** Interfeys tillari: RU, UZ (lotin), EN. Barcha matnlar `i18n/*.json` da, kod ichida matn bo'lmaydi.

---

## 11. Xavfsizlik va maxfiylik

| Soha | Chora |
|---|---|
| Izolyatsiya | Har so'rovda `org_id` kontekstga o'rnatiladi. Postgres RLS ikkinchi himoya qatlami sifatida ishlaydi. S3 kalitlari `{org_id}/...` prefiksi bilan saqlanadi |
| Shifrlash | TLS 1.2+ (nginx). R2 da saqlashda shifrlash AES-256 (default). Postgres disk darajasida shifrlanadi |
| Kirish | RBAC: `admin`, `specialist`, `viewer`. JWT qisqa muddatli (15 daqiqa) + refresh. Login urinishlariga rate-limit |
| Audit | Statusni o'zgartirish, chek-listni tahrirlash va tasdiqlash, eksport, o'chirish, sozlamalar o'zgarishi `audit_log` ga yoziladi |
| Fayllar | ClamAV tekshiruvi, MIME sniffing (kengaytmaga ishonilmaydi). Zip-slip va zip-bomb himoyasi: hajm, siqish nisbati, fayllar soni, chuqurlik ≤ 3 |
| Prompt injection | Hujjat matni ishonchsiz ma'lumot sifatida `<document>` teglari ichida beriladi. Tizim prompti buni aniq aytadi. Raqamli qarorlarni kod qabul qiladi. LLM sitatalari manbada tekshiriladi. Injection testlari to'plami bor ([PIPELINE.md §9.3](PIPELINE.md)) |
| Saqlash | Saqlash muddati tashkilot sozlamasida (default 12 oy). `beat` vazifasi muddati o'tganlarni o'chiradi. So'rov bo'yicha darhol o'chirish (fayllar, sahifalar, embeddinglar, `llm_calls`) |
| LLM provayder | Anthropic tijoriy shartlari bo'yicha API ma'lumotlari model o'qitishga ishlatilmaydi. Buni yurist tasdiqlashi kerak, ZDR kelishuvini ham ko'rib chiqish lozim. Lokalizatsiya talab qilinsa, on-prem provayder (R-04) |
| Shaxsiy ma'lumotlar | Arizalarda mutaxassislar rezyumesi, pasport ma'lumotlari, telefonlar bo'lishi mumkin. Loglarda PII yashiriladi. O'zR shaxsiy ma'lumotlar qonunchiligi (lokalizatsiya) bo'yicha qaror R-04 da |
| Sirlar | `.env` faqat dev'da. Pilot va prod'da Docker/K8s secrets yoki Vault |

---

## 12. Deploy va infratuzilma

### Muhitlar

| Muhit | Maqsad | Infra |
|---|---|---|
| `local` | Dasturlash | `docker compose up` (barcha servislar, GPU'siz) |
| `staging` | Integratsiya, eval, demo | 1 VM, Compose |
| `pilot` | 5–10 kompaniya | 1–2 VM, Compose, backup, monitoring |
| `prod` | Kengaytirish bosqichi | Kubernetes, worker'lar navbatlar bo'yicha avtomasshtablanadi |

### Compose servislari

`web` (nginx + statik), `api`, `worker-ingest`, `worker-ocr`, `worker-llm`, `worker-core`, `worker-report`, `beat`, `postgres` (pgvector image), `redis`, `clamav`, `embedder` (BGE-M3), `prometheus`, `grafana`.

### Pilot serveri (dastlabki baho, R-02 dan keyin aniqlanadi)

16 vCPU, 64 GB RAM, 1 TB SSD. OCR GPU'da tezroq bo'lsa, ixtiyoriy NVIDIA L4 yoki T4. LLM bulutda bo'lsa, serverga GPU faqat OCR va embeddinglar uchun kerak.

### Hosting

Ma'lumotlarni lokalizatsiya qilish talab qilinsa, O'zbekistondagi data-markaz (R-04). LLM API'ga faqat ishlov berish uchun matn va sahifa rasmlari ketadi, saqlanmaydi. Bunga ruxsat bor-yo'qligi yuridik qaror.

### CI/CD (GitHub Actions)

- PR: ruff, mypy, pytest (unit + integration testcontainers bilan), eslint, vitest, Docker build.
- `main`: image'lar registry'ga, staging'ga avtomatik deploy.
- Eval: `prompts/` yoki `pipeline/extract|match` o'zgargan PR'larda **qo'lda** ishga tushadi (pul sarflaydi). Tungi to'liq eval Batch API orqali.

---

## 13. Kuzatuv (observability)

- **Loglar:** structlog JSON, `project_id`, `run_id`, `stage`, `org_id` bilan. PII yashiriladi.
- **Xatolar:** Sentry (api, workers, web).
- **Metrikalar (Prometheus):** bosqich davomiyligi (p50, p95), navbat chuqurligi, sahifa/daqiqa, LLM tokenlari va xarajati (route bo'yicha), kesh hit-rate, ⚪ ulushi, sitata rad etilishi.
- **Panellar (Grafana):** «100 sahifa SLA», «LLM xarajati / tekshiruv», «Sifat signallari».
- **LLM tracing:** Langfuse (self-host, ixtiyoriy) — prompt, javob, latency, eval natijalari.

---

## 14. Nofunksional talablar → arxitektura

| NFT (TZ §10) | Qanday ta'minlanadi | Qanday o'lchanadi |
|---|---|---|
| OCR: CER ≤ 2% (skan ≥ 200 dpi), ≤ 5% (foto) | Benchmark asosida engine tanlash, preprocessing, vision orqali ikkinchi o'qish | R-02 benchmark, eval to'plami |
| Raqamlar 100% (ishonch ≥ 90% bo'lsa) | Ikki o'quvchi (OCR va vision LLM) raqamlarni o'zaro tekshiradi, kelishmasa ishonch < 90% va qo'lda tekshiruvga | Eval: raqamli maydonlar aniqligi |
| Gallyutsinatsiyadan himoya | Sitata darvozasi: matnda topilmagan sitata rad etiladi | Citation validity = 100% (avtomatik) |
| ≤ 10 daq / 100 sahifa, ≤ 30 daq / 500 sahifa | Sahifa va chunk bo'yicha parallellik, kesh, oraliq natijalar | Bosqich metrikalari, yuklama testi |
| ≥ 50 parallel tekshiruv | Stateless API, navbatlar bo'yicha gorizontal worker'lar, rate-limiter | k6 / locust (H-02) |
| Maxfiylik | RLS, TLS, AES-256, o'qitishda ishlatmaslik | Xavfsizlik cheklisti (H-03) |
| Saqlash 12 oy va o'chirish | `beat` retention vazifasi, o'chirish API | Integration test |
| Shaxsiy ma'lumotlar | R-04 qarori (lokalizatsiya) | Yuridik xulosa |
| Kirish | RBAC, audit, telefon OTP (pilot), platforma SSO (3-bosqich) | — |
| Mavjudlik 99.5% | Healthcheck, restart siyosati, backup, alertlar. K8s keyinroq | Uptime monitor |
| Tushuntiriluvchanlik | `reasoning` va manbalar sxemada majburiy, DB constraint | Avtomatik tekshiruv |
| Takrorlanuvchanlik | Model va prompt versiyasi qotirilgan, LLM keshi xesh bo'yicha | H-04: bir xil fayllar → bir xil natija |
