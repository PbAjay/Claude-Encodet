import asyncio
import math
import subprocess
import time

from html_telegraph_poster import TelegraphPoster


def hbs(size) -> str:
    """Human-readable byte size."""
    if not size:
        return "0 B"
    power = 2 ** 10
    n = 0
    names = {0: "B", 1: "K", 2: "M", 3: "G", 4: "T", 5: "P"}
    size = float(size)
    while size > power and n < 5:
        size /= power
        n += 1
    return f"{round(size, 2)} {names[n]}B"


def ts(milliseconds: int) -> str:
    """Human-readable duration from milliseconds."""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return ", ".join(parts)


def bar(percentage: float, width: int = 10) -> str:
    filled = math.floor(percentage / 100 * width)
    return "■" * filled + "□" * (width - filled)


async def edit_throttled(event, text: str, state: dict, min_interval: float = 3.0):
    """Edit a message but never more than once every `min_interval` seconds,
    to avoid hitting Telegram's flood limits on fast-moving progress bars."""
    now = time.time()
    if now - state.get("last", 0) < min_interval:
        return
    state["last"] = now
    try:
        await event.edit(text)
    except Exception:
        pass


async def get_mediainfo_url(file_path: str, bot_name: str, bot_username: str) -> str:
    process = subprocess.run(
        ["mediainfo", file_path, "--Output=HTML"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    out = process.stdout.decode(errors="ignore")
    client = TelegraphPoster(use_api=True)
    client.create_api_token("Vid-comp-Mediainfo")
    page = client.post(
        title="Vid-comp-Mediainfo",
        author=bot_name,
        author_url=f"https://t.me/{bot_username}",
        text=out,
    )
    return page["url"]


# --- callback_data <-> job id encoding (Telegram limits callback_data to 64 bytes) ---
_CODES: dict[str, str] = {}
_COUNTER = 0


def encode_ref(job_id: str) -> str:
    global _COUNTER
    key = str(_COUNTER)
    _COUNTER += 1
    _CODES[key] = job_id
    return key


def decode_ref(key: str):
    return _CODES.get(key)
