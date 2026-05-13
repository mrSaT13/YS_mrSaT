# Matrix Bot - требуемые зависимости

## Установка Matrix библиотеки

Matrix бот требует установку клиента Matrix. Выберите один из вариантов:

### Вариант 1: Через pip (рекомендуется)

```bash
# Для Linux (SSH доступ к серверу Home Assistant)
pip install matrix-client

# Или более современная библиотека
pip install nio
```

### Вариант 2: Через Home Assistant

Если у вас есть доступ через SSH:

```bash
# Войти в контейнер Home Assistant (если используется Docker)
docker exec -it homeassistant bash

# Установить библиотеку
pip install matrix-client
```

### Вариант 3: Встроенный Python Home Assistant

```bash
# Найти путь к Python Home Assistant
python3 -m site

# Установить пакет в этот Python
/usr/local/bin/python3 -m pip install matrix-client
```

## Проверка установки

После установки проверьте что все работает:

```python
# В Python консоли
python3
>>> import nio
>>> print(nio.__version__)
```

Если ошибка ImportError - библиотека не установлена, повторите установку.

## Альтернативные матрикс библиотеки

Если `matrix-client` не работает, попробуйте:

```bash
# Более новая библиотека nio (рекомендуется)
pip install matrix-nio

# Или старая, но стабильная
pip install matrix-client-0.0.6
```

## Поиск и решение проблем

### Ошибка "ModuleNotFoundError: No module named 'nio'"

```bash
# Переустановите библиотеку
pip uninstall matrix-nio
pip install matrix-nio --upgrade
```

### Конфликты версий

```bash
# Очистить кэш pip
pip cache purge

# Переустановить все Matrix зависимости
pip install --upgrade matrix-nio requests aiohttp
```

### Проверка в Home Assistant

Если библиотека установлена но не работает в HA, проверьте:

1. Перезагрузить Home Assistant: Settings → System → Restart
2. Проверить логи: Settings → System → Logs
3. Включить debug логирование:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.yandex_station.hass.matrix_bot: debug
```

## Docker (Home Assistant в Docker)

Если используется Docker контейнер Home Assistant:

```bash
# Добавить в Dockerfile
RUN pip install matrix-nio

# Или создать requirements.txt
echo "matrix-nio" >> requirements.txt

# Пересобрать контейнер
docker build -t homeassistant .
```

## Home Assistant OS (с использованием Terminal addon)

1. Установить Terminal add-on (если еще нет)
2. Запустить Terminal
3. Выполнить:

```bash
apk add --no-cache python3-dev
pip install matrix-nio
```

## Требуемые версии Python

- Python 3.9+ (рекомендуется 3.11+)
- Home Assistant 2023.10+

## Проверка совместимости

```python
import sys
print(f"Python версия: {sys.version}")

# Должно быть 3.9 или выше
assert sys.version_info >= (3, 9), "Python 3.9+ требуется"
```

## Дополнительные зависимости

Matrix клиент может потребовать:

```bash
# Криптография для end-to-end encryption
pip install matrix-nio[e2e]

# Для всех опциональных зависимостей
pip install matrix-nio[all]
```

## Где найти помощь

- [Matrix Python SDK](https://github.com/matrix-org/matrix-python-sdk)
- [nio документация](https://matrix-nio.readthedocs.io/)
- [Home Assistant официальная документация](https://www.home-assistant.io/)

## Успешная установка

После установки вы должны увидеть в логах:

```
✅ Matrix bot интеграция инициализирована
🤖 Matrix бот инициализирован: https://matrix.org
```
