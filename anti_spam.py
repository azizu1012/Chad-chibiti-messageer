from collections import defaultdict, deque
from config import logger

user_queue = defaultdict(deque)
SPAM_THRESHOLD = 3
SPAM_WINDOW = 30

# Hàm check spam (giả định từ code gốc, anh adjust)
async def is_rate_limited(user_id):
    # Code gốc ở đây
    pass