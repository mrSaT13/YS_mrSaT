# Примеры automations для Matrix бота

## 1. Основная интеграция - обработка сообщений через Алису

```yaml
- id: "matrix_alice_conversation"
  alias: "🤖 Matrix → Alice → Matrix"
  description: "Отправка сообщений в Алису и ответов обратно"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  action:
    # Обработать сообщение через Алису
    - service: conversation.process
      data:
        agent_id: conversation.yandex_station_mini  # Замените на вашу станцию!
        text: "{{ trigger.event.data.text }}"
        conversation_id: "{{ trigger.event.data.room_id }}"
      response_variable: response
    
    # Отправить ответ обратно в Matrix
    - service: yandex_station.matrix_send_message
      data:
        message: "{{ response.response.speech.plain.speech }}"
```

## 2. Уведомления о воспроизведении в Matrix

```yaml
- id: "matrix_playback_start"
  alias: "🎵 Начало воспроизведения"
  description: "Отправить уведомление в Matrix когда начинает играть музыка"
  trigger:
    platform: state
    entity_id: media_player.yandex_station_mini
    to: "playing"
  action:
    - service: yandex_station.matrix_send_message
      data:
        message: |
          🎵 Сейчас играет:
          **{{ state_attr('media_player.yandex_station_mini', 'media_title') }}**
          👤 {{ state_attr('media_player.yandex_station_mini', 'media_artist') }}

- id: "matrix_playback_stop"
  alias: "⏸️ Пауза воспроизведения"
  description: "Отправить уведомление в Matrix при паузе"
  trigger:
    platform: state
    entity_id: media_player.yandex_station_mini
    to: "paused"
  action:
    - service: yandex_station.matrix_send_message
      data:
        message: "⏸️ Пауза"
```

## 3. Команды управления (slash команды)

```yaml
- id: "matrix_command_handler"
  alias: "Matrix команды управления"
  description: "Обработка команд типа /play, /pause, /next"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.text.startswith('/') }}"
  action:
    - choose:
        # /play - включить воспроизведение
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/play' }}"
          sequence:
            - service: media_player.media_play
              entity_id: media_player.yandex_station_mini
            - service: yandex_station.matrix_send_message
              data:
                message: "▶️ Проигрывание"
        
        # /pause - пауза
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/pause' }}"
          sequence:
            - service: media_player.media_pause
              entity_id: media_player.yandex_station_mini
            - service: yandex_station.matrix_send_message
              data:
                message: "⏸️ Пауза"
        
        # /next - следующий трек
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/next' }}"
          sequence:
            - service: media_player.media_next_track
              entity_id: media_player.yandex_station_mini
            - service: yandex_station.matrix_send_message
              data:
                message: "⏭️ Следующий трек"
        
        # /prev - предыдущий трек
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/prev' }}"
          sequence:
            - service: media_player.media_previous_track
              entity_id: media_player.yandex_station_mini
            - service: yandex_station.matrix_send_message
              data:
                message: "⏮️ Предыдущий трек"
        
        # /status - статус
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/status' }}"
          sequence:
            - service: yandex_station.matrix_send_message
              data:
                message: |
                  📊 Статус станции:
                  🎵 Трек: {{ state_attr('media_player.yandex_station_mini', 'media_title') }}
                  👤 Исполнитель: {{ state_attr('media_player.yandex_station_mini', 'media_artist') }}
                  🔊 Громкость: {{ state_attr('media_player.yandex_station_mini', 'volume_level') | int(0) * 100 }}%
                  ⏱️ Состояние: {{ states('media_player.yandex_station_mini') }}
      default:
        - service: yandex_station.matrix_send_message
          data:
            message: "❓ Неизвестная команда. Попробуйте /play, /pause, /next, /prev, /status"
```

## 4. Игровые команды

```yaml
- id: "matrix_game_command"
  alias: "Matrix игровые команды"
  description: "Начать игру через Matrix"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.text.startswith('/game') }}"
  action:
    - service: conversation.process
      data:
        agent_id: conversation.yandex_station_mini
        text: "Поиграй в {{ trigger.event.data.text[6:] }}"
        conversation_id: "{{ trigger.event.data.room_id }}"
      response_variable: response
    
    - service: yandex_station.matrix_send_message
      data:
        message: "🎮 {{ response.response.speech.plain.speech }}"
```

## 5. Погодные уведомления в Matrix

```yaml
- id: "matrix_weather_daily"
  alias: "🌤️ Ежедневный прогноз в Matrix"
  description: "Отправлять погоду в Matrix каждое утро"
  trigger:
    platform: time
    at: "07:00:00"
  action:
    - service: conversation.process
      data:
        agent_id: conversation.yandex_station_mini
        text: "Какая будет погода?"
        conversation_id: "matrix_weather_daily"
      response_variable: response
    
    - service: yandex_station.matrix_send_message
      data:
        message: "🌤️ Погода на сегодня:\n{{ response.response.speech.plain.speech }}"
```

## 6. Управление умным домом через Matrix

```yaml
- id: "matrix_smart_home_control"
  alias: "🏠 Управление умным домом через Matrix"
  description: "Включать/выключать устройства через Matrix"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  action:
    - choose:
        # /light on - включить свет
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/light on' }}"
          sequence:
            - service: light.turn_on
              entity_id: light.living_room  # Измените на вашу лампу!
            - service: yandex_station.matrix_send_message
              data:
                message: "💡 Свет включен"
        
        # /light off - выключить свет
        - conditions:
            - condition: template
              value_template: "{{ trigger.event.data.text == '/light off' }}"
          sequence:
            - service: light.turn_off
              entity_id: light.living_room
            - service: yandex_station.matrix_send_message
              data:
                message: "🌙 Свет выключен"
      default:
        - service: yandex_station.matrix_send_message
          data:
            message: "Доступные команды: /play, /pause, /next, /prev, /status, /light on, /light off"
```

## 7. Логирование сообщений в Matrix

```yaml
- id: "matrix_message_log"
  alias: "📝 Логирование сообщений Matrix"
  description: "Сохранять все сообщения в лог"
  trigger:
    platform: event
    event_type: yandex_station_matrix_text
  action:
    - service: logger.log
      data:
        level: INFO
        message: "[Matrix] {{ trigger.event.data.sender }}: {{ trigger.event.data.text }}"
```

## Использование в YAML

Сохраните эти automations в файл `automation/matrix.yaml` и добавьте в `configuration.yaml`:

```yaml
automation: !include_dir_merge_list automation/
```

Или используйте встроенный редактор automations в Home Assistant UI.

## Устранение неполадок

### Ответ не приходит
- Проверьте что conversation агент существует (должен быть conversation.yandex_station_mini или похожий)
- Проверьте логи для ошибок синхронизации Matrix
- Убедитесь что станция в локальном режиме

### Команды не распознаются
- Проверьте что Алиса включена и слушает (в гарнитуре должна быть голубая полоса)
- Проверьте что текст точно совпадает (регистр важен!)

### Matrix бот не подключается
- Проверьте Access Token - не истек ли?
- Проверьте Room ID - правильный ли формат? (начинается с `!`)
- Проверьте что сервер доступен: `curl https://matrix.org`
