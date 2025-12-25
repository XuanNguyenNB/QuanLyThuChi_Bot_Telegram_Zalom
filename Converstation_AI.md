Bạn là 1 lập trình viên lâu năm chuyên nghiệp, muốn tạo 1 bot telegram ghi lại các chi tiêu thu nhập hàng ngày.

Hãy nói ra suy nghĩ của bạn

Chào bạn, với tư cách là một người làm kỹ thuật lâu năm ("Senior Dev"), khi tiếp cận bài toán tưởng chừng đơn giản như "làm bot ghi chép chi tiêu", tôi sẽ không lao vào code ngay. Tôi sẽ tư duy theo hướng Product Mindset (Tư duy sản phẩm) kết hợp với Technical Architecture (Kiến trúc kỹ thuật) để đảm bảo bot này phải: Nhanh, Tiện, và Bền bỉ.

Dưới đây là dòng suy nghĩ (monologue) của tôi khi thiết kế con bot này:

1. Phân tích nỗi đau (Pain Points) & Yêu cầu cốt lõi
"Tại sao các app quản lý tài chính trên store đều thất bại với mình?

Quá nặng nề: Mở app, đợi loading, quảng cáo, bấm 3-4 bước mới nhập được '50k tiền cà phê'.

Rời rạc: Nó không nằm ở nơi mình hay chat (Telegram).

Dữ liệu không phải của mình: App đóng cửa là mất data, hoặc export ra CSV rất cực.

-> Mục tiêu tối thượng: 'Frictionless' (Không ma sát). Thời gian từ lúc rút điện thoại ra đến lúc ghi xong phải dưới 5 giây. Nếu quá 5 giây, sau 1 tuần mình sẽ lười và bỏ ngay."

2. Thiết kế trải nghiệm (UX Flow)
"Đừng bắt người dùng (chính là mình) phải gõ theo cú pháp cứng nhắc như /add 50000 an_sang. Quá phiền phức.

Input tự nhiên: Mình muốn gõ 50k cafe hoặc 50 an sang hoặc 2tr điện. Bot phải tự hiểu.

Categories (Danh mục): Đừng bắt chọn danh mục mỗi lần nhập. Hãy dùng AI đơn giản hoặc keyword matching để tự gán (ví dụ: thấy chữ 'cafe' -> auto vào mục 'Ăn uống'). Nếu bot không hiểu, lúc đó mới hiện Inline Button để mình chọn nhanh.

Feedback: Ghi xong phải báo ngay số dư hiện tại trong ví hoặc tổng chi tiêu hôm nay để mình 'đau lòng' mà bớt tiêu lại."

3. Lựa chọn Tech Stack (Công nghệ)
"Bài toán nhỏ nhưng kiến trúc phải sạch sẽ, dễ mở rộng (scale) sau này lỡ có share cho vợ dùng chung."

Ngôn ngữ: Python. Tại sao? Vì thư viện python-telegram-bot rất mạnh, hỗ trợ Async tốt. Quan trọng hơn, sau này muốn phân tích dữ liệu (Data Analysis) hay gắn thêm AI thì Python là trùm.

Database:

Option 1 (Lười): Google Sheets. Dễ xem, dễ share. NHƯNG API chậm, delay 1-2s là không chấp nhận được với trải nghiệm 'real-time'.

Option 2 (Chuẩn): PostgreSQL (hoặc SQLite nếu chạy local). Mình sẽ chọn Postgres (dùng gói free của Supabase hoặc Neon). Đảm bảo tính toàn vẹn dữ liệu (ACID).

Hosting: Không chạy trên laptop cá nhân. Đẩy lên VPS (tôi có sẵn Droplet 5$) hoặc dùng Docker deploy lên một serverless platform. Bot phải sống 24/7.

4. Luồng xử lý dữ liệu (Data Flow & Logic)
Tôi sẽ chia làm 3 module chính:

A. Input Parser (Bộ phân tích đầu vào):

Dùng Regex đơn giản trước: [Số tiền] [Nội dung].

Xử lý hậu tố: k = 000, tr/m = 000,000.

Ví dụ: 50k -> 50000.

Advanced: Sau này rảnh tích hợp NLP nhẹ hoặc LLM API (Gemini/OpenAI) để parse những câu phức tạp hơn như "Hôm nay đi siêu thị hết 500k, trong đó 200k mua thịt, 300k mua bia".

B. Controller (Xử lý nghiệp vụ):

Hàm add_transaction(user_id, amount, category, note, date).

Logic tính toán: Income (+) và Expense (-).

Logic ngân sách (Budget): Nếu chi tiêu tháng này vượt 80% ngân sách -> Gửi cảnh báo đỏ 🔴.

C. Reporting (Báo cáo):

Không text dài dòng. Dùng thư viện matplotlib hoặc quickchart.io vẽ biểu đồ tròn (Pie chart) gửi thẳng ảnh vào chat. Nhìn ảnh 1 giây là hiểu ngay tiền đi về đâu.

Lệnh /today: Tổng thu chi hôm nay.

Lệnh /month: Tổng quan tháng này + Dự báo cuối tháng hết bao nhiêu tiền dựa trên tốc độ tiêu hiện tại.

5. Tính năng "Killer Feature" (Dành cho dân Pro)
"Ghi chép thủ công vẫn là hạ sách. Mình cần tự động hóa."

Tự động sync Google Sheets: Bot lưu vào DB xong, bắn một job background đẩy data lên Google Sheets. Tối về mở Sheets ra xem Dashboard đẹp, vợ vào xem cũng dễ.

Quét QR/Bill: Tích hợp OCR. Chụp ảnh hóa đơn siêu thị, bot tự đọc total và item.

Webhook ngân hàng (Khó nhưng đáng làm): Nếu app ngân hàng có biến động số dư -> bắn noti về điện thoại -> forward tin nhắn đó cho Bot -> Bot tự parse và lưu. Đây mới là cảnh giới cao nhất của lười.

6. Kế hoạch triển khai (Action Plan)
Phase 1 (MVP - 2 tiếng): Bot chạy local, database SQLite, gõ 50k an trua là lưu được. Lệnh /report text đơn giản.

Phase 2 (Cloud & UI - 1 buổi): Đóng gói Docker, deploy lên VPS. Thêm Inline Keyboard chọn danh mục. Vẽ biểu đồ ảnh.

Phase 3 (Integration - Cuối tuần): Kết nối Google Sheets API làm backup.

Câu chốt hạ:
"Code một cái bot không khó, cái khó là code sao cho mình muốn dùng nó mỗi ngày. Sự đơn giản và tốc độ phản hồi là chìa khóa."

Bạn có muốn tôi phác thảo cấu trúc Database (SQL Schema) hoặc đoạn code Python mẫu cho phần xử lý tin nhắn "50k cafe" này không?

dòng suy nghĩ đúng ý tôi đó, hãy tạo 1 file .md để tôi triển khai trong IDE với sự hỗ trợ của AI nhé

Tuyệt vời. Để làm việc hiệu quả với các công cụ AI trong IDE (như GitHub Copilot, Cursor, Windsurf hay ChatGPT), bạn cần một bản Context/Specification thật rõ ràng. AI viết code giỏi hay dở phụ thuộc hoàn toàn vào cái "đề bài" này.

Dưới đây là file PROJECT_SPEC.md. Bạn hãy tạo file này trong thư mục gốc của dự án, mở nó lên để AI đọc, sau đó bắt đầu ra lệnh code.

Markdown
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
Hướng dẫn sử dụng file này với IDE AI (Cursor/VS Code Copilot):
Bước 1: Tạo file PROJECT_SPEC.md và paste nội dung trên vào.

Bước 2: Mở khung chat của AI trong IDE (Cmd+L hoặc Ctrl+L).

Bước 3: Tag file này vào context (gõ @PROJECT_SPEC.md hoặc kéo file vào chat).

Bước 4: Bắt đầu ra lệnh (Prompt):

"Dựa trên file spec @PROJECT_SPEC.md, hãy giúp tôi khởi tạo cấu trúc dự án và viết code cho file models.py sử dụng SQLAlchemy và SQLite trước."