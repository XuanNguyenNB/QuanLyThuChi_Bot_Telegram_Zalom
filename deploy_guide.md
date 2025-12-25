# Hướng dẫn Deploy Bot lên VPS Ubuntu với Backup Google Drive

## Bước 5: Cài đặt Google Drive API dependencies

```bash
# Cài thêm Google Drive API
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Bước 6: Thiết lập Google Drive API

### 6.1 Tạo Google Cloud Project và enable Drive API
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới hoặc chọn project có sẵn
3. Enable Google Drive API:
   - Vào "APIs & Services" > "Library"
   - Tìm "Google Drive API" và click "Enable"

### 6.2 Tạo OAuth2 Credentials
1. Vào "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Chọn "Desktop application"
4. Đặt tên: "Expense Bot Backup"
5. Download file JSON credentials

### 6.3 Upload credentials lên VPS
```bash
# Upload file credentials.json lên VPS
scp credentials.json botuser@your_vps_ip:/home/botuser/

# Hoặc tạo file trực tiếp trên VPS
nano /home/botuser/credentials.json
# Paste nội dung file JSON vào đây
```

## Bước 7: Upload backup script lên VPS

```bash
# Tạo thư mục backup
mkdir -p /home/botuser/backups

# Upload backup script
# (Copy nội dung từ backup_script.py)
nano /home/botuser/backup_script.py
# Paste code backup script

# Cấp quyền thực thi
chmod +x /home/botuser/backup_script.py
```

## Bước 8: Test backup script

```bash
# Chạy bot trước để tạo database
cd /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom
source venv/bin/activate
python run.py
# Ctrl+C để dừng sau khi bot khởi động thành công

# Test backup script
python /home/botuser/backup_script.py
```

**Lần đầu chạy sẽ mở browser để authorize Google Drive**

## Bước 9: Thiết lập Cron Job cho backup tự động

```bash
# Mở crontab
crontab -e

# Thêm dòng sau để backup mỗi 6 tiếng
0 */6 * * * /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/venv/bin/python /home/botuser/backup_script.py >> /home/botuser/backup.log 2>&1

# Lưu và thoát (Ctrl+X, Y, Enter)
```

## Bước 10: Tạo Systemd Service

```bash
# Tạo service file
sudo nano /etc/systemd/system/expense-bot.service
```

Paste nội dung từ file `systemd_service.txt`:

```ini
[Unit]
Description=Telegram & Zalo Expense Bot
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

StandardOutput=journal
StandardError=journal
SyslogIdentifier=expense-bot

[Install]
WantedBy=multi-user.target
```

## Bước 11: Khởi động và enable service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (tự khởi động khi boot)
sudo systemctl enable expense-bot

# Khởi động service
sudo systemctl start expense-bot

# Kiểm tra status
sudo systemctl status expense-bot

# Xem logs
sudo journalctl -u expense-bot -f
```

## Bước 12: Kiểm tra và monitoring

### Kiểm tra bot hoạt động
```bash
# Xem logs realtime
sudo journalctl -u expense-bot -f

# Kiểm tra backup logs
tail -f /home/botuser/backup.log

# Kiểm tra cron jobs
crontab -l
```

### Các lệnh quản lý service
```bash
# Dừng bot
sudo systemctl stop expense-bot

# Khởi động lại bot
sudo systemctl restart expense-bot

# Vô hiệu hóa auto-start
sudo systemctl disable expense-bot
```

## Bước 13: Bảo mật VPS (Khuyến nghị)

```bash
# Cập nhật firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 22

# Đổi port SSH (tùy chọn)
sudo nano /etc/ssh/sshd_config
# Thay đổi Port 22 thành port khác
sudo systemctl restart ssh

# Tạo SSH key thay vì password
ssh-keygen -t rsa -b 4096
```

## Troubleshooting

### Bot không khởi động
```bash
# Kiểm tra logs chi tiết
sudo journalctl -u expense-bot --no-pager

# Kiểm tra file .env
cat /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/.env

# Test chạy manual
cd /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom
source venv/bin/activate
python run.py
```

### Backup không hoạt động
```bash
# Test backup manual
python /home/botuser/backup_script.py

# Kiểm tra Google Drive credentials
ls -la /home/botuser/credentials.json
ls -la /home/botuser/token.pickle

# Kiểm tra cron logs
grep CRON /var/log/syslog
```

### Database issues
```bash
# Kiểm tra database file
ls -la /home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/expense_bot.db

# Backup manual database
cp expense_bot.db expense_bot_backup_$(date +%Y%m%d_%H%M%S).db
```

## Tóm tắt

✅ **Đã hoàn thành:**
- Deploy bot lên VPS Ubuntu
- Thiết lập backup tự động mỗi 6 tiếng
- Upload backup lên Google Drive
- Bot chạy như service tự động khởi động
- Logging và monitoring

🔄 **Backup schedule:** Mỗi 6 tiếng (0:00, 6:00, 12:00, 18:00)
📁 **Backup location:** Google Drive của bạn
🔧 **Service management:** `systemctl` commands
📊 **Monitoring:** `journalctl` và backup logs
