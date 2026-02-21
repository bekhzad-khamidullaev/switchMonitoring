# SnmpSwitch -> switchMonitoring: план портирования

## Цель
Интегрировать полезные сценарии из `carlosjordao/SnmpSwitch` в текущую архитектуру `switchMonitoring` без регресса по безопасности, поддерживаемости и производительности.

Базовый принцип: **не переносить legacy-код 1:1**, а переносить поведение в текущий сервисный слой (`snmp/services/*`, `snmp/web/views/*`, `snmp/models.py`) на Django 4.2 + PySNMP.

## Статус внедрения (2026-02-21)
- [x] PR-1: vendor profile engine (factory + Huawei/H3C profiles + pipeline integration).
- [x] PR-2: LLDP сбор, синхронизация `DeviceNeighbor`, enrichment topology links.
- [x] PR-3: массовый запуск discovery/poll jobs через защищенный bulk endpoint + lock для discovery task.
- [x] PR-4: отчет по активности портов (`Port Activity Report`) с фильтрацией и пагинацией.

## Что уже покрыто в текущем проекте
- Современный discovery/polling слой:
  - `snmp/services/discovery/read_base_snmp.py`
  - `snmp/services/discovery/pipeline.py`
  - `snmp/services/polling/poller.py`
- Реестр метрик, binding и алертинг:
  - `snmp/services/metrics/runtime.py`
  - `snmp/services/alerting/evaluator.py`
- Топология соседей и UI dashboard:
  - `snmp/web/views/dashboard.py`
- Security baseline и prod-настройки уже выделены в `config/settings/*`.

## Что нужно забрать из SnmpSwitch (функциональные gap'ы)
1. Vendor-aware слой для SNMP-особенностей (Huawei/3Com/HP/D-Link/Extreme), как в `SwitchFactory` + `Switch*` классах.
2. Нормализацию VLAN/STP/PoE/LLDP/MAC-таблиц до единой модели порта.
3. Инвентаризационные отчеты уровня «что подключено к порту» (voip/wifi/printer/surveillance-аналог).
4. Массовый probe/update сценарий (безопасно, по очередям, с ограничением конкуренции).

## Не переносим напрямую
- Любые insecure-паттерны из legacy:
  - `eval()` из env
  - raw SQL с динамическим ORDER BY из запроса
  - незащищенные probe endpoints
  - hardcoded `SECRET_KEY`/`DEBUG=True`

## Целевая карта соответствий (Source -> Target)
- `netstatus/lib/switch/Switch.py` + subclasses -> `snmp/services/discovery/vendor_profiles/` (новый пакет)
- `netstatus/lib/switchfactory.py` -> `snmp/services/discovery/vendor_profiles/factory.py`
- `netstatus/lib/probe.py` -> `snmp/services/discovery/jobs.py` + Celery task в `snmp/tasks.py`
- `netstatus/views/status.py` (форматирование портов) -> вычисляемые DTO + Jinja context builders в `snmp/web/views/devices.py`
- `netstatus/views/reports.py` -> `snmp/web/views/exports.py` + агрегаты ORM
- `switches_neighbors` логика -> расширение `DeviceNeighbor` pipeline в `snmp/services/discovery/pipeline.py`

## Этапы внедрения

### Этап 1: Vendor profile engine (PR-1)
Объем:
- Добавить интерфейс vendor-профиля (`supports(sys_descr/sys_object_id)`, `collect_port_state(...)`, `collect_neighbors(...)`).
- Реализовать минимум 2 профиля: `Huawei`, `H3C/HP` (наиболее полезные для текущей базы).
- Подключить выбор профиля в discovery-пайплайн.

Файлы:
- `snmp/services/discovery/vendor_profiles/base.py` (new)
- `snmp/services/discovery/vendor_profiles/factory.py` (new)
- `snmp/services/discovery/vendor_profiles/huawei.py` (new)
- `snmp/services/discovery/vendor_profiles/h3c.py` (new)
- `snmp/services/discovery/pipeline.py` (update)

Критерии готовности:
- Discovery заполняет `DevicePort` полями VLAN/STP/PoE для поддержанных вендоров.
- Покрытие unit-тестами профилей (позитив/неподдержанный OID/timeout).

### Этап 2: LLDP + topology parity (PR-2)
Объем:
- Добавить сбор LLDP-таблиц на discovery.
- Обновлять `DeviceNeighbor` транзакционно и идемпотентно.
- Улучшить визуализацию линков на `neighbor_devices_map` (портовые подписи, статус).

Файлы:
- `snmp/services/discovery/read_base_snmp.py` (LLDP walk helpers)
- `snmp/services/discovery/pipeline.py` (neighbor sync)
- `snmp/web/views/dashboard.py` (расширенные link attributes)
- `snmp/templates/neighbor_devices_map.html` (легкий UI апдейт)

Критерии готовности:
- Для пары известных устройств карта показывает корректные `left_port/right_port`.
- Повторный discovery не создает дубликатов соседей.

### Этап 3: Probe jobs и массовое обновление (PR-3)
Объем:
- Реализовать безопасный запуск `discover/update inventory` для пачки устройств через Celery.
- Добавить rate-limit/concurrency guard (устройство + ATS/branch).
- Веб-эндпоинт только для авторизованных ролей, POST-only.

Файлы:
- `snmp/tasks.py` (new bulk tasks)
- `snmp/web/views/integrations.py` или `snmp/web/views/device_operations.py` (POST endpoints)
- `snmp/urls.py` (route)

Критерии готовности:
- Массовый запуск по branch не блокирует worker и не дублирует job.
- Есть audit-лог: кто запустил, сколько успешно/ошибок.

### Этап 4: Отчеты «что на порту» (PR-4)
Объем:
- Ввести обобщенную модель endpoint-классификации (voip/wifi/printer/camera) без жесткой привязки к legacy-таблицам.
- Построить отчеты по последнему местоположению MAC/IP (аналог `mat_listmachistory`).

Файлы:
- `snmp/models.py` (new inventory classification models)
- `snmp/web/views/metrics.py` или `snmp/web/views/exports.py` (report views)
- `snmp/templates/*` (табличные отчеты)

Критерии готовности:
- Отчет строится без raw SQL-инъекционных конструкций.
- Есть пагинация, фильтры, сортировка через whitelist.

## Security gate для каждого PR
- Только ORM/параметризованный SQL.
- Нет `eval/exec` для конфигурации.
- Закрытые mutation endpoints: `login_required + permission_required + require_POST`.
- Негативные тесты на доступ (403) и валидацию параметров.

## Тестовая стратегия
- Unit:
  - vendor profile parsers
  - OID mapping/normalization
  - topology link resolver
- Integration:
  - onboarding -> discovery -> ports/neighbors persisted
  - bulk probe task -> samples/events/logging
- Regression:
  - существующие `snmp/tests_*` не должны падать

## Порядок выполнения (рекомендуемый)
1. PR-1 (vendor profile engine)
2. PR-2 (LLDP/topology)
3. PR-3 (bulk probe jobs)
4. PR-4 (port reports)

## Оценка риска
- Высокий: vendor-specific OID вариативность -> закрывается профилями и fallback-стратегией.
- Средний: нагрузка на SNMP/worker при bulk jobs -> закрывается lock + chunking + retry budget.
- Средний: консистентность портов/соседей -> закрывается транзакциями и upsert-паттерном.

## Definition of Done
- Основные сценарии SnmpSwitch (vendor-aware ports, neighbors, probe/update, port-level visibility) реализованы в новой архитектуре.
- Нет возврата к небезопасным legacy-практикам.
- Все новые фичи покрыты тестами и включены в текущий CI-поток.
