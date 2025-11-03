import time
from collections import defaultdict, deque
from logging_setup import logger

user_queue = defaultdict(deque)
SPAM_THRESHOLD = 3 # Giới hạn 3 tin nhắn
SPAM_WINDOW = 30   # Trong vòng 30 giây

async def is_rate_limited(user_id):
    """
    Kiểm tra giới hạn tốc độ (rate limit) dựa trên số lượng tin nhắn trong một khoảng thời gian.
    """
    current_time = time.time()
    
    # 1. Loại bỏ các tin nhắn cũ hơn SPAM_WINDOW
    # Chạy vòng lặp trong khi queue không rỗng VÀ tin nhắn cũ nhất (bên trái) đã quá hạn
    while user_queue[user_id] and user_queue[user_id][0] < current_time - SPAM_WINDOW:
        user_queue[user_id].popleft()
        
    # 2. Thêm timestamp của tin nhắn hiện tại
    user_queue[user_id].append(current_time)
    
    # 3. Kiểm tra số lượng tin nhắn
    if len(user_queue[user_id]) > SPAM_THRESHOLD:
        logger.warning(f"User {user_id} is rate-limited: {len(user_queue[user_id])} messages in {SPAM_WINDOW}s")
        return True
    
    return False