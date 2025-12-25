# Personal Finance Telegram Bot 💰

Bot Telegram giúp ghi chép chi tiêu/thu nhập cá nhân với tiêu chí **Zero-Friction** - nhập liệu dưới 5 giây.

## Features

- ✅ **Smart Input Parser**: Gõ tự nhiên như `50k cafe`, `2tr tiền nhà`
- 🏷️ **Auto Category Detection**: Tự động phân loại dựa trên từ khóa
- 📊 **Daily/Monthly Reports**: Xem tổng chi tiêu theo ngày/tháng
- 📄 **CSV Export**: Xuất dữ liệu ra file CSV

## Quick Start

### 1. Clone & Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Telegram Bot Token
# Get token from @BotFather on Telegram
```

### 3. Run

```bash
python run.py
```

## Usage

### Record Expenses
Just send a message with amount and description:

| Input | Amount | Category |
|-------|--------|----------|
| `50k cafe` | 50,000₫ | Ăn uống |
| `2tr tiền nhà` | 2,000,000₫ | Nhà cửa |
| `10k gửi xe` | 10,000₫ | Di chuyển |
| `1.5m điện` | 1,500,000₫ | Nhà cửa |

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Bắt đầu sử dụng bot |
| `/today` | Xem chi tiêu hôm nay |
| `/month` | Xem chi tiêu tháng này |
| `/export` | Xuất file CSV |
| `/help` | Xem hướng dẫn |

## Project Structure

```
├── src/
│   ├── __init__.py
│   ├── bot.py          # Telegram handlers
│   ├── models.py       # SQLAlchemy models
│   ├── services.py     # Business logic
│   └── utils.py        # Helper functions
├── tests/
│   └── test_services.py
├── .env.example
├── requirements.txt
├── run.py
└── README.md
```

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot** v20+ (async)
- **SQLAlchemy** (async) + SQLite
- **Pydantic** for validation

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT
