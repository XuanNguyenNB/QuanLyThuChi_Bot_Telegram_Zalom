# Kiến trúc hệ thống

## Tổng quan

```
┌─────────────────┐     ┌─────────────────┐
│  Telegram App   │     │    Zalo App     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Telegram API   │     │   Zalo Bot API  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│              run.py                      │
│  (Chạy cả 2 bot đồng thời)              │
├─────────────────┬───────────────────────┤
│    bot.py       │     zalo_bot.py       │
│  (Telegram)     │       (Zalo)          │
└────────┬────────┴───────────┬───────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────┐
│            services.py                   │
│  (Business logic, parsing, queries)     │
├─────────────────────────────────────────┤
│            ai_service.py                 │
│  (Gemini AI: voice, parsing, chat)      │
├─────────────────────────────────────────┤
│            models.py                     │
│  (SQLAlchemy ORM models)                │
└────────────────────┬────────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │   SQLite DB  │
              │ finance_bot.db│
              └──────────────┘
```

## Database Schema

### User Model
```python
class User(Base):
    id: int              # Auto-increment primary key
    telegram_id: int     # Telegram user ID (nullable, unique)
    zalo_id: str         # Zalo user ID (nullable, unique)
    phone: str           # Số điện thoại để liên kết (nullable, unique)
    username: str
    full_name: str
    created_at: datetime
```

**Quan trọng:** 
- `id` là database ID, dùng cho tất cả foreign keys
- `telegram_id` và `zalo_id` là platform IDs, chỉ dùng để lookup user
- Đồng bộ qua `phone` - khi 2 platform cùng link 1 số điện thoại

### Category Model
```python
class Category(Base):
    id: int
    name: str           # "Ăn uống", "Di chuyển", etc.
    keywords: str       # Comma-separated: "cafe,cà phê,coffee"
    type: TransactionType  # EXPENSE hoặc INCOME
```

### Transaction Model
```python
class Transaction(Base):
    id: int
    user_id: int        # FK to User.id (database ID!)
    amount: float
    category_id: int    # FK to Category.id
    note: str
    date: datetime
    raw_text: str       # Original user message
```

### UserKeyword Model
```python
class UserKeyword(Base):
    id: int
    user_id: int        # FK to User.id
    category_id: int    # FK to Category.id
    keyword: str        # User-specific learned keyword
```

## Flow xử lý tin nhắn

### 1. Text Message Flow
```
User gửi: "cafe 50k"
         │
         ▼
┌─────────────────────────────┐
│ get_or_create_user()        │ ← Lấy/tạo db_user từ telegram_id
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ is_question(text)?          │ ← Kiểm tra có phải câu hỏi không
└────────────┬────────────────┘
             │ No
             ▼
┌─────────────────────────────┐
│ parse_with_ai(text)         │ ← AI parse: amount, note, category
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ find_category_from_user_    │ ← Tìm từ lịch sử user
│ history(db_user.id, note)   │
└────────────┬────────────────┘
             │ Not found
             ▼
┌─────────────────────────────┐
│ detect_category(note)       │ ← Tìm từ keywords mặc định
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ add_transaction(            │
│   user_id=db_user.id,       │ ← Dùng database ID!
│   amount, note, category_id │
│ )                           │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ generate_transaction_       │ ← AI tạo comment vui
│ comment()                   │
└─────────────────────────────┘
```

### 2. Voice Message Flow
```
User gửi voice
         │
         ▼
┌─────────────────────────────┐
│ Download voice file         │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ transcribe_voice()          │ ← Gemini chuyển audio → text
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ parse_with_ai(text)         │ ← Parse thành giao dịch
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Hiển thị preview +          │
│ Confirm/Cancel buttons      │
└────────────┬────────────────┘
             │ User nhấn Confirm
             ▼
┌─────────────────────────────┐
│ add_transaction()           │
└─────────────────────────────┘
```

### 3. Smart Query Flow
```
User hỏi: "Tháng này chi cafe bao nhiêu?"
         │
         ▼
┌─────────────────────────────┐
│ is_question(text) = True    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ parse_query_intent(text)    │ ← AI parse: time_range, keyword
│ → time_range="month"        │
│ → keyword="cafe"            │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ smart_query_transactions(   │
│   db_user.id,               │
│   time_range="month",       │
│   keyword="cafe"            │
│ )                           │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Format & return results     │
└─────────────────────────────┘
```

## Đồng bộ Telegram ↔ Zalo

### Cách liên kết
```
1. User A dùng Telegram:
   /link 0901234567
   → Tạo User(id=1, telegram_id=123, phone="0901234567")

2. User A dùng Zalo:
   /link 0901234567
   → Tìm User có phone="0901234567"
   → Update: User(id=1, telegram_id=123, zalo_id="abc", phone="0901234567")

3. Kết quả: Cả 2 platform dùng chung user_id=1
   → Transactions đồng bộ!
```

### Code logic (services.py)
```python
async def link_user_by_phone(session, phone, telegram_id=None, zalo_id=None):
    # Tìm user có phone này
    user = await find_by_phone(phone)
    if user:
        # Update với platform ID mới
        if telegram_id: user.telegram_id = telegram_id
        if zalo_id: user.zalo_id = zalo_id
        return user
    
    # Tìm user có platform ID và add phone
    if telegram_id:
        user = await find_by_telegram_id(telegram_id)
        if user:
            user.phone = phone
            return user
    ...
```

## AI Services (ai_service.py)

### 1. parse_with_ai(text)
Parse tin nhắn thành giao dịch:
```python
Input:  "cafe 50 và bánh mì 20"
Output: AIParseResult(
    understood=True,
    transactions=[
        AITransaction(amount=50000, note="cafe", category="Ăn uống"),
        AITransaction(amount=20000, note="bánh mì", category="Ăn uống")
    ]
)
```

### 2. transcribe_voice(audio_bytes)
Chuyển audio thành text:
```python
Input:  bytes (audio file)
Output: "cafe năm mươi nghìn"
```

### 3. parse_query_intent(text)
Parse câu hỏi thành query params:
```python
Input:  "tuần này chi cafe bao nhiêu"
Output: QueryIntent(
    is_query=True,
    time_range="week",
    keyword="cafe",
    category=None
)
```

### 4. chat_casual(text)
Trò chuyện tự nhiên khi không hiểu:
```python
Input:  "hello bạn ơi"
Output: "Chào bạn! Mình là bot ghi chép chi tiêu..."
```

### 5. generate_transaction_comment(amount, note, category, type)
Tạo comment vui cho giao dịch:
```python
Input:  (50000, "cafe", "Ăn uống", "expense")
Output: "Ly cafe sáng giúp tỉnh táo làm việc nè! ☕"
```

## Lưu ý quan trọng

### 1. User ID vs Platform ID
```python
# ❌ SAI - dùng Telegram ID trực tiếp
await add_transaction(session, user_id=update.effective_user.id, ...)

# ✅ ĐÚNG - lấy database user trước
db_user = await get_or_create_user(session, user.id, ...)
await add_transaction(session, user_id=db_user.id, ...)
```

### 2. Zalo API khác Telegram
```python
# Telegram: getUpdates trả về list
{"ok": true, "result": [{"update_id": 1, "message": {...}}]}

# Zalo: getUpdates trả về dict với message trực tiếp
{"ok": true, "result": {"message": {...}}}
```

### 3. Zalo dùng POST cho tất cả methods
```python
# Telegram có thể dùng GET
# Zalo: luôn dùng POST, kể cả getMe, getUpdates
```

### 4. SQLite autoincrement
```python
# BigInteger không tự động increment trong SQLite
# Phải dùng Integer hoặc không specify type
id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
```
