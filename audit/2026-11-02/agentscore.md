# Аудит: AgentScore (agent-trainer)

Дата аудита: 2026-11-02. Метод: только чтение.

**Конфликт имён.** «AgentScore» — имя этого продукта (`README.md`, пакеты `@agentscore/*`) и одновременно имя старого рекрутингового MVP (репозиторий agenthunter и первый коммит этого репо `ca472df`). Два разных продукта для одной аудитории под одним названием.

**1. Назначение.** Тренажёр и оценка навыков агентов по недвижимости: диалоги с ИИ-клиентом, экзамены, отчёт руководителю (`TZ_agent_trainer.md` §1). Домена нет.

**2. Статус: Development.** Сделаны этапы 0 и 1 из 7 (`docs/STATE.md`, PR #3, #4). Деплой-скриптов нет; `docs/DECISIONS.md`: «Этап 0 — локальный запуск + CI, деплой позже».

**3. Аудитория.** Агенты и руководители агентств, B2B для многих агентств; организации создаёт владелец платформы.

**4. Монетизация.** Не реализована, тарифов нет ни в коде, ни в ТЗ. Есть учёт себестоимости: `packages/providers/src/pricing.ts` (тарифы LLM в ₽, курс 95 ₽/$, пометка «СВЕРИТЬ»), суточный бюджет `ORG_DAILY_TOKEN_BUDGET=2 000 000` (`packages/api/src/limits.ts`).

**5. Стек.** pnpm + Turborepo; `apps/web` (Next.js 15, React 19, Tailwind 4, tRPC + Zod, Auth.js v5 beta), `apps/worker` (BullMQ); `packages/{db,api,auth,ai,providers,queue,scoring,storage,shared,config}`; Prisma + PostgreSQL 16 (pgvector), Redis, MinIO/S3; LLM — Anthropic или YandexGPT за `LLMProvider`. Хостинг — VPS Timeweb, деплоя нет.

**6. Источники бизнес-данных** (`packages/db/prisma/schema.prisma`): `Organization`, `User`; **`UsageEvent`** — `kind LLM|STT|TTS|TELEPHONY`, provider, model, токены, `audioSeconds`, `cost` Decimal(12,6), `currency=RUB`, привязка к организации/пользователю/сессии, пишется на каждый вызов LLM (`packages/api/src/usage.ts`) — лучший учёт себестоимости в портфеле; `TrainingSession`, `Message`, `SessionEvaluation`, `AuditLog`. Подписок и платежей нет; дашборд расходов — этап 6 ТЗ.

**7. Состояние разработки.** 46 коммитов; репо прежде использовался под калькулятор автомойки (PR #1–#2) и ассеты «Eva AI», очищен 28.10 (`07a0a69`). Реальная работа с 28.10, последний коммит в `main` — 29.10. Открытых PR и issues нет. В ветке `claude/sweet-mayer-52pz2d` коммиты от 01.11 (макеты лендинга) без PR.

**8. Качество.** 32 тестовых файла (Vitest + Playwright), по `STATE.md` 441 unit/integration и 43 e2e. CI `.github/workflows/ci.yml`: lint, prettier, typecheck, test, build, e2e; последний успешный 29.10. ESLint `--max-warnings=0`. Evals: 12 диалогов, 8 атак на персону.

**9. Безопасность.** В текущем дереве секретов нет. **В истории** (`ca472df`, удалён в `07a0a69`) — `backend/.env` с DATABASE_URL, JWT_SECRET, OPENAI_API_KEY, ANTHROPIC_API_KEY: если значения где-то использовались — считать скомпрометированными. В истории zip-архивы 38 и 44 МБ (`eva_training_data*.zip`, `9bba8e1`) — проверить на ПДн. `infra/docker-compose.yml` открывает порты на всех интерфейсах (допустимо только локально). Демо-пароль в `README.md`.

**10. Технический долг.** `tests_prototype.html` в корне; чужая история в репо; тарифы LLM не сверены; эталонных диалогов 12 из 18; RLS отложен; Auth.js v5 beta.

**11. Риски (вывод).** Технические: выбор провайдера (YandexGPT/Claude) заблокирован отсутствием ключей; телефония и голос не решены; стоимость в `UsageEvent` по несверенным тарифам. Бизнес: модели монетизации нет; пересечение с Agent Hunter и тренажёром RELTA — каннибализация; конфликт имени.

**12. Вопросы владельцу.** Модель цен и платёжный провайдер? Где и когда деплой? Отдельный продукт или модуль Agent Hunter / RELTA? Переименование? ПДн в архивах Eva AI? Использовались ли значения старого `backend/.env`? Судьба ветки `sweet-mayer`?
