import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# API Keys & Notion setup
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# Scheduler config
RUN_HOUR = int(os.getenv("RUN_HOUR", "8"))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Notifications
NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Execution settings
DRY_RUN_DEFAULT = os.getenv("DRY_RUN", "true").lower() == "true"

# Paths
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = BASE_DIR / "run_logs.db"
SEED_KEYWORDS_PATH = DATA_DIR / "seed_keywords.json"
CACHED_NEWS_PATH = DATA_DIR / "cached_news.json"

# Quality thresholds & loop limits
MAX_REWRITE_ATTEMPTS = 3
SEO_PASS_THRESHOLD = 75
GROUNDEDNESS_PASS_THRESHOLD = 75

# Category options (strictly AI or Mobile App Development)
ALLOWED_CATEGORIES = ["AI", "Mobile App Development"]

# Ensure required directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
