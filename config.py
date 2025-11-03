import os
from dotenv import load_dotenv

load_dotenv()

# Discord token (giữ reference, nhưng Teams không dùng)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Gemini keys
GEMINI_API_KEYS = [
    os.getenv('GEMINI_API_KEY_PROD'),
    os.getenv('GEMINI_API_KEY_TEST'),
    os.getenv('GEMINI_API_KEY_BACKUP'),
    os.getenv('GEMINI_API_KEY_EXTRA1'),
    os.getenv('GEMINI_API_KEY_EXTRA2')
]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k]

MODEL_NAME = os.getenv('MODEL_NAME')

# User ID

# Search API keys
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
EXA_API_KEY = os.getenv('EXA_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')
GOOGLE_CSE_API_KEY = os.getenv('GOOGLE_CSE_API_KEY')
GOOGLE_CSE_ID_1 = os.getenv("GOOGLE_CSE_ID_1")
GOOGLE_CSE_API_KEY_1 = os.getenv("GOOGLE_CSE_API_KEY_1")
GOOGLE_CSE_ID_2 = os.getenv("GOOGLE_CSE_ID_2")
GOOGLE_CSE_API_KEY_2 = os.getenv("GOOGLE_CSE_API_KEY_2")

# Weather
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
CITY = os.getenv('CITY')
WEATHER_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'weather_cache.json')

# File paths
DB_PATH = os.path.join(os.path.dirname(__file__), 'chat_history.db')
DB_BACKUP_PATH = os.path.join(os.path.dirname(__file__), 'chat_history_backup.db')
NOTE_PATH = os.path.join(os.path.dirname(__file__), 'notes.txt')
MEMORY_PATH = os.path.join(os.path.dirname(__file__), 'short_term_memory.json')

# City map
CITY_NAME_MAP = {
    "hồ chí minh": ("Ho Chi Minh City", "Thành phố Hồ Chí Minh"),
    "tp.hcm": ("Ho Chi Minh City", "Thành phố Hồ Chí Minh"),
    "sài gòn": ("Ho Chi Minh City", "Thành phố Hồ Chí Minh"),
    "ho chi minh city": ("Ho Chi Minh City", "Thành phố Hồ Chí Minh"),
    "hcmc": ("Ho Chi Minh City", "Thành phố Hồ Chí Minh"),
    "hà nội": ("Hanoi", "Hà Nội"),
    "ha noi": ("Hanoi", "Hà Nội"),
    "danang": ("Da Nang", "Đà Nẵng"),
    "đà nẵng": ("Da Nang", "Đà Nẵng"),
    "da nang": ("Da Nang", "Đà Nẵng"),
}

# Teams-specific
TEAMS_APP_ID = os.getenv('TEAMS_APP_ID')
TEAMS_APP_PASSWORD = os.getenv('TEAMS_APP_PASSWORD')