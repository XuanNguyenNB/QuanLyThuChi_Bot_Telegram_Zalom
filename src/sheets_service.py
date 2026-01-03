"""
Google Sheets integration service - Two-way sync với auto-sync
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import gspread
from gspread_asyncio import AsyncioGspreadClientManager
from google.oauth2.service_account import Credentials

from .utils import get_vietnam_now, format_datetime

logger = logging.getLogger(__name__)

# Scopes for Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Credentials file path
CREDENTIALS_FILE = os.getenv(
    'GOOGLE_SHEETS_CREDENTIALS',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'telebot-482220-55edad8d13cf.json')
)

# Global client manager
_client_manager: Optional[AsyncioGspreadClientManager] = None


def get_credentials():
    """Get Google credentials from service account file"""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"Credentials file not found: {CREDENTIALS_FILE}")
        return None
    return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)


def get_client_manager() -> AsyncioGspreadClientManager:
    """Get or create async gspread client manager"""
    global _client_manager
    if _client_manager is None:
        _client_manager = AsyncioGspreadClientManager(get_credentials)
    return _client_manager


async def create_user_sheet(user_name: str) -> Optional[str]:
    """
    Create a new Google Sheet for a user
    Returns the sheet ID
    """
    try:
        manager = get_client_manager()
        client = await manager.authorize()
        
        # Create new spreadsheet
        sheet_name = f"Chi tiêu - {user_name}"
        spreadsheet = await client.create(sheet_name)
        
        # Get worksheet and setup headers
        worksheet = await spreadsheet.get_worksheet(0)
        
        # Set headers
        headers = ["ID", "Ngày", "Số tiền", "Ghi chú", "Danh mục", "Loại", "Synced"]
        await worksheet.update('A1:G1', [headers])
        
        # Format header row (bold)
        await worksheet.format('A1:G1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
        
        # Make the sheet public (anyone with link can edit)
        await spreadsheet.share('', perm_type='anyone', role='writer')
        
        logger.info(f"Created sheet for {user_name}: {spreadsheet.id}")
        return spreadsheet.id
        
    except Exception as e:
        logger.error(f"Error creating sheet: {e}")
        return None


async def get_sheet_url(sheet_id: str) -> str:
    """Get the URL of a Google Sheet"""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


async def push_transaction_to_sheet(
    sheet_id: str,
    tx_id: int,
    tx_date: datetime,
    amount: float,
    note: str,
    category: str,
    tx_type: str
) -> bool:
    """Push a single transaction to the sheet"""
    try:
        manager = get_client_manager()
        client = await manager.authorize()
        
        spreadsheet = await client.open_by_key(sheet_id)
        worksheet = await spreadsheet.get_worksheet(0)
        
        # Append row
        row = [
            tx_id,
            format_datetime(tx_date),
            amount,
            note or "",
            category or "Khác",
            tx_type,
            "✓"
        ]
        await worksheet.append_row(row)
        
        logger.info(f"Pushed transaction {tx_id} to sheet {sheet_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error pushing transaction to sheet: {e}")
        return False


async def sync_all_transactions_to_sheet(
    sheet_id: str,
    transactions: List[Dict[str, Any]]
) -> bool:
    """Sync all transactions to the sheet (full refresh)"""
    try:
        manager = get_client_manager()
        client = await manager.authorize()
        
        spreadsheet = await client.open_by_key(sheet_id)
        worksheet = await spreadsheet.get_worksheet(0)
        
        # Clear existing data (keep header)
        await worksheet.clear()
        
        # Set headers
        headers = ["ID", "Ngày", "Số tiền", "Ghi chú", "Danh mục", "Loại", "Synced"]
        
        # Build all rows
        rows = [headers]
        for tx in transactions:
            rows.append([
                tx['id'],
                format_datetime(tx['date']),
                tx['amount'],
                tx['note'] or "",
                tx['category'] or "Khác",
                tx['type'],
                "✓"
            ])
        
        # Batch update
        if rows:
            await worksheet.update(f'A1:G{len(rows)}', rows)
        
        # Format header
        await worksheet.format('A1:G1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
        
        logger.info(f"Synced {len(transactions)} transactions to sheet {sheet_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error syncing to sheet: {e}")
        return False


async def pull_transactions_from_sheet(sheet_id: str) -> List[Dict[str, Any]]:
    """
    Pull transactions from the sheet
    Returns list of transactions with their data
    """
    try:
        manager = get_client_manager()
        client = await manager.authorize()
        
        spreadsheet = await client.open_by_key(sheet_id)
        worksheet = await spreadsheet.get_worksheet(0)
        
        # Get all values
        all_values = await worksheet.get_all_values()
        
        if len(all_values) <= 1:  # Only header or empty
            return []
        
        # Parse rows (skip header)
        transactions = []
        for row in all_values[1:]:
            if len(row) >= 6:
                try:
                    tx = {
                        'id': int(row[0]) if row[0] else None,
                        'date_str': row[1],
                        'amount': float(row[2]) if row[2] else 0,
                        'note': row[3],
                        'category': row[4],
                        'type': row[5],
                        'synced': row[6] if len(row) > 6 else ""
                    }
                    transactions.append(tx)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing row: {row}, error: {e}")
                    continue
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error pulling from sheet: {e}")
        return []


def is_sheets_enabled() -> bool:
    """Check if Google Sheets integration is configured"""
    return os.path.exists(CREDENTIALS_FILE)
