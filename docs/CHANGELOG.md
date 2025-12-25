# Changelog

## [2.0.0] - 2025-12-25

### Thêm mới
- **Zalo Bot Integration** - Hỗ trợ cả Telegram và Zalo
- **Cross-platform sync** - Đồng bộ dữ liệu qua số điện thoại
- **Voice-to-text** - Ghi chi tiêu bằng giọng nói (Gemini AI)
- **Unified run.py** - Chạy cả 2 bot cùng lúc
- **AI casual chat** - Trò chuyện tự nhiên khi không hiểu
- **AI transaction comments** - Comment vui cho mỗi giao dịch
- `/link` command - Liên kết Telegram ↔ Zalo

### Thay đổi
- User model: Thêm `telegram_id`, `zalo_id`, `phone` fields
- User.id: Đổi từ Telegram ID sang auto-increment
- Tất cả handlers dùng `db_user.id` thay vì `user.id`

### Breaking Changes
- **Phải xóa database cũ** trước khi chạy
- Code cũ dùng `user.id` trực tiếp sẽ không hoạt động

---

## [1.5.0] - 2025-12-24

### Thêm mới
- **Smart Query** - Hỏi đáp chi tiêu bằng ngôn ngữ tự nhiên
- **Income tracking** - Ghi thu nhập với categories riêng
- **Category learning** - Bot học từ khóa từ user
- `/insights` command - Phân tích chi tiêu thông minh
- `/today` và `/month` hiển thị cả thu và chi

### Thay đổi
- TransactionType enum: EXPENSE và INCOME
- Category có `type` field
- Summary bao gồm `total_income`

---

## [1.0.0] - 2025-12-20

### Thêm mới
- **Telegram Bot** - Ghi chép chi tiêu cơ bản
- **AI Parsing** - Gemini AI parse tin nhắn
- **Auto-categorization** - Tự động phân loại
- **SQLite Database** - Lưu trữ local
- Commands: `/start`, `/today`, `/month`, `/delete`, `/edit`, `/export`, `/help`

---

## Upgrade Guide

### Từ v1.x lên v2.0

1. **Backup data** (nếu cần):
```bash
# Export transactions trước
/export
```

2. **Xóa database cũ**:
```bash
del finance_bot.db
```

3. **Update code**:
```bash
git pull origin main
pip install -r requirements.txt
```

4. **Cập nhật .env**:
```env
# Thêm Zalo token
ZALO_BOT_TOKEN=your_token_here
```

5. **Chạy bot mới**:
```bash
python run.py
```

6. **Re-import data** (nếu cần):
- Hiện chưa có import tool
- Phải ghi lại thủ công
