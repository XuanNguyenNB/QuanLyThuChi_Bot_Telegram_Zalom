"""
AI Service using Google Gemini for smart parsing and category detection.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Available categories for AI to choose from
CATEGORIES = [
    # Chi tiêu - sinh hoạt
    "Chợ/Siêu thị",
    "Ăn uống", 
    "Di chuyển",
    # Chi phí phát sinh
    "Cho vay",
    "Mua sắm",
    "Giải trí",
    "Làm đẹp",
    "Sức khỏe",
    "Từ thiện",
    # Chi phí cố định
    "Hóa đơn",
    "Người thân",
    # Đầu tư - tiết kiệm
    "Đầu tư",
    "Học tập",
    # Thu nhập
    "Lương",
    "Thưởng",
    "Thu khác",
    # Khác
    "Khác"
]

SYSTEM_PROMPT = """Bạn là một trợ lý phân tích chi tiêu thông minh. Nhiệm vụ của bạn là trích xuất thông tin giao dịch tài chính từ tin nhắn tiếng Việt tự nhiên.

QUAN TRỌNG - Quy tắc parse:
1. Số tiền có thể ở BẤT KỲ vị trí nào trong câu (đầu, giữa, cuối)
2. Hậu tố tiền: k/K = nghìn (x1000), tr/m/M = triệu (x1000000), đ/d/dong = đơn vị
3. Số tiền có thể viết: "20k", "20K", "20 nghìn", "20000", "20.000"
4. **QUAN TRỌNG**: Nếu số tiền KHÔNG có hậu tố và < 1000, mặc định là NGHÌN ĐỒNG
   - "350" = 350,000đ (350k), "80" = 80,000đ (80k), "15" = 15,000đ (15k)
   - Vì ở Việt Nam không ai dùng 350 đồng, 80 đồng nữa
5. Nếu có nhiều giao dịch, tách thành nhiều items
6. Nếu có phép tính (chia đôi, chia 3, /2, trừ vốn...), tính toán số tiền thực tế
7. Mặc định là CHI (expense), chỉ THU (income) nếu rõ ràng là thu nhập (bán, nhận, lương...)
8. "trừ vốn X" nghĩa là: số tiền nhận - X = lợi nhuận thực

Danh mục có sẵn: """ + ", ".join(CATEGORIES) + """

Trả về JSON:
{
  "transactions": [
    {
      "amount": <số tiền đã tính, kiểu number>,
      "note": "<mô tả ngắn gọn>",
      "category": "<tên danh mục phù hợp nhất>",
      "type": "expense" hoặc "income"
    }
  ],
  "understood": true/false,
  "message": "<lý do nếu không hiểu>"
}

VÍ DỤ PARSE:
- "mua bánh mì 20k" -> amount=20000, note="mua bánh mì", category="Ăn uống"
- "20k bánh mì" -> amount=20000, note="bánh mì", category="Ăn uống"  
- "cafe 50" -> amount=50000, note="cafe", category="Ăn uống" (50 = 50k)
- "đổ xăng 100" -> amount=100000, note="đổ xăng", category="Di chuyển" (100 = 100k)
- "grab 35" -> amount=35000, note="grab", category="Di chuyển" (35 = 35k)
- "siêu thị 500" -> amount=500000, note="siêu thị", category="Chợ/Siêu thị" (500 = 500k)
- "ăn trưa 150k chia đôi" -> amount=75000, note="ăn trưa", category="Ăn uống"
- "lương tháng 12 15tr" -> amount=15000000, note="lương tháng 12", category="Lương", type="income"
- "up x7u colorvs 350 trừ vốn 80" -> amount=270000, note="up x7u colorvs", category="Lương", type="income" (350k - 80k = 270k lợi nhuận)
- "bán gói gpt plus 50" -> amount=50000, note="bán gói gpt plus", category="Lương", type="income"

NẾU KHÔNG TÌM THẤY SỐ TIỀN trong tin nhắn -> understood=false
"""


@dataclass
class AITransaction:
    """Parsed transaction from AI"""
    amount: float
    note: str
    category: str
    type: str  # "expense" or "income"


@dataclass
class AIParseResult:
    """Result from AI parsing"""
    transactions: List[AITransaction]
    understood: bool
    message: Optional[str] = None
    raw_response: Optional[str] = None


def is_ai_enabled() -> bool:
    """Check if AI service is configured"""
    return bool(GEMINI_API_KEY)


async def parse_with_ai(text: str) -> AIParseResult:
    """
    Use Gemini AI to parse user message into transactions.
    
    Args:
        text: Raw user message
        
    Returns:
        AIParseResult with parsed transactions
    """
    if not is_ai_enabled():
        return AIParseResult(
            transactions=[],
            understood=False,
            message="AI chưa được cấu hình"
        )
    
    try:
        # Combine system prompt with user message
        full_prompt = f"""{SYSTEM_PROMPT}

---

Phân tích tin nhắn chi tiêu sau và trả về JSON:

Tin nhắn: "{text}"

Chỉ trả về JSON, không giải thích thêm."""

        # Use sync API with asyncio.to_thread to avoid event loop conflicts
        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        
        response_text = response.text.strip()
        logger.info(f"AI response: {response_text}")
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (```json and ```)
            response_text = "\n".join(lines[1:-1])
        
        # Parse JSON response
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                return AIParseResult(
                    transactions=[],
                    understood=False,
                    message="Không thể parse response từ AI",
                    raw_response=response_text
                )
        
        # Convert to AITransaction objects
        transactions = []
        for tx in data.get("transactions", []):
            transactions.append(AITransaction(
                amount=float(tx.get("amount", 0)),
                note=tx.get("note", ""),
                category=tx.get("category", "Khác"),
                type=tx.get("type", "expense")
            ))
        
        return AIParseResult(
            transactions=transactions,
            understood=data.get("understood", True),
            message=data.get("message"),
            raw_response=response_text
        )
        
    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        return AIParseResult(
            transactions=[],
            understood=False,
            message=f"Lỗi AI: {str(e)}"
        )


def get_category_name_from_ai(ai_category: str) -> str:
    """Map AI category to actual category name"""
    # Normalize and find best match
    ai_cat_lower = ai_category.lower().strip()
    
    for cat in CATEGORIES:
        if cat.lower() == ai_cat_lower:
            return cat
    
    # Fuzzy matching
    for cat in CATEGORIES:
        if ai_cat_lower in cat.lower() or cat.lower() in ai_cat_lower:
            return cat
    
    return "Khác"


def is_question(text: str) -> bool:
    """Check if text is a question rather than a transaction"""
    text_lower = text.lower().strip()
    
    # Question patterns
    question_words = [
        'bao nhiêu', 'mấy', 'sao', 'tại sao', 'như thế nào', 'thế nào',
        'ở đâu', 'khi nào', 'ai', 'gì', 'cái gì', 'là gì',
        'có thể', 'làm sao', 'giúp', 'hỏi', 'cho hỏi',
        'tháng này', 'hôm nay', 'tuần này', 'chi tiêu',
        'tổng', 'trung bình', 'nhiều nhất', 'ít nhất'
    ]
    
    # Check if starts with question word or contains question mark
    if text.endswith('?'):
        return True
    
    for word in question_words:
        if word in text_lower:
            return True
    
    return False


@dataclass
class QueryIntent:
    """Parsed query intent from natural language"""
    is_query: bool = False
    time_range: str = "all"  # today, week, month, year, all
    category: Optional[str] = None
    keyword: Optional[str] = None


async def parse_query_intent(text: str) -> QueryIntent:
    """Use AI to parse a natural language query about spending"""
    if not is_ai_enabled():
        return QueryIntent(is_query=False)
    
    try:
        prompt = f"""Phân tích câu hỏi về chi tiêu sau và trả về JSON.

Câu hỏi: "{text}"

Trả về JSON với format:
{{
    "is_query": true/false,  // true nếu đây là câu hỏi về thống kê/tổng tiền
    "time_range": "today" | "week" | "month" | "year" | "all",
    "category": "tên danh mục nếu có" | null,
    "keyword": "từ khóa tìm trong ghi chú" | null
}}

Ví dụ:
- "tháng này cho người yêu bao nhiêu" → {{"is_query": true, "time_range": "month", "category": "Người thân", "keyword": "người yêu"}}
- "tuần này cafe bao nhiêu" → {{"is_query": true, "time_range": "week", "category": "Ăn uống", "keyword": "cafe"}}
- "năm nay chi bao nhiêu" → {{"is_query": true, "time_range": "year", "category": null, "keyword": null}}
- "từ đầu tới giờ cho bố mẹ bao nhiêu" → {{"is_query": true, "time_range": "all", "category": "Người thân", "keyword": "bố mẹ"}}
- "hôm nay tiêu gì vậy" → {{"is_query": true, "time_range": "today", "category": null, "keyword": null}}

Danh mục có sẵn: {', '.join(CATEGORIES)}

CHỈ trả về JSON, không giải thích."""

        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=200,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        response_text = response.text.strip()
        # Clean up markdown if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        
        return QueryIntent(
            is_query=data.get("is_query", False),
            time_range=data.get("time_range", "all"),
            category=data.get("category"),
            keyword=data.get("keyword")
        )
        
    except Exception as e:
        logger.error(f"AI query parse error: {e}")
        return QueryIntent(is_query=False)


async def answer_question(text: str, spending_context: str = "") -> str:
    """Use AI to answer a natural language question about spending"""
    if not is_ai_enabled():
        return "AI chưa được cấu hình. Vui lòng thử lại sau."
    
    try:
        qa_prompt = f"""Bạn là trợ lý tài chính cá nhân thông minh. Trả lời câu hỏi của người dùng một cách ngắn gọn và hữu ích.

Dữ liệu chi tiêu của người dùng:
{spending_context}

Câu hỏi: "{text}"

Quy tắc:
- Trả lời ngắn gọn, thân thiện
- Dùng số liệu cụ thể nếu có
- Đưa ra gợi ý thiết thực
- Nếu không có dữ liệu, hãy nói rõ
- Trả lời bằng tiếng Việt"""

        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                qa_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=500,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"AI Q&A error: {e}")
        return f"Xin lỗi, mình không thể trả lời lúc này. Hãy thử lại sau nhé!"


async def generate_transaction_comment(amount: float, note: str, category: str, tx_type: str = "expense") -> str:
    """Generate a fun/engaging comment for a transaction"""
    if not is_ai_enabled():
        return ""
    
    try:
        type_text = "thu nhập" if tx_type == "income" else "chi tiêu"
        
        prompt = f"""Tạo một câu bình luận ngắn, vui vẻ về giao dịch sau:
- Loại: {type_text}
- Số tiền: {amount:,.0f}đ
- Mô tả: {note}
- Danh mục: {category}

Quy tắc:
- Chỉ 1 câu ngắn (dưới 15 từ)
- Vui vẻ, thân thiện, có thể hài hước nhẹ
- Dùng 1-2 emoji phù hợp
- Nếu là thu nhập: chúc mừng, động viên
- Nếu là chi tiêu: nhận xét nhẹ nhàng, không phán xét
- Trả lời bằng tiếng Việt
- CHỈ trả về câu bình luận, không giải thích"""

        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.9,
                    max_output_tokens=50,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"AI comment error: {e}")
        return ""


async def transcribe_voice(audio_bytes: bytes) -> Optional[str]:
    """Transcribe voice message to text using Gemini"""
    if not is_ai_enabled():
        return None
    
    try:
        # Upload audio data
        audio_part = {
            "mime_type": "audio/ogg",
            "data": audio_bytes
        }
        
        prompt = """Chuyển đoạn ghi âm này thành văn bản tiếng Việt.
Chỉ trả về văn bản được nói, không thêm gì khác.
Nếu không nghe rõ hoặc không có tiếng nói, trả về: [không nghe rõ]"""
        
        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                [prompt, audio_part],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=500,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        text = response.text.strip()
        if text and text != "[không nghe rõ]":
            return text
        return None
        
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        return None


async def chat_casual(text: str) -> str:
    """Use AI for casual conversation when message is not about transactions"""
    if not is_ai_enabled():
        return "Chào bạn! Mình là bot ghi chép chi tiêu. Gõ như: `cafe 50` để ghi chi tiêu nhé!"
    
    try:
        chat_prompt = f"""Bạn là một trợ lý ghi chép chi tiêu thân thiện.

Người dùng vừa nhắn: "{text}"

Đây KHÔNG phải là tin nhắn về chi tiêu/thu nhập. Hãy trả lời thân thiện, ngắn gọn.

Quy tắc:
- Trả lời tự nhiên, vui vẻ như bạn bè
- Ngắn gọn (1-2 câu)
- Có thể dùng emoji
- Nếu phù hợp, nhắc nhẹ về chức năng ghi chi tiêu
- Trả lời bằng tiếng Việt
- KHÔNG trả lời các câu hỏi nhạy cảm/không phù hợp"""

        def _sync_generate():
            model = genai.GenerativeModel('gemini-2.0-flash')
            return model.generate_content(
                chat_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.8,
                    max_output_tokens=150,
                )
            )
        
        response = await asyncio.to_thread(_sync_generate)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return "Chào bạn! 👋 Mình là bot ghi chi tiêu. Gõ như: `cafe 50` nhé!"
