"""
Unlike the original bot (which just showed a static "Compressing..."
message with no feedback until ffmpeg finished), this parses ffmpeg's
`-progress pipe:1` machine-readable output against the source duration
(via ffprobe) to show a live percentage/ETA during encoding too.
"""
import asyncio
import re
import time

from .helpers import bar, hbs, ts, edit_throttled


async def probe_duration_seconds(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrapper=1:nokey=1", path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except (ValueError, TypeError):
        return 0.0


_TIME_RE = re.compile(r"out_time_ms=(\d+)")
_SPEED_RE = re.compile(r"speed=([\d.]+)x")
_PROGRESS_RE = re.compile(r"progress=(\w+)")


async def encode(src: str, dst: str, ffmpeg_args: str, event=None, label: str = ""):
    """Run ffmpeg with progress reporting. Returns (returncode, stderr_text)."""
    duration = await probe_duration_seconds(src)
    cmd = f'ffmpeg -y -i "{src}" {ffmpeg_args} -progress pipe:1 -nostats "{dst}"'

    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    start = time.time()
    state = {"last": 0.0}
    stderr_chunks = []

    async def read_stderr():
        async for line in process.stderr:
            stderr_chunks.append(line)

    stderr_task = asyncio.create_task(read_stderr())

    buf = b""
    finished = False
    async for chunk in process.stdout:
        buf += chunk
        if b"progress=" not in chunk:
            continue
        text = buf.decode(errors="ignore")
        buf = b""
        time_match = _TIME_RE.search(text)
        speed_match = _SPEED_RE.search(text)
        if event and duration and time_match:
            out_ms = int(time_match.group(1)) / 1000
            pct = min(100.0, (out_ms / duration) * 100)
            elapsed = time.time() - start
            speed_x = float(speed_match.group(1)) if speed_match else None
            eta = ts(int(((duration - out_ms) / speed_x) * 1000)) if speed_x else "?"
            msg = (
                f"**🗜 Encoding{': ' + label if label else ''}**\n\n"
                f"{bar(pct)} {pct:.1f}%\n\n"
                f"**⏱ Elapsed:** {ts(int(elapsed * 1000))}\n"
                f"**⚡ Speed:** {speed_x or '?'}x\n"
                f"**⏰ ETA:** {eta}"
            )
            await edit_throttled(event, msg, state)
        if "progress=end" in text:
            finished = True

    await stderr_task
    returncode = await process.wait()
    stderr_text = b"".join(stderr_chunks).decode(errors="ignore")
    return returncode, stderr_text
