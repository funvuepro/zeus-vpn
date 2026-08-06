# Zeus VPN — редизайн VpnBot: спецификация

## Контекст

Партнёры сменились (старый VPN-сервер недоступен, платёжный партнёр меняется). Вместо переделки боевого `VpnBot` — новый независимый проект под новым брендом, на основе того же кода. Старый `VpnBot` не трогается.

## Цели

1. Новый бренд: **Zeus VPN**, визуальный стиль — молнии/энергия (⚡), серьёзный технологичный тон.
2. Новый сервер VPN (Remnawave, тот же протокол интеграции — только новые креды).
3. Новая платёжная система: **ЮKassa** (оформление под ИП, ИП будет готово позже — код готовим заранее, реальные ключи подключаются потом).
4. Смена бизнес-модели: с фиксированных тарифов (Plan, 30/60/90 дней) на **баланс + суточное списание за устройства**.
5. Реферальная система: без вывода средств, разовое начисление 100₽ на баланс за первую оплату приглашённого.

## Архитектура и стек

Без изменений относительно `VpnBot`: Python, aiogram (бот), FastAPI (вебхуки), SQLAlchemy + Alembic (БД), Remnawave (VPN-панель), APScheduler-подобный `scheduler/tasks.py` (фоновые задачи).

Новый git-репозиторий, независимый от `VpnBot`. Копия кода как стартовая точка, дальше — точечные правки.

## 1. Бренд

- Название: **Zeus VPN**
- Тон: серьёзный/технологичный, визуальная тема — молнии/энергия. Использовать ⚡ вместо/наряду с существующими эмодзи в ключевых точках (заголовки разделов, кнопки оплаты, приветствие), не захламляя текст.
- Саппорт: `@zeus_vpnsupport` (заглушка до реального аккаунта)
- Обновить: `bot/handlers/about.py` (privacy/terms/support тексты), `bot/handlers/start.py` (приветствие/меню), клавиатуры с упоминанием бренда.
- Все упоминания `DS-VPN` / `FreeKassa` / `CryptoBot` в текстах (включая юридические — политика конфиденциальности, где перечислены операторы платежей) заменяются на актуальные.

## 2. Оплата — ЮKassa

- `bot/services/yookassa.py`:
  - `create_payment(amount_rub, payment_id, description) -> confirmation_url` — POST `https://api.yookassa.ru/v3/payments`, Basic Auth (`YOOKASSA_SHOP_ID:YOOKASSA_SECRET_KEY`), заголовок `Idempotence-Key` (например, `str(payment_id)` + uuid), `confirmation.type = "redirect"`.
  - `verify_notification(payload) -> bool` — проверка через `payment.succeeded`/`payment.canceled` статус и сверку суммы/id; согласно докам ЮKassa, HTTP-уведомления не подписываются секретом как в FreeKassa/Lava — верификация через IP-whitelist ЮKassa либо повторный GET-запрос статуса платежа по API (`GET /v3/payments/{id}`) для подтверждения. Использовать второй способ (надёжнее, не зависит от IP-листов).
- `bot/webhooks/yookassa.py`: `POST /webhook/yookassa`, парсит `event`, при `payment.succeeded` — подтверждает статус через API и зачисляет сумму на `User.balance`.
- Если `YOOKASSA_SHOP_ID`/`YOOKASSA_SECRET_KEY` пустые — хендлер пополнения баланса показывает «⚡ Пополнение баланса скоро откроется» вместо вызова API.
- Удаляются: `bot/services/{cryptobot,lava,freekassa}.py`, `bot/webhooks/{cryptobot,lava,freekassa}.py`, соответствующие тесты.
- `.env`: убрать `CRYPTOBOT_TOKEN`, `LAVA_API_KEY`, `LAVA_SHOP_ID`, `FREEKASSA_*`; добавить `YOOKASSA_SHOP_ID=""`, `YOOKASSA_SECRET_KEY=""`.
- `PaymentProvider` enum → только `yookassa`.
- `Payment` теряет обязательный `plan_id`/`devices_count` (это были параметры покупки тарифа) — теперь представляет пополнение баланса: `amount`, `status`, `external_id` (id платежа в ЮKassa).

## 3. Баланс и суточное списание

Новая модель монетизации вместо Plan/Subscription с `expires_at`.

**User (новые поля):**
- `balance: Numeric(10,2)` default `0`
- `devices_limit: Integer` default `1`
- `access_active: Boolean` default `True`
- `grace_started_at: DateTime` nullable

**AppSetting (новая таблица, key-value):**
- `daily_rate_per_device: Numeric` default `1.00` — базовая ставка за 1 устройство/день, меняется админ-командой в боте (без редеплоя).

**Формула суточной ставки:**
`rate = daily_rate_per_device × 0.5 × (devices_limit + 1)`
→ 1 устройство = ×1 (1₽), 2 устройства = ×1.5 (1.5₽), 3 устройства = ×2 (2₽), и т.д.

**Регистрация нового пользователя:** при принятии условий — `balance = 1.00`, `devices_limit = 1`, создаётся Remnawave-пользователь с доступом сразу (без ограничения по времени со стороны Remnawave — управление доступом полностью на стороне бота через `access_active`).

**Планировщик (`bot/scheduler/tasks.py`, новая ежедневная задача, 00:00 МСК):**
Для каждого пользователя с `access_active=True`:
1. Списать `rate` с `balance` (может уйти в отрицательный/0).
2. Если после списания `balance <= rate` (то есть следующего списания не хватит) — отправить предупреждение «⚡ Баланс скоро закончится, пополните» (за 1 день до обнуления).
3. Если `balance <= 0`:
   - если `grace_started_at is None` → выставить `grace_started_at = now`, доступ пока активен, отправить «⚡ Баланс исчерпан, 24 часа на пополнение».
   - если `grace_started_at` уже стоит и прошло ≥24ч → отключить доступ в Remnawave, `access_active = False`.
4. При успешном пополнении баланса (вебхук ЮKassa) — если был `grace_started_at`, сбросить его в `None`; если `access_active=False`, включить доступ в Remnawave обратно и выставить `access_active = True`.

**Изменение количества устройств:** отдельный хендлер — пользователь выбирает `devices_limit` (например, 1-5), значение сохраняется сразу, без оплаты — влияет только на следующее суточное списание.

**Удаляются:** `Plan`, `Subscription` (модели, миграции, все хендлеры/клавиатуры/сервисы, завязанные на покупку тарифа — `order_confirm`, `confirm_pay`, `upgrade_to`, `confirm_upgrade` и связанный код в `bot/handlers/payment.py`, `bot/services/subscription.py`).

## 4. Реферальная система

- `ReferralTransaction`/`Withdrawal`/`WithdrawalProvider` (весь флоу вывода) — удаляются из моделей, хендлеров (`bot/handlers/referral.py`), сервисов (`bot/services/referral.py`), клавиатур, админки.
- Взамен: при первой успешной оплате (пополнении баланса) приглашённого пользователя — рефереру начисляется фиксированные `100₽` прямо на `balance`. Разовая операция — защищается флагом на пользователе (например, `User.referral_bonus_granted: Boolean`) или проверкой «это первый успешный `Payment` приглашённого».
- `REFERRAL_PERCENT` конфиг убирается (был % от суммы — больше не применим).

## 5. Сервер VPN

Код интеграции с Remnawave не меняется. В `.env` — новые `REMNAWAVE_URL`, `REMNAWAVE_API_TOKEN`, `SUBSCRIPTION_HOST` (передаются пользователем позже, при разворачивании нового сервера).

## 6. Telegram-бот

Новый бот создаётся пользователем через BotFather (в процессе). `BOT_TOKEN`/`BOT_USERNAME` добавятся в `.env`, когда бот будет готов.

## 7. Миграции БД

Одна новая ревизия Alembic на весь набор изменений (новый проект, чистая БД — не нужно несколько шагов ради продакшен-совместимости):
- Новые поля `User`: `balance`, `devices_limit`, `access_active`, `grace_started_at`, `referral_bonus_granted`.
- Новая таблица `app_settings` (или аналог) с `daily_rate_per_device`.
- `PaymentProvider` enum → `yookassa`.
- Упрощение `Payment`: убрать `plan_id`/`devices_count` как обязательные (или сделать nullable, раз старая схема покупки тарифов больше не действует).
- Дроп таблиц: `plans`, `subscriptions`, `withdrawals`, `referral_transactions`.

## 8. Тесты

- `tests/test_webhooks/test_yookassa_webhook.py` вместо `test_cryptobot_webhook.py`.
- Тесты сервисов `freekassa`/`lava`/`remnawave` (в части старой оплаты) — удаляются/переписываются под `yookassa`.
- Новые тесты: расчёт суточной ставки по формуле, сценарии планировщика (списание, предупреждение, грейс, отключение, восстановление после пополнения), реферальный бонус (разовость).

## Явные ограничения / что не входит

- Реальные креды (ЮKassa, Remnawave, BOT_TOKEN) — не часть кода, добавляются пользователем в `.env` при разворачивании.
- UI-редизайн ограничен текстами/эмодзи/брендингом — не меняется общая структура диалогов/меню бота (кроме того, что напрямую вытекает из смены модели Plan → баланс).
