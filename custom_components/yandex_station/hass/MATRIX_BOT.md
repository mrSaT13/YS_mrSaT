# Matrix Bot для Yandex Station

Яндекс Алиса в Matrix чате! 

Вы можете общаться со своей Алисой через Matrix. И она вам будет отвечать в Matrix! Можете спросить погоду, вызвать такси, включить песню, поиграть в города или управлять вашим умным домом (если настроили интеграцию с умным домом Яндекса).

**Только для локального режима!**

## Требования

1. **Yandex Station интеграция** - основная интеграция должна быть установлена
2. **Matrix сервер** - доступ к Matrix серверу (например, matrix.org или локальный Synapse)
3. **Matrix Bot аккаунт** - зарегистрированный аккаунт для бота
4. **Home Assistant** - с поддержкой conversation сервиса

## Установка

### 1. Создать Matrix бота

В клиенте Matrix (Element, FluffyChat и др.):
- Создайте новый аккаунт для бота (например, `alice_bot`)
- Запомните:
  - **Server URL**: `https://matrix.org` (или адрес вашего сервера)
  - **User ID**: `@alice_bot:matrix.org`
  - **Access Token**: получить через terminal или скрипт:

```python
# Получить access token
import httpx
import asyncio

async def get_token(homeserver, username, password):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{homeserver}/_matrix/client/r0/login",
            json={"type": "m.login.password", "user": username, "password": password}
        )
        print(response.json()["access_token"])

asyncio.run(get_token("https://matrix.org", "alice_bot", "PASSWORD"))
```

### 2. Создать Matrix комнату

- В Element создайте приватную комнату
- Пригласите бота (@alice_bot:matrix.org)
- Получите **Room ID**: правый клик на комнате → копировать ID (например, `!abc123:matrix.org`)

### 3. Настроить Home Assistant

Добавьте в `configuration.yaml`:

```yaml
yandex_station:
  # ... остальная конфигурация ...
  
  matrix_bot:
    server_url: "https://matrix.org"  # Matrix сервер
    room_id: "!abc123:matrix.org"     # ID комнаты бота
    access_token: "syt_..."           # Access token бота

conversation: # !include conversation.yaml

automation: !include_dir_merge_list automation/
```

### 4. Настроить Automation для обработки сообщений

Создайте файл `automation/matrix_alice.yaml`:

```yaml
- id: "matrix_alice_conversation"
  alias: "🤖 Matrix → Alice → Matrix"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  action:
    # Обработать сообщение через Алису
    - service: conversation.process
      data:
        agent_id: conversation.yandex_station_mini  # Измените на вашу станцию
        text: "{{ trigger.event.data.text }}"
        conversation_id: "{{ trigger.event.data.room_id }}"
      response_variable: response
    
    # Отправить ответ обратно в Matrix
    - service: yandex_station.matrix_send_message
      data:
        message: "{{ response.response.speech.plain.speech }}"
```

### 5. Перезагрузить Home Assistant

```bash
Developer Tools → YAML → Restart Home Assistant
```

## Использование

Просто пишите в Matrix комнате:

```
Ты: "Включи музыку"
Алиса: "Включаю музыку"

Ты: "Какая погода?"
Алиса: "Сейчас в Москве -5 градусов, идет снег"

Ты: "Повторись"
Алиса: "Повторю предыдущее сообщение..."
```

## Отладка

Включите debug логирование в `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.yandex_station.hass.matrix_bot: debug
```

Логи помогут отследить:
- ✅ Подключение к Matrix
- 📨 Входящие сообщения
- 📤 Отправленные ответы
- ❌ Ошибки синхронизации

## Troubleshooting

### "Matrix требует установки matrix-client"
```bash
pip install matrix-client
```

### Бот не получает сообщения
- Проверьте, что бот приглашен в комнату
- Проверьте Room ID (должен начинаться с `!`)
- Проверьте Access Token

### Ответ не отправляется обратно
- Проверьте conversation.yandex_station_mini существует
- Проверьте логи для ошибок
- Убедитесь что станция в локальном режиме (sync_enabled: true)

## Примеры расширения

### Отправка уведомлений о воспроизведении

```yaml
automation:
  - id: "matrix_playback_notify"
    alias: "🎵 Уведомление о воспроизведении в Matrix"
    trigger:
      platform: state
      entity_id: media_player.yandex_station_mini
      to: "playing"
    action:
      - service: yandex_station.matrix_send_message
        data:
          message: |
            🎵 Сейчас играет:
            {{ state_attr('media_player.yandex_station_mini', 'media_title') }}
            👤 {{ state_attr('media_player.yandex_station_mini', 'media_artist') }}
```

### Управление через Matrix кнопки

```yaml
automation:
  - id: "matrix_command_handler"
    alias: "Matrix команды управления"
    trigger:
      platform: event
      event_type: yandex_station_matrix_text
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.text.startswith('/') }}"
    action:
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.text == '/play' }}"
            sequence:
              - service: media_player.media_play
                entity_id: media_player.yandex_station_mini
              - service: yandex_station.matrix_send_message
                data:
                  message: "▶️ Проигрывание"
          
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.text == '/pause' }}"
            sequence:
              - service: media_player.media_pause
                entity_id: media_player.yandex_station_mini
              - service: yandex_station.matrix_send_message
                data:
                  message: "⏸️ Пауза"
```

## Лицензия

MIT License
