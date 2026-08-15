import asyncio
import io
import sys
import traceback

from .config import OWNER, DEV


def is_authorised(sender_id: int) -> bool:
    """Proper equality/membership check — NOT substring matching."""
    return sender_id in OWNER or sender_id == DEV


async def run_eval(event):
    if not is_authorised(event.sender_id):
        return await event.reply("**Not authorised.**")
    try:
        cmd = event.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await event.reply("**Usage:** `/eval <code>`")

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = out_buf = io.StringIO()
    sys.stderr = err_buf = io.StringIO()
    exc = None
    try:
        exec_code = "async def __aexec(event):\n" + "\n".join(
            f" {line}" for line in cmd.split("\n")
        )
        exec(exec_code, globals())
        await globals()["__aexec"](event)
    except Exception:
        exc = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    result = exc or err_buf.getvalue() or out_buf.getvalue() or "Success"
    text = f"**EVAL:** `{cmd}`\n\n**OUTPUT:**\n`{result}`"
    await _send_possibly_long(event, text, cmd)


async def run_bash(event):
    if not is_authorised(event.sender_id):
        return await event.reply("**Not authorised.**")
    try:
        cmd = event.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await event.reply("**Usage:** `/bash <command>`")

    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    out = stdout.decode() or "(no output)"
    err = stderr.decode() or "(no errors)"
    text = f"**CMD:** `{cmd}`\n**PID:** `{process.pid}`\n\n**stderr:**\n`{err}`\n\n**stdout:**\n`{out}`"
    await _send_possibly_long(event, text, cmd)


async def _send_possibly_long(event, text, cmd):
    if len(text) > 4000:
        with io.BytesIO(text.encode()) as f:
            f.name = "output.txt"
            await event.client.send_file(
                event.chat_id, f, force_document=True, caption=cmd[:1000]
            )
    else:
        await event.reply(text)
