"""
Environment-based configuration. Nothing is hardcoded — the bot refuses
to start if required vars are missing.
"""
import sys
from decouple import config

try:
    APP_ID = config("APP_ID", cast=int)
    API_HASH = config("API_HASH")
    BOT_TOKEN = config("BOT_TOKEN")
    DEV = config("DEV", cast=int)
    OWNER = [int(x) for x in config("OWNER").split(",") if x.strip()]

    MONGO_URI = config("MONGO_URI")
    MONGO_DB_NAME = config("MONGO_DB_NAME", default="compbot")

    DEFAULT_FFMPEG = config(
        "FFMPEG",
        default=(
            '-preset faster -c:v libx265 -crf 28 -pix_fmt yuv420p '
            '-c:a aac -b:a 96k -c:s copy -map 0 -threads 0'
        ),
    )
    DEFAULT_THUMBNAIL = config(
        "THUMBNAIL", default="https://telegra.ph/file/711777fbb7317a73c211a.jpg"
    )

    DOWNLOAD_DIR = config("DOWNLOAD_DIR", default="downloads")
    ENCODE_DIR = config("ENCODE_DIR", default="encode")
except Exception as e:
    print("Missing/invalid environment variables. Required: "
          "APP_ID, API_HASH, BOT_TOKEN, DEV, OWNER, MONGO_URI")
    print(str(e))
    sys.exit(1)
