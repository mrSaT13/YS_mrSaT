# 🤖 Matrix Bot для Yandex Station - Полное руководство

## 📋 Что это такое?

Интеграция, которая позволяет общаться с Яндекс Алисой через Matrix чат! Напишите сообщение в Matrix - Алиса поймет и ответит вам.

## ✨ Возможности

- 💬 Диалог с Алисой в Matrix
- 🎵 Управление музыкой на станции
- 🏠 Управление умным домом
- 🌤️ Запрос информации (погода, новости)
- 🎮 Игры и развлечения
- ⚡ Автоматизация через Home Assistant
- 📱 Работает в любом Matrix клиенте (Element, FluffyChat и др.)

## 🚀 Быстрый старт (5 минут)

### 1. Установить зависимости

```bash
pip install matrix-nio
```

[Подробнее про установку](MATRIX_DEPS.md)

### 2. Создать Matrix бота

В Element (или другом Matrix клиенте):
- Создайте новый аккаунт для бота (например, `alice_bot`)
- Запомните:
  - Server URL: `https://matrix.org` (или ваш сервер)
  - Access Token: [получить в settings](MATRIX_BOT.md#получить-access-token)
  - Room ID: [комната для бота](MATRIX_BOT.md#создать-matrix-комнату)

### 3. Добавить в Home Assistant

Settings → Devices & Services → Create Integration → Yandex Station → Options → Matrix Bot

Заполните:
- **Server URL**: `https://matrix.org`
- **Room ID**: `!abc123:matrix.org`
- **Access Token**: `syt_...`

### 4. Создать Automation

Копируйте из [MATRIX_AUTOMATIONS.md](MATRIX_AUTOMATIONS.md) нужный пример

### 5. Готово!

Напишите в Matrix комнате - Алиса ответит! 🎉

## 📚 Документация

- **[MATRIX_BOT.md](MATRIX_BOT.md)** - Полное руководство по настройке
- **[MATRIX_AUTOMATIONS.md](MATRIX_AUTOMATIONS.md)** - Примеры automations
- **[MATRIX_DEPS.md](MATRIX_DEPS.md)** - Установка зависимостей

## 🎯 Примеры использования

### Просто поговорить с Алисой

```
Ты: "Включи песню Imagine"
Алиса: "Включаю John Lennon - Imagine"

Ты: "Какая сейчас температура?"
Алиса: "Сейчас за окном -5 градусов"

Ты: "Расскажи шутку"
Алиса: "Почему программист вышел из ванны?
         Потому что там была ошибка 404!"
```

### Команды управления

```
/play              - включить музыку
/pause             - пауза
/next              - следующий трек
/prev              - предыдущий трек
/status            - текущий статус
/light on          - включить свет
/light off         - выключить свет
/game города       - поиграть в города
```

### Умное домашнее управление

```
Ты: "Выключи свет в спальне"
Алиса: "Свет в спальне выключен"

Ты: "Включи кондиционер на 22 градуса"
Алиса: "Кондиционер включен на 22 градуса"

Ты: "Какая температура на кухне?"
Алиса: "На кухне 21 градус"
```

## 🔧 Архитектура

```
Matrix Chat
    ↓
Matrix Sync (nio library)
    ↓
Home Assistant Event Bus
    ↓
Automation (conversation.process)
    ↓
Yandex Alice (local Glagol protocol)
    ↓
Media Player / Smart Home
```

## ⚙️ Конфигурация

### Минимальная (без UI)

```yaml
# configuration.yaml
yandex_station:
  matrix_bot:
    server_url: "https://matrix.org"
    room_id: "!abc123:matrix.org"
    access_token: "syt_..."
```

### С автоматизацией

```yaml
# configuration.yaml
automation: !include_dir_merge_list automation/

# automation/matrix.yaml
- id: "matrix_alice"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  action:
    - service: conversation.process
      data:
        agent_id: conversation.yandex_station_mini
        text: "{{ trigger.event.data.text }}"
        conversation_id: "{{ trigger.event.data.room_id }}"
      response_variable: response
    
    - service: yandex_station.matrix_send_message
      data:
        message: "{{ response.response.speech.plain.speech }}"
```

## 🐛 Отладка

### Включить debug логирование

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.yandex_station.hass.matrix_bot: debug
```

### Проверить подключение

```bash
# SSH на сервер
ssh user@home-assistant

# Проверить Matrix клиент
python3 -c "import nio; print(nio.__version__)"

# Проверить логи
tail -f /config/home-assistant.log | grep -i matrix
```

## ❓ FAQ

### Q: Нужен ли интернет?
**A:** Да, нужен доступ к Matrix серверу (https://matrix.org или локальный Synapse). Home Assistant не обязательно должен быть доступен из интернета.

### Q: Какие Matrix серверы поддерживаются?
**A:** Любые! matrix.org, собственный Synapse, Matrix.to и др.

### Q: Можно ли использовать несколько комнат?
**A:** Сейчас поддерживается одна комната. Для нескольких нужно запустить несколько instances интеграции.

### Q: Работает ли в docker?
**A:** Да! Добавьте `pip install matrix-nio` в Dockerfile.

### Q: Работает ли только локальный режим?
**A:** Да, пока что только локальный режим (Glagol protocol). Облачный режим будет добавлен позже.

### Q: Как получить Access Token?
**A:** [Подробная инструкция в MATRIX_BOT.md](MATRIX_BOT.md#получить-access-token)

## 🔐 Безопасность

- Access Token хранится в конфиге Home Assistant - **защищайте config папку!**
- Сообщения НЕ отправляются на внешние серверы (кроме Matrix сервера)
- Локальный режим - Алиса работает на устройстве, не в облаке

## 📊 Логирование

Matrix бот логирует события:
```
✅ Matrix bot интеграция загружена
🤖 Matrix бот инициализирован: https://matrix.org
📨 Matrix сообщение от @user:matrix.org: Включи музыку
🎵 Ответ: Включаю музыку
📤 Отправлено в Matrix: Музыка включена
```

## 🤝 Помощь

Если что-то не работает:
1. Проверьте [MATRIX_DEPS.md](MATRIX_DEPS.md) - установлена ли библиотека?
2. Проверьте [MATRIX_BOT.md](MATRIX_BOT.md) - правильно ли настроено?
3. Включите debug и проверьте логи
4. Откройте issue на GitHub

## 📝 Лицензия

MIT License

## 🎉 Готовы начать?

[Перейти к полному руководству](MATRIX_BOT.md)
