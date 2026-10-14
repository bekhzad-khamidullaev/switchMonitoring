# switchMonitoring

Django-проект мониторинга сетевых устройств через SNMP.

## Структура

- [`config/`](config/)
- [`snmp/`](snmp/)
- [`static/`](static/)
- [`templates/`](templates/)
- [`theme/`](theme/)
- [`users/`](users/)

- [`AGENTS.md`](AGENTS.md)
- [`manage.py`](manage.py)
- [`requirements.txt`](requirements.txt)

## Локальная разработка

Создайте отдельное окружение и установите зависимости из репозитория:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

Точка входа — `manage.py`; модуль настроек по умолчанию — `config.settings`.

Перед запуском проверьте настройки базы данных и внешних сервисов. Используйте отдельную локальную базу и тестовые интеграции. После настройки окружения:

```sh
python manage.py check
python manage.py migrate
python manage.py runserver
```

## Состояние документации

Описание составлено по структуре основной ветки. Запуск, сборка и тесты в чистом окружении ещё не проверены. Производственный статус и поддерживаемые версии необходимо подтвердить владельцу проекта.

## Условия использования

Лицензия требует уточнения владельцем. Эта документация не меняет существующие права на код.
