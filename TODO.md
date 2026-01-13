# TODO: довести проект до полноценного корпоративного мониторинга (оптика/доступность/полоса)

## 0) Короткий аудит текущего состояния (что уже есть)

### Что уже реализовано
- Django-проект + приложение `snmp`.
- Базовая инвентаризация устройств в таблице `Switch`:
  - `hostname`, `ip`, `status` (через ICMP), `uptime` и `model` (частично через `sysDescr`).
  - глобальные поля `rx_signal/tx_signal/sfp_vendor/part_number` (но это по сути «одна точка», без привязки к интерфейсу).
- Таблица портов `SwitchesPorts` с полями для:
  - описаний/состояний (`admin/oper/speed/alias/name`),
  - счётчиков (`oct_in/oct_out`, discards, lastchange),
  - оптики (`rx_signal/tx_signal`, `sfp_vendor`, `part_number`).
- Периодические задачи Celery beat:
  - `update_switch_status` (каждые 5 мин)
  - `update_optical_info` (каждые 4 часа)
  - `update_switch_inventory` (ежедневно)
  - `subnet_discovery` (ежедневно)
- Несколько подходов к сбору оптики:
  - `update_optical_info.py` / `update_optical_info_async.py`: «хардкод» OID’ов по модели.
  - `update_optical_info_mib.py`: попытка перейти на MIB/IF-MIB/ENTITY-MIB/ENTITY-SENSOR-MIB, с авто-выбором оптических интерфейсов и маппингом ifIndex→entPhysical.
- Отчёт (Excel) по устройствам с высоким RX (по полю `Switch.rx_signal`).

### Главные разрывы/проблемы
1. **Оптика сейчас хранится “на устройстве” (`Switch.rx_signal/tx_signal`)**, а не на портах (хотя в `SwitchesPorts` поля есть). Это мешает:
   - мониторингу именно оптических интерфейсов,
   - отчётам по портам/клиентским линкам,
   - хранению истории и алёртам по конкретному интерфейсу.
2. `update_optical_info_mib.py` ожидает поля в `SwitchModel` (например `required_mibs`, `rx_power_object`, `ddm_index_type`, `power_unit` и т.д.), **которых нет в текущей модели `SwitchModel`**. Т.е. фундамент под MIB-подход не доведён.
3. **Нет чёткого детекта типа устройства** (switch/OLT/MSAN/маршрутизатор и т.п.). Сейчас всё кладётся в `Switch`.
4. Нет единого слоя “device discovery” (sysObjectID/sysDescr/entPhysical) и нормализованного каталога моделей/вендоров.
5. В проекте **нет системы исключения виртуальных интерфейсов** (Loopback, VLAN, Bridge, Tunnel, CPU, Null, Stack, Port-channel/LAG, etc.) как общей политики для всех типов мониторинга.
6. **Мониторинг пропускной способности** на фундаментальном уровне отсутствует как метрика/временной ряд:
   - есть поля `oct_in/oct_out`, но нет нормальной модели хранения истории и расчёта bps/Util%.
7. Нет отчетов:
   - по доступности (SLA/uptime %, MTTR/MTBF),
   - по сигналам (распределения, мин/макс/перцентили, деградация),
   - по загрузке интерфейсов (95-й перцентиль, топ-N, перегруз).
8. Масштабирование:
   - текущая схема polling’а ориентирована на «один процесс» и линейный опрос.
   - нет шардирования по регионам/корпорации, нет очередей per-region/per-site, нет лимитов/квот.

---

## 1) Целевая архитектура (фундамент под корпорацию/регионы)

### 1.1. Модель данных (нормализация)
- [ ] Ввести универсальную сущность **`Device`** (вместо `Switch` как общего контейнера):
  - `id`, `hostname`, `mgmt_ip`, `snmp_profile`, `site/region`, `vendor`, `model`, `device_type`, `sysObjectID`, `sysDescr`, `serial`, `sw_version`, `last_seen`, `status`.
- [ ] Перенести/переименовать `Switch` → `Device` (или оставить `Switch` как legacy и постепенно мигрировать).
- [ ] Ввести `DeviceType` (enum/таблица): `SWITCH`, `OLT`, `MSAN`, `ROUTER`, `FIREWALL`, `WIFI`, `UNKNOWN`.
- [ ] Ввести `Interface` (вместо `SwitchesPorts` или эволюция текущей модели):
  - ключ: (`device`, `ifIndex`) + поля: `ifName/ifDescr/ifAlias`, `ifType`, `admin/oper`, `speed`, `is_virtual`, `is_optical_candidate`, `is_optical`, `parent_ifIndex` (если нужно).
  - обязательно: `unique_together(device, ifIndex)`.
- [ ] Ввести модели временных рядов (минимум):
  - `InterfaceCountersSample` (octets, discards, errors) с `ts`.
  - `InterfaceOpticalSample` (rx/tx dBm, temperature, voltage, vendor/part/serial если надо) с `ts`.
  - **Рекомендация**: для корп. масштаба лучше TimescaleDB/ClickHouse/Prometheus-remote-write, но на старте можно PostgreSQL + партиционирование.
- [ ] Ввести сущности для иерархии корпорации:
  - `Region` → `Branch`/`Division` → `Site` (ATS) → `Device`.
  - Сейчас `Ats` и `Branch` уже есть, но нужна строгая модель и индексы.

### 1.2. Каталог вендоров/моделей и SNMP capabilities
- [ ] Расширить `SwitchModel` (или новую `DeviceModel`) до **capabilities-driven** подхода:
  - `vendor`, `model_name`, `sysObjectID_patterns`, `sysDescr_patterns`.
  - SNMP-конфигурация чтения оптики по MIB:
    - `required_mibs` (csv)
    - `ddm_index_type` (`ifIndex`/`entPhysicalIndex`/vendor-specific)
    - символические объекты: `rx_power_object`, `tx_power_object`, `temperature_object`, `voltage_object`, `sfp_vendor_object`, `part_num_object`, `serial_num_object`
    - единицы/скейлы: `power_unit` (`dbm/mw/scaled_*`), `temperature_unit`.
  - SNMP-конфигурация интерфейсов:
    - правила исключения виртуальных (`exclude_ifType`, `exclude_name_regex`, `exclude_descr_regex`).
  - (опционально) vendor OID fallback, если MIB недоступны.

---

## 2) Автоопределение: вендор, модель, тип устройства, оптические порты

### 2.1. Discovery pipeline (один источник правды)
- [ ] Реализовать единый процесс `device_discovery`:
  1) SNMP GET: `sysObjectID.0`, `sysDescr.0`, `sysName.0`, `sysUpTime.0`.
  2) ENTITY-MIB: `entPhysicalTable` (модель/серийник/класс) при наличии.
  3) По правилам (patterns) матчить `vendor/model/device_type`.
  4) Заполнять `Device.vendor/model/device_type/sysObjectID/sysDescr/...`.
- [ ] На discovery завязать выбор метода опроса оптики (MIB vs fallback OID).

### 2.2. Определение «виртуальный интерфейс» (единая политика)
Во всех мониторингах (оптика/полоса/состояние интерфейса) нужно отсекать виртуальные интерфейсы.
- [ ] Ввести функцию/сервис `is_virtual_interface(ifType, ifName, ifDescr, ifAlias)`:
  - исключать типы и имена: `loopback`, `vlan`, `bridge`, `tunnel`, `ppp`, `hdlc`, `mpls`, `l2vlan`, `l3vlan`, `virtual`, `cpu`, `null`, `stack`, `port-channel`, `bond`, `lag`, `ae`, `po`, `lo`, `vl` и т.п.
  - исключать интерфейсы с `ifType` != физических классов (по списку).
- [ ] Хранить флаг `Interface.is_virtual` + причину классификации (для отладки).

### 2.3. Автоопределение оптических портов
- [ ] Использовать комбинацию:
  - `ifType` (набор потенциально оптических),
  - `ifHighSpeed/ifSpeed` (>=1G как эвристика),
  - ключевые слова в `ifName/ifDescr` (`sfp`, `qsfp`, `xg`, `fiber`, `optic`, `pon`, `gpon`, `epon`),
  - ENTITY-MIB маппинг на entPhysicalClass=port.
- [ ] Для OLT/MSAN: отдельные правила классификации (GPON/EPON PON/UNI/NNI) и нормализация имён.

---

## 3) Мониторинг оптики (DDM/DOM) на оптических интерфейсах

### 3.1. Привести `update_optical_info_mib.py` в рабочее состояние
- [ ] Синхронизировать модель `SwitchModel` с тем, что использует `update_optical_info_mib.py`:
  - добавить нужные поля (см. раздел 1.2) + миграции.
- [ ] Сделать `update_optical_info_mib` основным сборщиком оптики по интерфейсам.
- [ ] Обеспечить запись в `SwitchesPorts`/`Interface` **строго по ifIndex**.
- [ ] Разделить понятия:
  - «инвентарь интерфейса» (описание, скорость, alias) — редкий опрос;
  - «метрики оптики» — частый опрос;
  - «счётчики трафика» — частый опрос.
- [ ] Добавить обработку отрицательных/инвалидных значений, `NoSuchInstance`, пустых данных.

### 3.2. История сигналов
- [ ] Добавить хранение истории `InterfaceOpticalSample` (rx/tx dBm + ts).
- [ ] Сформировать политику retention:
  - raw: 7–30 дней, 
  - агрегации (час/день) 1–2 года.

### 3.3. Пороговые события и алёрты (в будущем)
- [ ] Конфиг порогов на уровне модели/типа порта/региона:
  - критические пороги RX/TX (например: RX < -27 dBm, warning -25 dBm).
- [ ] Генерация событий деградации (падение на X dB за Y часов).

---

## 4) Мониторинг доступности (host availability)

- [ ] Уйти от «только ICMP» к многометодному:
  - ICMP ping
  - SNMP reachability (GET sysUpTime)
  - (опционально) TCP connect (22/161/443)
- [ ] Хранить историю доступности:
  - `DeviceAvailabilitySample(ts, is_up, rtt_ms, method)`
- [ ] Расчёт SLA по периодам (день/неделя/месяц) для корпорации/региона/ATS.

---

## 5) Мониторинг пропускной способности (utilization)

- [ ] Опрашивать `IF-MIB::ifHCInOctets/ifHCOutOctets` (приоритет) и fallback на `ifInOctets/ifOutOctets`.
- [ ] Вычислять bps по дельте и времени, сохранять `InterfaceCountersSample`.
- [ ] Учитывать:
  - rollover 32-bit,
  - reset счётчиков,
  - интерфейсы down/admin down,
  - не учитывать `is_virtual=True`.
- [ ] Отчёты:
  - top-N по загрузке,
  - 95-й перцентиль,
  - порты с постоянной перегрузкой.

---

## 6) Отчёты (разные типы)

### 6.1. Отчёт по доступности
- [ ] “Uptime %” по:
  - корпорации → регион → филиал → ATS → устройство.
- [ ] Список самых проблемных устройств (по downtime).

### 6.2. Отчёт по уровням оптики
- [ ] По всем оптическим портам:
  - текущий RX/TX,
  - min/avg/max за период,
  - количество событий ниже порога.
- [ ] Отдельно для uplink’ов/транзитов/клиентских портов (если есть классификация).

### 6.3. Отчёт по пропускной способности
- [ ] По портам/устройствам:
  - avg/max, 95p,
  - время перегруза,
  - таблицы и экспорт в Excel/CSV.

---

## 7) Масштабирование и надежность (корпоративный уровень)

- [ ] Перейти к архитектуре «polling workers»:
  - отдельная очередь Celery на регион (`polling:region:<id>`) или shard.
  - лимиты параллельности per-site/per-vendor (чтобы не убивать SNMP).
- [ ] Разделить джобы:
  - discovery (редко)
  - inventory интерфейсов (редко)
  - availability (часто)
  - optical (средне)
  - counters (часто)
- [ ] Ввести `SNMPProfile`:
  - community/v3 creds, timeout/retries, max_oids_per_request.
- [ ] Наблюдаемость самого polling:
  - метрики времени опроса, ошибок, таймаутов.

---

## 8) Безопасность и качество кода
- [ ] Убрать секреты из кода (`zabbix_token` в `snmp/views/requests_views.py`) → env vars/Secret Manager.
- [ ] Централизовать SNMP-операции в сервисном слое (`snmp/services/`) и убрать дублирование.
- [ ] Добавить тесты:
  - unit-тесты классификации виртуальных интерфейсов,
  - тесты парсинга SNMP значений и конвертаций dBm,
  - интеграционные тесты на запись в БД (с моками).

---

## 9) Конкретные ближайшие шаги (MVP по оптике на портах)

1) **Данные/модели**
- [ ] Доработать `SwitchModel` (или `DeviceModel`) под MIB-подход (поля из `update_optical_info_mib.py`).
- [ ] Миграции + заполнение конфигов для 2–3 основных моделей.

2) **Оптика по портам**
- [ ] Сделать команду `update_optical_info_mib` рабочей “из коробки” на этих моделях.
- [ ] Запись в `SwitchesPorts` по ifIndex.
- [ ] Включить фильтрацию виртуальных интерфейсов.

3) **Отчёт по портам**
- [ ] Добавить экспорт в Excel по оптическим портам (не по `Switch.rx_signal`).

4) **Пропускная способность (минимум)**
- [ ] Сбор `ifHC*Octets` и расчёт bps, хотя бы без длительного хранения (пока в БД с retention 7 дней).

---

## Примечания по текущему коду (на что обратить внимание при рефакторинге)
- `config/celery.py` содержит задачу `snmp.tasks.update_switch_data_task`, которой нет (в `snmp/tasks.py` другие имена). Это нужно синхронизировать.
- `update_optical_info.py` и `update_optical_info_async.py` — хардкод OID’ов по моделям; сохранить только как fallback.
- `update_optical_info_mib.py` — лучший фундамент под автоопределение оптических портов и масштабируемость, но требует довести модель `SwitchModel` и политику фильтрации виртуальных интерфейсов.
