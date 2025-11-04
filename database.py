import os
import aiosqlite # Import aiosqlite
from datetime import datetime
from config import DB_PATH
from logging_setup import logger

# Sử dụng một biến toàn cục để lưu trữ kết nối database
# Điều này giúp tránh việc mở/đóng kết nối liên tục
_db_connection = None

async def get_db_connection():
    """Lấy hoặc tạo kết nối database bất đồng bộ."""
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
        # Tùy chọn: Bật chế độ WAL (Write-Ahead Logging) để cải thiện hiệu suất
        # và cho phép đọc/ghi đồng thời.
        await _db_connection.execute("PRAGMA journal_mode=WAL;")
        await _db_connection.commit()
    return _db_connection

async def init_db():
    """Khởi tạo database và tạo bảng nếu chưa tồn tại."""
    conn = await get_db_connection()
    await conn.execute('''CREATE TABLE IF NOT EXISTS chat_history
                          (user_id TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
    await conn.commit()
    logger.info("Database initialized.")

async def log_message(user_id, role, content):
    """Ghi log tin nhắn vào database bất đồng bộ."""
    conn = await get_db_connection()
    timestamp = datetime.now()
    await conn.execute("INSERT INTO chat_history VALUES (?, ?, ?, ?)", (user_id, role, content, timestamp))
    await conn.commit()

async def get_user_history_async(user_id):
    """Lấy lịch sử chat của người dùng từ database bất đồng bộ."""
    conn = await get_db_connection()
    cursor = await conn.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    history = await cursor.fetchall()
    return [{"role": r, "content": c} for r, c in history]

# Hàm để đóng kết nối database khi ứng dụng tắt
async def close_db_connection():
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed.")