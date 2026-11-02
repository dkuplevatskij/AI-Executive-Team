# Аудит: OnFive (onfive)

Дата аудита: 2026-11-02. Метод: только чтение; коммиты по GitHub API.

**1. Назначение.** ИИ-репетитор для школьников 5–11 классов, сократический метод, доклады, панель родителя. Домен — onfive.pro (`infra/caddy/edge-snippet.Caddyfile`).

**2. Статус: Production или поздняя бета (вывод).** Автодеплой по SSH на Timeweb (`.github/workflows/deploy.yml`), последний успешен — run #36, 22.10.2026. Админка показывает реальные счётчики (`/api/admin/summary`). Оплата не запущена по юридическим причинам: чек-лист `MONETIZATION.md` не закрыт (реквизиты, РКН), в `client/src/pages/legal/Oferta.tsx` заглушки `[ФИО полностью]`, `[ИНН]`. Число пользователей: нет подтверждённых данных.

**3. Аудитория.** Школьники и их родители.

**4. Монетизация.** Подписка 500 ₽/мес через CloudPayments: виджет `client/src/lib/subscription.ts`, вебхук с HMAC и отмена (`server/src/routes/subscribe.ts`), `SUBSCRIPTION_PRICE_RUB = 500` (`server/src/subscriptionWebhook.ts`), подарочные подписки (`adminActions.ts`). Вывод: лимиты от подписки не зависят — 3 бесплатных вопроса до email, затем 100 сообщений в сутки для всех (`chat.ts`); ценность подписки в коде не выражена.

**5. Стек.** npm workspaces: React 18, Vite 6, Tailwind 4, Zustand; Fastify 5, `pg`, `@anthropic-ai/sdk` (claude-sonnet-4-6); PostgreSQL 15. `docker compose` на **том же сервере, что и RELTA** (общий Caddy, `/opt/caddy-sites/onfive.caddy`). Anthropic через `ai.onfive.pro`. Очереди нет.

**6. Источники бизнес-данных** (`server/migrations/0001–0003`): `users` (created_at, email, email_verified_at, blocked_at, free_requests_used); `profiles` (grade, xp, coins, streak, last_active, город); `reports`; `subscriptions` (status, provider, cp_subscription_id, amount, current_period_end, cancelled_at). **Таблицы платежей нет** — история только в кабинете CloudPayments. **Учёта токенов и стоимости ИИ нет**; счётчик сообщений в памяти (`chatLimits.ts`), обнуляется при рестарте. Метрики: `/api/admin/summary` (пользователи, новые за день/неделю, активные за 7 дней, подписки, подарки, доклады, ИИ-сообщения за сегодня).

**7. Состояние разработки.** 82 коммита, 02.06.2026 — 22.10.2026; за 30 дней 18, с 22.10 работы нет. PR/issues открытых нет. 11 веток кроме main без открытых PR. Релизов нет.

**8. Качество.** 24 тестовых файла (12 client, 12 server). CI `ci.yml`: ci, typecheck, build — **тесты в CI не запускаются** (вывод). 145 прогонов, последние успешны.

**9. Безопасность.** `.env` в git нет, секретов не найдено. Порты не публикуются. Вебхук с HMAC, вход в админку по паролю с rate-limit. Вывод: аудитория — несовершеннолетние, сообщения уходят в Anthropic (США) — повышенные требования 152-ФЗ, уведомление о трансграничной передаче не подано (`MONETIZATION.md`). Бэкапы (`infra/scripts/backup-db.sh`) на том же сервере.

**10. Технический долг.** Устаревшие `infra/COOLIFY.md`, `DEPLOY-RU-HYBRID.md`, `migrate_from_supabase.sql`, упоминания Supabase/Vercel в 20 файлах. CLAUDE.md описывает несуществующее: `voice.ts`, `stats.ts`, Whisper, Telegram Mini App SDK.

**11. Риски (вывод).** Технические: зависимость от инфраструктуры RELTA; лимиты в памяти, учёта стоимости ИИ нет; бэкапы без выноса. Бизнес: подписка ничего не открывает; юридически оплата не готова (реквизиты, РКН, трансграничная передача данных детей); разработка остановилась 22.10.

**12. Вопросы владельцу.** Живые пользователи и подписчики, сколько подарков? Подключён ли боевой CloudPayments? Что должна давать подписка? Проект жив? Куда копируются бэкапы?
