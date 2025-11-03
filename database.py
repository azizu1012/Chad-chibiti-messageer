import os
import sqlite3
import asyncio # <-- Đã dùng asyncio.to_thread
from datetime import datetime
from config import DB_PATH, DB_BACKUP_PATH, MEMORY_PATH
from logging_setup import logger

# Init DB (Có thể giữ đồng bộ vì chỉ chạy 1 lần lúc khởi động)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history
                      (user_id TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

async def log_message(user_id, role, content):
    def sync_log():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        timestamp = datetime.now()
        cursor.execute("INSERT INTO chat_history VALUES (?, ?, ?, ?)", (user_id, role, content, timestamp))
        conn.commit()
        conn.close()
        
    # Chuyển hoạt động I/O chặn sang threadpool
    await asyncio.to_thread(sync_log)

async def get_user_history_async(user_id):
    def sync_get():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
        history = cursor.fetchall()
        conn.close()
        return history
        
    # Chuyển hoạt động I/O chặn sang threadpool
    history = await asyncio.to_thread(sync_get)
    return [{"role": r, "content": c} for r, c in history]