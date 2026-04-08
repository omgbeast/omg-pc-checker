import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import json
import uuid
from datetime import datetime
import re

# ============================================================
# DATA STORAGE
# ============================================================

CONFIG_FILE = "bot_config.json"
CHECK_REQUESTS_FILE = "check_requests.json"
CHECK_DATA_FILE = "check_data.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return get_default_config()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_default_config():
    return {
        "bot_token": os.getenv("DISCORD_BOT_TOKEN", ""),
        "webhook_url": "",
        "pc_check_channel_id": 0,
        "log_channel_id": 0,
        "staff_role_id": 0,
        "download_url": "https://example.com/PCCheck.exe",
        "auto_flag_keywords": ["cheat", "hack", "injector", "aimbot", "wallhack", "exploit"],
        "vm_check_enabled": True,
        "approved_role_id": 0,  # Role to give when approved
        "rejected_role_id": 0,  # Role to take when rejected
        "pending_role_id": 0,  # Role to give when check is requested
    }

def load_requests():
    try:
        with open(CHECK_REQUESTS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_requests(requests):
    with open(CHECK_REQUESTS_FILE, "w") as f:
        json.dump(requests, f, indent=2)

def load_check_data():
    try:
        with open(CHECK_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_check_data(data):
    with open(CHECK_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_config():
    return load_config()

# ============================================================
# EMOJIS
# ============================================================

APPROVE_EMOJI = "✅"
REJECT_EMOJI = "❌"
MORE_INFO_EMOJI = "🔍"
PENDING_EMOJI = "⏳"
CONFIG_EMOJI = "⚙️"
CHECK_EMOJI = "🔍"

# ============================================================
# DISCORD UI - CONFIGURATION PANEL
# ============================================================

class ConfigView(discord.ui.View):
    """View for configuration management."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Bot Token", style=discord.ButtonStyle.secondary, emoji="🔑", custom_id="cfg_token")
    async def cfg_token(self, interaction, button):
        await interaction.response.send_modal(ConfigModal(self.bot, "bot_token", "Bot Token", "Enter your Discord bot token", True))

    @discord.ui.button(label="Webhook URL", style=discord.ButtonStyle.secondary, emoji="🔗", custom_id="cfg_webhook")
    async def cfg_webhook(self, interaction, button):
        await interaction.response.send_modal(ConfigModal(self.bot, "webhook_url", "Webhook URL", "Enter Discord webhook URL", True))

    @discord.ui.button(label="PC Check Channel", style=discord.ButtonStyle.secondary, emoji="📁", custom_id="cfg_pc_channel")
    async def cfg_pc_channel(self, interaction, button):
        modal = ConfigChannelModal(self.bot, "pc_check_channel_id", "PC Check Channel")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Log Channel", style=discord.ButtonStyle.secondary, emoji="📝", custom_id="cfg_log_channel")
    async def cfg_log_channel(self, interaction, button):
        modal = ConfigChannelModal(self.bot, "log_channel_id", "Log Channel")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Staff Role", style=discord.ButtonStyle.secondary, emoji="👮", custom_id="cfg_staff_role")
    async def cfg_staff_role(self, interaction, button):
        modal = ConfigRoleModal(self.bot, "staff_role_id", "Staff Role")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Download URL", style=discord.ButtonStyle.secondary, emoji="📥", custom_id="cfg_download")
    async def cfg_download(self, interaction, button):
        await interaction.response.send_modal(ConfigModal(self.bot, "download_url", "Download URL", "Enter EXE download URL", False))

    @discord.ui.button(label="Approved Role", style=discord.ButtonStyle.success, emoji="✅", custom_id="cfg_approved_role")
    async def cfg_approved_role(self, interaction, button):
        modal = ConfigRoleModal(self.bot, "approved_role_id", "Approved Role (Auto-assign)")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Rejected Role", style=discord.ButtonStyle.danger, emoji="❌", custom_id="cfg_rejected_role")
    async def cfg_rejected_role(self, interaction, button):
        modal = ConfigRoleModal(self.bot, "rejected_role_id", "Rejected Role (Auto-assign)")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Pending Role", style=discord.ButtonStyle.secondary, emoji="⏳", custom_id="cfg_pending_role")
    async def cfg_pending_role(self, interaction, button):
        modal = ConfigRoleModal(self.bot, "pending_role_id", "Pending Role (Auto-assign)")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Flag Keywords", style=discord.ButtonStyle.secondary, emoji="🚩", custom_id="cfg_keywords")
    async def cfg_keywords(self, interaction, button):
        modal = ConfigModal(self.bot, "auto_flag_keywords", "Flag Keywords", "Comma-separated keywords to flag (no spaces)", False, is_list=True)

class ConfigModal(discord.ui.Modal):
    def __init__(self, bot, key, title, placeholder, is_password=False, is_list=False):
        super().__init__(title=title)
        self.bot = bot
        self.key = key
        self.is_list = is_list

        self.input = discord.ui.TextInput(
            label=title,
            placeholder=placeholder,
            required=True,
            style=discord.TextStyle.long
        )
        if is_password:
            self.input.style = discord.TextStyle.short
        self.add_item(self.input)

    async def callback(self, interaction):
        config = load_config()

        if self.is_list:
            # Parse comma-separated list
            value = [v.strip().lower() for v in self.input.value.split(",") if v.strip()]
            config[self.key] = value
            display_value = ", ".join(value)
        else:
            value = self.input.value.strip()
            if self.key in ["pc_check_channel_id", "log_channel_id", "staff_role_id", "approved_role_id", "rejected_role_id", "pending_role_id"]:
                # Try to extract ID from mention or use as number
                match = re.match(r'<#(\d+)>', value) or re.match(r'<@&(\d+)>', value) or re.match(r'<@(\d+)>', value)
                if match:
                    value = int(match.group(1))
                else:
                    value = int(value) if value.isdigit() else 0
            config[self.key] = value
            display_value = "•" * len(value) if self.key == "bot_token" else value

        save_config(config)
        await interaction.response.send_message(
            f"✅ Updated `{self.key}` to: `{display_value}`",
            ephemeral=True
        )

class ConfigChannelModal(discord.ui.Modal):
    def __init__(self, bot, key, title):
        super().__init__(title=title)
        self.bot = bot
        self.key = key

        self.input = discord.ui.TextInput(
            label="Channel ID or Mention",
            placeholder="#channel-name or Channel ID",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction):
        config = load_config()
        value = self.input.value.strip()

        # Extract channel ID from mention
        match = re.match(r'<#(\d+)>', value)
        if match:
            value = int(match.group(1))
        else:
            value = int(value) if value.isdigit() else 0

        config[self.key] = value
        save_config(config)

        channel = self.bot.get_channel(value)
        channel_name = channel.name if channel else f"ID: {value}"

        await interaction.response.send_message(
            f"✅ Updated `{self.key}` to: #{channel_name}",
            ephemeral=True
        )

class ConfigRoleModal(discord.ui.Modal):
    def __init__(self, bot, key, title):
        super().__init__(title=title)
        self.bot = bot
        self.key = key

        self.input = discord.ui.TextInput(
            label="Role ID or Mention",
            placeholder="@RoleName or Role ID",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction):
        config = load_config()
        value = self.input.value.strip()

        # Extract role ID from mention
        match = re.match(r'<@&(\d+)>', value)
        if match:
            value = int(match.group(1))
        else:
            value = int(value) if value.isdigit() else 0

        config[self.key] = value
        save_config(config)

        # Find the role in guild
        role = interaction.guild.get_role(value) if interaction.guild else None
        role_name = role.name if role else f"ID: {value}"

        await interaction.response.send_message(
            f"✅ Updated `{self.key}` to: @{role_name}",
            ephemeral=True
        )

class ConfigStatusView(discord.ui.View):
    """Show current configuration status."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Show Current Config", style=discord.ButtonStyle.primary, emoji="📋", custom_id="show_config")
    async def show_config(self, interaction, button):
        config = load_config()

        embed = discord.Embed(
            title="⚙️ PC Check Bot Configuration",
            color=discord.Color.blue()
        )

        # Bot Token (masked)
        token = config.get("bot_token", "")
        token_display = token[:8] + "..." + token[-4:] if len(token) > 12 else "❌ Not Set"

        embed.add_field(
            name="🔑 Bot Token",
            value=f"`{token_display}`" if token else "❌ Not Set",
            inline=True
        )

        # Webhook URL (masked)
        webhook = config.get("webhook_url", "")
        webhook_display = webhook[:30] + "..." if webhook else "❌ Not Set"

        embed.add_field(
            name="🔗 Webhook URL",
            value=f"`{webhook_display}`" if webhook else "❌ Not Set",
            inline=True
        )

        # Channels
        pc_channel = bot.get_channel(config.get("pc_check_channel_id", 0))
        log_channel = bot.get_channel(config.get("log_channel_id", 0))

        embed.add_field(
            name="📁 PC Check Channel",
            value=f"{pc_channel.mention}" if pc_channel else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="📝 Log Channel",
            value=f"{log_channel.mention}" if log_channel else "❌ Not Set",
            inline=True
        )

        # Roles
        staff_role = interaction.guild.get_role(config.get("staff_role_id", 0))
        approved_role = interaction.guild.get_role(config.get("approved_role_id", 0))
        rejected_role = interaction.guild.get_role(config.get("rejected_role_id", 0))
        pending_role = interaction.guild.get_role(config.get("pending_role_id", 0))

        embed.add_field(
            name="👮 Staff Role",
            value=f"{staff_role.mention}" if staff_role else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="✅ Approved Role",
            value=f"{approved_role.mention}" if approved_role else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="❌ Rejected Role",
            value=f"{rejected_role.mention}" if rejected_role else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="⏳ Pending Role",
            value=f"{pending_role.mention}" if pending_role else "❌ Not Set",
            inline=True
        )

        # Download URL
        download_url = config.get("download_url", "")
        embed.add_field(
            name="📥 Download URL",
            value=f"[Click here]({download_url})" if download_url else "❌ Not Set",
            inline=False
        )

        # Flag Keywords
        keywords = config.get("auto_flag_keywords", [])
        embed.add_field(
            name="🚩 Flag Keywords",
            value=", ".join(keywords) if keywords else "❌ Not Set",
            inline=False
        )

        embed.add_field(
            name="🔧 VM Check",
            value="✅ Enabled" if config.get("vm_check_enabled", True) else "❌ Disabled",
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# PC CHECK ACTION BUTTONS
# ============================================================

class PCCheckActionView(discord.ui.View):
    """Buttons for staff to approve/reject PC checks."""

    def __init__(self, check_id: str):
        super().__init__(timeout=None)
        self.check_id = check_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji=APPROVE_EMOJI, custom_id=f"pccheck_approve")
    async def approve(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "APPROVED")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji=REJECT_EMOJI, custom_id=f"pccheck_reject")
    async def reject(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "REJECTED")

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.secondary, emoji=MORE_INFO_EMOJI, custom_id=f"pccheck_moreinfo")
    async def more_info(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "NEEDS_INFO")

async def handle_check_action(interaction, check_id: str, new_status: str):
    """Handle approve/reject/moreinfo button clicks."""

    config = load_config()

    # Check permissions
    user = interaction.user
    staff_role_id = config.get("staff_role_id", 0)

    has_permission = False
    if user.guild_permissions.manage_messages:
        has_permission = True
    elif staff_role_id and any(role.id == staff_role_id for role in user.roles):
        has_permission = True

    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to review PC checks.",
            ephemeral=True
        )
        return

    # Load check data
    requests = load_requests()
    check_data = requests.get(check_id)

    if not check_data:
        await interaction.response.send_message(
            "❌ Check not found. It may have already been processed.",
            ephemeral=True
        )
        return

    # Update status
    check_data["status"] = new_status
    check_data["processed_by"] = interaction.user.id
    check_data["processed_at"] = datetime.now().isoformat()
    requests[check_id] = check_data
    save_requests(requests)

    # Update persistent check data
    all_data = load_check_data()
    user_id = check_data.get("user_id")
    if user_id:
        all_data[user_id] = {
            "status": new_status,
            "check_id": check_id,
            "processed_by": interaction.user.id,
            "processed_at": datetime.now().isoformat(),
            "hostname": check_data.get("hostname"),
            "username": check_data.get("username"),
        }
        save_check_data(all_data)

    # Update user's roles if configured
    member = interaction.guild.get_member(int(user_id)) if user_id else None
    if member:
        try:
            approved_role_id = config.get("approved_role_id", 0)
            rejected_role_id = config.get("rejected_role_id", 0)
            pending_role_id = config.get("pending_role_id", 0)

            # Remove pending role
            if pending_role_id:
                pending_role = interaction.guild.get_role(pending_role_id)
                if pending_role and pending_role in member.roles:
                    await member.remove_roles(pending_role)

            # Handle new status
            if new_status == "APPROVED" and approved_role_id:
                approved_role = interaction.guild.get_role(approved_role_id)
                if approved_role:
                    await member.add_roles(approved_role)
                    # Remove rejected if they had it
                    if rejected_role_id:
                        rejected_role = interaction.guild.get_role(rejected_role_id)
                        if rejected_role and rejected_role in member.roles:
                            await member.remove_roles(rejected_role)

            elif new_status == "REJECTED" and rejected_role_id:
                rejected_role = interaction.guild.get_role(rejected_role_id)
                if rejected_role:
                    await member.add_roles(rejected_role)
                    # Remove approved if they had it
                    if approved_role_id:
                        approved_role = interaction.guild.get_role(approved_role_id)
                        if approved_role and approved_role in member.roles:
                            await member.remove_roles(approved_role)
        except Exception as e:
            print(f"Error updating roles: {e}")

    # Update the message
    check_data["status"] = new_status
    embed = create_pc_check_embed(check_data)

    # Update view based on status
    view = None
    if new_status in ["APPROVED", "REJECTED"]:
        view = None  # Hide buttons
    else:
        view = PCCheckActionView(check_id)

    try:
        await interaction.message.edit(embed=embed, view=view)
    except:
        pass

    # Confirmation message
    status_emoji = {"APPROVED": "✅", "REJECTED": "❌", "NEEDS_INFO": "🔍"}
    await interaction.response.send_message(
        f"{status_emoji.get(new_status, '⚠️')} Check {new_status.replace('_', ' ')}!",
        ephemeral=True
    )

    # Send to log channel
    log_channel_id = config.get("log_channel_id", 0)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(
                title=f"PC Check {new_status.replace('_', ' ')}",
                color=discord.Color.green() if new_status == "APPROVED" else discord.Color.red(),
                timestamp=datetime.now()
            )
            log_embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
            log_embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Check ID", value=check_id, inline=True)
            if check_data.get("hostname"):
                log_embed.add_field(name="Hostname", value=check_data["hostname"], inline=True)
            if check_data.get("username"):
                log_embed.add_field(name="Username", value=check_data["username"], inline=True)

            await log_channel.send(embed=log_embed)

# ============================================================
# EMBED CREATION
# ============================================================

def get_status_color(status: str) -> discord.Color:
    colors = {
        "PENDING": discord.Color.blue(),
        "APPROVED": discord.Color.green(),
        "REJECTED": discord.Color.red(),
        "NEEDS_INFO": discord.Color.orange(),
    }
    return colors.get(status, discord.Color.greyple())

def get_status_emoji(status: str) -> str:
    emojis = {
        "PENDING": PENDING_EMOJI,
        "APPROVED": APPROVE_EMOJI,
        "REJECTED": REJECT_EMOJI,
        "NEEDS_INFO": MORE_INFO_EMOJI,
    }
    return emojis.get(status, "❓")

def create_pc_check_embed(data: dict) -> discord.Embed:
    """Create an embed showing PC check results."""
    status = data.get("status", "PENDING")

    embed = discord.Embed(
        title=f"PC Verification Check",
        color=get_status_color(status),
        timestamp=datetime.now()
    )

    # User info
    user_id = data.get("user_id", "Unknown")
    embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
    embed.add_field(name="Discord ID", value=user_id, inline=True)
    embed.add_field(name="Check ID", value=data.get("check_id", "N/A"), inline=True)

    # Status
    status_emoji = get_status_emoji(status)
    embed.add_field(
        name="Status",
        value=f"{status_emoji} **{status.replace('_', ' ').title()}**",
        inline=True
    )

    # System info
    embed.add_field(name="Hostname", value=data.get("hostname", "N/A"), inline=True)
    embed.add_field(name="Username", value=data.get("username", "N/A"), inline=True)
    embed.add_field(name="OS", value=data.get("os_version", "N/A"), inline=False)

    # Hardware
    embed.add_field(name="CPU", value=data.get("cpu", "N/A"), inline=False)
    embed.add_field(name="GPU", value=data.get("gpu", "N/A"), inline=True)
    embed.add_field(name="RAM", value=data.get("ram", "N/A"), inline=True)

    # Network
    embed.add_field(name="MAC Address", value=data.get("mac_address", "N/A"), inline=True)
    embed.add_field(name="Public IP", value=data.get("public_ip", "N/A"), inline=True)

    # Warnings
    warnings = []
    if data.get("is_vm"):
        warnings.append(f"🚨 Virtual Machine: {data.get('vm_indicator', 'Detected')}")

    if data.get("suspicious_processes"):
        procs = ", ".join(data["suspicious_processes"][:5])
        warnings.append(f"⚠️ Suspicious: {procs}")

    if warnings:
        embed.add_field(name="Warnings", value="\n".join(warnings), inline=False)

    # Analysis based on status
    if status == "PENDING":
        embed.add_field(
            name="Action Required",
            value="Awaiting staff review. Use buttons below to Approve/Reject.",
            inline=False
        )
    elif status == "APPROVED":
        embed.add_field(
            name="Result",
            value="✅ This user has been approved to play.",
            inline=False
        )
    elif status == "REJECTED":
        embed.add_field(
            name="Result",
            value="❌ This user has been rejected.",
            inline=False
        )
    elif status == "NEEDS_INFO":
        embed.add_field(
            name="Action Required",
            value="Staff requested more information from this user.",
            inline=False
        )

    embed.set_footer(text=f"Check ID: {data.get('check_id', 'N/A')}")

    return embed

# ============================================================
# BOT COMMANDS
# ============================================================

class PCBOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_interaction(self, interaction: discord.Interaction):
        # Handle PC check button clicks
        if interaction.data.get("custom_id", "").startswith("pccheck_"):
            custom_id = interaction.data["custom_id"]
            check_id = custom_id.replace("pccheck_approve", "").replace("pccheck_reject", "").replace("pccheck_moreinfo", "")

            # Determine action from original custom_id
            if "approve" in custom_id:
                action = "APPROVED"
            elif "reject" in custom_id:
                action = "REJECTED"
            else:
                action = "NEEDS_INFO"

            await handle_check_action(interaction, check_id, action)

bot = PCBOT()

# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name="pccheck_config", description="[Owner] Configure PC Check bot settings")
async def pccheck_config(interaction: discord.Interaction):
    """Show configuration panel."""
    config = load_config()

    # Check if user is bot owner or has admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only administrators can configure the bot.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="⚙️ PC Check Bot Configuration",
        description="Click buttons to configure each setting:",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed, view=ConfigView(bot), ephemeral=True)


@bot.tree.command(name="pccheck_status", description="[Owner] View current configuration")
async def pccheck_status(interaction: discord.Interaction):
    """Show current configuration status."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only administrators can view configuration.",
            ephemeral=True
        )
        return

    await interaction.response.send_message("Loading configuration...", view=ConfigStatusView(bot), ephemeral=True)


@bot.tree.command(name="send_pc_check", description="[Staff] Send PC check request to a user")
@app_commands.describe(user="The user to request a PC check from")
async def send_pc_check(interaction: discord.Interaction, user: discord.User):
    """Send a PC check request to a user via DM."""

    config = load_config()

    # Check permissions
    staff_role_id = config.get("staff_role_id", 0)
    has_permission = False

    if interaction.user.guild_permissions.manage_messages:
        has_permission = True
    elif staff_role_id and any(role.id == staff_role_id for role in interaction.user.roles):
        has_permission = True

    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to request PC checks.",
            ephemeral=True
        )
        return

    # Generate check ID
    check_id = str(uuid.uuid4())[:8]
    webhook_url = config.get("webhook_url", "")
    download_url = config.get("download_url", "")

    # Create pending check data
    check_data = {
        "check_id": check_id,
        "user_id": str(user.id),
        "username": user.name,
        "status": "PENDING",
        "created_at": datetime.now().isoformat(),
        "created_by": interaction.user.id,
    }

    # Save request
    requests = load_requests()
    requests[check_id] = check_data
    save_requests(requests)

    # Send DM to user with download link
    try:
        dm_embed = discord.Embed(
            title="🔍 PC Verification Required",
            description=f"You have been requested to complete a PC verification check by {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        dm_embed.add_field(
            name="Download Tool",
            value=f"[Click here to download PC Check Tool]({download_url})" if download_url else "❌ Download URL not configured",
            inline=False
        )
        dm_embed.add_field(
            name="Instructions",
            value="1. Download the tool above\n"
                  "2. Run the downloaded .exe file\n"
                  "3. Wait for it to finish (auto-closes)\n"
                  "4. Your results will be sent automatically\n"
                  "5. Use `/check_status` to check your verification",
            inline=False
        )
        dm_embed.add_field(
            name="Check ID",
            value=f"`{check_id}`",
            inline=False
        )
        dm_embed.set_footer(text="If you have issues, contact staff.")

        await user.send(embed=dm_embed)
        dm_sent = True
    except discord.Forbidden:
        dm_sent = False

    # Post check request in channel (without download link, for staff)
    pc_channel_id = config.get("pc_check_channel_id", 0)
    if pc_channel_id:
        pc_channel = bot.get_channel(pc_channel_id)
        if pc_channel:
            embed = create_pc_check_embed(check_data)
            view = PCCheckActionView(check_id)
            await pc_channel.send(
                content=f"PC check requested for {user.mention} (`{check_id}`)",
                embed=embed,
                view=view
            )

    # Give pending role if configured
    pending_role_id = config.get("pending_role_id", 0)
    if pending_role_id:
        member = interaction.guild.get_member(user.id)
        if member:
            try:
                pending_role = interaction.guild.get_role(pending_role_id)
                if pending_role:
                    await member.add_roles(pending_role)
            except:
                pass

    # Confirmation message
    confirm_msg = f"✅ PC check request sent!"
    if dm_sent:
        confirm_msg += f"\n• DM sent to {user.mention}"
    else:
        confirm_msg += f"\n• ⚠️ Could not DM {user.mention} (DMs disabled)"

    confirm_msg += f"\n• Check ID: `{check_id}`"

    await interaction.response.send_message(confirm_msg, ephemeral=True)


@bot.tree.command(name="check_status", description="Check your PC verification status")
async def check_status(interaction: discord.Interaction):
    """Users check their own status."""
    user_id = str(interaction.user.id)
    all_data = load_check_data()

    user_check = all_data.get(user_id)

    if not user_check:
        await interaction.response.send_message(
            "ℹ️ You haven't submitted a PC check yet.",
            ephemeral=True
        )
        return

    status = user_check.get("status", "UNKNOWN")
    status_emoji = get_status_emoji(status)

    embed = discord.Embed(
        title="PC Check Status",
        color=get_status_color(status)
    )
    embed.add_field(name="Status", value=f"{status_emoji} **{status.replace('_', ' ').title()}**", inline=True)
    embed.add_field(name="Check ID", value=user_check.get("check_id", "N/A"), inline=True)

    if status == "APPROVED":
        embed.description = "✅ Your PC has been approved. You're good to go!"
    elif status == "REJECTED":
        embed.description = "❌ Your PC check was rejected. Contact staff for more info."
    elif status == "NEEDS_INFO":
        embed.description = "🔍 Staff requested more information from you. Please contact them."
    else:
        embed.description = "Your check is being processed."

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="pccheck_help", description="Get help with PC checks")
async def pccheck_help(interaction: discord.Interaction):
    """Show help information."""
    embed = discord.Embed(
        title="PC Check System Help",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="For Users",
        value="1. You will receive a DM with download link\n"
              "2. Download and run the PC Check tool\n"
              "3. It auto-closes when done\n"
              "4. Use `/check_status` to check your status",
        inline=False
    )

    embed.add_field(
        name="For Staff",
        value="• `/send_pc_check @user` - Request a check\n"
              "• Click Approve/Reject buttons on checks\n"
              "• `/pccheck_config` - Configure bot settings",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# WEBHOOK HANDLER (for PC Check EXE)
# ============================================================

@bot.event
async def on_message(self, message):
    """Handle messages - for potential webhook processing."""
    await self.process_commands(message)

# ============================================================
# MAIN
# ============================================================

@bot.event
async def on_ready():
    config = load_config()
    print(f"\n{'='*50}")
    print(f"PC Check Bot Ready!")
    print(f"{'='*50}")
    print(f"Bot: {bot.user.name}")
    print(f"Channel: {bot.get_channel(config.get('pc_check_channel_id', 0))}")
    print(f"Commands synced: Yes")
    print(f"\nConfiguration file: {CONFIG_FILE}")

    if not config.get("bot_token"):
        print("\n⚠️  Bot token not configured! Run /pccheck_config to set it up.")

    if not config.get("webhook_url"):
        print("⚠️  Webhook URL not configured! PC Check EXE won't work.")

    print(f"{'='*50}\n")

def main():
    config = load_config()

    # Check if token is configured
    token = config.get("bot_token", os.getenv("DISCORD_BOT_TOKEN"))

    if not token:
        print("ERROR: Bot token not set!")
        print("\nPlease run the bot and use /pccheck_config to set your bot token.")
        print("Then restart the bot.\n")

        # Create config file if doesn't exist
        if not os.path.exists(CONFIG_FILE):
            save_config(get_default_config())
            print(f"Created default config: {CONFIG_FILE}")

    bot.run(token if token else "")

if __name__ == "__main__":
    main()
