# Аудит: RELTA (ai-mentor)

Дата аудита: 2026-11-02. Метод: только чтение; клон неглубокий — коммиты по GitHub API.

**1. Назначение.** ИИ-платформа для брокеров и агентств недвижимости: ИИ-разборы, CRM сделок и объектов, запись и разбор звонков, тренажёр переговоров, KPI и прогноз, экономика агентства, мессенджеры (Wazzup, личный WhatsApp, Telegram). Домен — relta.tech.

**2. Статус: Production.** Автодеплой на VPS по мержу в main (`.github/workflows/deploy.yml`); последний «Deploy to VPS» успешен — run #158, 02.11.2026. Прод-инфраструктура: `infra/docker-compose.yml`, `infra/deploy.sh`, `infra/monitor/server-health.sh`, `infra/cron/daily.sh`. Открыт issue #247 «[error-watch] infra-app-1: prisma:error» (26.10) — мониторинг живого контейнера. Следы живых пользователей: «у части пользователей подписка на него [PRO] уже оформлена» (`src/lib/pricing.ts`). Число пользователей: нет подтверждённых данных.

**3. Аудитория.** Брокеры (тариф Agent) и руководители агентств (пакеты мест).

**4. Монетизация.** Цены в `src/lib/pricing.ts`: Free 0 ₽; Agent 990 ₽; PRO снят с продажи; пакеты агентства 5 мест 3 900 ₽, 10 — 6 900 ₽, до 50 — 23 900 ₽, до 100 — 39 900 ₽ + места сверх пакета. **Онлайн-оплаты нет**: `subscription.changePlan` отказывает (`PAID_PLAN_UNAVAILABLE`), платный тариф включает администратор (`admin.changePlan`, `admin.setAgencyPlan`, `Agency.paidUntil`). ЮKassa — только план. Legacy-поля Stripe в `Subscription`. Промокоды реализованы.

**5. Стек.** TypeScript, Next.js 15.5 (CLAUDE.md устарел: «14»), tRPC 11, Prisma 5, PostgreSQL (Timeweb Managed), NextAuth 4, S3, Claude (sonnet-4-6, haiku-4-5), OpenAI Whisper. Сервис `services/wa` (baileys) на узле в Амстердаме, деплой `deploy-wa.yml`. Хостинг: Timeweb VPS, `/opt/relta`, общий Caddy на пять доменов; исходящие к Anthropic/OpenAI/Telegram через ai.relta.tech. Очереди нет, фоновые задачи — cron `/api/cron/daily`.

**6. Источники бизнес-данных** (`prisma/schema.prisma`, 33 миграции):
- `User`, `Agency` (plan, maxAgents, extraSeats, paidUntil), `Team`, `TeamMember`, `ActivityLog`;
- `Subscription` (plan, status, priceRub, nextBillingDate, cancelAtPeriodEnd);
- `BillingHistoryItem` (amountRub, status) — **в коде нет ни одной записи в эту таблицу**, но `admin.revenueChart` считает по ней MRR. Вывод: реальной выручки в базе нет;
- `LlmUsage` (feature, model, токены, cache, costUsd, plan) — пишется из 7 мест; Whisper не пишется (вывод); `UsageLog`, `CreditGrant`;
- отчёты: `admin.stats`, `admin.llmCostReport`, `usageByDay`, `activityChart`, `planDistribution`, `revenueChart`, `agencies`; `scripts/llm-cost-report.js`;
- `docs/finmodel.md` (июнь 2026) устарела: Agent 1 990 ₽ и Agency 9 900/29 900 ₽ против 990 ₽ и пакетов мест в коде.

**7. Состояние разработки.** 382 коммита, 03.05.2026 — 02.11.2026; за 30 дней 109 — темп высокий. Открыт PR #243 (25.10), issue #247. Веток 50, из них 48 — вероятно остатки смерженных PR. Релизов нет.

**8. Качество.** 111 тестовых файлов (vitest), ~693 теста (#244). Проверки (`tsc`, `typecheck:wa`, `vitest`) — только на push в main перед деплоем; **на PR проверок нет**. ESLint-конфига нет. `as any` — 174 раза.

**9. Безопасность.** `.env` в git нет; боевых секретов не найдено. Наружу только 80/443. `xlsx@^0.18.5` — известные уязвимости без исправления на npm (вывод). `npm run build` содержит `prisma db push --accept-data-loss`. В CLAUDE.md записаны IP и SSH под root к общему серверу; видимость репозитория неизвестна.

**10. Технический долг.** Мусор эпохи Manus/Vercel в корне: `devops-audit.zip`, `diagnostic-files.zip`, `DIAGNOSTIC_*.md`, `DEVOPS_*.md`, `MANUS_TASK.md`, `AUDIT_REPORT.md`, `terraform/`, `scripts/deploy-to-aws.sh`, `Dockerfile.backend/.frontend`, `vercel.json`, `capture_console.js`. Поля Stripe. Неиспользуемая `@aws-sdk/s3-request-presigner`. CLAUDE.md ~80 КБ, местами расходится с кодом.

**11. Риски (вывод).** Технические: общий VPS и Caddy на пять сайтов; WhatsApp через baileys нарушает условия WhatsApp (баны номеров); нет проверок на PR — сломанный main сразу в прод. Бизнес: оплаты нет, выручка ручная и не отражается в базе; переписка, звонки и ПДн уходят в Anthropic/OpenAI — трансграничная передача по 152-ФЗ; цены в финмодели, на лендингах и в коде расходятся.

**12. Вопросы владельцу.** Сколько платящих пользователей и агентств, MRR по ручным счетам? Что лежит в `BillingHistoryItem` на проде? Когда ЮKassa? Публичен ли репозиторий? Можно ли убрать архивы эпохи Manus?
