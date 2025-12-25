# Bot Ghi Chép Chi Tiêu - Telegram & Zalo

Bot ghi chép thu chi cá nhân thông minh, hỗ trợ cả **Telegram** và **Zalo** với dữ liệu đồng bộ.

## Tính năng chính

### 💰 Ghi chi tiêu tự nhiên
```
cafe 50        → 50,000₫
grab 35k       → 35,000₫
tiền nhà 2tr   → 2,000,000₫
```

### 📈 Ghi thu nhập
```
lương 15tr     → Thu 15,000,000₫
bán hàng 500   → Thu 500,000₫
```

### 🎤 Voice-to-Text
Gửi voice message, bot sẽ:
1. Chuyển giọng nói thành văn bản (dùng Gemini AI)
2. Parse thông tin giao dịch
3. Hiển thị preview để xác nhận
4. Lưu sau khi user confirm

### 💬 Hỏi đáp thông minh
```
"Tháng này chi bao nhiêu?"
"Tuần này tôi chi nhiều nhất vào gì?"
"Hôm nay chi cafe bao nhiêu?"
```

### 🔗 Đồng bộ Telegram ↔ Zalo
Liên kết 2 tài khoản bằng số điện thoại:
```
/link 0901234567
```

## Các lệnh

| Lệnh | Mô tả |
|------|-------|
| `/start` | Bắt đầu sử dụng |
| `/today` | Xem chi tiêu hôm nay |
| `/month` | Xem chi tiêu tháng |
| `/insights` | Phân tích thông minh |
| `/edit` | Sửa giao dịch gần nhất |
| `/delete` | Xóa giao dịch gần nhất |
| `/link` | Liên kết với Zalo/Telegram |
| `/export` | Xuất file CSV |
| `/help` | Hướng dẫn |

## Cấu trúc thư mục

```
Telegram_bot_GhiChepChiTieu/
├── run.py              # Entry point - chạy cả 2 bot
├── src/
│   ├── bot.py          # Telegram bot handlers
│   ├── zalo_bot.py     # Zalo bot handlers
│   ├── models.py       # SQLAlchemy models
│   ├── services.py     # Business logic
│   ├── ai_service.py   # Gemini AI integration
│   └── utils.py        # Helper functions
├── tests/              # Unit tests
├── docs/               # Documentation
├── .env                # Environment variables
└── requirements.txt    # Dependencies
```

## Quick Start

```bash
# 1. Clone và cài đặt
pip install -r requirements.txt

# 2. Tạo file .env
cp .env.example .env
# Điền các token vào .env

# 3. Chạy bot
python run.py          # Chạy cả 2 bot
python run.py telegram # Chỉ Telegram
python run.py zalo     # Chỉ Zalo
```

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot v20+** - Async Telegram Bot API
- **httpx** - Async HTTP client cho Zalo API
- **SQLAlchemy 2.0** - Async ORM
- **SQLite** - Database (aiosqlite)
- **Google Gemini** - AI cho voice, parsing, chat

## Tài liệu chi tiết

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Kiến trúc hệ thống
- [SETUP.md](./SETUP.md) - Hướng dẫn cài đặt
- [ZALO_BOT_API.md](./ZALO_BOT_API.md) - Zalo Bot API reference
