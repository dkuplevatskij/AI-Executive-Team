# Аудит: Agent Hunter (ai-recruit)

Дата аудита: 2026-11-02. Метод: только чтение; клон неглубокий (граница `a52d9c4`, 18.04.2026) — полная история по GitHub API, история до 18.04 на секреты не проверялась.

**1. Назначение.** Сервис оценки кандидатов-риелторов для агентств: ссылка кандидату → тест → голосовая ролевая симуляция звонка → отчёт с баллом и стоп-факторами; HR ведёт кандидатов по воронке (`README.md`). Домен — `agent-hunter.ru` (`deploy/Caddyfile.snippet`).

**2. Статус: Production.** `.github/workflows/deploy.yml` выкатывает каждый push в `main` по SSH; 45 запусков, последний успешный — 01.11.2026 (run #45, PR #39). Прод-стек `deploy/docker-compose.prod.yml` (`agenthunter-ai-app`, `agenthunter-ai-db`, общий Caddy, сеть `infra_web`). Issue #27 (28.10, `[error-watch]`): «Email service not configured» на живом контейнере. `docs/product/finmodel.json`: «Первые клиенты, данные ограничены. [заполнить: число агентств, MRR]», `initial_agencies = 0` — подтверждённых платящих клиентов нет.

**3. Аудитория.** HR и руководители агентств недвижимости; проблема — дорогой и субъективный отбор агентов.

**4. Монетизация.** Тарифы в БД (`plans`, `planLimits`, `workspaceSubscriptions` в `drizzle/schema.ts`); цены в `server/billing.ts` (`seedOnce`): «Старт» 4 900 ₽/мес (3 920 за год), «Pro» 12 900 ₽ (10 320, пробный 14 дней, по умолчанию при регистрации), «Business» 29 900 ₽ (23 920). Лимиты и флаги функций; правка суперадмином (`server/billing-router.ts`). Оплата только по счёту — суперадмин ставит `paidUntil` вручную. Платёжного провайдера и таблицы платежей нет.

**5. Стек.** React 19, Vite 7, wouter, Tailwind 4, shadcn; Node 22, Express 4, tRPC 11, MySQL 8.4 + Drizzle; S3 Timeweb; SMTP/Resend; LLM — OpenAI-совместимый API через прокси на Vercel (`tools/openai-proxy`), модели `gpt-4o-mini`, `whisper-1`, `gpt-4o-mini-tts` (`server/_core/env.ts`), вариант YandexGPT. Очереди нет. Docker Compose за общим Caddy (`infra-caddy-1`), сервер Timeweb — тот же, что у RELTA (по `ai-mentor/CLAUDE.md`).

**6. Источники бизнес-данных** (`drizzle/schema.ts`): `users`, `workspaces` (ИНН, `status trial|active|suspended`, `trialEndsAt`), `workspaceUsers`, `workspaceMembers`, `agencyLeads`, `earlyAccessSignups`; `workspaceSubscriptions` (`planCode`, `status`, `trialEndsAt`, `paidUntil`, `note`), `plans` — платежей и счетов нет; использование — `candidates`, `assessments`, `voiceSimulations`, `candidateJourney`, `candidateStageHistory`, `publicLinkViews`, `apiUsage`, `auditLog`, `crmPushLog`. Расход LLM в БД не пишется (`server/_core/aiBudget.ts` считает в памяти). Отчёты: `admin.getStats` (`server/routers.ts:1201`) — лиды, агентства (всего/active/trial), кандидаты; `server/analytics-router.ts` отдаёт захардкоженные демо-данные; отчёта по выручке нет.

**7. Состояние разработки.** ~271 коммит, 17.03.2026 — 01.11.2026; 60 коммитов с 03.10, пик 27–30.10. Открыт черновик PR #38 (30.10, «Тест сокращён до 24 вопросов…»), issue #27. Веток 25, 24 смержены, но не удалены. Релизов нет.

**8. Качество.** 57 тестовых файлов (Vitest). **В CI тесты не идут**: единственный workflow — деплой без тестов и `tsc`. ESLint нет.

**9. Безопасность.** В git только `deploy/.env.prod.example`; ключей нет. MySQL в изолированной сети. Swagger открыт публично на `/api-docs` (`server/_core/index.ts:257`). `superAdminProcedure` пускает и роль `admin` (`server/routers.ts:48–52`) — вывод: если `admin` получают сотрудники агентств, у них доступ к суперадминке; проверить. Голос кандидатов (ПДн) уходит в OpenAI через Vercel; трансграничная передача упомянута в `ConsentDoc.tsx`, `Privacy.tsx`.

**10. Технический долг.** Мусор в корне (`todo.md` 1 827 строк, 258 открытых пунктов; `TEST_REPORT.md`, `IMPROVEMENTS_SUMMARY.md`, `HEYGEN_SCRIPT.md`, `VEO_SCRIPT_SHORT.md`, `potok_analysis.md`, `ideas.md`, `seed-*.mjs`). Наследие Manus (`vite-plugin-manus-runtime`, `/__manus__/logs`, `oauth.ts`, `sdk.ts`). Миграции в прод не накатываются — таблицы создаются кодом (`server/billing.ts`); `scripts/register-migration.mjs`. Заглушки `analytics-router.ts`, `ComponentShowcase.tsx`. CLAUDE.md в корне нет.

**11. Риски (вывод).** Технические: схема БД расходится между окружениями; автодеплой без тестов; LLM через зарубежный прокси, лимит расходов в памяти. Бизнес: нет онлайн-оплаты; нет подтверждённых клиентов и MRR; голос кандидатов в OpenAI — риск по 152-ФЗ.

**12. Вопросы владельцу.** Сколько агентств платят и сколько в пробном периоде? Кто выставляет счета, где учитываются оплаты? Месячный счёт OpenAI и Vercel? Кому выдаётся роль `admin`? Нужен ли `/api-docs` в проде? Судьба 24 веток?

## Связанный репозиторий agenthunter (вне портфеля)
Прежний «AgentScore MVP» (Express + Next.js 14 + PostgreSQL, 15 коммитов 02–20.09.2026, без тестов). `ai-recruit/deploy/README.md` называет его временной заглушкой, которую ai-recruit заменил. Вывод: вытеснен и заброшен.
