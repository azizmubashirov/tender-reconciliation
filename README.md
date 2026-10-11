# Тендер-Сверка (tenderai)

Ishtirokchi arizasini tender hujjatlaridagi talablar bilan AI yordamida solishtiruvchi vosita. Natijada moslik foizi, rad etilish xavfi, nomuvofiqliklar ro'yxati va ularni tuzatish rejasi chiqadi.

Manba TZ: [docs/spec/TZ-v0.1.docx](docs/spec/TZ-v0.1.docx) (qoralama v0.1, 08.10.2026, @Марат)

## MVP funksiyalari

| # | Funksiya | Qayerda |
|---|---|---|
| 1 | PDF (matn va skan), Word, RTF, ODT, Excel, rasm, ZIP/RAR/7Z yuklash | «Документы» ekrani, `pipeline/convert.py` |
| 2 | O'zbek (lotin/kirill), rus, ingliz tilidagi hujjatlarni qayta ishlash | Claude hujjatni o'zi o'qiydi, hisobot tili RU/UZ/EN |
| 3 | Buyurtmachi talablaridan chek-list (T-/U-, tur, manba sitatasi, «Вопросы к заказчику») | «Чек-лист» ekrani, `pipeline/extract.py` |
| 4 | Ishtirokchi hujjatlaridan fakt va ma'lumotlarni ajratish | `pipeline/check.py` (`extract_facts`) |
| 5 | Har bir talabni avtomatik solishtirish (5 status) | Raqamlar: kod (`pipeline/rules.py`), ma'no: Claude |
| 6 | Moslik foizi va rad etilish xavfi (TZ §7 formulasi) | `pipeline/scoring.py`, «Сравнение» ekrani |
| 7 | Muammolar va ularni bartaraf etish rejasi | «Сводка» ekrani |
| 8 | PDF va Excel hisobot eksporti | `pipeline/report.py` |

## Ishga tushirish

Kerak: Docker. Lokal dasturlash uchun qo'shimcha: [uv](https://docs.astral.sh/uv/), Node 24+.

```bash
make env       # .env yaratiladi
```

`.env` da kalitlarni to'ldiring:

| O'zgaruvchi | Majburiy | Izoh |
|---|---|---|
| `ANTHROPIC_API_KEY` | **ha** | Claude kaliti. Usiz hujjatlar yuklanadi va konvertatsiya qilinadi, lekin tahlil qilinmaydi |
| `CF_ACCOUNT_ID`, `CF_AI_GATEWAY_ID` | yo'q | Cloudflare AI Gateway. To'ldirilsa, barcha so'rovlar gateway orqali ketadi (kesh, loglar, xarajat). Bo'sh bo'lsa, to'g'ridan-to'g'ri Anthropic'ka |
| `CF_AIG_TOKEN` | yo'q | Gateway «Authenticated» rejimida bo'lsa |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET` | yo'q | Cloudflare R2. Bo'sh bo'lsa, fayllar lokal docker volume'da saqlanadi |

```bash
make up
```

- Ilova: http://localhost:8080
- API docs: http://localhost:8000/api/docs
- Holat: http://localhost:8000/api/v1/health/ready (`llm: skipped` bo'lsa, kalit qo'yilmagan)

Lokal portlar band bo'lsa, `.env` da `POSTGRES_PORT`, `REDIS_PORT`, `API_PORT`, `WEB_PORT` ni o'zgartiring.

## Foydalanish

1. **Yangi tekshiruv** yarating (hisobot tilini tanlang).
2. **Документы**: buyurtmachi hujjatlarini yuklang → «Извлечь требования».
3. **Чек-лист**: talablarni tekshiring, kerak bo'lsa tahrirlang yoki qo'shing → «Утвердить чек-лист».
4. **Документы**: ariza hujjatlarini yuklang → «Подготовить документы» → «Запустить проверку».
5. **Сравнение**: statuslar, ikkala manba sitatasi, asos. Statusni izoh bilan qo'lda o'zgartirish mumkin, foiz qayta hisoblanadi.
6. **Сводка**: verdikt, foizlar, analitik xulosa, harakatlar rejasi, PDF va Excel. «Новая версия заявки» qayta tekshiruv uchun, foizlar tarixi shu yerda ko'rinadi.

## Tekshiruvlar

```bash
make lint
```

```bash
make test
```

Testlar butun zanjirni (yuklash → chek-list → faktlar → solishtirish → foiz → reja → PDF/Excel) haqiqiy fayl konvertatsiyasi bilan, model javoblarini esa skript bilan almashtirib tekshiradi.

## Hujjatlar

| Hujjat | Mazmuni |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Tamoyillar, komponentlar, stek, ma'lumotlar modeli, API, xavfsizlik, deploy |
| [docs/PIPELINE.md](docs/PIPELINE.md) | Konveyer: talablarni ajratish, solishtirish qoidalari, skoring formulasi, eval |
| [docs/MVP-PLAN.md](docs/MVP-PLAN.md) | Sprintlar va vazifalar, qabul mezonlari, risklar, ochiq savollar |
