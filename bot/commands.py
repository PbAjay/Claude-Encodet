import platform
import subprocess
import time
from datetime import datetime

import psutil
from telethon import Button

from . import LOGS, LOG_FILE_NAME
from .config import DEFAULT_FFMPEG, DOWNLOAD_DIR, ENCODE_DIR
from . import db
from .helpers import hbs

START_TIME = datetime.now()


async def start(event):
    await event.reply(
        "**Send me a video and I'll compress it.**\n\n"
        "Use /help for details, /cmds for the full command list.",
        buttons=[[Button.url("Source", url="https://github.com")]],
    )


async def ihelp(event):
    await event.reply(
        "**Send any video file and I'll queue it for compression "
        "and send back the result.**\n\n"
        "Use /leech <url> to compress a video from a direct link instead."
    )


async def cmds(event):
    await event.reply(
        "**Commands**\n\n"
        "/start - check the bot is alive\n"
        "/help - usage help\n"
        "/ping - latency + uptime\n"
        "/queue - show pending jobs\n"
        "/leech <url> [name] - compress a video from a direct link\n\n"
        "**Owner only**\n"
        "/setcode <ffmpeg args> - change the encode settings\n"
        "/getcode - show current encode settings\n"
        "/showthumb - show current thumbnail\n"
        "/sysinfo - server resource usage\n"
        "/logs - download the log file\n"
        "/clear - wipe the entire queue\n"
        "/speed - run a speedtest\n"
    )


async def ping(event):
    start = time.time()
    msg = await event.reply("Pinging...")
    ms = (time.time() - start) * 1000
    uptime = str(datetime.now() - START_TIME).split(".")[0]
    await msg.edit(f"**Pong!** `{ms:.0f}ms`\n**Uptime:** {uptime}")


async def queue_status(event):
    pending = await db.count_pending()
    await event.reply(f"**📋 Jobs in queue/processing:** {pending}")


async def sysinfo(event):
    du = psutil.disk_usage("/")
    mem = psutil.virtual_memory()
    await event.reply(
        f"**OS:** {platform.system()} {platform.release()}\n"
        f"**CPU:** {psutil.cpu_percent()}%\n"
        f"**Disk:** {hbs(du.used)} / {hbs(du.total)} (free {hbs(du.free)})\n"
        f"**Memory:** {hbs(mem.used)} / {hbs(mem.total)} ({mem.percent}%)"
    )


async def get_ffmpeg_code(event):
    code = await db.get_setting("ffmpeg_args") or DEFAULT_FFMPEG
    await event.reply(f"**Current FFmpeg args:**\n`{code}`")


async def set_ffmpeg_code(event):
    try:
        new_code = event.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await event.reply("**Usage:** `/setcode <ffmpeg args>`")
    await db.set_setting("ffmpeg_args", new_code)
    await event.reply(f"**FFmpeg args updated (persisted):**\n`{new_code}`")


async def show_thumb(event):
    import os
    if os.path.exists("thumb.jpg"):
        await event.reply(file="thumb.jpg")
    else:
        await event.reply("No thumbnail set.")


async def get_logs(event):
    await event.client.send_file(event.chat_id, file=LOG_FILE_NAME, force_document=True)


async def clear_queue(event):
    n = await db.clear_all_jobs()
    await event.reply(f"**Cleared {n} job(s) from the queue.**")


async def speedtest(event):
    msg = await event.reply("Running speedtest...")
    try:
        proc = subprocess.run(
            ["speedtest-cli", "--simple"], capture_output=True, timeout=120
        )
        result = proc.stdout.decode() + proc.stderr.decode()
        await msg.edit(f"**{result.strip()}**")
    except FileNotFoundError:
        await msg.edit("speedtest-cli not installed.")
    except subprocess.TimeoutExpired:
        await msg.edit("Speedtest timed out.")
