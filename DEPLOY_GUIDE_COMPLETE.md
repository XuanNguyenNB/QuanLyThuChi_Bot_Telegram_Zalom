# Hướng dẫn Deploy Bot Telegram & Zalo lên VPS Ubuntu

## Tổng quan
Bot này bao gồm:
- Telegram Bot để ghi chép thu chi
- Zalo Bot với tính năng tương tự
- AI service sử dụng Google Gemini
- Backup tự động lên Google Drive
- Database SQLite

## Files cần thiết cho deploy
- `run.py` - Entry point chạy cả 2 bot
- `src/` - Source code chính
- `backup_script.py` - Script backup database
- `systemd_service.txt` - Service configuration
- `requirements.txt` - Dependencies
- `.env.example` - Template environment variables

---

## Bước 1: Chuẩn bị VPS Ubuntu

### 1.1 Cập nhật hệ thống
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Cài đặt Python và dependencies
```bash
sudo apt install python3 python3-pip python3-venv git -y
```

### 1.3 Tạo user cho bot
```bash
sudo useradd -m -s /bin/bash botuser
sudo passwd botuser
sudo usermod -aG sudo botuser
```

---

## Bước 2: Clone và setup project

### 2.1 Đăng nhập user botuser
```bash
su - botuser
```

### 2.2 Clone repository
```bash
cd /home/botuser
git clone https://github.com/XuanNguyenNB/QuanLyThuChi_Bot_Telegram_Zalom.git
cd QuanLyThuChi_Bot_Telegram_Zalom
```

### 2.3 Tạo virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Bước 3: Cấu hình Environment Variables

### 3.1 Tạo file .env
```bash
cp .env.example .env
nano .env
```

### 3.2 Điền thông tin vào .env
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

---

## Bước 4: Tạo thư mục logs
```bash
mkdir -p /home/botuser/logs
mkdir -p /home/botuser/backups
```

---

## Bước 5: Test bot
```bash
cd /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom
source venv/bin/activate
python run.py
```

Nhấn Ctrl+C sau khi thấy bot khởi động thành công.

---

## Bước 6: Setup Google Drive Backup (Tùy chọn)

### 6.1 Tạo Google Cloud Project
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới
3. Enable Google Drive API
4. Tạo OAuth 2.0 credentials (Desktop application)
5. Download file `credentials.json`

### 6.2 Upload credentials lên VPS
```bash
# Upload file credentials.json vào /home/botuser/credentials.json
nano /home/botuser/credentials.json
# Paste nội dung file credentials.json
```

### 6.3 Copy backup script
```bash
cp backup_script.py /home/botuser/backup_script.py
```

### 6.4 Test backup script
```bash
python /home/botuser/backup_script.py
```

Lần đầu chạy sẽ yêu cầu authorization:
1. Copy URL hiển thị
2. Mở trên browser và authorize
3. Copy authorization code
4. Paste vào terminal

---

## Bước 7: Tạo Systemd Service

### 7.1 Tạo service file
```bash
sudo nano /etc/systemd/system/finance_bot.service
```

### 7.2 Paste nội dung từ systemd_service.txt
```ini
# Systemd service file for Finance Bot
# Save as: /etc/systemd/system/finance_bot.service

[Unit]
Description=Telegram & Zalo Finance Bot
After=network.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/QuanLyThuChi_Bot_Telegram_Zalom
Environment=PATH=/home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/venv/bin
ExecStart=/home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/venv/bin/python run.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=finance_bot

[Install]
WantedBy=multi-user.target
```

### 7.3 Enable và start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable finance_bot.service
sudo systemctl start finance_bot.service
```

### 7.4 Kiểm tra status
```bash
sudo systemctl status finance_bot.service
```

---

## Bước 8: Setup Cron Job cho Backup (Tùy chọn)

### 8.1 Mở crontab
```bash
crontab -e
```

### 8.2 Thêm backup job (mỗi 6 tiếng)
```bash
0 */6 * * * /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/venv/bin/python /home/botuser/backup_script.py >> /home/botuser/backup.log 2>&1
```

---

## Bước 9: Monitoring và Debug

### 9.1 Xem log service
```bash
# Xem log realtime
journalctl -u finance_bot.service -f

# Xem log từ hôm qua
journalctl -u finance_bot.service --since "yesterday"

# Xem log chi tiết
tail -f /home/botuser/logs/telegram_bot.log
tail -f /home/botuser/logs/zalo_bot.log
```

### 9.2 Restart service
```bash
sudo systemctl restart finance_bot.service
```

### 9.3 Stop service
```bash
sudo systemctl stop finance_bot.service
```

---

## Bước 10: Update Bot

### 10.1 Pull code mới
```bash
cd /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom
git pull origin main
```

### 10.2 Update dependencies (nếu cần)
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 10.3 Restart service
```bash
sudo systemctl restart finance_bot.service
```

---

## Troubleshooting

### Bot tự tắt sau một thời gian
```bash
# Kiểm tra log lỗi
journalctl -u finance_bot.service --since "yesterday" | grep -i error

# Kiểm tra memory usage
free -h
df -h
```

### Lỗi kết nối database
```bash
# Kiểm tra file database
ls -la /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/finance_bot.db

# Kiểm tra quyền file
chmod 664 /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/finance_bot.db
```

### Lỗi Google Drive backup
```bash
# Xóa token cũ và authorize lại
rm /home/botuser/token.json
python /home/botuser/backup_script.py
```

### Lỗi Telegram/Zalo API
- Kiểm tra token trong file .env
- Kiểm tra kết nối internet
- Kiểm tra rate limit

---

## Cấu trúc thư mục sau khi deploy

```
/home/botuser/
├── QuanLyThuChi_Bot_Telegram_Zalom/    # Main project
│   ├── src/                            # Source code
│   ├── venv/                           # Virtual environment
│   ├── run.py                          # Entry point
│   ├── .env                            # Environment variables
│   └── finance_bot.db                  # SQLite database
├── logs/                               # Log files
│   ├── telegram_bot.log
│   ├── zalo_bot.log
│   ├── ai_service.log
│   └── message_handler.log
├── backups/                            # Local backups
├── backup_script.py                    # Backup script
├── credentials.json                    # Google Drive credentials
├── token.json                          # Google Drive token
└── backup.log                          # Backup log
```

---

## Lệnh hữu ích

```bash
# Xem tất cả services đang chạy
systemctl list-units --type=service --state=running

# Xem resource usage
htop

# Xem disk usage
du -sh /home/botuser/*

# Backup manual
python /home/botuser/backup_script.py

# Test bot manual
cd /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom && source venv/bin/activate && python run.py
```
