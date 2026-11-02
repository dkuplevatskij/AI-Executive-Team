# Аудит: Агроконтур (LogisDoc-Pro)

Дата аудита: 2026-11-02. Метод: только чтение — локальный клон, GitHub API (PR, ветки, Actions). Сборки не запускались.

**1. Название и назначение.** B2B-платформа зерновой логистики и закупки: регистрация перевозчиков и парка, реестры погрузки, рейсы, генерация транспортных документов (ТН, заявка, СП-31, акты), OCR документов, биржа перевозок, контур «Закупка», интеграция с 1С (README.md:1–20). Боевой домен — `agrokontur.ru` (README.md:3, CLAUDE.md).

**2. Статус: Beta / пилот на проде.** Деплой по SSH в `/opt/logisdoc` (`.github/workflows/ci.yml`, job `deploy`), только вручную (`workflow_dispatch`) и только с `main`. Последняя успешная выкладка — 21.10.2026 (`ae9da83`). На проде есть данные («13 прицепов у шести перевозчиков», docs/bugs.md:122), но владелец решил: «на проде всё, что заведено до сих пор, тестовое» (tools/maintenance/cleanup_test_registries.sql, 24.09.2026). Вывод: выложен, реальной коммерческой эксплуатации на подтверждённых данных нет.

**3. Аудитория и проблема.** Агент или экспедитор по закупке и перевозке зерна (оператор платформы), принципалы-заказчики, перевозчики, водители, отборщики, терминалы (`backend/app/api/v1/*_portal.py`, `qa_miniapp.py`). Проблема — ручное ведение реестров, документов и взаиморасчётов по рейсам.

**4. Монетизация.** Платёжного провайдера, подписок и тарифов платформы в коде нет. Модель — «один заказчик на инсталляцию» (`backend/app/models/organization.py:31-34`). Деньги в коде — выручка оператора, не плата за SaaS: агентское вознаграждение `AGENT_FEE_PER_TON_DEFAULT = 150` ₽/т (`backend/app/models/procurement_order.py:12, 386`), вознаграждение экспедитора `expeditor_fee_per_ton` (`expeditor_order.py:154`). Планы монетизации платформы: нет подтверждённых данных.

**5. Стек и архитектура.** Python 3.11, FastAPI 0.141, SQLAlchemy 2.0, Alembic (122 миграции), PostgreSQL 16; OCR Tesseract / Yandex Vision; WeasyPrint; RabbitMQ 4.3 (pika); Jaeger + OpenTelemetry; Traefik v3. Фронтенд: React 19, TypeScript 6, Vite 8, oxlint. Боты Telegram и MAX. Внешние API: Checko, Yandex Vision, SMTP. Один `docker-compose.yml`, профиль `bus` на проде не поднят (README.md:126). Хост — в секрете `DEPLOY_HOST`.

**6. Источники бизнес-данных** (`backend/app/models/`, 68 таблиц):
- `users`, `companies`, `carriers`, `organization_profile`;
- `procurement_orders` (`actual_accepted_volume_tons`, `agent_fee_per_ton`, `agent_commission_amount`) — главный источник выручки оператора; `deal_stage_changes`;
- `trips`, `registries`, `transport_requests`, `expeditor_orders`, `carrier_contracts`, `carrier_bids`, `freight_offers`, `vehicle_advances`, `carrier_settlements` (`marketplace.py:384`);
- `ocr_jobs` — косвенный счётчик OCR; учёта Yandex Vision и Checko нет; LLM не используется;
- отчёты: `GET /api/v1/dashboard/summary`, `execution-summary` (`customer_portal.py:294`), Excel-реестры и акты.

**7. Состояние разработки.** 520 коммитов в `main`, 02.08.2026 — 22.10.2026. За 30 дней — 27 коммитов (04–22.10), с 22.10 работы нет. PR всего 215, открытых 0; issues 0; релизов нет. Веток 12: 2 несмерженные заброшенные (`claude/bot-creation-spec-o5hbgq`, `claude/hopeful-ride-xf8gv9`), 9 влиты, но не удалены.

**8. Качество и тесты.** 108 файлов `backend/tests/test_*.py`, 5 e2e-сценариев, аудиты `tools/audit/*.py`. CI: pytest на PostgreSQL, `alembic upgrade head`, oxlint, `tsc -b`, сборка, e2e. Юнит-тестов фронтенда нет. Actions 21–22.10 успешны — запись CLAUDE.md о «красном CI из-за лимита» на эту дату не подтверждается.

**9. Безопасность.** `.env` в git нет, ключей не найдено. Слабые значения по умолчанию в `docker-compose.yml`: пароли PostgreSQL/RabbitMQ `agrokontur`, `JWT_SECRET_KEY=change-me-in-production` — приложение стартует с предупреждением (`backend/app/main.py:21`). Переопределены ли на проде — нет подтверждённых данных. Все порты на 127.0.0.1. Лимит неудачных входов с 13.10. Вывод: `passlib==1.7.4` не обновляется.

**10. Технический долг.** Страницы на 2–3 тыс. строк (`ProcurementPage.tsx` 3283, `RegistriesPage.tsx` 2934, `TransportRequestsPage.tsx` 2654, `ContractorsPage.tsx` 2011, `CustomerPortalPage.tsx` 1952). README 43 КБ. Остатки имени `logisdoc`. Шина на проде не поднята (`docs/microservices-migration.md`). Разовые SQL в `tools/maintenance/`, PDF в git. Устаревший раздел о CI в CLAUDE.md, неудалённые ветки.

**11. Риски (вывод).** Технические: слабые секреты по умолчанию (если не переопределены — подделка JWT); монолитные страницы; один сервер, бэкапы не описаны. Бизнес: «один заказчик на инсталляцию» не масштабируется как SaaS; реальных операций не подтверждено; выручка привязана к одной отрасли с сезонностью.

**12. Вопросы владельцу.** Кто оператор — своя компания или клиент студии, есть ли договор? Идёт ли реальная работа после 24.09? Планируется ли многоарендная модель с тарифами? Где бэкапы БД и документов? Переопределены ли секреты на проде? Сколько стоят Yandex Vision и Checko?
