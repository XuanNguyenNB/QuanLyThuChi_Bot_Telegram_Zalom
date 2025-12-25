# Zalo Bot API Documentation

> Cập nhật lần cuối: 10/12/2025

Tài liệu này mô tả các API của Zalo Bot Platform để tích hợp chatbot trên Zalo.

## Mục lục

- [Hướng dẫn nhanh](#hướng-dẫn-nhanh)
  - [Xây dựng Bot với Polling](#xây-dựng-bot-với-polling)
  - [Xây dựng Bot với Webhook](#xây-dựng-bot-với-webhook)
- [Base URL](#base-url)
- [Xác thực](#xác-thực)
- [Nhận tin nhắn](#nhận-tin-nhắn)
  - [getUpdates](#getupdates)
  - [Webhook](#webhook)
- [Gửi tin nhắn](#gửi-tin-nhắn)
  - [sendMessage](#sendmessage)
  - [sendPhoto](#sendphoto)
  - [sendSticker](#sendsticker)
  - [sendChatAction](#sendchataction)
- [Thông tin Bot](#thông-tin-bot)
  - [getMe](#getme)

---

## Hướng dẫn nhanh

### Hiểu sơ lược về Zalo Bot

Zalo Bot là một tài khoản tự động (bot) hoạt động trên nền tảng Zalo, cho phép tương tác với người dùng thông qua tin nhắn. Bot có thể giúp bạn:

- Trả lời tin nhắn theo từ khóa, yêu cầu...
- Gửi thông tin cảnh báo
- Tự động phản hồi đơn hàng, hỗ trợ khách hàng, khảo sát, v.v.

### Xây dựng Bot với Polling

> Cập nhật lần cuối: 4/7/2025

Hướng dẫn xây dựng Zalo Bot cơ bản sử dụng chế độ Polling, phù hợp cho người mới bắt đầu và có thể dễ dàng chạy trên máy local.

#### Bước 1: Tạo Bot

Để tạo Zalo Bot, vui lòng làm theo hướng dẫn [tại đây](https://zalo.me/s/botcreator/). Sau khi tạo Bot, bạn sẽ nhận được thông tin `Bot Token` để tiến hành tích hợp API.

#### Bước 2: Lập trình Bot

Tham khảo code mẫu bên dưới để lập trình Bot đơn giản sử dụng cơ chế `getUpdates` và Zalo Bot SDK, phù hợp với môi trường **Development**, nhu cầu chạy thử nghiệm từ local trong quá trình tích hợp.

- **Python:** Tham khảo thêm tài liệu tại [python-zalo-bot](https://github.com/example/python-zalo-bot)
- **Node.js:** Tham khảo thêm tài liệu tại [node-zalo-bot](https://github.com/example/node-zalo-bot)

#### Sample Code (Python)

```python
from zalo-bot import Update
from zalo-bot.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Hàm xử lý cho lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chào {update.effective_user.display_name}! Tôi là chatbot!")

# Hàm xử lý cho lệnh /echo
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = " ".join(context.args)
    if message:
        await update.message.reply_text(f"Bạn vừa nói: {message}")
    else:
        await update.message.reply_text("Hãy nhập gì đó sau lệnh /echo")

if __name__ == "__main__":
    app = ApplicationBuilder().token("YOUR TOKEN HERE").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("echo", echo))

    print("🤖 Bot đang chạy...")
    app.run_polling()
```

---

### Xây dựng Bot với Webhook

> Cập nhật lần cuối: 4/7/2025

Hướng dẫn xây dựng Zalo Bot sử dụng cơ chế Webhook dành cho người mới bắt đầu.

#### Mục tiêu

- Tạo một bot Zalo sử dụng cơ chế Webhook để nhận sự kiện từ người dùng.
- Xử lý các sự kiện như nhận tin nhắn, gửi phản hồi, gửi ảnh...
- Hiện thực bằng Node.js hoặc Python sử dụng các SDK có sẵn.

#### Bước 1: Tạo Bot

Để tạo Zalo Bot, vui lòng làm theo hướng dẫn [tại đây](https://zalo.me/s/botcreator/). Sau khi tạo Bot, bạn sẽ có thông tin `Bot Token` để tích hợp API.

#### Bước 2: Thiết lập Webhook

Bạn cần thiết lập Server với domain HTTPS để đăng ký Webhook nhận sự kiện. Bạn có thể dùng:

- **Ngrok** (dành cho dev local): `ngrok http 3000`
- **Render, Railway, Vercel...** (có hỗ trợ HTTPS)

Sau đó sử dụng API `setWebhook` để thiết lập Webhook cho Zalo Bot của bạn.

#### Bước 3: Lập trình Bot

Sử dụng Zalo Bot SDK theo code mẫu bên dưới để hiện thực logic cho Bot của bạn.

- **Python:** Tham khảo thêm tài liệu tại [python-zalo-bot](https://github.com/example/python-zalo-bot)
- **Node.js:** Tham khảo thêm tài liệu tại [node-zalo-bot](https://github.com/example/node-zalo-bot)

#### Sample Code (Python với Flask)

```python
from flask import Flask, request
from zalo import Bot, Update
from zalo.ext import Dispatcher, CommandHandler, MessageHandler, filters

TOKEN = "YOUR_ZALO_BOT_TOKEN"
bot = Bot(token=TOKEN)

app = Flask(__name__)

# Cấu hình webhook 1 lần khi chạy lần đầu
@app.before_first_request
def setup_webhook():
    webhook_url = "https://your-ngrok-or-domain/webhook"
    bot.set_webhook(url=webhook_url)

# Hàm xử lý /start
def start(update: Update, context):
    update.message.reply_text(f"Xin chào {update.effective_user.first_name}!")

# Hàm xử lý tin nhắn thường
def echo(update: Update, context):
    update.message.reply_text(f"Bạn vừa nói: {update.message.text}")

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# Cấu hình dispatcher và handler
from zalo.ext import CallbackContext
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

if __name__ == "__main__":
    app.run(port=8443)
```

---

## Base URL

```
https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/<method>
```

## Xác thực

Sử dụng Bot Token được cấp khi tạo bot tại [Zalo Bot Creator](https://zalo.me/s/botcreator/).

Token có định dạng: `{bot_id}:{access_token}`

---

## Nhận tin nhắn

Zalo hỗ trợ 2 cách để bot nhận tin nhắn:

1. **getUpdates** - Long polling
2. **Webhook** - Push notification

> ⚠️ **Lưu ý:** `getUpdates` sẽ không hoạt động nếu đã thiết lập Webhook. Sử dụng `deleteWebhook` để xóa Webhook trước khi dùng `getUpdates`.

### getUpdates

Sử dụng cơ chế long polling để nhận tin nhắn mới.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/getUpdates`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `timeout` | String | false | Thời gian timeout của HTTP Request tính theo giây. Mặc định 30 giây. |

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/getUpdates`;
const response = await axios.post(entrypoint, {
  timeout: 30
});
```

#### Sample Response

Dữ liệu tin nhắn nhận được là JSON object với cấu trúc:

```json
{
  "ok": true,
  "result": {
    "message": {
      "chat": {
        "id": "e4ea2cd5189df1c3a88c",
        "chat_type": "PRIVATE"
      },
      "text": "Xin chào",
      "message_id": "16f6366b3f02645a3d15",
      "date": 1766619597466,
      "from": {
        "id": "e4ea2cd5189df1c3a88c",
        "first_name": "Nguyen Van A"
      }
    }
  }
}
```

---

### Webhook

#### setWebhook

Cấu hình Webhook URL cho Bot.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/setWebhook`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `url` | String | true | URL nhận thông báo dạng HTTPS. |
| `secret_token` | String | true | Khóa bí mật từ 8 tới 256 ký tự, để xác thực yêu cầu từ Zalo. Token được đính kèm trong header `X-Bot-Api-Secret-Token`. |

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/setWebhook`;
const response = await axios.post(entrypoint, {
  url: "https://your-webhookurl.com",
  secret_token: "mykey-abcxyz"
});
```

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "url": "https://your-webhookurl.com",
    "updated_at": 1749538250568
  }
}
```

---

#### getWebhookInfo

Lấy trạng thái cấu hình hiện tại của webhook.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/getWebhookInfo`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

Không yêu cầu tham số đi kèm.

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "url": "https://your-webhookurl.com",
    "updated_at": 1749633372026
  }
}
```

---

#### deleteWebhook

Gỡ bỏ thiết lập webhook nếu bạn quyết định chuyển lại sang `getUpdates`.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/deleteWebhook`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

Không yêu cầu tham số đi kèm.

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "url": "",
    "updated_at": 1749538250568
  }
}
```

---

## Gửi tin nhắn

### sendMessage

Gửi tin nhắn văn bản đến người dùng hoặc cuộc trò chuyện.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `chat_id` | String | true | ID của người nhận hoặc cuộc trò chuyện |
| `text` | String | true | Nội dung văn bản của tin nhắn sẽ được gửi, với độ dài từ 1 đến 2000 ký tự |

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendMessage`;
const response = await axios.post(entrypoint, {
  chat_id: "abc.xyz",
  text: "Hello"
});
```

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "message_id": "82599fa32f56d00e8941",
    "date": 1749632637199
  }
}
```

---

### sendPhoto

Gửi tin nhắn hình ảnh đến người dùng hoặc cuộc trò chuyện.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendPhoto`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `chat_id` | String | true | ID của người nhận hoặc cuộc trò chuyện |
| `photo` | String | true | Đường dẫn hình ảnh sẽ được gửi |
| `caption` | String | false | Nội dung văn bản của tin nhắn sẽ được gửi kèm, với độ dài từ 1 đến 2000 ký tự |

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendPhoto`;
const response = await axios.post(entrypoint, {
  chat_id: "abc.xyz",
  caption: "My photo",
  photo: "https://placehold.co/600x400"
});
```

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "message_id": "82599fa32f56d00e8941",
    "date": 1749632637199
  }
}
```

---

### sendSticker

Gửi tin nhắn Sticker đến người dùng hoặc cuộc trò chuyện.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendSticker`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `chat_id` | String | true | ID của người nhận hoặc cuộc trò chuyện |
| `sticker` | String | true | Truyền vào sticker lấy từ nguồn: https://stickers.zaloapp.com/ |

> 📺 Video hướng dẫn: https://vimeo.com/649330161

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendSticker`;
const response = await axios.post(entrypoint, {
  chat_id: "abc.xyz",
  sticker: "0e078a2fb66a5f34067b"
});
```

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "message_id": "82599fa32f56d00e8941",
    "date": 1749632637199
  }
}
```

---

### sendChatAction

Hiển thị một trạng thái tạm thời trong cuộc trò chuyện, như **đang soạn tin nhắn** hoặc **đang gửi ảnh**.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendChatAction`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
|--------|--------------|----------|-------|
| `chat_id` | String | true | ID của người nhận hoặc cuộc trò chuyện |
| `action` | String | true | Loại hành động. Có sẵn: `typing` (tin nhắn văn bản), `upload_photo` (sắp ra mắt) |

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/sendChatAction`;
const response = await axios.post(entrypoint, {
  chat_id: "abc.xyz",
  action: "typing"
});
```

#### Sample Response

```json
{
  "ok": true
}
```

---

## Thông tin Bot

### getMe

Sử dụng phương thức này để kiểm tra Bot Token, nếu token hợp lệ sẽ trả về các thông tin cơ bản về Bot của bạn.

- **URL:** `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/getMe`
- **Method:** `POST`
- **Response Type:** `application/json`

#### Parameters

Không yêu cầu tham số đi kèm.

#### Sample Code (Node.js)

```javascript
const axios = require("axios");

const entrypoint = `https://bot-api.zaloplatforms.com/bot${BOT_TOKEN}/getMe`;
const response = await axios.post(entrypoint, {});
```

#### Sample Response

```json
{
  "ok": true,
  "result": {
    "id": "1459232241454765289",
    "account_name": "bot.VDKyGxQvc",
    "account_type": "BASIC",
    "can_join_groups": false
  }
}
```

---

## Tham khảo thêm

- **Zalo Bot Creator:** https://zalo.me/s/botcreator/
- **Tài liệu chính thức:** https://bot.zaloplatforms.com/docs/build-your-bot/
- **Stickers:** https://stickers.zaloapp.com/
