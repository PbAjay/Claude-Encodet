# Deploying

## 1. MongoDB (free) — Atlas
1. Sign up at https://www.mongodb.com/cloud/atlas/register
2. Create a free **M0** cluster (512MB, free forever, no card required for M0).
3. Database Access → add a user + password.
4. Network Access → allow access from anywhere (`0.0.0.0/0`) — simplest for
   a small personal bot; restrict to your VM's IP if you want it tighter.
5. Connect → Drivers → copy the `mongodb+srv://...` connection string into
   `MONGO_URI` in your `.env`.

This is what makes the queue survive a restart: every job's stage
(queued/downloading/encoding/uploading) is written to this database as it
moves through the pipeline, and your `/setcode` FFmpeg settings persist
here too instead of resetting to defaults every reboot.

## 2. Server — Oracle Cloud Always Free (recommended)
Video encoding needs real CPU; Oracle's Always Free tier gives you an
actual persistent VM (up to 4 OCPU / 24GB RAM on the Ampere A1 arm64 shape)
for free, indefinitely — unlike Render/Railway/Koyeb free tiers, which
sleep or throttle background compute.

1. https://www.oracle.com/cloud/free/ → Create Compute Instance
2. Shape: **Ampere A1 (arm64)**, Always Free eligible. Ubuntu 22.04/24.04.
3. Open port 22 only — the bot makes outbound connections to Telegram and
   MongoDB, nothing needs to accept inbound traffic.

```bash
ssh ubuntu@<vm-ip>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

```bash
# from your machine
scp compbot-rebuilt.zip ubuntu@<vm-ip>:~

# on the VM
unzip compbot-rebuilt.zip && cd compbot-rebuilt
cp .env.example .env
nano .env    # fill in APP_ID, API_HASH, BOT_TOKEN, DEV, OWNER, MONGO_URI
docker compose up -d --build
docker compose logs -f
```

`restart: unless-stopped` means Docker restarts the bot automatically on
crash or VM reboot — and because the queue lives in Mongo, whatever was
in-flight just picks back up.

## Alternative: Fly.io
```bash
fly launch --no-deploy      # detects the Dockerfile
fly secrets set APP_ID=... API_HASH=... BOT_TOKEN=... DEV=... OWNER=... MONGO_URI=...
fly deploy
```
Smaller free allowance than Oracle, fine for light/occasional use.

## Credentials
- `APP_ID` / `API_HASH`: https://my.telegram.org
- `BOT_TOKEN`: **@BotFather** → `/newbot`
- `DEV` / `OWNER`: your numeric Telegram ID from **@userinfobot**
