#!/usr/bin/env python3
"""
Database backup script for Expense Bot
Backs up SQLite database to Google Drive every 6 hours
"""

import os
import sqlite3
import shutil
import datetime
from pathlib import Path
import zipfile
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/botuser/backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DatabaseBackup:
    def __init__(self, db_path, backup_dir, credentials_file):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.credentials_file = credentials_file
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self):
        """Create database backup with timestamp"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"expense_bot_backup_{timestamp}"
            
            # Create backup directory
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            # Copy database file
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path / "expense_bot.db")
                logger.info(f"Database copied to {backup_path}")
            else:
                logger.warning(f"Database file not found: {self.db_path}")
                return None
            
            # Create info file
            info_file = backup_path / "backup_info.txt"
            with open(info_file, 'w') as f:
                f.write(f"Backup created: {datetime.datetime.now()}\n")
                f.write(f"Database size: {self.db_path.stat().st_size} bytes\n")
                f.write(f"Bot version: Telegram & Zalo Expense Bot\n")
            
            # Create zip file
            zip_path = self.backup_dir / f"{backup_name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in backup_path.rglob('*'):
                    if file_path.is_file():
                        zipf.write(file_path, file_path.relative_to(backup_path))
            
            # Remove temporary directory
            shutil.rmtree(backup_path)
            
            logger.info(f"Backup created: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
    def authenticate_drive(self):
        """Authenticate with Google Drive API"""
        creds = None
        token_file = Path(self.credentials_file).parent / 'token.pickle'
        
        # Load existing token
        if token_file.exists():
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(self.credentials_file).exists():
                    logger.error(f"Credentials file not found: {self.credentials_file}")
                    return None
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    def upload_to_drive(self, file_path, folder_id=None):
        """Upload backup file to Google Drive"""
        try:
            creds = self.authenticate_drive()
            if not creds:
                logger.error("Failed to authenticate with Google Drive")
                return False
            
            service = build('drive', 'v3', credentials=creds)
            
            file_metadata = {
                'name': file_path.name,
                'description': f'Expense Bot Database Backup - {datetime.datetime.now()}'
            }
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(str(file_path), resumable=True)
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f"Backup uploaded to Google Drive. File ID: {file.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to Google Drive: {e}")
            return False
    
    def cleanup_old_backups(self, keep_days=7):
        """Remove local backup files older than specified days"""
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=keep_days)
            
            for backup_file in self.backup_dir.glob("expense_bot_backup_*.zip"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()
                    logger.info(f"Removed old backup: {backup_file}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def run_backup(self, drive_folder_id=None):
        """Run complete backup process"""
        logger.info("Starting database backup...")
        
        # Create backup
        backup_file = self.create_backup()
        if not backup_file:
            logger.error("Failed to create backup")
            return False
        
        # Upload to Google Drive
        if self.upload_to_drive(backup_file, drive_folder_id):
            logger.info("Backup uploaded successfully")
        else:
            logger.warning("Failed to upload backup to Google Drive")
        
        # Cleanup old backups
        self.cleanup_old_backups()
        
        logger.info("Backup process completed")
        return True

def main():
    # Configuration
    DB_PATH = "/home/botuser/QuanLyThuChi_Bot_Telegram_Zalom/expense_bot.db"
    BACKUP_DIR = "/home/botuser/backups"
    CREDENTIALS_FILE = "/home/botuser/credentials.json"
    DRIVE_FOLDER_ID = None  # Set this to your Google Drive folder ID
    
    # Create backup instance
    backup = DatabaseBackup(DB_PATH, BACKUP_DIR, CREDENTIALS_FILE)
    
    # Run backup
    backup.run_backup(DRIVE_FOLDER_ID)

if __name__ == "__main__":
    main()
