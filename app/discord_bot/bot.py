"""
Discord bot client setup.

The bot only handles Direct Messages from the configured owner (DISCORD_USER_ID).
All message parsing is delegated to reply_handler.
"""

import logging

import discord

from app.config import settings

log = logging.getLogger(__name__)

# Minimal intents: we need to receive DMs and read message content
intents = discord.Intents.default()
intents.message_content = True

class BullsClient(discord.Client):
    async def setup_hook(self) -> None:
        from app.tasks.scheduler import scheduler, setup_jobs
        setup_jobs()
        scheduler.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        print(f"Bot ready: {self.user}")

    async def on_message(self, message: discord.Message) -> None:
        from app.discord_bot.reply_handler import handle_reply
        if message.author == self.user:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return
        if message.author.id != settings.discord_user_id:
            return
        await handle_reply(message)


client = BullsClient(intents=intents)


async def send_dm(content: str) -> None:
    """Send a Direct Message to the configured owner."""
    user = await client.fetch_user(settings.discord_user_id)
    await user.send(content)
