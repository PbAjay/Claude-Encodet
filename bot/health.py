"""
Tiny HTTP server so Render's free Web Service type has something to
health-check. Render requires the app to bind to $PORT — without this,
Render considers the deploy failed even though the Telegram bot itself
doesn't need to serve HTTP at all.
"""
import os
from aiohttp import web


async def _health(request):
    return web.Response(text="OK")


async def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
