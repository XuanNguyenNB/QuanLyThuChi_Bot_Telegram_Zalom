# PROJECT SPECIFICATION: Personal Finance Telegram Bot (Zero-Friction)

## 1. Project Overview
Xây dựng một Telegram Bot giúp ghi lại chi tiêu/thu nhập cá nhân hàng ngày với tiêu chí "Zero-Friction" (Không ma sát).
- **Mục tiêu:** Thời gian nhập liệu < 5s.
- **Phong cách:** Minimalist, text-based input, xử lý ngôn ngữ tự nhiên đơn giản.
- **Người dùng:** Cá nhân (Single user hoặc Small group family).

## 2. Tech Stack & Architecture
- **Language:** Python 3.10+
- **Core Lib:** `python-telegram-bot` (v20+, sử dụng `async/await` pattern).
- **Database:** SQLite (Giai đoạn MVP), migrate sang PostgreSQL (Giai đoạn Production).
- **ORM:** SQLAlchemy (Async) hoặc Tortoise-ORM.
- **Data Validation:** Pydantic.
- **Visualization:** `matplotlib` hoặc `QuickChart.io` (để render chart gửi về tele).
- **Hosting Strategy:** Docker container.

## 3. Database Schema (Draft)

### Table: Users
- `id` (BigInt, PK): Telegram User ID.
- `username` (String): Telegram username.
- `full_name` (String).
- `created_at` (DateTime).

### Table: Categories (Danh mục)
- `id` (Int, PK).
- `name` (String): Tên danh mục (VD: Ăn uống, Di chuyển, Nhà cửa).
- `keywords` (String/JSON): Các từ khóa để auto-detect (VD: "cafe, cơm, phở" -> Ăn uống).
- `type` (Enum): 'EXPENSE' (Chi) | 'INCOME' (Thu).

### Table: Transactions (Giao dịch)
- `id` (UUID/Int, PK).
- `user_id` (FK -> Users).
- `amount` (Decimal/Float): Số tiền.
- `category_id` (FK -> Categories, Nullable).
- `note` (String): Nội dung ghi chú gốc.
- `date` (DateTime): Thời gian giao dịch.
- `raw_text` (String): Tin nhắn gốc của user.

## 4. Core Features & Logic Flow

### 4.1. Smart Input Parser (Logic quan trọng nhất)
Bot phải lắng nghe mọi tin nhắn văn bản và cố gắng parse theo quy tắc sau:
- **Format:** `[Amount][Suffix] [Note/Category]`
- **Suffix logic:**
    - `k` = 1,000 (VD: 50k -> 50,000)
    - `m` hoặc `tr` = 1,000,000 (VD: 1.5m -> 1,500,000)
    - Không suffix -> Giữ nguyên.
- **Category Detection:**
    - Dựa vào `keywords` trong bảng Categories để map với `Note`.
    - Nếu không tìm thấy -> Đưa vào danh mục "Uncategorized" (Khác) hoặc hỏi lại user bằng Inline Button.
- **Ví dụ inputs:**
    - `50k cafe` -> Amount: 50,000, Note: cafe, Category: Ăn uống (Auto).
    - `2tr tiền nhà` -> Amount: 2,000,000, Note: tiền nhà, Category: Nhà cửa.
    - `10k gui xe` -> Amount: 10,000, Note: gui xe, Category: Di chuyển.

### 4.2. Reporting
- Command `/today`: Tổng thu/chi ngày hôm nay.
- Command `/month`:
    - Tổng thu/chi tháng hiện tại.
    - Breakdown theo Category (Top 3 tốn kém nhất).
    - (Optional) Gửi 1 ảnh Pie Chart.

### 4.3. Data Export
- Command `/export`: Xuất file .CSV lịch sử giao dịch và gửi qua chat.

## 5. Coding Standards & Instructions for AI
Khi generate code, hãy tuân thủ các quy tắc sau:
1.  **Architecture:** Sử dụng kiến trúc tách biệt (Separation of Concerns).
    - `bot.py`: Xử lý Telegram handlers.
    - `services.py`: Xử lý logic nghiệp vụ (Parse text, tính toán).
    - `models.py`: Định nghĩa DB schema.
    - `utils.py`: Các hàm phụ trợ (Format tiền tệ, Date time).
2.  **Type Hinting:** Bắt buộc sử dụng Python Type Hints đầy đủ.
3.  **Error Handling:** Luôn bọc các external call trong try/except. Nếu lỗi, log ra console và báo user một cách thân thiện ("Em chưa hiểu ý anh, thử lại nhé").
4.  **Environment:** Sử dụng `python-dotenv` để load `TELEGRAM_TOKEN` và `DB_URL`.
5.  **Language:** Code comment bằng tiếng Anh, nhưng Bot reply user bằng tiếng Việt.

## 6. Implementation Steps (Prompting Guide)
1.  **Step 1:** Setup Project structure, `requirements.txt`, và `models.py` (SQLAlchemy).
2.  **Step 2:** Viết hàm `parse_message(text: str)` trong `services.py` để xử lý logic "50k -> 50000". Viết Unit Test cho hàm này ngay lập tức.
3.  **Step 3:** Setup `bot.py` với `python-telegram-bot`, kết nối handler text message với hàm save transaction.
4.  **Step 4:** Implement Reporting (Text summary trước, Chart sau).
5.  **Step 5:** Dockerize.