import os
import sqlite3
import asyncio
from config import DB_PATH, DB_BACKUP_PATH, MEMORY_PATH, memory_lock, weather_lock, logger

# Init DB
def init_db():
    # Code gốc init_db ở đây (giả định tạo table nếu cần)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Create table if not exists (from code gốc)
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history
                      (user_id TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

async def log_message(user_id, role, content):
    # Code gốc log_message
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now()
    cursor.execute("INSERT INTO chat_history VALUES (?, ?, ?, ?)", (user_id, role, content, timestamp))
    conn.commit()
    conn.close()

async def get_user_history_async(user_id):
    # Code gốc get_user_history_async (giả định async wrapper)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    history = cursor.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in history]

# Thêm các hàm khác như backup DB nếu có từ code gốc