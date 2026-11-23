# notify-bus: писать пользователю Telegram через Васю

Любой сервис публикует JSON в RabbitMQ по TLS, Вася доставляет его в Telegram.
Внутренняя шина Васи (`vasya.bus`) отдельная и не затрагивается.

- Endpoint: `amqps://api.vasyafun.ru:5671`, vhost `/notify` (только TLS, порт 5672/15672 снаружи закрыты)
- Exchange: `notify` (topic), routing key: `send.<имя_сервиса>`
- У каждого сервиса свой пользователь, права только на публикацию в `notify`.
  Выдача: админ на 80.74 создаёт `rabbitmqctl add_user <svc> <pass>` и
  `rabbitmqctl set_permissions -p /notify <svc> '^$' '^notify$' '^$'`;
  учётки лежат в `/root/notify-bus/users/<svc>.env` (chmod 600).

## Формат сообщения (JSON)
| поле | описание |
|---|---|
| `text` | обязательно, до 4000 символов (длиннее обрезается) |
| `user_id` / `user_ids` | один получатель или список (рассылка). Не указано — админу. Любой Telegram id, список разрешённых не ведётся |
| `source` | имя сервиса, добавляется префиксом `[source]` (по умолчанию из routing key) |
| `level` | `info` (по умолчанию) / `warn` / `error` — иконка |
| `parse_mode` | `HTML` / `MarkdownV2` / не задано (простой текст). Если разметка кривая, отправим простым текстом |
| `correlation_id` | необязательно: если задан (или AMQP `correlation_id`/`reply_to`), Вася опубликует отчёт |

## Python (aio-pika)
```python
import asyncio, json, os, aio_pika

async def notify(text, user_ids=None):
    conn = await aio_pika.connect_robust(os.environ["NOTIFY_AMQP_URL"])  # amqps://user:pass@api.vasyafun.ru:5671/%2Fnotify
    async with conn:
        ch = await conn.channel()
        ex = await ch.get_exchange("notify", ensure=False)
        body = {"text": text, "source": "school", "user_ids": user_ids or []}
        await ex.publish(aio_pika.Message(json.dumps(body).encode(),
                         content_type="application/json"), routing_key="send.school")

asyncio.run(notify("Новый урок!", [111, 222]))
```
pika: `pika.URLParameters(url)` (схема `amqps://` включает TLS), затем
`channel.basic_publish("notify", "send.school", json.dumps(body))`.

## Доставка и ошибки
- Лимиты Telegram: ~25 сообщений/с глобально, 1/с в один чат (очередь-троттлер).
- `Forbidden` (бот заблокирован / чат не начат / аккаунт удалён) и `chat not found`:
  пользователь помечается недостижимым на 7 дней (Redis `notify:unreachable:<id>`), дальше пропускается.
- `RetryAfter` — ждём и повторяем; сетевые ошибки — до 3 попыток с паузой. Одна ошибка не ломает рассылку.
- Сообщение берётся один раз (без повторной доставки): невалидное или упавшее отбрасывается с записью в лог.
- Лимиты на источник: 30 публикаций/мин и 20 000 получателей/час, до 5000 получателей в одном сообщении (настраивается `NOTIFY_*` в .env).
- Брокер недоступен — бот работает как раньше, потребитель переподключается с паузой до 5 минут.

## Отчёт о доставке
Если указан `correlation_id`, в exchange `notify` уходит сообщение с ключом `report.<source>`:
`{"correlation_id","source","status":"done|rejected","total","sent","skipped_unreachable","failed_count","failed":[{"user_id","reason"}]}`.
Чтобы читать отчёты, сервису нужна своя очередь и право чтения (админ):
```
rabbitmqctl set_permissions -p /notify <svc> '^$' '^notify$' '^report\.<svc>$'   # и очередь report.<svc> с биндингом report.<svc> на notify
```

## Фото и ответ пользователя (captcha / код подтверждения)
Дополнительные поля сообщения:
| поле | описание |
|---|---|
| `photo_b64` (или `photo`) | base64 PNG/JPEG до 8 МБ. Уйдёт фото, `text` станет подписью (до 1024 символов) |
| `expect_reply` | `true` — ждём ответ пользователя. Нужны ровно один получатель, `correlation_id` и `reply_to` |
| `reply_to` | строго `reply.<source>` (чужие ключи отбрасываются) |

Вася добавляет к тексту подсказку «ответь на это сообщение реплаем» и запоминает
`message_id` в Redis (`notify:reply:<chat>:<message_id>`, hash: reply_to, correlation_id, user_id, source, expires_at).
Окно ответа `NOTIFY_REPLY_TTL_SEC` (по умолчанию 1200 с = 20 мин), сама запись живёт ещё сутки,
чтобы ответить «опоздал».

Когда получатель отвечает **реплаем** на это сообщение, Вася публикует в exchange `notify`
с ключом `reply_to`: `{"correlation_id","text","user_id","source"}` и отвечает пользователю «Передал ✅».
Опоздавший ответ — «Ответ опоздал…», реплай от другого человека игнорируется (обычная обработка).
Обычные сообщения и реплаи на другие сообщения работают как раньше.

### Права для сервиса, который ждёт ответ (админ, на 80.74)
Очередь и биндинг создаёт админ, сервису нужно только чтение своей очереди:
```
rabbitmqctl set_permissions -p /notify <svc> '^reply\.<svc>$' '^notify$' '^reply\.<svc>$'
# очередь reply.<svc> (durable) + биндинг на exchange notify с ключом reply.<svc>
```
У `vasya-bot` уже есть запись в `notify` — отдельных прав для публикации ответов не нужно.

### Пример (pika): отправить и ждать ответ
```python
body = {"text": "Капча: введи символы", "source": "svc", "photo_b64": b64, "expect_reply": True,
        "reply_to": "reply.svc", "correlation_id": cid, "user_id": 123}
ch.basic_publish("notify", "send.svc", json.dumps(body))
# затем basic_get / consume очереди reply.svc, фильтр по correlation_id
```
