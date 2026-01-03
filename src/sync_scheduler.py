"""
Background scheduler cho auto-sync Google Sheets
Chạy mỗi 5 phút để pull changes từ Sheets về database
"""

import logging
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import get_session, User, Transaction, Category, TransactionType
from .sheets_service import is_sheets_enabled, pull_transactions_from_sheet
from .utils import get_vietnam_now

logger = logging.getLogger(__name__)

# Sync interval in seconds (5 minutes)
SYNC_INTERVAL = 300


async def sync_user_from_sheet(session: AsyncSession, user: User) -> int:
    """
    Sync transactions from user's Google Sheet to database
    Returns number of new/updated transactions
    """
    if not user.sheet_id:
        return 0
    
    try:
        # Pull data from sheet
        sheet_data = await pull_transactions_from_sheet(user.sheet_id)
        
        if not sheet_data:
            return 0
        
        # Get existing transaction IDs
        result = await session.execute(
            select(Transaction.id).where(Transaction.user_id == user.id)
        )
        existing_ids = {row[0] for row in result.fetchall()}
        
        # Get category mapping
        cat_result = await session.execute(select(Category))
        categories = {cat.name.lower(): cat for cat in cat_result.scalars().all()}
        
        new_count = 0
        
        for tx_data in sheet_data:
            tx_id = tx_data.get('id')
            
            # Skip if already exists (we don't update existing for now)
            if tx_id and tx_id in existing_ids:
                continue
            
            # Skip rows without valid data
            if not tx_data.get('amount') or tx_data['amount'] == 0:
                continue
            
            # Find category
            cat_name = tx_data.get('category', '').lower()
            category = categories.get(cat_name)
            
            # Parse date
            try:
                date_str = tx_data.get('date_str', '')
                # Expected format: "03/01/2026 14:30"
                if date_str:
                    tx_date = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
                else:
                    tx_date = get_vietnam_now()
            except ValueError:
                tx_date = get_vietnam_now()
            
            # Create new transaction (only if ID is None - new row added in sheet)
            if tx_id is None:
                new_tx = Transaction(
                    user_id=user.id,
                    amount=tx_data['amount'],
                    note=tx_data.get('note', ''),
                    category_id=category.id if category else None,
                    date=tx_date
                )
                session.add(new_tx)
                new_count += 1
        
        if new_count > 0:
            await session.commit()
            logger.info(f"Synced {new_count} new transactions for user {user.id}")
        
        return new_count
        
    except Exception as e:
        logger.error(f"Error syncing from sheet for user {user.id}: {e}")
        return 0


async def run_sync_job():
    """Run sync job for all users with sheets"""
    if not is_sheets_enabled():
        return
    
    try:
        async with await get_session() as session:
            # Get all users with sheet_id
            result = await session.execute(
                select(User).where(User.sheet_id.isnot(None))
            )
            users = result.scalars().all()
            
            total_synced = 0
            for user in users:
                count = await sync_user_from_sheet(session, user)
                total_synced += count
                
                # Update last_sync
                if count > 0:
                    user.last_sync = get_vietnam_now()
            
            if total_synced > 0:
                await session.commit()
                logger.info(f"Auto-sync completed: {total_synced} new transactions from {len(users)} users")
                
    except Exception as e:
        logger.error(f"Error in sync job: {e}")


async def start_sync_scheduler():
    """Start the background sync scheduler"""
    logger.info(f"Starting sync scheduler (interval: {SYNC_INTERVAL}s)")
    
    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL)
            await run_sync_job()
        except asyncio.CancelledError:
            logger.info("Sync scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Error in sync scheduler: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry
