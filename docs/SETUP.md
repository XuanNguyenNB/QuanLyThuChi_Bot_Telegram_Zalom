# Hướng dẫn cài đặt

## Yêu cầu

- Python 3.10+
- pip

## 1. Clone và cài đặt dependencies

```bash
git clone <repo-url>
cd Telegram_bot_GhiChepChiTieu

# Tạo virtual environment (khuyến nghị)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Cài đặt dependencies
pip install -r requirements.txt
```

## 2. Tạo Bot Telegram

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot`
3. Đặt tên và username cho bot
4. Copy **Bot Token** được cấp

## 3. Tạo Bot Zalo

1. Truy cập [Zalo Bot Creator](https://zalo.me/s/botcreator/)
2. Tạo bot mới
3. Copy **Bot Token** được cấp

## 4. Lấy Gemini API Key

1. Truy cập [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Tạo API key mới
3. Copy API key

## 5. Cấu hình .env

```bash
# Copy file mẫu
cp .env.example .env
```

Mở `.env` và điền các giá trị:

```env
# Telegram Bot Token (Get from @BotFather)
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Zalo Bot Token (Get from https://zalo.me/s/botcreator/)
ZALO_BOT_TOKEN=your_zalo_bot_token_here

# Database URL (SQLite for MVP)
DB_URL=sqlite+aiosqlite:///./finance_bot.db

# Gemini AI API Key (Get from https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here
```

## 6. Chạy bot

### Chạy cả 2 bot (Telegram + Zalo)
```bash
python run.py
```

### Chỉ chạy Telegram
```bash
python run.py telegram
```

### Chỉ chạy Zalo
```bash
python run.py zalo
```

## 7. Test

```bash
# Chạy unit tests
pytest tests/ -v

# Chạy với coverage
pytest tests/ --cov=src
```

## Troubleshooting

### Lỗi database schema
```bash
# Xóa database cũ và chạy lại
del finance_bot.db  # Windows
# rm finance_bot.db  # Linux/Mac
python run.py
```

### Lỗi "NOT NULL constraint failed: users.id"
- Đã xóa database chưa?
- Kiểm tra `models.py`:
```python
# id phải là autoincrement, không dùng BigInteger
id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
```

### Zalo bot không nhận tin nhắn
1. Kiểm tra đã `deleteWebhook` chưa (bot tự động làm khi start)
2. Kiểm tra token đúng format: `bot_id:access_token`
3. Xem log để debug:
```
API response type: dict, content: {'ok': True, 'result': {'message': ...}}
```

### Telegram bot không response
1. Kiểm tra TELEGRAM_TOKEN đúng
2. Kiểm tra bot chưa bị block
3. Thử `/start` để init user

### AI không hoạt động
1. Kiểm tra GEMINI_API_KEY
2. Kiểm tra quota API còn không
3. Xem log lỗi từ `ai_service.py`

## Cấu trúc Database

Database tự động tạo khi chạy lần đầu với các categories mặc định:

### Categories (Chi tiêu)
- Chợ/Siêu thị
- Ăn uống
- Di chuyển
- Mua sắm
- Giải trí
- Sức khỏe
- Học tập
- Công việc
- Hóa đơn
- Người thân
- Khác

### Categories (Thu nhập)
- Lương
- Thưởng
- Bán hàng
- Đầu tư
- Khác (Thu)

## Development

### Thêm category mới
Sửa `seed_default_categories()` trong `models.py`:
```python
Category(
    name="Tên danh mục",
    keywords="keyword1,keyword2,keyword3",
    type=TransactionType.EXPENSE  # hoặc INCOME
)
```

### Thêm command mới
1. Tạo handler trong `bot.py`:
```python
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with await get_session() as session:
        db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
        # Logic here...
```

2. Đăng ký trong `main()`:
```python
application.add_handler(CommandHandler("mycommand", my_command))
```

3. Thêm vào menu bot:
```python
BotCommand("mycommand", "Mô tả"),
```

### Thêm AI service mới
1. Tạo function trong `ai_service.py`:
```python
async def my_ai_function(text: str) -> str:
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"..."
    response = await model.generate_content_async(prompt)
    return response.text.strip()
```

2. Import và sử dụng trong `bot.py` hoặc `zalo_bot.py`
