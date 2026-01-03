"""
Handlers cho lệnh /budget - quản lý ngân sách
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..models import get_session
from ..services import (
    get_or_create_user,
    get_user_budgets,
    check_budget_status,
    set_budget,
    parse_message,
    detect_category,
    get_category_by_name,
)
from ..utils import format_currency_full

logger = logging.getLogger(__name__)


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /budget command - set or view budgets"""
    user = update.effective_user
    args = context.args
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Case 1: View budgets (no args)
            if not args:
                budgets = await get_user_budgets(session, db_user.id)
                status = await check_budget_status(session, db_user.id)
                
                if not budgets:
                    await update.message.reply_text(
                        "📭 Bạn chưa thiết lập ngân sách.\n\n"
                        "Gõ: `/budget set 10tr` để đặt ngân sách tổng.\n"
                        "Gõ: `/budget set 2tr ăn uống` để đặt ngân sách danh mục.",
                        parse_mode="Markdown"
                    )
                    return
                
                lines = ["📊 *Tình hình ngân sách tháng này*"]
                
                # Total budget status
                if status:
                     icon = "🟢" if not status.is_exceeded else "🔴"
                     lines.append(f"\n{icon} *Tổng chi:* {format_currency_full(status.spent)} / {format_currency_full(status.budget.amount)}")
                     lines.append(f"   (Đã dùng: {status.percentage:.0f}%)")
                
                lines.append("\n*Chi tiết:*")
                for b in budgets:
                    if b.category_id is None: continue # Skip total (shown above)
                    
                    cat_status = await check_budget_status(session, db_user.id, category_id=b.category_id)
                    icon = "✅" if not cat_status.is_exceeded else "⚠️"
                    lines.append(f"{icon} {cat_status.category_name}: {format_currency_full(cat_status.spent)} / {format_currency_full(b.amount)} ({cat_status.percentage:.0f}%)")
                    
                await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
                return
            
            # Case 2: Set budget
            if args[0].lower() == "set":
                # /budget set 500k [category]
                if len(args) < 2:
                    await update.message.reply_text("❌ Thiếu số tiền. VD: `/budget set 5tr`")
                    return
                    
                # Parse amount using parse_message service logic (simplified)
                amount_str = args[1]
                parse_res = parse_message(f"{amount_str} budget")
                if not parse_res.is_valid:
                     await update.message.reply_text("❌ Số tiền không hợp lệ.")
                     return
                
                amount = parse_res.amount
                
                # Category?
                category_id = None
                cat_name = "Tổng"
                
                if len(args) > 2:
                    note = " ".join(args[2:])
                    # Find category
                    category = await detect_category(session, note)
                    if not category:
                         # Try finding by name explicitly
                         category = await get_category_by_name(session, note)
                    
                    if category:
                        category_id = category.id
                        cat_name = category.name
                    else:
                        await update.message.reply_text(f"❌ Không tìm thấy danh mục '{note}'")
                        return
                
                await set_budget(session, db_user.id, amount, category_id)
                await update.message.reply_text(
                    f"✅ Đã đặt ngân sách *{cat_name}*: {format_currency_full(amount)}/tháng",
                    parse_mode="Markdown"
                )
                        
    except Exception as e:
        logger.error(f"Error in budget_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra.")
