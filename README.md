# Compbot — rebuilt

A Telegram video-compression bot. Send it a video (or `/leech <url>`),
it queues, downloads, encodes with ffmpeg, and sends back the compressed
file.

Rebuilt from scratch on top of your original repos, combining what worked
across them, on current dependencies:

- **Telethon** (official PyPI package, not a third-party fork)
- **Python 3.12**, latest static **ffmpeg** build (not whatever's frozen
  in Debian's package repo)
- **MongoDB** (via `motor`, async) for the job queue and runtime settings
  — restarting the container no longer drops whatever was queued or
  resets your `/setcode` settings
- Live progress bars for **download, encode, and upload** (the original
  only showed progress for download/upload — encoding just sat on
  "Compressing..." with no feedback)
- Fixed: hardcoded credentials, an owner-auth check that used substring
  matching instead of equality (exploitable on `/eval` and `/bash`), and
  a hidden forward-to-channel call that copied every processed video
  elsewhere

See `DEPLOY.md` for setup (MongoDB Atlas + Oracle Cloud free VM).

## Structure
```
bot/
  config.py        env-only configuration
  db.py             MongoDB queue + settings persistence
  worker.py          queue processing loop (download -> encode -> upload)
  ffmpeg_utils.py    ffmpeg wrapper with live progress parsing
  fast_transfer.py    parallel download/upload (Telethon MTProto)
  helpers.py           formatting, progress-bar rendering, mediainfo
  commands.py           user + owner commands
  devtools.py             /eval /bash (owner-only, proper auth check)
  __main__.py               event handlers, startup + resume logic
```

## Local dev
```bash
cp .env.example .env   # fill in values
pip install -r requirements.txt
python3 -m bot
```
(ffmpeg + mediainfo need to be installed locally too, or just use Docker.)
