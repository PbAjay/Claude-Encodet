import asyncio
import os
import time
from pathlib import Path
from urllib.parse import unquote

import aiohttp
from telethon import Button
from telethon.tl.types import DocumentAttributeVideo

from . import bot, LOGS
from .config import DOWNLOAD_DIR, ENCODE_DIR, DEV
from . import db
from .db import STATUS_DOWNLOADING, STATUS_ENCODING, STATUS_UPLOADING
from .fast_transfer import download_file, upload_file
from .helpers import hbs, ts, bar, edit_throttled, get_mediainfo_url, encode_ref
from .ffmpeg_utils import encode as ffmpeg_encode

_STOP = asyncio.Event()
CURRENT_JOB_ID = None  # id of job actively processing, for /skip


async def _download_progress_cb(event, state, label):
    def cb(current, total):
        if not total:
            return
        pct = current * 100 / total
        elapsed = time.time() - state["start"]
        speed = current / elapsed if elapsed > 0 else 0
        eta = ts(int(((total - current) / speed) * 1000)) if speed else "?"
        msg = (
            f"**📥 Downloading{': ' + label if label else ''}**\n\n"
            f"{bar(pct)} {pct:.1f}%\n\n"
            f"**📁 Size:** {hbs(current)} / {hbs(total)}\n"
            f"**🚀 Speed:** {hbs(speed)}/s\n"
            f"**⏰ ETA:** {eta}"
        )
        asyncio.get_event_loop().create_task(edit_throttled(event, msg, state))
    return cb


async def _download_from_telegram(job, status_msg):
    src_chat = job["source_chat_id"]
    src_msg_id = job["source_msg_id"]
    msg = await bot.get_messages(src_chat, ids=src_msg_id)
    if not msg or not msg.media:
        raise RuntimeError("Original message/media no longer available (deleted?).")
    filename = job["filename"]
    dest = os.path.join(DOWNLOAD_DIR, f"{job['_id']}_{filename}")
    state = {"start": time.time(), "last": 0.0}
    cb = await _download_progress_cb(status_msg, state, filename)
    with open(dest, "wb") as f:
        await download_file(
            client=bot,
            location=msg.media.document,
            out=f,
            progress_callback=cb,
        )
    return dest


async def _download_from_link(job, status_msg):
    url = job["url"]
    filename = job["filename"] or unquote(url.rpartition("/")[-1]) or "video.mp4"
    dest = os.path.join(DOWNLOAD_DIR, f"{job['_id']}_{filename}")
    state = {"start": time.time(), "last": 0.0}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=None) as resp:
            total = int(resp.headers.get("content-length", 0)) or None
            downloaded = 0
            with open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 / total
                        msg = (
                            f"**📥 Downloading (link)**\n\n"
                            f"{bar(pct)} {pct:.1f}%\n\n**📁 Size:** {hbs(downloaded)} / {hbs(total)}"
                        )
                        await edit_throttled(status_msg, msg, state)
    return dest


async def _process_job(job):
    global CURRENT_JOB_ID
    job_id = job["_id"]
    CURRENT_JOB_ID = job_id
    owner_chat = job["owner_chat_id"]

    status_msg = await bot.send_message(owner_chat, "**📥 Starting...**")

    dl_path = None
    out_path = None
    try:
        # --- download ---
        await db.set_status(job_id, STATUS_DOWNLOADING)
        if job["source_type"] == "telegram":
            dl_path = await _download_from_telegram(job, status_msg)
        else:
            dl_path = await _download_from_link(job, status_msg)

        # --- encode ---
        await db.set_status(job_id, STATUS_ENCODING)
        stem = Path(dl_path).stem
        out_path = os.path.join(ENCODE_DIR, f"{stem}.mkv")
        ffmpeg_args = await db.get_setting("ffmpeg_args") or job.get("ffmpeg_args")
        from .config import DEFAULT_FFMPEG
        ffmpeg_args = ffmpeg_args or DEFAULT_FFMPEG

        ref = encode_ref(str(job_id))
        cancel_msg = await status_msg.respond(
            "🗜 Encoding starting...",
            buttons=[[Button.inline("CANCEL", data=f"skip{ref}")]],
        )
        returncode, stderr_text = await ffmpeg_encode(
            dl_path, out_path, ffmpeg_args, event=status_msg, label=job.get("filename", "")
        )
        try:
            await cancel_msg.delete()
        except Exception:
            pass

        if returncode != 0:
            await status_msg.edit(f"**❌ Encode failed:**\n`{stderr_text[-3500:]}`")
            return

        # --- upload ---
        await db.set_status(job_id, STATUS_UPLOADING)
        thumb_path = "thumb.jpg" if os.path.exists("thumb.jpg") else None
        state = {"start": time.time(), "last": 0.0}

        def up_cb(current, total):
            if not total:
                return
            pct = current * 100 / total
            asyncio.get_event_loop().create_task(
                edit_throttled(
                    status_msg,
                    f"**📤 Uploading**\n\n{bar(pct)} {pct:.1f}%\n\n**📁** {hbs(current)} / {hbs(total)}",
                    state,
                )
            )

        with open(out_path, "rb") as f:
            uploaded = await upload_file(
                client=bot, file=f, name=out_path, progress_callback=up_cb,
            )

        org_size = Path(dl_path).stat().st_size
        com_size = Path(out_path).stat().st_size
        saved_pct = 100 - (com_size / org_size * 100) if org_size else 0

        caption = (
            f"<b>File:</b> {job.get('filename', 'video')}\n\n"
            f"<b>Original:</b> {hbs(org_size)}\n"
            f"<b>Compressed:</b> {hbs(com_size)}\n"
            f"<b>Saved:</b> {saved_pct:.2f}%"
        )
        await bot.send_file(
            owner_chat, file=uploaded, force_document=True, caption=caption,
            thumb=thumb_path, parse_mode="html",
        )
        await status_msg.delete()

    except Exception as e:
        LOGS.exception("Job %s failed", job_id)
        try:
            await status_msg.edit(f"**❌ Error:** `{e}`")
        except Exception:
            pass
    finally:
        for p in (dl_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        await db.delete_job(job_id)
        CURRENT_JOB_ID = None


async def queue_loop():
    """Runs forever: pulls the next queued job from Mongo and processes it.
    Because job state is written to Mongo at every stage transition, a crash
    at any point just means the job gets picked up again (from scratch) the
    next time the bot starts — nothing is silently lost."""
    while not _STOP.is_set():
        job = await db.next_queued_job()
        if not job:
            await asyncio.sleep(3)
            continue
        await _process_job(job)


async def enqueue(*, owner_chat_id, source_type, filename, source_chat_id=None,
                   source_msg_id=None, url=None):
    job = {
        "owner_chat_id": owner_chat_id,
        "source_type": source_type,
        "filename": filename,
        "source_chat_id": source_chat_id,
        "source_msg_id": source_msg_id,
        "url": url,
    }
    return await db.add_job(job)
