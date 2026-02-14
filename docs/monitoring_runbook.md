# Runbook: Optical Monitoring Duty

## 1) SNMP timeouts spike
1. Проверить `/healthz/` и `/metrics/app/`.
2. Если `redis`/`celery` degraded, восстановить broker/worker в первую очередь.
3. Проверить доступность устройства (`ping`, ACL, SNMP community).
4. Временно увеличить `SNMP_DEFAULT_TIMEOUT` и/или `retries` для проблемной группы устройств.
5. Перезапустить poller only после устранения сетевой причины.

## 2) Duplicate polling jobs
1. Проверить логи `poll skipped because lock is active`.
2. Убедиться, что cache backend общий для всех воркеров (Redis, не local-memory).
3. Проверить расписание Celery beat: нет ли дублирующихся задач с одинаковой целью.
4. Уменьшить частоту запуска для конфликтующих профилей устройств.

## 3) Error rate growth
1. Проверить `snmp_errors_total` и queue depth в `/metrics/app/`.
2. Сегментировать ошибки: auth, timeout, OID not found, parser failures.
3. Для массовых `OID not found` отключить проблемный binding через UI метрик.
4. Для auth-ошибок сверить `SNMP_DEFAULT_COMMUNITY_RO` и профиль устройства.
5. Если ошибки >30 минут, перевести устройство в degraded и открыть инцидент.

## 4) Safe rollback
1. Остановить новые polling jobs (pause beat schedule).
2. Отключить новые binding/subscription через UI.
3. Вернуть предыдущую стабильную версию кода.
4. Проверить `healthz` и целостность записи `MetricSample`.
5. Возобновить polling поэтапно (по филиалам/группам).
