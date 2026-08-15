import logging
import os
from logging.handlers import RotatingFileHandler

from telethon import TelegramClient

from .config import APP_ID, API_HASH, DOWNLOAD_DIR, ENCODE_DIR

LOG_FILE_NAME = "bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=20 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(),
    ],
)
logging.getLogger("telethon").setLevel(logging.WARNING)
LOGS = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(ENCODE_DIR, exist_ok=True)

bot = TelegramClient("bot_session", APP_ID, API_HASH)
