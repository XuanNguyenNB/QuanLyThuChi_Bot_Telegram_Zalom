# Tính năng chi tiết

## 1. Ghi chi tiêu thông minh

### Cú pháp hỗ trợ
```
cafe 50           → 50,000₫ (tự thêm k)
grab 35k          → 35,000₫
tiền nhà 2tr      → 2,000,000₫
bánh mì 20 nghìn  → 20,000₫
ăn sáng 15,5k     → 15,500₫
50 cafe           → 50,000₫ (đảo vị trí OK)
```

### AI Parsing
Bot dùng Gemini AI để hiểu ngữ cảnh:
```
"mua bánh mì cho mẹ 25k"
→ amount: 25,000
→ note: "mua bánh mì cho mẹ"
→ category: "Người thân" hoặc "Ăn uống"
```

### Multiple transactions
```
"cafe 50 và bánh mì 20"
→ Ghi 2 giao dịch riêng biệt
```

## 2. Ghi thu nhập

### Từ khóa nhận diện thu nhập
- lương, salary
- thưởng, bonus
- bán, sold
- thu, income
- nhận

### Ví dụ
```
"lương tháng 12 15tr"
→ Thu: 15,000,000₫
→ Category: Lương

"bán điện thoại cũ 2tr"
→ Thu: 2,000,000₫
→ Category: Bán hàng
```

## 3. Voice Message

### Flow
1. User gửi voice message
2. Bot download audio file
3. Gemini transcribe: audio → text
4. AI parse: text → transaction
5. Bot hiển thị preview:
   ```
   🎤 Đã nhận voice:
   💰 50,000₫
   📝 cafe
   🏷️ Ăn uống

   Chọn danh mục hoặc:
   [Xác nhận ✅] [Hủy ❌]
   ```
6. User chọn category hoặc confirm
7. Bot lưu transaction

### Trường hợp category không rõ
Bot hiển thị inline keyboard để user chọn:
```
[Ăn uống] [Di chuyển] [Mua sắm]
[Giải trí] [Sức khỏe] [Học tập]
...
```

## 4. Smart Query (Hỏi đáp)

### Cú pháp câu hỏi
Bot nhận diện câu hỏi qua:
- Dấu `?` cuối câu
- Từ khóa: bao nhiêu, mấy, chi tiêu, tổng, thống kê

### Ví dụ
```
"Tháng này chi bao nhiêu?"
→ Tổng chi tiêu tháng này

"Tuần này chi cafe bao nhiêu?"
→ Tổng chi cho keyword "cafe" trong tuần

"Hôm nay ăn uống hết bao nhiêu?"
→ Tổng chi category "Ăn uống" hôm nay
```

### Time ranges hỗ trợ
- `hôm nay`, `today`
- `tuần này`, `week`
- `tháng này`, `month`
- `năm nay`, `year`
- `tất cả`, `all`

## 5. Category Learning (RAG-like)

### Cách hoạt động
1. User ghi: `starbucks 80k`
2. Bot không biết category → hiển thị buttons
3. User chọn "Ăn uống"
4. Bot lưu mapping: `starbucks → Ăn uống` cho user này
5. Lần sau: `starbucks 100k` → tự động "Ăn uống"

### Storage
```python
class UserKeyword(Base):
    user_id: int      # FK to User.id
    category_id: int  # FK to Category.id
    keyword: str      # "starbucks"
```

### Lookup priority
1. User's learned keywords
2. AI suggestion
3. Default keyword matching
4. "Khác" category

## 6. Đồng bộ Telegram ↔ Zalo

### Liên kết tài khoản
```
# Trên Telegram:
/link 0901234567

# Trên Zalo:
/link 0901234567
```

### Kết quả
- Cùng số điện thoại → cùng user_id trong DB
- Transactions từ cả 2 platform đều ghi vào cùng 1 user
- `/today`, `/month` hiển thị tổng hợp từ cả 2

### Bảo mật
- Chỉ có 2 users (owner), không cần xác thực phức tạp
- Ai biết số điện thoại có thể link (chấp nhận được cho use case này)

## 7. Reports

### /today
```
📅 Hôm nay (25/12/2025)

💰 Thu: 0₫

💸 Chi: 150,000₫
📝 Chi tiết (3 giao dịch):
  • 50k - cafe (Ăn uống)
  • 80k - grab (Di chuyển)
  • 20k - bánh mì (Ăn uống)

📉 Thâm hụt: -150,000₫
```

### /month
```
📊 Tháng 12/2025

💰 Thu: 15,000,000₫
💸 Chi: 8,500,000₫

📈 Thặng dư: +6,500,000₫
```

### /insights
```
💡 PHÂN TÍCH CHI TIÊU

📊 Tháng này: 8,500,000₫
📊 Tháng trước: 9,200,000₫
📉 Xu hướng: Giảm

💰 Trung bình/ngày: 340,000₫

🏆 Top danh mục:
1. Ăn uống: 3,500,000₫
2. Di chuyển: 2,000,000₫
3. Mua sắm: 1,500,000₫
```

## 8. AI Fun Comments

### Khi ghi giao dịch
Bot tạo comment vui dựa trên context:
```
✅ Đã ghi: 50,000₫
📝 cafe
🏷️ Ăn uống

💬 "Ly cafe sáng giúp tỉnh táo làm việc nè! ☕"
```

### Ví dụ comments
- Chi cafe: "Năng lượng để chiến đấu cả ngày! ☕"
- Chi grab: "Di chuyển an toàn, tiết kiệm thời gian! 🚗"
- Thu lương: "Chúc mừng! Tiền về rồi, nhớ tiết kiệm nha! 💰"

## 9. Export CSV

### Lệnh
```
/export
```

### Output format
```csv
Ngày,Số tiền,Ghi chú,Danh mục,Loại
2025-12-25,50000,cafe,Ăn uống,expense
2025-12-25,80000,grab,Di chuyển,expense
2025-12-24,15000000,lương tháng 12,Lương,income
```

## 10. Casual Chat

### Khi bot không hiểu
Thay vì "Không hiểu", bot trò chuyện tự nhiên:
```
User: "hello"
Bot: "Chào bạn! Mình là bot ghi chép chi tiêu. 
      Bạn có thể ghi như: cafe 50k hoặc hỏi: tháng này chi bao nhiêu?"
```

### Personality
- Thân thiện, vui vẻ
- Hướng dẫn cách dùng bot
- Không trả lời off-topic (chính trị, nhạy cảm)
