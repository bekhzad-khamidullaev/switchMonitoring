# 🚀 SNMP Network Monitoring System - Production Overview

## 🎯 Система автоматического обнаружения и мониторинга сетевых устройств

### Ключевые возможности системы

#### 🔍 **Автоматическое обнаружение устройств**
- **Автоматическое определение вендора** через Enterprise OID и системное описание
- **Автоматическое определение модели** с использованием regex-паттернов
- **Поддержка MIB файлов** для точного определения OID'ов
- **Интеллектуальное обнаружение аплинков** на основе скорости и названий интерфейсов

#### 📊 **Мониторинг оптических сигналов**
- **Real-time мониторинг** RX/TX мощности на аплинках
- **Vendor-specific OID mapping** для точных измерений
- **Автоматическая конвертация значений** в dBm
- **Настраиваемые пороги** предупреждений и критических уровней

#### ⚡ **Производительность для продакшн сервера**
- **Параллельная обработка** до 50 устройств одновременно
- **Кэширование результатов** для быстрого отклика
- **Оптимизированные SQL запросы** с индексами
- **Graceful error handling** без остановки мониторинга

---

## 🏭 Архитектура продакшн системы

### Компоненты системы
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │    │   REST API      │    │   Admin Panel   │
│   (Django Views)│    │   (DRF)         │    │   (Django Admin)│
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────┬───────────────────────────────┘
                         │
┌─────────────────────────▼─────────────────────────┐
│                Service Layer                      │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │ DeviceDiscovery│ │ UplinkMonitor│ │ MibManager   ││
│  │ Service       │ │ Service      │ │ Service      ││
│  └───────────────┘ └──────────────┘ └──────────────┘│
└─────────────────────┬─────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────┐
│              Database Layer                   │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │ PostgreSQL  │ │   Redis     │ │  Files   │ │
│  │ (Primary DB)│ │ (Cache/Jobs)│ │ (MIBs)   │ │
│  └─────────────┘ └─────────────┘ └──────────┘ │
└───────────────────────────────────────────────┘
```

### Автоматические задачи (Celery)
```python
# Расписание продакшн задач
CELERY_BEAT_SCHEDULE = {
    'auto-discover-devices': {          # 02:30 ежедневно
        'task': 'auto_discover_devices_task',
        'schedule': crontab(minute=30, hour=2),
    },
    'monitor-all-uplinks': {            # Каждые 10 минут  
        'task': 'monitor_all_uplinks_task',
        'schedule': 600,
    },
    'comprehensive-health-check': {     # Каждые 4 часа
        'task': 'comprehensive_health_check_task', 
        'schedule': crontab(minute=0, hour='*/4'),
    },
}
```

---

## 🔧 Конфигурация для продакшн сервера

### Поддерживаемые вендоры
```python
SUPPORTED_VENDORS = {
    'cisco': {
        'enterprise_oid': '1.3.6.1.4.1.9',
        'optical_oids': {
            'rx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.5',
            'tx_power': '1.3.6.1.4.1.9.9.92.1.1.1.1.4',
        },
        'uplink_patterns': [r'gi\d+/0/\d+', r'te\d+/0/\d+'],
        'models': ['Catalyst', 'Nexus', 'ASR']
    },
    'huawei': {
        'enterprise_oid': '1.3.6.1.4.1.2011', 
        'optical_oids': {
            'rx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',
            'tx_power': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',
        },
        'uplink_patterns': [r'gi0/0/\d+', r'xe0/0/\d+'],
        'models': ['S5700', 'S6700', 'S9300']
    },
    'h3c': {
        'enterprise_oid': '1.3.6.1.4.1.25506',
        'optical_oids': {
            'rx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.2',
            'tx_power': '1.3.6.1.4.1.25506.8.35.18.4.3.1.3',
        },
        'uplink_patterns': [r'gi1/0/\d+', r'xe1/0/\d+'],
        'models': ['S5120', 'S5130', 'S6520']
    }
}
```

### MIB файлы структура
```
mibs/
├── cisco/
│   ├── CISCO-OPTICAL-MONITOR-MIB.mib
│   ├── CISCO-ENTITY-FRU-CONTROL-MIB.mib
│   └── CISCO-PRODUCTS-MIB.mib
├── huawei/
│   ├── HUAWEI-ENTITY-EXTENT-MIB.mib
│   ├── HUAWEI-OPTICAL-MIB.mib
│   └── HUAWEI-DEVICE-MIB.mib
├── h3c/
│   ├── H3C-TRANSCEIVER-INFO-MIB.mib
│   └── H3C-ENTITY-EXT-MIB.mib
└── standard/
    ├── IF-MIB.mib
    └── ENTITY-MIB.mib
```

---

## 📋 Management команды для продакшн

### Автоматическое обнаружение устройств
```bash
# Обнаружение всех устройств с мониторингом аплинков
python manage.py auto_discover_devices --update-existing --monitor-uplinks

# Обнаружение диапазона IP адресов
python manage.py auto_discover_devices --ip-range 192.168.1.0/24 --auto-assign-branch

# Параллельное обнаружение (быстрее для больших сетей)
python manage.py auto_discover_devices --parallel --max-workers 20

# Dry-run для тестирования без изменений
python manage.py auto_discover_devices --dry-run --verbose
```

### Мониторинг аплинков
```bash
# Мониторинг всех аплинков с алертами
python manage.py monitor_uplinks --parallel --send-alerts

# Непрерывный мониторинг каждые 5 минут
python manage.py monitor_uplinks --continuous --interval 300

# Мониторинг конкретного вендора
python manage.py monitor_uplinks --vendor cisco --critical-only

# Экспорт в JSON/CSV
python manage.py monitor_uplinks --output-format json --output-file uplinks.json
```

### Сбор метрик
```bash
# Сбор всех системных метрик
python manage.py collect_metrics --output json --file daily_metrics.json

# Мониторинг производительности
python manage.py collect_metrics --period 24 --output csv
```

---

## 🔧 API Endpoints для интеграции

### REST API для автоматизации
```python
# Автоматическое обнаружение через API
POST /api/v1/switches/123/discover_info/
{
    "update_model": true,
    "monitor_uplinks": true
}

# Мониторинг аплинков через API  
POST /api/v1/health-check/
{
    "switch_ids": [1, 2, 3],
    "monitor_uplinks": true,
    "send_alerts": true
}

# Получение информации об аплинках
GET /api/v1/switches/123/uplinks/
Response: {
    "uplinks": [
        {
            "port_index": 25,
            "port_name": "GigabitEthernet0/0/1",
            "speed": 1000000000,
            "rx_power": -12.5,
            "tx_power": -8.2,
            "status": "healthy"
        }
    ]
}

# Системные метрики
GET /api/v1/metrics/
Response: {
    "timestamp": "2024-01-15T10:30:00Z",
    "uplink_monitoring": {
        "total_uplinks": 150,
        "critical": 2,
        "warnings": 5,
        "healthy": 143
    }
}
```

---

## ⚙️ Настройки производительности

### Оптимизация для большого количества устройств
```python
# settings/production.py
SNMP_MONITORING_CONFIG = {
    'parallel_workers': 20,          # Параллельных воркеров
    'snmp_timeout': 5,               # SNMP таймаут (секунды)
    'snmp_retries': 2,               # Повторные попытки
    'discovery_interval': 3600,      # Интервал переобнаружения
    'uplink_monitoring_interval': 600, # Интервал мониторинга аплинков
    'cache_timeout': 1800,           # Кэширование результатов
    'batch_size': 50,                # Размер батча обработки
}

# Пороги для оптических сигналов
OPTICAL_SIGNAL_THRESHOLDS = {
    'rx_power': {
        'critical_low': -25.0,   # dBm
        'warning_low': -20.0,    # dBm  
        'warning_high': -8.0,    # dBm
        'critical_high': -3.0,   # dBm
    },
    'tx_power': {
        'critical_low': -25.0,
        'warning_low': -20.0, 
        'warning_high': -8.0,
        'critical_high': -3.0,
    }
}
```

### Мониторинг производительности системы
```bash
# Проверка состояния Celery задач
python manage.py shell -c "
from django.core.cache import cache
print('Task Health:', cache.get('celery_health_stats'))
print('Uplink Report:', cache.get('uplink_monitoring_report'))
print('Auto Discovery:', cache.get('auto_discovery_stats'))
"

# Статистика базы данных
python manage.py dbshell -c "
SELECT 
    COUNT(*) as total_switches,
    COUNT(CASE WHEN status = true THEN 1 END) as online,
    COUNT(CASE WHEN model_id IS NOT NULL THEN 1 END) as with_models
FROM switches;
"
```

---

## 🚨 Алертинг и уведомления

### Email уведомления
```python
# Настройка алертов в .env
ALERT_EMAIL_RECIPIENTS=admin@company.com,netops@company.com
EMAIL_HOST=smtp.company.com
EMAIL_HOST_USER=snmp-alerts@company.com

# Типы алертов
ALERT_TYPES = {
    'device_offline': 'Устройство недоступно',
    'optical_signal_critical': 'Критический уровень оптического сигнала',  
    'optical_signal_warning': 'Предупреждение об уровне сигнала',
    'uplink_down': 'Аплинк интерфейс недоступен',
    'discovery_failed': 'Ошибка автообнаружения',
    'snmp_timeout': 'Таймаут SNMP запроса'
}
```

### Пример алерта
```
Subject: [SNMP Monitor] Uplink Alert - 3 Critical, 7 Warnings

Uplink Monitoring Alert Report  
Timestamp: 2024-01-15T14:30:00Z

Summary:
- Total uplinks monitored: 156
- Critical issues: 3
- Warning issues: 7  
- Switches affected: 8

CRITICAL ISSUES:
- SW-CORE-01 (10.0.1.1) - Port Gi0/0/1: Critical low RX power: -26.2 dBm
- SW-DIST-03 (10.0.2.3) - Port Te0/0/2: Interface operationally down
- SW-ACC-15 (10.0.5.15) - Port Gi1/0/1: Critical high TX power: -2.1 dBm
```

---

## 📊 Dashboard и отчетность

### Real-time мониторинг
- **Системная панель**: `/snmp/monitoring/`
- **Метрики производительности**: `/snmp/metrics/`
- **Health check интерфейс**: `/snmp/health-check/`
- **Экспорт отчетов**: CSV, JSON, Excel форматы

### Ключевые метрики
- Общее количество устройств и их статус
- Количество активных аплинков и их состояние  
- Статистика оптических сигналов по порогам
- История изменений и трендов
- Производительность системы мониторинга

---

## 🔐 Безопасность в продакшн

### SNMP Security
```python
# Рекомендуемые настройки SNMP
SNMP_SECURITY = {
    'default_community_ro': 'monitoring_readonly',  # Изменить стандартные
    'timeout': 5,
    'retries': 2,
    'allowed_networks': ['10.0.0.0/8', '192.168.0.0/16'],  # Ограничить сети
    'rate_limiting': True,
    'connection_pooling': True,
}
```

### Системная безопасность
- Firewall правила для SNMP (161/UDP)
- Isolated VLAN для monitoring traffic
- Encrypted storage для community strings
- Regular security audits
- Access logging и monitoring

---

## 📈 Масштабирование

### Горизонтальное масштабирование
```python
# Конфигурация для больших сетей (1000+ устройств)
SCALING_CONFIG = {
    'celery_workers': 10,           # Увеличить воркеров
    'redis_instances': 2,           # Несколько Redis инстансов  
    'database_connections': 50,     # Пул соединений
    'snmp_parallel_limit': 100,     # Параллельные SNMP запросы
    'batch_processing': True,       # Батчевая обработка
    'geographic_distribution': True, # Географическое распределение
}
```

### Мониторинг производительности
- Response time для SNMP запросов
- Database query performance  
- Memory usage мониторинг
- Network bandwidth utilization
- Error rate tracking

---

## 🎯 Результат

✅ **Полностью автоматизированная система** обнаружения и мониторинга  
✅ **Продакшн-готовая архитектура** с error handling и масштабированием  
✅ **Vendor-agnostic подход** с поддержкой MIB файлов  
✅ **Real-time мониторинг** аплинков и оптических сигналов  
✅ **Comprehensive alerting** система с email уведомлениями  
✅ **REST API** для интеграции с другими системами  
✅ **Performance optimized** для больших корпоративных сетей  

Система готова к развертыванию в продакшн среде и может масштабироваться для мониторинга тысяч сетевых устройств с автоматическим обнаружением и continuous monitoring аплинков.