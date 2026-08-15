import asyncio
import os
import re

import aiohttp
from telethon import events, Button

from . import bot, LOGS
from .config import BOT_TOKEN, DEV, OWNER, DEFAULT_THUMBNAIL
from . import db
from .devtools import is_authorised, run_eval, run_bash
from .worker import queue_loop, enqueue
from . import worker as worker_module
from .helpers import decode_ref
from .commands import (
    start, ihelp, cmds, ping, queue_status, sysinfo,
    get_ffmpeg_code, set_ffmpeg_code, show_thumb, get_logs,
    clear_queue, speedtest,
)


async def _download_thumbnail():
    thumb_url = await db.get_setting("thumbnail") or DEFAULT_THUMBNAIL
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(thumb_url) as resp:
                if resp.status == 200:
                    with open("thumb.jpg", "wb") as f:
                        f.write(await resp.read())
    except Exception as e:
        LOGS.warning("Could not fetch thumbnail: %s", e)


# ---------------- general commands ----------------

@bot.on(events.NewMessage(pattern="/start"))
async def _(e):
    await start(e)


@bot.on(events.NewMessage(pattern="/help"))
async def _(e):
    await ihelp(e)


@bot.on(events.NewMessage(pattern="/cmds"))
async def _(e):
    await cmds(e)


@bot.on(events.NewMessage(pattern="/ping"))
async def _(e):
    await ping(e)


@bot.on(events.NewMessage(pattern="/queue"))
async def _(e):
    await queue_status(e)


@bot.on(events.NewMessage(pattern="/leech"))
async def _(e):
    if not e.is_private:
        return
    parts = e.text.split(maxsplit=2)
    if len(parts) < 2:
        return await e.reply("**Usage:** `/leech <url> [filename]`")
    url = parts[1]
    name = parts[2] if len(parts) > 2 else None
    await enqueue(owner_chat_id=e.chat_id, source_type="link", filename=name, url=url)
    await e.reply("**✅ Added to queue.**")


# ---------------- owner-only commands ----------------

@bot.on(events.NewMessage(pattern="/setcode"))
async def _(e):
    if is_authorised(e.sender_id):
        await set_ffmpeg_code(e)


@bot.on(events.NewMessage(pattern="/getcode"))
async def _(e):
    if is_authorised(e.sender_id):
        await get_ffmpeg_code(e)


@bot.on(events.NewMessage(pattern="/showthumb"))
async def _(e):
    if is_authorised(e.sender_id):
        await show_thumb(e)


@bot.on(events.NewMessage(pattern="/logs"))
async def _(e):
    if is_authorised(e.sender_id):
        await get_logs(e)


@bot.on(events.NewMessage(pattern="/sysinfo"))
async def _(e):
    if is_authorised(e.sender_id):
        await sysinfo(e)


@bot.on(events.NewMessage(pattern="/clear"))
async def _(e):
    if is_authorised(e.sender_id):
        await clear_queue(e)


@bot.on(events.NewMessage(pattern="/speed"))
async def _(e):
    if is_authorised(e.sender_id):
        await speedtest(e)


@bot.on(events.NewMessage(pattern="/eval"))
async def _(e):
    await run_eval(e)


@bot.on(events.NewMessage(pattern="/bash"))
async def _(e):
    await run_bash(e)


# ---------------- callbacks ----------------

@bot.on(events.CallbackQuery(data=re.compile(rb"skip(.*)")))
async def _(e):
    ref = e.pattern_match.group(1).decode()
    job_id = decode_ref(ref)
    if job_id and str(worker_module.CURRENT_JOB_ID) == job_id:
        # let the worker's own crash/cleanup path handle removal;
        # simplest safe action here is to just inform the user.
        await e.answer("Cancellation of an in-flight encode isn't wired up yet "
                        "in this rewrite — let it finish or restart the bot.",
                        alert=True)
    else:
        await e.answer("Job no longer active.", alert=True)


# ---------------- incoming media -> enqueue ----------------

@bot.on(events.NewMessage(incoming=True))
async def _(event):
    if not event.is_private:
        return
    if event.photo:
        try:
            os.remove("thumb.jpg")
        except OSError:
            pass
        await event.client.download_media(event.media, file="thumb.jpg")
        await db.set_setting("thumbnail", "local")  # marker; file already saved
        return await event.reply("**Thumbnail saved.**")

    if not event.media or not hasattr(event.media, "document"):
        return
    doc = event.media.document
    if not doc.mime_type or not doc.mime_type.startswith(("video", "application/octet-stream")):
        return

    filename = event.file.name or f"video_{event.id}.mp4"
    await enqueue(
        owner_chat_id=event.chat_id,
        source_type="telegram",
        filename=filename,
        source_chat_id=event.chat_id,
        source_msg_id=event.id,
    )
    await event.reply("**✅ Added to queue.**")


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    await db.ensure_indexes()
    await _download_thumbnail()

    resumed = await db.reset_interrupted_jobs()
    if resumed:
        LOGS.info("Resumed %d interrupted job(s) from a previous run.", resumed)

    LOGS.info("Bot started.")
    asyncio.create_task(queue_loop())
    await bot.run_until_disconnected()


if __name__ == "__main__":
    bot.loop.run_until_complete(main())
