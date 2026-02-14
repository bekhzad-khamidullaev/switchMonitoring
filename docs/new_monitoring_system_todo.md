# TODO: Новая система мониторинга оптического сигнала

## 0. Организация и безопасность (обязательный старт)
- [x] Создать `.env.example` с обязательными переменными (`DJANGO_SECRET_KEY`, `DB_*`, `REDIS_URL`, `SNMP_DEFAULT_TIMEOUT`, `ZABBIX_*`).
- [x] Удалить секреты из кода и перевести чтение в `os.getenv`.
- [x] Добавить проверку старта приложения: падать с явной ошибкой при отсутствии критичных переменных.
- [x] Разделить настройки на `config/settings/base.py`, `dev.py`, `prod.py`.
- [x] В `prod.py` включить безопасные флаги (`DEBUG=False`, `SECURE_*`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE`).
- [x] Добавить `pre-commit` (ruff/black/isort, базовые security checks).

## 1. Целевая модель данных (MVP)
- [x] Создать модель `Device` (ip, hostname, vendor, model, firmware, sys_object_id, snmp_version, auth_profile, status).
- [x] Создать модель `DeviceProfile` (vendor, model_pattern, firmware_pattern, priority, active).
- [x] Создать модель `MetricDefinition` (key, title, description, unit, value_type, default_interval_sec).
- [x] Создать модель `MetricBinding` (profile -> metric, oid_template, index_strategy, converter, scale, enabled_by_default).
- [x] Создать модель `Interface` (device, if_index, if_name, if_alias, if_type, is_optical, admin_up).
- [x] Создать модель `MetricSubscription` (device/interface + metric, enabled, warn_threshold, crit_threshold, poll_interval_sec).
- [x] Создать модель `MetricSample` (subscription, ts, value_float/value_text, quality, raw_value).
- [x] Создать миграции и проверить `makemigrations/migrate` на чистой БД.

## 2. Discovery-пайплайн устройства
- [x] Реализовать сервис `discovery/read_base_snmp.py` (sysObjectID, sysDescr, ifTable).
- [x] Реализовать нормализацию `vendor/model` из sysDescr + sysObjectID.
- [x] Реализовать матчинг `DeviceProfile` по приоритету.
- [x] Реализовать детект оптических портов (`ifType`, vendor OID hints, DOM support).
- [x] Сохранять/обновлять `Interface` в транзакции.
- [x] Логировать результат discovery в структурированном виде (device_id, profile_id, interfaces_count, warnings).

## 3. Реестр метрик и OID-логика
- [x] Убрать `if/elif` по моделям из runtime-кода в пользу таблицы `MetricBinding`.
- [x] Добавить поддержку шаблонов OID (пример: `{if_index}`).
- [x] Добавить стратегии индексации (`if_index`, `fixed`, `vendor_map`).
- [x] Реализовать конвертеры (`identity`, `div100`, `div1000`, `mw_to_dbm`, `enum_map`).
- [x] Реализовать валидацию границ значений (например, отсечь технический мусор `-65535`).

## 4. Импорт MIB в каталог метрик
- [x] Создать management command `import_mibs`.
- [x] Добавить чтение MIB из указанной директории и сбор числовых OID.
- [x] Добавить dry-run режим (`--dry-run`) и отчёт по потенциальным новым метрикам.
- [x] Добавить маппинг MIB-символов -> `MetricDefinition`.
- [x] Добавить ручное подтверждение конфликтов (один символ = несколько OID).
- [x] Сохранить кеш разобранных MIB для ускорения повторного запуска.

## 5. UI для ручного включения метрик админом
- [x] Страница устройства: блок "Обнаруженные метрики".
- [x] Чекбоксы включения/выключения метрик per-device и per-interface.
- [x] Кнопка "Применить шаблон" (например, включить все optical RX/TX).
- [x] Поля порогов warning/critical и интервала polling.
- [x] Валидация формы: `critical` не может быть выше/ниже `warning` (по типу метрики).
- [x] Массовые операции по интерфейсам (выделить несколько и применить одинаковые настройки).

## 6. Polling-движок
- [x] Создать Celery task `poll_device_metrics(device_id)`.
- [x] Для одного устройства собирать все активные `MetricSubscription`.
- [x] Группировать запросы по OID и делать батч через GETBULK/GETNEXT где возможно.
- [x] Реализовать retry + exponential backoff + timeout.
- [x] Сохранять `MetricSample` пакетно (`bulk_create`) для снижения нагрузки на БД.
- [x] Добавить idempotency guard (чтобы один и тот же job не запускался параллельно для устройства).

## 7. Алертинг и правила
- [x] Модель `AlertRule` (scope: subscription/device/profile, severity, condition, hysteresis).
- [x] Модель `AlertEvent` (opened_at, closed_at, state, last_value).
- [x] Реализовать проверку порогов при записи `MetricSample`.
- [x] Добавить anti-flap логику (минимальная длительность/кол-во срабатываний).
- [x] Добавить каналы уведомлений (пока: email/telegram webhook).

## 8. API и интеграции
- [x] DRF endpoint: `POST /api/devices/onboard`.
- [x] DRF endpoint: `POST /api/devices/{id}/discover`.
- [x] DRF endpoint: `GET /api/devices/{id}/metrics`.
- [x] DRF endpoint: `PATCH /api/subscriptions/{id}`.
- [x] DRF endpoint: `GET /api/devices/{id}/timeseries?metric=rx_power_dbm&if_index=...`.
- [x] Права доступа: только авторизованные + объектные права по филиалам.

## 9. Тестирование (обязательный минимум)
- [x] Unit tests для discovery-парсера (vendor/model match).
- [x] Unit tests для всех конвертеров значений.
- [x] Unit tests для генерации OID из шаблонов.
- [x] Integration tests: onboarding -> discovery -> subscribe -> polling -> sample.
- [x] Integration tests для permission boundary по филиалам.
- [x] Нагрузочный тест polling на N устройств (в тестовой среде).

## 10. Наблюдаемость и эксплуатация
- [x] Добавить structured logging (json формат).
- [x] Добавить метрики приложения (время polling, ошибки SNMP, длина очередей Celery).
- [x] Добавить health-check endpoint (DB, Redis, Celery ping).
- [x] Добавить runbook для дежурного администратора (что делать при таймаутах, дубли задач, рост ошибок).

## 11. Поэтапный релиз
- [x] Этап 1 (MVP): onboarding + discovery + ручное включение + polling RX/TX + базовые графики.
- [x] Этап 2: импорт MIB, расширенный каталог метрик, пороги и алерты.
- [x] Этап 3: оптимизация polling, массовые операции, отчёты и экспорт.
- [x] Этап 4: миграция старого кода на новый реестр метрик и удаление legacy-веток.

## Definition of Done (для MVP)
- [x] Для нового устройства система определяет профиль и порты без ручного редактирования OID.
- [x] Админ за 2-3 клика включает нужные метрики на выбранных интерфейсах.
- [x] Значения RX/TX корректно нормализуются и видны в истории.
- [x] Ошибки SNMP не ломают очередь и не создают бесконечные ретраи.
- [x] Покрытие тестами критичного пути не ниже 70%.
